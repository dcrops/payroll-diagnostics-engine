from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from rkeg.rules import Finding, write_findings_csv
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


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data" / "sample"
    out_dir = repo_root / "outputs"
    modules_dir = out_dir / "modules"

    out_dir.mkdir(parents=True, exist_ok=True)
    modules_dir.mkdir(parents=True, exist_ok=True)

    # --------
    # Load inputs (v1 assumes they live alongside your leave datasets)
    # You can tweak filenames later if needed.
    # --------
    employees = pd.read_csv(
        data_dir / "employees.csv",
        dtype={"employee_id": "string"},
    )

    pay_events_path = data_dir / "pay_events.csv"
    leave_ledger_path = data_dir / "leave_ledger.csv"
    leave_snapshot_path = data_dir / "balances_snapshot.csv"
    terminations_path = data_dir / "terminations.csv"

    pay_events = pd.read_csv(pay_events_path, dtype={"employee_id": "string"}) if pay_events_path.exists() else pd.DataFrame()
    leave_ledger = pd.read_csv(leave_ledger_path, dtype={"employee_id": "string"}) if leave_ledger_path.exists() else pd.DataFrame()
    leave_snapshot = pd.read_csv(leave_snapshot_path, dtype={"employee_id": "string"}) if leave_snapshot_path.exists() else pd.DataFrame()
    terminations = pd.read_csv(terminations_path, dtype={"employee_id": "string"}) if terminations_path.exists() else pd.DataFrame()

    # Normalise employee_id
    for df in (employees, pay_events, leave_ledger, leave_snapshot, terminations):
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
    # Run RKEG engine
    # ----------------------------
    datasets = {
        "employee_master": employees,
        "pay_events": pay_events,
        "leave_ledger": leave_ledger,
        "leave_snapshot": leave_snapshot,
        "terminations": terminations,
    }

    findings: list[Finding] = list(run_rkeg_engine(datasets))

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
