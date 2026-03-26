from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml
import argparse


from rkeg.models import Finding, write_findings_csv
from rkeg.detectors.registry import run_rule
from common.data_window import write_data_window
from rkeg.datasets import load_all_datasets

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
REQUIRED_PAY = {"employee_id"}          # we'll tighten this later
REQUIRED_LEDGER = {"employee_id"}       # for leave evidence
REQUIRED_SNAP = {"employee_id"}         # for leave snapshot
REQUIRED_TERM = {"employee_id"}         # for term records


def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")

def _load_rules(rules_path: Path) -> list[dict]:
    with rules_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("rules", [])


def _collect_dates_from_df(df: pd.DataFrame, candidate_cols: Iterable[str]) -> list[date]:
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

            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    d = datetime.strptime(s, fmt).date()
                    dates.append(d)
                    break
                except ValueError:
                    continue

    return dates


def _risk_score_and_rating(findings_df: pd.DataFrame) -> tuple[int, str]:
    """
    Deterministic exec risk score (0–100) based on:
    - severity counts
    - breadth of risk dimensions impacted
    - repeat frequency (many findings)
    """
    if findings_df is None or len(findings_df) == 0:
        return 0, "LOW"

    sev_counts = findings_df["severity"].astype(str).str.upper().value_counts().to_dict()
    high = int(sev_counts.get("HIGH", 0))
    medium = int(sev_counts.get("MEDIUM", 0))
    low = int(sev_counts.get("LOW", 0))

    # 1) Severity score (dominant factor)
    severity_points = (high * 10) + (medium * 4) + (low * 1)
    severity_score = min(60, severity_points)

    # 2) Breadth score (how many risk dimensions are actually hit)
    dims: set[str] = set()
    for x in findings_df.get("risk_dimension", []):
        if isinstance(x, list):
            dims.update([str(d).strip() for d in x if str(d).strip()])
        elif isinstance(x, str) and x.strip():
            dims.add(x.strip())

    breadth_score = min(25, len(dims) * 4)

    # 3) Frequency score
    freq_score = min(15, int(len(findings_df) * 1.5))

    score = int(min(100, severity_score + breadth_score + freq_score))

    if score >= 70:
        rating = "HIGH"
    elif score >= 35:
        rating = "MEDIUM"
    else:
        rating = "LOW"

    return score, rating


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(description="Run RKEG module")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to input data directory",
    )

    args = parser.parse_args()

    data_dir = (
        Path(args.data_dir).resolve()
        if args.data_dir
        else repo_root / "data" / "sample"
    )
    out_dir = repo_root / "outputs"
    modules_dir = out_dir / "modules"
    rules_yaml_path = repo_root / "src" / "rkeg" / "config" / "rkeg_rules.yml"

    out_dir.mkdir(parents=True, exist_ok=True)
    modules_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------
    # Output paths
    # ----------------------------
    findings_path = modules_dir / "rkeg_findings.csv"
    summary_path = modules_dir / "rkeg_summary.csv"
    severity_summary_path = modules_dir / "rkeg_summary_by_severity.csv"

    risk_dim_summary_path = modules_dir / "rkeg_summary_by_risk_dimension.csv"
    risk_x_sev_path = modules_dir / "rkeg_summary_risk_x_severity.csv"
    heatmap_path = modules_dir / "rkeg_summary_risk_x_severity_pivot.csv"

    exec_md_path = modules_dir / "rkeg_exec_risk_summary.md"

    # ----------------------------
    # Load datasets
    # ----------------------------
    datasets = load_all_datasets(data_dir)

    print("[RKEG] Using data directory:", data_dir)
    print("[RKEG] Loaded dataset keys:", list(datasets.keys()))
    for name, df in datasets.items():
        print(f"[RKEG] {name}: shape={df.shape}")

    # Pull out key datasets for convenience / validation
    employees = datasets.get("employee_master", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())

    # Optional Tier 2 / extended datasets
    employee_super = datasets.get("employee_super", pd.DataFrame())
    super_payments = datasets.get("super_payments", pd.DataFrame())
    rate_history = datasets.get("rate_history", pd.DataFrame())
    pay_overrides = datasets.get("pay_overrides", pd.DataFrame())

    # Normalise employee_id across all employee-level datasets
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

    # Minimal column checks
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
    # Data window
    # ----------------------------
    rkeg_dates: list[date] = []
    rkeg_dates += _collect_dates_from_df(pay_events, ["pay_date", "period_start", "period_end"])
    rkeg_dates += _collect_dates_from_df(leave_ledger, ["as_of_date", "event_date"])
    rkeg_dates += _collect_dates_from_df(leave_snapshot, ["as_of_date"])
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
        print("[RKEG] No usable dates found for data window - rkeg_data_window.csv not written")

    # ----------------------------
    # Run RKEG engine
    # ----------------------------
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

    all_rules = _load_rules(rules_yaml_path)
    rules = [r for r in all_rules if int(r.get("tier", 1)) in {1, 2}]

    context: dict = {}

    findings: list[Finding] = []
    for rule in rules:
        findings.extend(run_rule(rule, engine_datasets, context=context))

    # Write findings CSV (always)
    write_findings_csv(findings, findings_path)

    # Build findings df (always defined)
    if findings:
        findings_df = pd.DataFrame([f.__dict__ for f in findings])
    else:
        findings_df = pd.DataFrame(columns=["rule_code", "severity"])

    # ----------------------------
    # Summary df (always defined)
    # ----------------------------
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
    # Risk dimension summaries (ALWAYS define outputs)
    # ----------------------------
    risk_dim_summary_df = pd.DataFrame(columns=["risk_dimension", "finding_count"])
    risk_x_sev_df = pd.DataFrame(columns=["risk_dimension", "severity", "finding_count"])
    pivot = pd.DataFrame(columns=["risk_dimension", "HIGH", "MEDIUM", "LOW", "TOTAL"])

    # Build rule_id -> [risk_dimension...] map from YAML
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


        # ----------------------------
    # Payroll Evidence Integrity Map
    # ----------------------------
    layer_summary_path = modules_dir / "rkeg_evidence_integrity_map.csv"

    layer_df = pd.DataFrame(columns=["layer", "finding_count"])

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

    print(f"Wrote: {layer_summary_path}")
    # ----------------------------
    # Exec narrative (ALWAYS define exec_md)
    # ----------------------------
    if len(findings_df) == 0:
        exec_md = "# RKEG - Executive Risk Summary\n\nNo findings were generated.\n"
    else:
        total_findings = int(len(findings_df))
        risk_score, risk_rating = _risk_score_and_rating(findings_df)

        sev_counts = findings_df["severity"].astype(str).str.upper().value_counts().to_dict()
        sev_line = ", ".join([f"{k}={int(v)}" for k, v in sev_counts.items()])

        top_dims = risk_dim_summary_df.head(3).to_dict(orient="records") if len(risk_dim_summary_df) else []
        top_dimension = top_dims[0]["risk_dimension"] if top_dims else "unknown"
        top_lines = "\n".join([f"- **{d['risk_dimension']}**: {int(d['finding_count'])} linked findings" for d in top_dims]) or "- (no risk dimensions tagged)"

        top_rules = (
            summary_df.sort_values("finding_count", ascending=False)
            .head(5)
            .to_dict(orient="records")
            if len(summary_df) else []
        )

        rule_lines = "\n".join([f"- `{r['rule_code']}` ({r['severity']}): {int(r['finding_count'])}" for r in top_rules]) or "- (no rules)"

        # remediation mapping from YAML
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

        layer_lines = ""

        if len(layer_df) > 0:
            max_count = int(layer_df["finding_count"].max())
            max_bar_width = 24
            label_width = 22   # <- controls alignment

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

    # ----------------------------
    # Write outputs (single place)
    # ----------------------------
    summary_df.to_csv(summary_path, index=False)
    severity_summary_df.to_csv(severity_summary_path, index=False)

    risk_dim_summary_df.to_csv(risk_dim_summary_path, index=False)
    risk_x_sev_df.to_csv(risk_x_sev_path, index=False)
    pivot.to_csv(heatmap_path, index=False)

    exec_md_path.write_text(exec_md, encoding="utf-8")

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {severity_summary_path}")
    print(f"Wrote: {risk_dim_summary_path}")
    print(f"Wrote: {risk_x_sev_path}")
    print(f"Wrote: {heatmap_path}")
    print(f"Wrote: {exec_md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())