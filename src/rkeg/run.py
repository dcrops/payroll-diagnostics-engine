from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

from src.common.paths import get_processed_dir, get_outputs_dir
from src.common.data_window import write_data_window

from src.rkeg.models import Finding, write_findings_csv
from src.rkeg.detectors.registry import run_rule
from src.rkeg.datasets import load_all_datasets

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


EVIDENCE_LAYER_MAP = {
    "structural_completeness": "Workforce Identity",
    "evidence_traceability": "Workforce Identity",
    "calculation_integrity": "Pay Construction",
    "data_anomaly_sanity": "Pay Construction",
    "timing_integrity": "Entitlement Evidence",
    "cross_module_linkage_risk": "Entitlement Evidence",
    "exception_handling": "Governance & Controls",
    "governance_exposure": "Governance & Controls",
    "governance_monitoring_exposure": "Governance & Controls",
}

REQUIRED_EMP = {"employee_id"}
REQUIRED_PAY = {"employee_id"}
REQUIRED_LEDGER = {"employee_id"}
REQUIRED_SNAP = {"employee_id"}
REQUIRED_TERM = {"employee_id"}


def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _load_rules(rules_path: Path) -> list[dict]:
    with rules_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("rules", [])


def _collect_dates_from_df(df: pd.DataFrame, candidate_cols: Iterable[str]) -> list[date]:
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

            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    d = datetime.strptime(s, fmt).date()
                    dates.append(d)
                    break
                except ValueError:
                    continue

    return dates


def _risk_score_and_rating(findings_df: pd.DataFrame) -> tuple[int, str]:
    if findings_df is None or len(findings_df) == 0:
        return 0, "LOW"

    sev_counts = findings_df["severity"].astype(str).str.upper().value_counts().to_dict()
    high = int(sev_counts.get("HIGH", 0))
    medium = int(sev_counts.get("MEDIUM", 0))
    low = int(sev_counts.get("LOW", 0))

    severity_points = (high * 10) + (medium * 4) + (low * 1)
    severity_score = min(60, severity_points)

    dims: set[str] = set()
    for x in findings_df.get("risk_dimension", []):
        if isinstance(x, list):
            dims.update([str(d).strip() for d in x if str(d).strip()])
        elif isinstance(x, str) and x.strip():
            dims.add(x.strip())

    breadth_score = min(25, len(dims) * 4)
    freq_score = min(15, int(len(findings_df) * 1.5))

    score = int(min(100, severity_score + breadth_score + freq_score))

    if score >= 70:
        rating = "HIGH"
    elif score >= 35:
        rating = "MEDIUM"
    else:
        rating = "LOW"

    return score, rating


