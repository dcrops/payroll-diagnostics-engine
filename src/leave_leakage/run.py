from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
import pandas as pd
import yaml

from common.data_window import write_data_window

from leave_leakage.rules import Finding, run_rule



REQUIRED_EMP = {"employee_id", "employment_type", "fte", "start_date"}
REQUIRED_LEDGER = {"employee_id", "leave_type", "event_date", "units", "event_type"}
REQUIRED_SNAP = {"employee_id", "leave_type", "as_of_date", "balance_units"}


def _extract_dates_from_leave_ledger_df(df) -> list[date]:
    """
    Collect valid dates from the client leave ledger DataFrame.

    We prefer the actual ledger date column and accept a few
    common formats, ignoring anything that doesn't parse cleanly.
    """
    if df is None or df.empty:
        return []

    # If you know the real column name (e.g. 'as_of_date'), you can
    # just use that; this list is defensive.
    candidate_cols = [
        "as_of_date",
        "ledger_date",
        "leave_date",
        "transaction_date",
        "event_date",
        "snapshot_date",
        "date",
    ]

    for col in candidate_cols:
        if col in df.columns:
            series = df[col].dropna()
            break
    else:
        return []

    dates: list[date] = []

    for raw in series:
        raw_str = str(raw).strip()
        if not raw_str:
            continue

        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                d = datetime.strptime(raw_str, fmt).date()
                dates.append(d)
                break
            except ValueError:
                continue

    return dates

def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")

def _load_rules(rules_path: Path) -> list[dict]:
    with rules_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("rules", [])

def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data" / "sample"
    out_dir = repo_root / "outputs"
    modules_dir = out_dir / "modules"
    rules_path = Path(__file__).resolve().parent / "config" / "leave_rules.yml"

    out_dir.mkdir(parents=True, exist_ok=True)
    modules_dir.mkdir(parents=True, exist_ok=True)

    employees = pd.read_csv(
        data_dir / "employees.csv",
        dtype={"employee_id": "string"},
    )

    ledger = pd.read_csv(
        data_dir / "leave_ledger.csv",
        dtype={"employee_id": "string", "leave_type": "string", "event_type": "string"},
    )

    # NEW: derive LEAVE data window from client ledger
    dates = _extract_dates_from_leave_ledger_df(ledger)
    if dates:
        # Use the same outputs/modules structure as reporting.
        # This assumes you're running from repo root (which you are).
        modules_dir = Path("outputs") / "modules"
        window_path = modules_dir / "leave_data_window.csv"
        write_data_window(window_path, dates)

    snapshot = pd.read_csv(
        data_dir / "balances_snapshot.csv",
        dtype={"employee_id": "string", "leave_type": "string"},
    )

    for df in (employees, ledger, snapshot):
        df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    _require_cols(ledger, REQUIRED_LEDGER, "leave_ledger.csv")
    _require_cols(snapshot, REQUIRED_SNAP, "balances_snapshot.csv")

    # Parse dates
    ledger["event_date"] = pd.to_datetime(ledger["event_date"], errors="coerce")
    snapshot["as_of_date"] = pd.to_datetime(snapshot["as_of_date"], errors="coerce")

    bad_ledger_dates = ledger["event_date"].isna().sum()
    bad_snapshot_dates = snapshot["as_of_date"].isna().sum()
    print(f"[input] Unparseable ledger event_date rows: {bad_ledger_dates}")
    print(f"[input] Unparseable snapshot as_of_date rows: {bad_snapshot_dates}")

       # ----------------------------
    # Load rule metadata
    # ----------------------------
    rules = _load_rules(rules_path)

    # ----------------------------
    # Run rules
    # ----------------------------
    findings: list[Finding] = []

    # Join ledger to snapshot on employee + leave_type, then keep events up to as_of_date
    merged = snapshot.merge(
        ledger,
        on=["employee_id", "leave_type"],
        how="left",
    )

    merged = merged[merged["event_date"].isna() | (merged["event_date"] <= merged["as_of_date"])]

    ledger_bal = (
        merged.groupby(["employee_id", "leave_type", "as_of_date"], as_index=False)["units"]
        .sum()
        .rename(columns={"units": "ledger_balance_units"})
    )

    report = snapshot.merge(
        ledger_bal,
        on=["employee_id", "leave_type", "as_of_date"],
        how="left",
    )
    report["ledger_balance_units"] = report["ledger_balance_units"].fillna(0.0)
    report["diff_units"] = report["balance_units"] - report["ledger_balance_units"]
    report["ledger_balance_units"] = report["ledger_balance_units"].round(2)
    report["diff_units"] = report["diff_units"].round(2)

    datasets = {
        "employee_master": employees,
        "leave_ledger": ledger,
        "leave_snapshot": snapshot,
    }

    for rule in rules:
        findings.extend(run_rule(rule, datasets, ledger_recon=report))

    # ----------------------------
    # Write findings output (module-level)
    # ----------------------------
    if findings:
        findings_df = pd.DataFrame([f.__dict__ for f in findings])
    else:
        findings_df = pd.DataFrame(
            columns=[
                "employee_id",
                "leave_type",
                "as_of_date",
                "rule_code",
                "severity",
                "message",
                "diff_units",
                "evidence",
                "finding_id",
                "next_action",
            ]
        )

    findings_path = modules_dir / "leave_leakage_findings.csv"
    findings_df.to_csv(findings_path, index=False)

    # ----------------------------
    # Summary output (counts by rule and severity, module-level)
    # ----------------------------
    if len(findings_df) == 0:
        summary_df = pd.DataFrame(columns=["rule_code", "severity", "finding_count"])
    else:
        summary_df = (
            findings_df.groupby(["rule_code", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["severity", "finding_count"], ascending=[True, False])
        )

    summary_path = modules_dir / "leave_leakage_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(summary_df.to_string(index=False))

    # ----------------------------
    # Summary output (totals by severity, module-level)
    # ----------------------------
    if len(findings_df) == 0:
        severity_summary_df = pd.DataFrame(columns=["severity", "finding_count"])
    else:
        severity_summary_df = (
            findings_df.groupby("severity", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

    severity_summary_path = modules_dir / "leave_leakage_summary_by_severity.csv"
    severity_summary_df.to_csv(severity_summary_path, index=False)

    print(f"Wrote: {severity_summary_path}")
    print(severity_summary_df.to_string(index=False))

    # ----------------------------
    # Detailed leakage reconciliation report (suite-level)
    # ----------------------------
    tolerance = 0.25  # 15 minutes in hours
    report["risk_flag"] = report["diff_units"].abs() > tolerance
    report["risk_reason"] = report["risk_flag"].map(
        lambda x: "BALANCE_MISMATCH_LEDGER_VS_SNAPSHOT" if x else ""
    )

    out_path = out_dir / "leakage_report.csv"
    report.sort_values(["employee_id", "leave_type", "as_of_date"]).to_csv(out_path, index=False)

    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
