from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
from typing import Iterable

import pandas as pd

from rkeg.rules import Finding, write_findings_csv
from rkeg.engine import run_rkeg_engine
from common.data_window import write_data_window
from rkeg.datasets import load_all_datasets
from rkeg.engine import run_rkeg_engine


REQUIRED_EMP = {"employee_id"}
REQUIRED_PAY = {"employee_id"}          # we'll tighten this later
REQUIRED_LEDGER = {"employee_id"}       # for leave evidence
REQUIRED_SNAP = {"employee_id"}         # for leave snapshot
REQUIRED_TERM = {"employee_id"}         # for term records


def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _collect_dates_from_df(
    df: pd.DataFrame,
    candidate_cols: Iterable[str],
) -> list[date]:
    """
    Collect valid dates from a dataframe for the given list of candidate
    date columns. Used to derive the RKEG data window from client data,
    not from findings.
    """
    if df is None or df.empty:
        return []

    dates: list[date] = []

    for col in candidate_cols:
        if col not in df.columns:
            continue

        series = df[col].dropna()
        for raw in series:
            s = str(raw).strip()
            if not s:
                continue

            # Try a few common formats; ignore anything that won't parse
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    d = datetime.strptime(s, fmt).date()
                    dates.append(d)
                    break
                except ValueError:
                    continue

    return dates


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data" / "sample"
    out_dir = repo_root / "outputs"
    modules_dir = out_dir / "modules"

    out_dir.mkdir(parents=True, exist_ok=True)
    modules_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------
    # Load all datasets via central loader
    # ----------------------------
    datasets = load_all_datasets(data_dir)

    print("[RKEG] Loaded dataset keys:", list(datasets.keys()))
    for name, df in datasets.items():
        print(f"[RKEG] {name}: shape={df.shape}")

    # Pull out the core ones for convenience / validation
    employees = datasets.get("employee_master", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())
    employee_super = datasets.get("employee_super", pd.DataFrame())

    # Normalise employee_id across all employee-level datasets
    for df in (employees, pay_events, leave_ledger, leave_snapshot, terminations, employee_super):
        if not df.empty and "employee_id" in df.columns:
            df["employee_id"] = df["employee_id"].astype(str).str.strip()

    # Minimal column checks (we'll refine per-domain rules later)
    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    if not pay_events.empty:
        _require_cols(pay_events, REQUIRED_PAY, "pay_events.csv")
    if not leave_ledger.empty:
        _require_cols(leave_ledger, REQUIRED_LEDGER, "leave_ledger.csv")
    if not leave_snapshot.empty:
        _require_cols(leave_snapshot, REQUIRED_SNAP, "balances_snapshot.csv")
    if not terminations.empty:
        _require_cols(terminations, REQUIRED_TERM, "terminations.csv")

    # ----------------------------
    # Derive RKEG data window from client source data
    # ----------------------------
    rkeg_dates: list[date] = []

    rkeg_dates += _collect_dates_from_df(
        pay_events,
        ["pay_date", "period_start", "period_end"],
    )
    rkeg_dates += _collect_dates_from_df(
        leave_ledger,
        ["as_of_date", "event_date"],
    )
    rkeg_dates += _collect_dates_from_df(
        leave_snapshot,
        ["as_of_date"],
    )
    rkeg_dates += _collect_dates_from_df(
        terminations,
        ["termination_date", "final_pay_date", "term_date", "pay_date"],
    )

    if rkeg_dates:
        rkeg_window_path = modules_dir / "rkeg_data_window.csv"
        write_data_window(rkeg_window_path, rkeg_dates)
        print(
            f"[RKEG] Wrote data window to {rkeg_window_path} "
            f"({min(rkeg_dates)} → {max(rkeg_dates)})"
        )
    else:
        print("[RKEG] No usable dates found for data window – rkeg_data_window.csv not written")

    # ----------------------------
    # Run RKEG engine
    # ----------------------------
    # Update the central dict with the cleaned dataframes
    engine_datasets = dict(datasets)
    engine_datasets["employee_master"] = employees
    engine_datasets["pay_events"] = pay_events
    engine_datasets["leave_ledger"] = leave_ledger
    engine_datasets["leave_snapshot"] = leave_snapshot
    engine_datasets["terminations"] = terminations
    engine_datasets["employee_super"] = employee_super  # <- important one for SUP-004

    findings: list[Finding] = list(
        run_rkeg_engine(engine_datasets, enabled_tiers={1, 2})
    )

    # ----------------------------
    # Write findings output (module-level)
    # ----------------------------
    findings_path = modules_dir / "rkeg_findings.csv"
    write_findings_csv(findings, findings_path)

    # ----------------------------
    # Summary outputs (by rule/severity, then by severity)
    # ----------------------------
    if findings:
        findings_df = pd.DataFrame([f.__dict__ for f in findings])
    else:
        findings_df = pd.read_csv(findings_path)  # empty template from write_findings_csv

    if len(findings_df) == 0:
        summary_df = pd.DataFrame(columns=["rule_code", "severity", "finding_count"])
    else:
        summary_df = (
            findings_df.groupby(["rule_code", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["severity", "finding_count"], ascending=[True, False])
        )

    summary_path = modules_dir / "rkeg_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    if len(summary_df) > 0:
        print(summary_df.to_string(index=False))

    # Totals by severity
    if len(findings_df) == 0:
        severity_summary_df = pd.DataFrame(columns=["severity", "finding_count"])
    else:
        severity_summary_df = (
            findings_df.groupby("severity", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

    severity_summary_path = modules_dir / "rkeg_summary_by_severity.csv"
    severity_summary_df.to_csv(severity_summary_path, index=False)

    print(f"Wrote: {severity_summary_path}")
    if len(severity_summary_df) > 0:
        print(severity_summary_df.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())