def validate_rkeg_inputs(datasets: dict[str, pd.DataFrame]) -> ValidationResult:
    module_name = "RKEG"
    issues = []

    employee_master = datasets.get("employee_master", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())

    employee_super = datasets.get("employee_super", pd.DataFrame())
    super_payments = datasets.get("super_payments", pd.DataFrame())
    rate_history = datasets.get("rate_history", pd.DataFrame())
    pay_overrides = datasets.get("pay_overrides", pd.DataFrame())

    # Presence checks
    check_dataset_present(issues, module_name, "employee_master", employee_master, required=False)
    check_dataset_present(issues, module_name, "pay_events", pay_events, required=False)
    check_dataset_present(issues, module_name, "terminations", terminations, required=False)
    check_dataset_present(issues, module_name, "leave_snapshot", leave_snapshot, required=False)
    check_dataset_present(issues, module_name, "leave_ledger", leave_ledger, required=False)
    check_dataset_present(issues, module_name, "employee_super", employee_super, required=False)
    check_dataset_present(issues, module_name, "super_payments", super_payments, required=False)
    check_dataset_present(issues, module_name, "rate_history", rate_history, required=False)
    check_dataset_present(issues, module_name, "pay_overrides", pay_overrides, required=False)

    core_datasets = [
        employee_master,
        pay_events,
        terminations,
        leave_snapshot,
        leave_ledger,
    ]
    if all(df is None or df.empty for df in core_datasets):
        add_issue(
            issues,
            module_name,
            "ERROR",
            "module",
            None,
            "NO_USABLE_DATASETS",
            "No usable datasets were supplied to RKEG; governance checks cannot be assessed.",
        )
        return make_result(module_name, issues)

    # employee_master
    if not employee_master.empty:
        check_required_columns(
            issues, module_name, "employee_master", employee_master, ["employee_id"], level="WARNING"
        )
        check_critical_columns_not_all_missing(
            issues, module_name, "employee_master", employee_master, ["employee_id"], level="ERROR"
        )

        for col in ["start_date", "employment_type", "base_rate"]:
            if col not in employee_master.columns:
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "employee_master",
                    col,
                    "MISSING_OPTIONAL_COLUMN",
                    f"Employee master column '{col}' is missing; some employee/pay governance rules may have reduced coverage.",
                )

    # pay_events
    if not pay_events.empty:
        check_required_columns(
            issues, module_name, "pay_events", pay_events, ["employee_id", "pay_date"], level="WARNING"
        )
        check_critical_columns_not_all_missing(
            issues, module_name, "pay_events", pay_events, ["employee_id", "pay_date"], level="WARNING"
        )

        for col in ["gross_amount", "is_final_pay", "pay_code"]:
            if col not in pay_events.columns:
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "pay_events",
                    col,
                    "MISSING_OPTIONAL_COLUMN",
                    f"Pay events column '{col}' is missing; some pay governance rules may have reduced coverage.",
                )

    # terminations
    if not terminations.empty:
        check_required_columns(
            issues, module_name, "terminations", terminations, ["employee_id", "termination_date"], level="WARNING"
        )
        check_critical_columns_not_all_missing(
            issues, module_name, "terminations", terminations, ["employee_id", "termination_date"], level="WARNING"
        )

        if "evidence_reference" not in terminations.columns and "evidence_ref" not in terminations.columns:
            add_issue(
                issues,
                module_name,
                "WARNING",
                "terminations",
                "evidence_reference",
                "MISSING_EVIDENCE_FIELD",
                "Termination evidence field not found; evidence-traceability rules may have reduced coverage.",
            )

    # leave_snapshot
    if not leave_snapshot.empty:
        check_required_columns(
            issues,
            module_name,
            "leave_snapshot",
            leave_snapshot,
            ["employee_id", "leave_type", "balance_units"],
            level="WARNING",
        )
        check_critical_columns_not_all_missing(
            issues,
            module_name,
            "leave_snapshot",
            leave_snapshot,
            ["employee_id", "leave_type", "balance_units"],
            level="WARNING",
        )

        if "as_of_date" not in leave_snapshot.columns:
            add_issue(
                issues,
                module_name,
                "WARNING",
                "leave_snapshot",
                "as_of_date",
                "MISSING_OPTIONAL_COLUMN",
                "Leave snapshot 'as_of_date' is missing; timing-based leave governance checks may have reduced confidence.",
            )
        elif leave_snapshot["as_of_date"].isna().all():
            add_issue(
                issues,
                module_name,
                "WARNING",
                "leave_snapshot",
                "as_of_date",
                "ALL_VALUES_MISSING",
                "Leave snapshot 'as_of_date' is fully null/blank; timing-based leave governance checks may have reduced confidence.",
            )

    # leave_ledger
    if not leave_ledger.empty:
        check_required_columns(
            issues,
            module_name,
            "leave_ledger",
            leave_ledger,
            ["employee_id", "leave_type", "event_date", "units"],
            level="WARNING",
        )
        check_critical_columns_not_all_missing(
            issues,
            module_name,
            "leave_ledger",
            leave_ledger,
            ["employee_id", "leave_type", "event_date", "units"],
            level="WARNING",
        )

        for col in ["event_type", "transaction_id"]:
            if col not in leave_ledger.columns:
                add_issue(
                    issues,
                    module_name,
                    "WARNING",
                    "leave_ledger",
                    col,
                    "MISSING_OPTIONAL_COLUMN",
                    f"Leave ledger column '{col}' is missing; some evidence and traceability rules may have reduced coverage.",
                )

    # Assessability warnings
    if pay_events.empty:
        add_issue(
            issues,
            module_name,
            "WARNING",
            "pay_events",
            None,
            "DOMAIN_REDUCED_COVERAGE",
            "PAY governance checks are not assessable because pay_events is missing or empty.",
        )

    if terminations.empty:
        add_issue(
            issues,
            module_name,
            "WARNING",
            "terminations",
            None,
            "DOMAIN_REDUCED_COVERAGE",
            "Termination governance checks are not assessable because terminations is missing or empty.",
        )

    if leave_snapshot.empty and leave_ledger.empty:
        add_issue(
            issues,
            module_name,
            "WARNING",
            "leave",
            None,
            "DOMAIN_REDUCED_COVERAGE",
            "Leave governance checks are not assessable because both leave_snapshot and leave_ledger are missing or empty.",
        )

    return make_result(module_name, issues)


