from __future__ import annotations

from pathlib import Path
from datetime import date
import pandas as pd
import yaml

from src.common.paths import get_processed_dir, get_outputs_dir
from src.common.data_window import write_data_window

from src.termination_exposure.models import Finding
from src.termination_exposure.detectors.registry import run_rule
from src.termination_exposure.rules import prepare_term_state

from common.validation import (
    ValidationResult,
    add_issue,
    check_dataset_present,
    check_required_columns,
    check_critical_columns_not_all_missing,
    make_result,
    print_validation_result,
    write_validation_outputs,
)

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

def validate_term_inputs(datasets: dict[str, pd.DataFrame]) -> ValidationResult:
    module_name = "TERM"
    issues = []

    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    employee_master = datasets.get("employee_master", pd.DataFrame())

    check_dataset_present(issues, module_name, "terminations", terminations, required=True)
    check_dataset_present(issues, module_name, "pay_events", pay_events, required=True)
    check_dataset_present(issues, module_name, "employee_master", employee_master, required=False)

    check_required_columns(
        issues,
        module_name,
        "terminations",
        terminations,
        ["employee_id", "termination_date"],
    )
    check_required_columns(
        issues,
        module_name,
        "pay_events",
        pay_events,
        ["employee_id", "pay_date"],
    )

    check_critical_columns_not_all_missing(
        issues,
        module_name,
        "terminations",
        terminations,
        ["employee_id", "termination_date"],
    )
    check_critical_columns_not_all_missing(
        issues,
        module_name,
        "pay_events",
        pay_events,
        ["employee_id", "pay_date"],
    )

    # Useful warnings, not blockers
    if not terminations.empty:
        if "evidence_reference" not in terminations.columns and "evidence_ref" not in terminations.columns:
            add_issue(
                issues,
                module_name,
                "WARNING",
                "terminations",
                "evidence_reference",
                "MISSING_EVIDENCE_FIELD",
                "Termination evidence field not found; evidence-based TERM rules may have reduced coverage.",
            )

    if not employee_master.empty:
        for col in ["start_date", "employment_type"]:
            if col not in employee_master.columns:
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "employee_master",
                    col,
                    "MISSING_OPTIONAL_COLUMN",
                    f"Optional employee master column '{col}' is missing; some TERM context may be reduced.",
                )

    return make_result(module_name, issues)

def main(client: str, pilot: str) -> int:
    processed_dir = get_processed_dir(client, pilot)
    output_dir = get_outputs_dir(client, pilot)

    rules_path = Path(__file__).resolve().parent / "config" / "term_rules.yml"

    # ----------------------------
    # Load datasets
    # ----------------------------
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

    leave_snapshot = pd.read_csv(
        processed_dir / "balances_snapshot.csv",
        dtype={"employee_id": "string", "leave_type": "string"},
    )

    leave_ledger = pd.read_csv(
        processed_dir / "leave_ledger.csv",
        dtype={"employee_id": "string", "leave_type": "string", "event_type": "string"},
    )

    # ----------------------------
    # Clean + validate
    # ----------------------------
    for df in (terminations, pay_events, employees, leave_snapshot, leave_ledger):
        df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(terminations, REQUIRED_TERM, "terminations.csv")
    _require_cols(pay_events, REQUIRED_PAY, "pay_events.csv")
    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    _require_cols(leave_snapshot, REQUIRED_SNAPSHOT, "balances_snapshot.csv")
    _require_cols(leave_ledger, REQUIRED_LEDGER, "leave_ledger.csv")

    terminations["termination_date"] = pd.to_datetime(terminations["termination_date"], errors="coerce")
    pay_events["pay_date"] = pd.to_datetime(pay_events["pay_date"], errors="coerce")
    leave_snapshot["as_of_date"] = pd.to_datetime(leave_snapshot["as_of_date"], errors="coerce")
    leave_ledger["event_date"] = pd.to_datetime(leave_ledger["event_date"], errors="coerce")

        # ----------------------------
    # Module validation
    # ----------------------------
    datasets = {
        "terminations": terminations,
        "pay_events": pay_events,
        "employee_master": employees,
        "leave_snapshot": leave_snapshot,
        "leave_ledger": leave_ledger,
    }

    validation = validate_term_inputs(datasets)
    print_validation_result(validation)
    write_validation_outputs(validation, output_dir, "term")

    if not validation.can_run:
        print("TERM module blocked due to validation errors.")
        return 1

    # ----------------------------
    # Data window
    # ----------------------------
    window_dates: list[date] = []

    for series in [
        terminations["termination_date"],
        pay_events["pay_date"],
        leave_snapshot["as_of_date"],
        leave_ledger["event_date"],
    ]:
        valid = series.dropna()
        if not valid.empty:
            window_dates.extend(valid.dt.date.tolist())

    write_data_window(output_dir / "term_data_window.csv", window_dates)

    # ----------------------------
    # Prepare state + rules
    # ----------------------------
    state = prepare_term_state(
        terminations=terminations,
        pay_events=pay_events,
    )

    rules = _load_rules(rules_path)

    findings: list[Finding] = []

    context = {"state": state}

    for rule in rules:
        findings.extend(run_rule(rule, datasets, context=context))

    # ----------------------------
    # Findings
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

    findings_path = output_dir / "term_findings.csv"
    findings_df.to_csv(findings_path, index=False)

    # ----------------------------
    # Summary
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

    summary_path = output_dir / "term_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    # ----------------------------
    # Severity summary
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

    severity_summary_path = output_dir / "term_summary_by_severity.csv"
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

    classification_summary_path = output_dir / "term_summary_by_classification.csv"
    classification_x_severity_path = output_dir / "term_summary_classification_x_severity.csv"

    classification_summary_df.to_csv(classification_summary_path, index=False)
    classification_x_severity_df.to_csv(classification_x_severity_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {severity_summary_path}")
    print(f"Wrote: {classification_summary_path}")
    print(f"Wrote: {classification_x_severity_path}")

    return 0