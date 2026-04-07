from __future__ import annotations

from pathlib import Path
from datetime import date
import pandas as pd
import yaml

from src.common.paths import get_processed_dir, get_outputs_dir
from src.common.data_window import write_data_window

from src.cross_module_integrity.models import Finding
from src.cross_module_integrity.detectors.registry import run_rule


REQUIRED_TERM = {"employee_id", "termination_date"}
REQUIRED_PAY = {"employee_id", "pay_date"}
REQUIRED_EMP = {"employee_id"}
REQUIRED_SNAPSHOT = {"employee_id", "leave_type", "as_of_date", "balance_units"}
REQUIRED_LEDGER = {"employee_id", "leave_type", "event_date", "units", "event_type"}


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

    rules_path = Path(__file__).resolve().parent / "config" / "cross_module_rules.yml"

    print(f"[input] Using processed directory: {processed_dir}")

    terminations = pd.read_csv(
        processed_dir / "terminations.csv",
        dtype={"employee_id": "string"},
    )

    pay_events = pd.read_csv(
        processed_dir / "pay_events.csv",
        dtype={"employee_id": "string"},
    )

    employees = pd.read_csv(
        processed_dir / "employees.csv",
        dtype={"employee_id": "string"},
    )

    leave_snapshot_path = processed_dir / "balances_snapshot.csv"

    if leave_snapshot_path.exists() and leave_snapshot_path.stat().st_size > 0:
        leave_snapshot = pd.read_csv(
            leave_snapshot_path,
            dtype={"employee_id": "string", "leave_type": "string"},
        )
    else:
        print("INFO - balances_snapshot.csv not found or empty; continuing without snapshot data")
        leave_snapshot = pd.DataFrame(columns=["employee_id", "leave_type", "as_of_date", "balance_units"])

    leave_ledger = pd.read_csv(
        processed_dir / "leave_ledger.csv",
        dtype={"employee_id": "string", "leave_type": "string", "event_type": "string"},
    )

    for df in (terminations, pay_events, employees, leave_snapshot, leave_ledger):
        df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(terminations, REQUIRED_TERM, "terminations.csv")
    _require_cols(pay_events, REQUIRED_PAY, "pay_events.csv")
    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    _require_cols(leave_snapshot, REQUIRED_SNAPSHOT, "balances_snapshot.csv")
    _require_cols(leave_ledger, REQUIRED_LEDGER, "leave_ledger.csv")

    terminations["termination_date"] = pd.to_datetime(
        terminations["termination_date"], errors="coerce"
    )
    pay_events["pay_date"] = pd.to_datetime(
        pay_events["pay_date"], errors="coerce"
    )
    leave_snapshot["as_of_date"] = pd.to_datetime(
        leave_snapshot["as_of_date"], errors="coerce"
    )
    leave_ledger["event_date"] = pd.to_datetime(
        leave_ledger["event_date"], errors="coerce"
    )

    bad_term_dates = terminations["termination_date"].isna().sum()
    bad_pay_dates = pay_events["pay_date"].isna().sum()
    bad_snapshot_dates = leave_snapshot["as_of_date"].isna().sum()
    bad_ledger_dates = leave_ledger["event_date"].isna().sum()

    print(f"[input] Unparseable termination_date rows: {bad_term_dates}")
    print(f"[input] Unparseable pay_date rows: {bad_pay_dates}")
    print(f"[input] Unparseable snapshot as_of_date rows: {bad_snapshot_dates}")
    print(f"[input] Unparseable ledger event_date rows: {bad_ledger_dates}")

    window_dates: list[date] = []

    for series in (
        terminations["termination_date"].dropna(),
        pay_events["pay_date"].dropna(),
        leave_snapshot["as_of_date"].dropna(),
        leave_ledger["event_date"].dropna(),
    ):
        if not series.empty:
            window_dates.extend(series.dt.date.tolist())

    write_data_window(output_dir / "cross_module_data_window.csv", window_dates)

    rules = _load_rules(rules_path)

    datasets = {
        "terminations": terminations,
        "pay_events": pay_events,
        "employee_master": employees,
        "leave_snapshot": leave_snapshot,
        "leave_ledger": leave_ledger,
    }

    findings: list[Finding] = []

    # Pass 1: run all rules except CM-020
    for rule in rules:
        if rule["id"] == "CM-020":
            continue
        findings.extend(run_rule(rule, datasets, context={}))

    if findings:
        first_pass_df = pd.DataFrame([f.__dict__ for f in findings])
    else:
        first_pass_df = pd.DataFrame(
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

    # Make first-pass findings available to CM-020
    datasets["cross_module_findings"] = first_pass_df

    # Pass 2: run CM-020 only
    for rule in rules:
        if rule["id"] != "CM-020":
            continue
        findings.extend(run_rule(rule, datasets, context={}))

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

    findings_path = output_dir / "cross_module_findings.csv"
    findings_df.to_csv(findings_path, index=False)

    if len(findings_df) == 0:
        summary_df = pd.DataFrame(columns=["rule_code", "severity", "finding_count"])
    else:
        summary_df = (
            findings_df.groupby(["rule_code", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["severity", "finding_count"], ascending=[True, False])
        )

    summary_path = output_dir / "cross_module_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    if len(findings_df) == 0:
        severity_summary_df = pd.DataFrame(columns=["severity", "finding_count"])
    else:
        severity_summary_df = (
            findings_df.groupby("severity", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

    severity_summary_path = output_dir / "cross_module_summary_by_severity.csv"
    severity_summary_df.to_csv(severity_summary_path, index=False)

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

    classification_summary_path = output_dir / "cross_module_summary_by_classification.csv"
    classification_x_severity_path = output_dir / "cross_module_summary_classification_x_severity.csv"

    classification_summary_df.to_csv(classification_summary_path, index=False)
    classification_x_severity_df.to_csv(classification_x_severity_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {severity_summary_path}")
    print(f"Wrote: {classification_summary_path}")
    print(f"Wrote: {classification_x_severity_path}")

    return 0