from __future__ import annotations

from pathlib import Path
from datetime import date
import pandas as pd
import yaml

from src.common.paths import get_processed_dir, get_outputs_dir
from src.common.data_window import write_data_window

from src.lsl_exposure.models import Finding
from src.lsl_exposure.detectors.registry import run_rule
from src.lsl_exposure.rules import prepare_lsl_state, compute_exposure_band

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

REQUIRED_EMP = {"employee_id", "start_date"}
REQUIRED_SNAP = {"employee_id", "leave_type", "as_of_date", "balance_units"}
REQUIRED_LEDGER = {"employee_id", "leave_type", "event_date", "units"}


def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _load_rules(rules_path: Path) -> list[dict]:
    with rules_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("rules", [])


def validate_lsl_inputs(datasets: dict[str, pd.DataFrame]) -> ValidationResult:
    module_name = "LSL"
    issues = []

    employee_master = datasets.get("employee_master", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())

    check_dataset_present(issues, module_name, "employee_master", employee_master, required=False)
    check_dataset_present(issues, module_name, "leave_snapshot", leave_snapshot, required=False)
    check_dataset_present(issues, module_name, "leave_ledger", leave_ledger, required=False)

    core_datasets = [employee_master, leave_snapshot, leave_ledger]
    if all(df is None or df.empty for df in core_datasets):
        add_issue(
            issues,
            module_name,
            "ERROR",
            "module",
            None,
            "NO_USABLE_DATASETS",
            "No usable datasets were supplied to LSL; long service leave checks cannot be assessed.",
        )
        return make_result(module_name, issues)

    if not employee_master.empty:
        check_required_columns(
            issues,
            module_name,
            "employee_master",
            employee_master,
            ["employee_id"],
            level="WARNING",
        )
        check_critical_columns_not_all_missing(
            issues,
            module_name,
            "employee_master",
            employee_master,
            ["employee_id"],
            level="ERROR",
        )

        for col in ["start_date", "years_at_company", "fte"]:
            if col not in employee_master.columns:
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "employee_master",
                    col,
                    "MISSING_OPTIONAL_COLUMN",
                    f"Employee master column '{col}' is missing; some LSL eligibility or contextual checks may have reduced coverage.",
                )

    if not leave_snapshot.empty:
        check_required_columns(
            issues,
            module_name,
            "leave_snapshot",
            leave_snapshot,
            ["employee_id", "leave_type"],
            level="WARNING",
        )
        check_critical_columns_not_all_missing(
            issues,
            module_name,
            "leave_snapshot",
            leave_snapshot,
            ["employee_id", "leave_type"],
            level="WARNING",
        )

        for col in ["as_of_date", "balance_units"]:
            if col not in leave_snapshot.columns:
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "leave_snapshot",
                    col,
                    "MISSING_OPTIONAL_COLUMN",
                    f"Leave snapshot column '{col}' is missing; some LSL balance and timing checks may have reduced confidence.",
                )
            elif leave_snapshot[col].isna().all():
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "leave_snapshot",
                    col,
                    "ALL_VALUES_MISSING",
                    f"Leave snapshot column '{col}' is fully null/blank; some LSL checks may have reduced confidence.",
                )

    if not leave_ledger.empty:
        check_required_columns(
            issues,
            module_name,
            "leave_ledger",
            leave_ledger,
            ["employee_id", "leave_type"],
            level="WARNING",
        )
        check_critical_columns_not_all_missing(
            issues,
            module_name,
            "leave_ledger",
            leave_ledger,
            ["employee_id", "leave_type"],
            level="WARNING",
        )

        for col in ["event_date", "units", "event_type"]:
            if col not in leave_ledger.columns:
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "leave_ledger",
                    col,
                    "MISSING_OPTIONAL_COLUMN",
                    f"Leave ledger column '{col}' is missing; some LSL ledger checks may have reduced coverage.",
                )
            elif leave_ledger[col].isna().all():
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "leave_ledger",
                    col,
                    "ALL_VALUES_MISSING",
                    f"Leave ledger column '{col}' is fully null/blank; some LSL ledger checks may have reduced coverage.",
                )

    snapshot_has_lsl = False
    ledger_has_lsl = False

    if not leave_snapshot.empty and "leave_type" in leave_snapshot.columns:
        snapshot_has_lsl = (
            leave_snapshot["leave_type"]
            .astype("string")
            .str.strip()
            .str.upper()
            .eq("LSL")
            .any()
        )

    if not leave_ledger.empty and "leave_type" in leave_ledger.columns:
        ledger_has_lsl = (
            leave_ledger["leave_type"]
            .astype("string")
            .str.strip()
            .str.upper()
            .eq("LSL")
            .any()
        )

    if not snapshot_has_lsl and not ledger_has_lsl:
        add_issue(
            issues,
            module_name,
            "WARNING",
            "LSL",
            "leave_type",
            "NO_LSL_ROWS",
            "No LSL leave types were identified in leave_snapshot or leave_ledger; LSL-specific rules may not be assessable for this pilot.",
        )

    elif snapshot_has_lsl and not ledger_has_lsl:
        add_issue(
            issues,
            module_name,
            "WARNING",
            "leave_ledger",
            "leave_type",
            "NO_LSL_LEDGER_ROWS",
            "LSL balances exist in leave_snapshot but no LSL rows were identified in leave_ledger; reconciliation-style LSL rules may have reduced coverage.",
        )

    elif ledger_has_lsl and not snapshot_has_lsl:
        add_issue(
            issues,
            module_name,
            "WARNING",
            "leave_snapshot",
            "leave_type",
            "NO_LSL_SNAPSHOT_ROWS",
            "LSL activity exists in leave_ledger but no LSL rows were identified in leave_snapshot; balance-style LSL rules may have reduced coverage.",
        )

    return make_result(module_name, issues)