def main(client: str, pilot: str) -> int:
    processed_dir = get_processed_dir(client, pilot)
    output_dir = get_outputs_dir(client, pilot)

    rules_yaml_path = Path(__file__).resolve().parent / "config" / "rkeg_rules.yml"

    findings_path = output_dir / "rkeg_findings.csv"
    summary_path = output_dir / "rkeg_summary.csv"
    severity_summary_path = output_dir / "rkeg_summary_by_severity.csv"

    risk_dim_summary_path = output_dir / "rkeg_summary_by_risk_dimension.csv"
    risk_x_sev_path = output_dir / "rkeg_summary_risk_x_severity.csv"
    heatmap_path = output_dir / "rkeg_summary_risk_x_severity_pivot.csv"

    exec_md_path = output_dir / "rkeg_exec_risk_summary.md"
    layer_summary_path = output_dir / "rkeg_evidence_integrity_map.csv"
    rkeg_window_path = output_dir / "rkeg_data_window.csv"

    datasets = load_all_datasets(processed_dir)

    print("[RKEG] Using processed directory:", processed_dir)
    print("[RKEG] Loaded dataset keys:", list(datasets.keys()))
    for name, df in datasets.items():
        print(f"[RKEG] {name}: shape={df.shape}")

    employees = datasets.get("employee_master", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())

    employee_super = datasets.get("employee_super", pd.DataFrame())
    super_payments = datasets.get("super_payments", pd.DataFrame())
    rate_history = datasets.get("rate_history", pd.DataFrame())
    pay_overrides = datasets.get("pay_overrides", pd.DataFrame())

    for df in (
        employees,
        pay_events,
        leave_ledger,
        leave_snapshot,
        terminations,
        employee_super,
        super_payments,
        rate_history,
        pay_overrides,
    ):
        if not df.empty and "employee_id" in df.columns:
            df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    if not pay_events.empty:
        _require_cols(pay_events, REQUIRED_PAY, "pay_events.csv")
    if not leave_ledger.empty:
        _require_cols(leave_ledger, REQUIRED_LEDGER, "leave_ledger.csv")
    if not leave_snapshot.empty:
        _require_cols(leave_snapshot, REQUIRED_SNAP, "balances_snapshot.csv")
    if not terminations.empty:
        _require_cols(terminations, REQUIRED_TERM, "terminations.csv")

    # Module validation
    engine_datasets = dict(datasets)
    engine_datasets["employee_master"] = employees
    engine_datasets["pay_events"] = pay_events
    engine_datasets["leave_ledger"] = leave_ledger
    engine_datasets["leave_snapshot"] = leave_snapshot
    engine_datasets["terminations"] = terminations
    engine_datasets["employee_super"] = employee_super
    engine_datasets["super_payments"] = super_payments
    engine_datasets["rate_history"] = rate_history
    engine_datasets["pay_overrides"] = pay_overrides

    validation = validate_rkeg_inputs(engine_datasets)
    print_validation_result(validation)
    write_validation_outputs(validation, output_dir, "rkeg")

    if not validation.can_run:
        print("RKEG module blocked due to validation errors.")
        return 1

    # Data window
    rkeg_dates: list[date] = []
    rkeg_dates += _collect_dates_from_df(pay_events, ["pay_date", "period_start", "period_end"])
    rkeg_dates += _collect_dates_from_df(leave_ledger, ["as_of_date", "event_date"])
    rkeg_dates += _collect_dates_from_df(leave_snapshot, ["as_of_date"])
    rkeg_dates += _collect_dates_from_df(
        terminations,
        ["termination_date", "final_pay_date", "term_date", "pay_date"],
    )

    if rkeg_dates:
        write_data_window(rkeg_window_path, rkeg_dates)
        print(
            f"[RKEG] Wrote data window to {rkeg_window_path} "
            f"({min(rkeg_dates)} → {max(rkeg_dates)})"
        )
    else:
        print("[RKEG] No usable dates found for data window - rkeg_data_window.csv not written")

    # Run RKEG engine
    all_rules = _load_rules(rules_yaml_path)
    rules = [r for r in all_rules if int(r.get("tier", 1)) in {1, 2}]

    context: dict = {}

    findings: list[Finding] = []
    for rule in rules:
        findings.extend(run_rule(rule, engine_datasets, context=context))

    write_findings_csv(findings, findings_path)

    if findings:
        findings_df = pd.DataFrame([f.__dict__ for f in findings])
    else:
        findings_df = pd.DataFrame(columns=["rule_code", "severity", "classification"])

    if len(findings_df) == 0:
        summary_df = pd.DataFrame(columns=["rule_code", "severity", "finding_count"])
        severity_summary_df = pd.DataFrame(columns=["severity", "finding_count"])
    else:
        summary_df = (
            findings_df.groupby(["rule_code", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["severity", "finding_count"], ascending=[True, False])
        )

        severity_summary_df = (
            findings_df.groupby("severity", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

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

    classification_summary_path = output_dir / "rkeg_summary_by_classification.csv"
    classification_x_severity_path = output_dir / "rkeg_summary_classification_x_severity.csv"

    classification_summary_df.to_csv(classification_summary_path, index=False)
    classification_x_severity_df.to_csv(classification_x_severity_path, index=False)

    risk_dim_summary_df = pd.DataFrame(columns=["risk_dimension", "finding_count"])
    risk_x_sev_df = pd.DataFrame(columns=["risk_dimension", "severity", "finding_count"])
    pivot = pd.DataFrame(columns=["risk_dimension", "HIGH", "MEDIUM", "LOW", "TOTAL"])

    rule_to_risk: dict[str, list[str]] = {}
    if rules_yaml_path.exists():
        with rules_yaml_path.open("r", encoding="utf-8") as f:
            rules_doc = yaml.safe_load(f) or {}
        rules_list = rules_doc.get("rules", []) if isinstance(rules_doc, dict) else []

        for r in rules_list:
            rid = str(r.get("id", "")).strip()
            if not rid:
                continue

            dims = r.get("risk_dimension") or []
            if isinstance(dims, str):
                dims = [dims]
            if not isinstance(dims, list):
                dims = []

            rule_to_risk[rid] = [str(x).strip() for x in dims if str(x).strip()]

    if len(findings_df) > 0:
        findings_df["risk_dimension"] = (
            findings_df["rule_code"]
            .map(rule_to_risk)
            .apply(lambda x: x if isinstance(x, list) else ([] if x is None else [str(x)]))
        )

        exploded = findings_df.explode("risk_dimension")
        exploded = exploded[exploded["risk_dimension"].astype(str).str.len() > 0]

        if len(exploded) > 0:
            risk_dim_summary_df = (
                exploded.groupby("risk_dimension", as_index=False)
                .size()
                .rename(columns={"size": "finding_count"})
                .sort_values("finding_count", ascending=False)
            )

            risk_x_sev_df = (
                exploded.groupby(["risk_dimension", "severity"], as_index=False)
                .size()
                .rename(columns={"size": "finding_count"})
                .sort_values(["risk_dimension", "severity"])
            )

            pivot = (
                risk_x_sev_df.pivot(index="risk_dimension", columns="severity", values="finding_count")
                .fillna(0)
            )

            for col in ["HIGH", "MEDIUM", "LOW"]:
                if col not in pivot.columns:
                    pivot[col] = 0

            pivot = pivot[["HIGH", "MEDIUM", "LOW"]].astype(int)
            pivot["TOTAL"] = pivot.sum(axis=1)
            pivot = pivot.sort_values("TOTAL", ascending=False).reset_index()

    layer_df = pd.DataFrame(columns=["evidence_layer", "finding_count"])

    if len(findings_df) > 0:
        exploded = findings_df.explode("risk_dimension")
        exploded = exploded[exploded["risk_dimension"].notna()]
        exploded["evidence_layer"] = exploded["risk_dimension"].map(EVIDENCE_LAYER_MAP)

        layer_df = (
            exploded.groupby("evidence_layer", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

    layer_df.to_csv(layer_summary_path, index=False)

    if len(findings_df) == 0:
        exec_md = "# RKEG - Executive Risk Summary\n\nNo findings were generated.\n"
    else:
        total_findings = int(len(findings_df))
        risk_score, risk_rating = _risk_score_and_rating(findings_df)

        sev_counts = findings_df["severity"].astype(str).str.upper().value_counts().to_dict()
        sev_line = ", ".join([f"{k}={int(v)}" for k, v in sev_counts.items()])

        top_dims = (
            risk_dim_summary_df.head(3).to_dict(orient="records")
            if len(risk_dim_summary_df)
            else []
        )
        top_dimension = top_dims[0]["risk_dimension"] if top_dims else "unknown"
        top_lines = "\n".join(
            [f"- **{d['risk_dimension']}**: {int(d['finding_count'])} linked findings" for d in top_dims]
        ) or "- (no risk dimensions tagged)"

        top_rules = (
            summary_df.sort_values("finding_count", ascending=False)
            .head(5)
            .to_dict(orient="records")
            if len(summary_df)
            else []
        )

        rule_lines = "\n".join(
            [f"- `{r['rule_code']}` ({r['severity']}): {int(r['finding_count'])}" for r in top_rules]
        ) or "- (no rules)"

        rule_to_remediation: dict[str, str] = {}
        if rules_yaml_path.exists():
            with rules_yaml_path.open("r", encoding="utf-8") as f:
                rules_doc = yaml.safe_load(f) or {}
            for r in (rules_doc.get("rules", []) or []):
                rid = str(r.get("id", "")).strip()
                if not rid:
                    continue
                txt = r.get("text", {}) or {}
                rule_to_remediation[rid] = str(txt.get("remediation", "")).strip()

        action_lines = "\n".join(
            [
                f"- `{r['rule_code']}`: {rule_to_remediation.get(r['rule_code'], 'Review rule configuration')}"
                for r in top_rules
            ]
        ) or "- (no actions)"

        if len(layer_df) > 0:
            max_count = int(layer_df["finding_count"].max())
            max_bar_width = 24
            label_width = 22

            def _bar(count: int) -> str:
                filled = max(1, round((count / max_count) * max_bar_width))
                return "█" * filled

            layer_lines = "\n".join(
                [
                    f"- **{row['evidence_layer']:<{label_width}}** {_bar(int(row['finding_count']))} {int(row['finding_count'])}"
                    for _, row in layer_df.iterrows()
                ]
            )
        else:
            layer_lines = "- (no evidence layer findings)"

        exec_md = f"""# RKEG – Executive Risk Summary

## Overview
RKEG produced **{total_findings} findings** across the payroll evidence spine.

- **Risk rating:** **{risk_rating}**
- **Risk score:** **{risk_score}**
- **Severity distribution:** **{sev_line}**

## Payroll Evidence Integrity Map
{layer_lines}

## Top risk dimensions (by linked findings)
{top_lines}

## Interpretation
The dominant exposure is **{top_dimension}**, indicating gaps in the organisation's ability to reconstruct and substantiate payroll outcomes.

## Most frequently triggered rules
{rule_lines}

## Recommended actions
{action_lines}

## Notes
- Linked findings counts may exceed total findings because a single finding can map to multiple risk dimensions.
- This output is diagnostics-focused and does not constitute legal advice.
"""

    summary_df.to_csv(summary_path, index=False)
    severity_summary_df.to_csv(severity_summary_path, index=False)
    risk_dim_summary_df.to_csv(risk_dim_summary_path, index=False)
    risk_x_sev_df.to_csv(risk_x_sev_path, index=False)
    pivot.to_csv(heatmap_path, index=False)
    exec_md_path.write_text(exec_md, encoding="utf-8")

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {severity_summary_path}")
    print(f"Wrote: {classification_summary_path}")
    print(f"Wrote: {classification_x_severity_path}")
    print(f"Wrote: {risk_dim_summary_path}")
    print(f"Wrote: {risk_x_sev_path}")
    print(f"Wrote: {heatmap_path}")
    print(f"Wrote: {layer_summary_path}")
    print(f"Wrote: {exec_md_path}")

    return 0