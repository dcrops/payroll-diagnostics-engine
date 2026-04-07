from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
import pandas as pd
import yaml

from src.common.data_window import write_data_window
from src.common.paths import get_processed_dir, get_outputs_dir

from src.leave_leakage.models import Finding
from src.leave_leakage.detectors.registry import run_rule


REQUIRED_EMP = {"employee_id", "employment_type", "fte", "start_date", "termination_date"}
REQUIRED_LEDGER = {"employee_id", "leave_type", "event_date", "units", "event_type"}
REQUIRED_SNAP = {"employee_id", "leave_type", "as_of_date", "balance_units"}
REQUIRED_REQUESTS = {
    "request_id",
    "employee_id",
    "leave_type",
    "request_start_date",
    "request_end_date",
    "units_requested",
    "approval_status",
    "approval_date",
    "approved_by",
}
REQUIRED_TIMESHEETS = {
    "employee_id",
    "work_date",
    "hours_worked",
    "timesheet_status",
}


def _extract_dates_from_leave_ledger_df(df: pd.DataFrame) -> list[date]:
    """
    Collect valid dates from the client leave ledger DataFrame.

    We prefer the actual ledger date column and accept a few
    common formats, ignoring anything that doesn't parse cleanly.
    """
    if df is None or df.empty:
        return []

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


