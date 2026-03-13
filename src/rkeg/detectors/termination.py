from __future__ import annotations

from typing import Dict, List
from uuid import uuid4
import json

import pandas as pd

from rkeg.models import Finding


DEFAULT_FINAL_PAY_DAYS_THRESHOLD = 7


def _pick_first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in cols:
            return cols[candidate.lower()]
    return None


def _term_001_final_pay_outside_threshold(
    rule: dict,
    datasets: Dict[str, pd.DataFrame],
) -> List[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())

    if terminations.empty or pay_events.empty:
        return []

    if "employee_id" not in terminations.columns or "employee_id" not in pay_events.columns:
        return []

    term_date_col = _pick_first_existing_column(
        terminations,
        ["termination_date", "term_date", "end_date", "termination_effective_date"],
    )
    pay_date_col = _pick_first_existing_column(
        pay_events,
        ["pay_date", "payment_date", "event_date"],
    )

    if term_date_col is None or pay_date_col is None:
        return []

    term = terminations.copy()
    pay = pay_events.copy()

    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()

    term["_termination_date"] = pd.to_datetime(term[term_date_col], errors="coerce")
    pay["_pay_date"] = pd.to_datetime(pay[pay_date_col], errors="coerce")

    term = term[term["_termination_date"].notna()].copy()
    pay = pay[pay["_pay_date"].notna()].copy()

    if term.empty or pay.empty:
        return []

    merged = term.merge(
        pay[["employee_id", "_pay_date"]],
        on="employee_id",
        how="left",
    )

    candidates = merged[merged["_pay_date"] >= merged["_termination_date"]].copy()

    if candidates.empty:
        return []

    final_pay = (
        candidates.groupby(["employee_id", "_termination_date"], as_index=False)["_pay_date"]
        .max()
        .rename(columns={"_pay_date": "_final_pay_date"})
    )

    review = term.merge(
        final_pay,
        on=["employee_id", "_termination_date"],
        how="left",
    )

    review = review[review["_final_pay_date"].notna()].copy()
    if review.empty:
        return []

    review["_days_diff"] = (review["_final_pay_date"] - review["_termination_date"]).dt.days

    cfg = rule.get("config", {}) or {}
    threshold = int(cfg.get("max_days_after_termination", DEFAULT_FINAL_PAY_DAYS_THRESHOLD))

    flagged = review[review["_days_diff"] > threshold].copy()
    if flagged.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "One or more terminated employees appear to have received final pay outside the configured statutory timeframe.",
    )
    remediation = text.get(
        "remediation",
        "Review termination processing workflows and ensure final pay is calculated and processed within the required statutory timeframe.",
    )
    severity = rule.get("severity", "HIGH")

    findings: List[Finding] = []

    for _, row in flagged.iterrows():
        emp_id = str(row["employee_id"]).strip()
        term_date = row["_termination_date"]
        final_pay_date = row["_final_pay_date"]
        days_diff = int(row["_days_diff"])

        evidence_obj = {
            "sources": ["terminations.csv", "pay_events.csv"],
            "primary_keys": {
                "employee_id": emp_id,
                "termination_date": str(term_date.date()) if pd.notna(term_date) else None,
            },
            "values": {
                "termination_date": str(term_date.date()) if pd.notna(term_date) else None,
                "derived_final_pay_date": str(final_pay_date.date()) if pd.notna(final_pay_date) else None,
                "days_after_termination": days_diff,
            },
            "thresholds": {
                "max_days_after_termination": threshold,
            },
            "explanation": "Latest pay event on or after termination date exceeds the configured final pay timing threshold.",
        }

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=str(term_date.date()) if pd.notna(term_date) else None,
                rule_code=rule["id"],
                severity=severity,
                message=base_msg,
                diff_units=float(days_diff),
                evidence=json.dumps(evidence_obj, ensure_ascii=False),
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings


def run_rule(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    rule_id = rule.get("id")

    if rule_id == "RKEG-TERM-001":
        return _term_001_final_pay_outside_threshold(rule, datasets)

    return []