def main(client: str, pilot: str) -> int:
    processed_dir = get_processed_dir(client, pilot)
    output_dir = get_outputs_dir(client, pilot)

    rules_path = Path(__file__).resolve().parent / "config" / "lsl_rules.yml"

    employees = pd.read_csv(
        processed_dir / "employees.csv",
        dtype={"employee_id": "string"},
    )

    snapshot_path = processed_dir / "balances_snapshot.csv"
    if snapshot_path.exists() and snapshot_path.stat().st_size > 0:
        snapshot = pd.read_csv(
            snapshot_path,
            dtype={"employee_id": "string", "leave_type": "string"},
        )
    else:
        print("INFO - balances_snapshot.csv not found or empty; continuing without snapshot data")
        snapshot = pd.DataFrame(columns=["employee_id", "leave_type", "as_of_date", "balance_units"])

    ledger = pd.read_csv(
        processed_dir / "leave_ledger.csv",
        dtype={"employee_id": "string", "leave_type": "string", "event_type": "string"},
    )

    pay_rates_path = processed_dir / "pay_rates.csv"
    pay_rates = None
    if pay_rates_path.exists():
        pay_rates = pd.read_csv(
            pay_rates_path,
            dtype={"employee_id": "string"},
        )

    for df in (employees, snapshot, ledger):
        if not df.empty and "employee_id" in df.columns:
            df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    if not snapshot.empty:
        _require_cols(snapshot, REQUIRED_SNAP, "balances_snapshot.csv")
    _require_cols(ledger, REQUIRED_LEDGER, "leave_ledger.csv")

    employees["start_date"] = pd.to_datetime(employees["start_date"], errors="coerce")
    if not snapshot.empty:
        snapshot["as_of_date"] = pd.to_datetime(snapshot["as_of_date"], errors="coerce")
    ledger["event_date"] = pd.to_datetime(ledger["event_date"], errors="coerce")

    bad_emp_dates = employees["start_date"].isna().sum()
    bad_snapshot_dates = snapshot["as_of_date"].isna().sum() if not snapshot.empty else 0
    bad_ledger_dates = ledger["event_date"].isna().sum()

    print(f"[input] Using processed directory: {processed_dir}")
    print(f"[input] Unparseable employee start_date rows: {bad_emp_dates}")
    print(f"[input] Unparseable snapshot as_of_date rows: {bad_snapshot_dates}")
    print(f"[input] Unparseable ledger event_date rows: {bad_ledger_dates}")

    datasets = {
        "employee_master": employees,
        "leave_snapshot": snapshot,
        "leave_ledger": ledger,
    }

    validation = validate_lsl_inputs(datasets)
    print_validation_result(validation)
    write_validation_outputs(validation, output_dir, "lsl")

    if not validation.can_run:
        print("LSL module blocked due to validation errors.")
        return 1

    window_dates: list[date] = []

    emp_dates = employees["start_date"].dropna()
    if not emp_dates.empty:
        window_dates.extend(emp_dates.dt.date.tolist())

    if not snapshot.empty:
        snap_dates = snapshot["as_of_date"].dropna()
        if not snap_dates.empty:
            window_dates.extend(snap_dates.dt.date.tolist())

    ledger_dates = ledger["event_date"].dropna()
    if not ledger_dates.empty:
        window_dates.extend(ledger_dates.dt.date.tolist())

    write_data_window(output_dir / "lsl_data_window.csv", window_dates)

    snapshot_date = snapshot["as_of_date"].max() if not snapshot.empty else None

    state = prepare_lsl_state(
        employees=employees,
        snapshot=snapshot,
        pay_rates=pay_rates,
        snapshot_date=snapshot_date,
    )

    rules = _load_rules(rules_path)
    findings: list[Finding] = []

    datasets = {
        "employee_master": employees,
        "leave_snapshot": snapshot,
        "leave_ledger": ledger,
    }

    context = {"state": state}

    for rule in rules:
        findings.extend(run_rule(rule, datasets, context=context))

    eligibility_years = 7.0
    full_years = 10.0
    hours_per_day = 7.6

    total_low, total_high = compute_exposure_band(
        state=state,
        eligibility_years=eligibility_years,
        full_years=full_years,
        hours_per_day=hours_per_day,
    )

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

    findings_path = output_dir / "lsl_findings.csv"
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

    summary_path = output_dir / "lsl_summary.csv"
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

    severity_summary_path = output_dir / "lsl_summary_by_severity.csv"
    severity_summary_df.to_csv(severity_summary_path, index=False)

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

    classification_summary_path = output_dir / "lsl_summary_by_classification.csv"
    classification_x_severity_path = output_dir / "lsl_summary_classification_x_severity.csv"

    classification_summary_df.to_csv(classification_summary_path, index=False)
    classification_x_severity_df.to_csv(classification_x_severity_path, index=False)

    exposure_path = output_dir / "lsl_exposure_summary.csv"
    pd.DataFrame(
        [
            {"metric": "estimated_exposure_low", "value": round(total_low, 2), "currency": "AUD"},
            {"metric": "estimated_exposure_high", "value": round(total_high, 2), "currency": "AUD"},
            {
                "metric": "note",
                "value": "Indicative-only estimate based on heuristics, not statutory entitlement calculations.",
                "currency": "",
            },
        ]
    ).to_csv(exposure_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {severity_summary_path}")
    print(f"Wrote: {classification_summary_path}")
    print(f"Wrote: {classification_x_severity_path}")
    print(f"Wrote: {exposure_path}")

    return 0