def main(client: str, pilot: str) -> int:
    processed_dir = get_processed_dir(client, pilot)
    output_dir = get_outputs_dir(client, pilot)

    rules_path = Path(__file__).resolve().parent / "config" / "leave_rules.yml"

    employees = pd.read_csv(
        processed_dir / "employees.csv",
        dtype={"employee_id": "string"},
    )

    ledger = pd.read_csv(
        processed_dir / "leave_ledger.csv",
        dtype={"employee_id": "string", "leave_type": "string", "event_type": "string"},
    )

    leave_requests_path = processed_dir / "leave_requests.csv"
    if leave_requests_path.exists():
        leave_requests = pd.read_csv(
            leave_requests_path,
            dtype={
                "request_id": "string",
                "employee_id": "string",
                "leave_type": "string",
                "approval_status": "string",
                "approved_by": "string",
            },
        )
    else:
        leave_requests = pd.DataFrame()

    timesheets_path = processed_dir / "timesheets.csv"
    if timesheets_path.exists():
        timesheets = pd.read_csv(
            timesheets_path,
            dtype={
                "employee_id": "string",
                "timesheet_status": "string",
            },
        )
    else:
        timesheets = pd.DataFrame()

    snapshot_path = processed_dir / "balances_snapshot.csv"

    if snapshot_path.exists() and snapshot_path.stat().st_size > 0:
        snapshot = pd.read_csv(
            snapshot_path,
            dtype={"employee_id": "string", "leave_type": "string"},
        )
    else:
        print("INFO - balances_snapshot.csv not found or empty; continuing without snapshot data")
        snapshot = pd.DataFrame(columns=["employee_id", "leave_type", "as_of_date", "balance_units"])

    # Derive LEAVE data window from client ledger
    dates = _extract_dates_from_leave_ledger_df(ledger)
    if dates:
        window_path = output_dir / "leave_data_window.csv"
        write_data_window(window_path, dates)

    for df in (employees, ledger, snapshot, leave_requests, timesheets):
        if not df.empty and "employee_id" in df.columns:
            df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    _require_cols(ledger, REQUIRED_LEDGER, "leave_ledger.csv")
    _require_cols(snapshot, REQUIRED_SNAP, "balances_snapshot.csv")
    if not leave_requests.empty:
        _require_cols(leave_requests, REQUIRED_REQUESTS, "leave_requests.csv")

    if not timesheets.empty:
        _require_cols(timesheets, REQUIRED_TIMESHEETS, "timesheets.csv")

    # Parse dates
    employees["start_date"] = pd.to_datetime(employees["start_date"], errors="coerce")
    employees["termination_date"] = pd.to_datetime(employees["termination_date"], errors="coerce")

    ledger["event_date"] = pd.to_datetime(ledger["event_date"], errors="coerce")
    snapshot["as_of_date"] = pd.to_datetime(snapshot["as_of_date"], errors="coerce")

    if not leave_requests.empty:
        leave_requests["request_start_date"] = pd.to_datetime(
            leave_requests["request_start_date"], errors="coerce"
        )
        leave_requests["request_end_date"] = pd.to_datetime(
            leave_requests["request_end_date"], errors="coerce"
        )
        leave_requests["approval_date"] = pd.to_datetime(
            leave_requests["approval_date"], errors="coerce"
        )

    if not timesheets.empty:
        timesheets["work_date"] = pd.to_datetime(timesheets["work_date"], errors="coerce")

    bad_ledger_dates = ledger["event_date"].isna().sum()
    bad_snapshot_dates = snapshot["as_of_date"].isna().sum()

    bad_request_start_dates = (
        leave_requests["request_start_date"].isna().sum()
        if not leave_requests.empty and "request_start_date" in leave_requests.columns
        else 0
    )

    bad_request_end_dates = (
        leave_requests["request_end_date"].isna().sum()
        if not leave_requests.empty and "request_end_date" in leave_requests.columns
        else 0
    )

    bad_request_approval_dates = (
        leave_requests["approval_date"].isna().sum()
        if not leave_requests.empty and "approval_date" in leave_requests.columns
        else 0
    )

    bad_timesheet_dates = (
        timesheets["work_date"].isna().sum()
        if not timesheets.empty and "work_date" in timesheets.columns
        else 0
    )

    print(f"[input] Unparseable ledger event_date rows: {bad_ledger_dates}")
    print(f"[input] Unparseable snapshot as_of_date rows: {bad_snapshot_dates}")
    print(f"[input] Unparseable leave request start rows: {bad_request_start_dates}")
    print(f"[input] Unparseable leave request end rows: {bad_request_end_dates}")
    print(f"[input] Unparseable leave request approval rows: {bad_request_approval_dates}")
    print(f"[input] Unparseable timesheet work_date rows: {bad_timesheet_dates}")

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

    merged = merged[
        merged["event_date"].isna() | (merged["event_date"] <= merged["as_of_date"])
    ]

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
        "leave_requests": leave_requests,
        "timesheets": timesheets,
    }

    context = {"ledger_recon": report}

    for rule in rules:
        findings.extend(run_rule(rule, datasets, context=context))

    # ----------------------------
    # Write findings output
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
                "classification",
                "message",
                "diff_units",
                "evidence",
                "finding_id",
                "next_action",
            ]
        )

    findings_path = output_dir / "leave_leakage_findings.csv"
    findings_df.to_csv(findings_path, index=False)

    # ----------------------------
    # Summary output (counts by rule and severity)
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

    summary_path = output_dir / "leave_leakage_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(summary_df.to_string(index=False))

    # ----------------------------
    # Summary output (totals by severity)
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

    severity_summary_path = output_dir / "leave_leakage_summary_by_severity.csv"
    severity_summary_df.to_csv(severity_summary_path, index=False)

    print(f"Wrote: {severity_summary_path}")
    print(severity_summary_df.to_string(index=False))

        # ----------------------------
    # Classification summaries
    # ----------------------------
    if "classification" not in findings_df.columns:
        findings_df["classification"] = "UNCLASSIFIED"
    else:
        findings_df["classification"] = findings_df["classification"].fillna("UNCLASSIFIED")

    if len(findings_df) == 0:
        classification_summary_df = pd.DataFrame(columns=["classification", "finding_count"])
        classification_x_severity_df = pd.DataFrame(
            columns=["classification", "severity", "finding_count"]
        )
    else:
        classification_summary_df = (
            findings_df.groupby("classification", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

        classification_x_severity_df = (
            findings_df.groupby(["classification", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["classification", "severity"])
        )

    classification_summary_path = output_dir / "leave_leakage_summary_by_classification.csv"
    classification_x_severity_path = output_dir / "leave_leakage_summary_classification_x_severity.csv"

    classification_summary_df.to_csv(classification_summary_path, index=False)
    classification_x_severity_df.to_csv(classification_x_severity_path, index=False)

    print(f"Wrote: {classification_summary_path}")
    print(f"Wrote: {classification_x_severity_path}")

    # ----------------------------
    # Detailed leakage reconciliation report
    # ----------------------------
    tolerance = 0.25  # 15 minutes in hours
    report["risk_flag"] = report["diff_units"].abs() > tolerance
    report["risk_reason"] = report["risk_flag"].map(
        lambda x: "BALANCE_MISMATCH_LEDGER_VS_SNAPSHOT" if x else ""
    )

    out_path = output_dir / "leakage_report.csv"
    report.sort_values(["employee_id", "leave_type", "as_of_date"]).to_csv(out_path, index=False)

    print(f"Wrote: {out_path}")
    return 0