from __future__ import annotations

from pathlib import Path
from datetime import date
import pandas as pd
import yaml

from src.common.paths import get_processed_dir, get_outputs_dir
from src.common.data_window import write_data_window
from src.common.rule_filter import should_run_rule
from src.common.execution_metadata import write_execution_metadata
from src.common.rule_metadata import load_rule_metadata_map

from src.cross_module_integrity.models import Finding
from src.cross_module_integrity.detectors.registry import run_rule


REQUIRED_TERM = {"employee_id", "termination_date"}
REQUIRED_PAY = {"employee_id", "pay_date"}
REQUIRED_EMP = {"employee_id"}
REQUIRED_SNAPSHOT = {"employee_id", "leave_type", "as_of_date", "balance_units"}
REQUIRED_LEDGER = {"employee_id", "leave_type", "event_date", "units"}


def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _load_rules(rules_path: Path) -> list[dict]:
    with rules_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("rules", [])


def main(
    client: str,
    pilot: str,
    mode: str = "full",
    include_supporting: bool = False,
) -> int:
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
        if not df.empty and "employee_id" in df.columns:
            df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(terminations, REQUIRED_TERM, "terminations.csv")
    _require_cols(pay_events, REQUIRED_PAY, "pay_events.csv")
    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    if not leave_snapshot.empty:
        _require_cols(leave_snapshot, REQUIRED_SNAPSHOT, "balances_snapshot.csv")
    _require_cols(leave_ledger, REQUIRED_LEDGER, "leave_ledger.csv")

    terminations["termination_date"] = pd.to_datetime(
        terminations["termination_date"], errors="coerce"
    )
    pay_events["pay_date"] = pd.to_datetime(
        pay_events["pay_date"], errors="coerce"
    )
    if not leave_snapshot.empty:
        leave_snapshot["as_of_date"] = pd.to_datetime(
            leave_snapshot["as_of_date"], errors="coerce"
        )
    leave_ledger["event_date"] = pd.to_datetime(
        leave_ledger["event_date"], errors="coerce"
    )

    bad_term_dates = terminations["termination_date"].isna().sum()
    bad_pay_dates = pay_events["pay_date"].isna().sum()
    bad_snapshot_dates = leave_snapshot["as_of_date"].isna().sum() if not leave_snapshot.empty else 0
    bad_ledger_dates = leave_ledger["event_date"].isna().sum()

    print(f"[input] Unparseable termination_date rows: {bad_term_dates}")
    print(f"[input] Unparseable pay_date rows: {bad_pay_dates}")
    print(f"[input] Unparseable snapshot as_of_date rows: {bad_snapshot_dates}")
    print(f"[input] Unparseable ledger event_date rows: {bad_ledger_dates}")

    metadata_path = write_execution_metadata(
        output_dir=output_dir,
        module_name="CROSS_MODULE",
        mode=mode,
        include_supporting=include_supporting,
    )
    print(f"Wrote: {metadata_path}")

    window_dates: list[date] = []

    for series in (
        terminations["termination_date"].dropna(),
        pay_events["pay_date"].dropna(),
        leave_snapshot["as_of_date"].dropna() if not leave_snapshot.empty else pd.Series(dtype="datetime64[ns]"),
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

    print(f"CROSS_MODULE execution mode: mode={mode}, include_supporting={include_supporting}")

    for rule in rules:
        if rule["id"] == "CM-020":
            continue

        if not should_run_rule(
            rule,
            mode=mode,
            include_supporting=include_supporting,
        ):
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
                "classification",
                "message",
                "diff_units",
                "evidence",
                "finding_id",
                "next_action",
            ]
        )

    datasets["cross_module_findings"] = first_pass_df

    for rule in rules:
        if rule["id"] != "CM-020":
            continue

        if not should_run_rule(
            rule,
            mode=mode,
            include_supporting=include_supporting,
        ):
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

    rule_meta = load_rule_metadata_map(rules_path)

    if not findings_df.empty:
        findings_df["payroll_only_viable"] = findings_df["rule_code"].map(
            lambda x: rule_meta.get(x, {}).get("payroll_only_viable")
        )
        findings_df["viability_level"] = findings_df["rule_code"].map(
            lambda x: rule_meta.get(x, {}).get("viability_level")
        )
        findings_df["payroll_signal_strength"] = findings_df["rule_code"].map(
            lambda x: rule_meta.get(x, {}).get("payroll_signal_strength")
        )
    else:
        findings_df["payroll_only_viable"] = pd.Series(dtype="object")
        findings_df["viability_level"] = pd.Series(dtype="object")
        findings_df["payroll_signal_strength"] = pd.Series(dtype="object")

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

    if len(findings_df) == 0:
        viability_summary_df = pd.DataFrame(columns=["viability_level", "finding_count"])
    else:
        viability_summary_df = (
            findings_df.groupby("viability_level", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

    viability_summary_path = output_dir / "cross_module_summary_by_viability.csv"
    viability_summary_df.to_csv(viability_summary_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {severity_summary_path}")
    print(f"Wrote: {classification_summary_path}")
    print(f"Wrote: {classification_x_severity_path}")
    print(f"Wrote: {viability_summary_path}")

    return 0