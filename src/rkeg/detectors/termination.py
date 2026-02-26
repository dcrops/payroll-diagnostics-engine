# src/rkeg/detectors/termination.py
from __future__ import annotations

from typing import Iterable, Dict, Optional

from datetime import datetime

import pandas as pd

from rkeg.schemas import RkegFinding


# You can tune this to whatever statutory / policy threshold you want
DEFAULT_FINAL_PAY_DAYS_THRESHOLD = 7  # e.g. 7 calendar days after termination


def _parse_date(series: pd.Series) -> pd.Series:
    """
    Coerce a string-like series to datetime.date, ignoring unparseable values.
    """
    return pd.to_datetime(series, errors="coerce").dt.date


def _term_001_final_pay_outside_threshold(
    rule: dict,
    datasets: Dict[str, pd.DataFrame],
) -> Iterable[RkegFinding]:
    """
    RKEG-TERM-001:
    Final pay processed outside termination timing threshold.

    Uses the 'terminations' dataset and looks for rows where the difference
    between termination_date and final_pay_date exceeds the configured
    threshold in days.
    """
    terminations = datasets.get("terminations")
    if terminations is None or terminations.empty:
        return []

    # Make a copy so we don't mutate upstream data
    df = terminations.copy()

    # Try to locate date columns
    term_date_col: Optional[str] = None
    final_pay_date_col: Optional[str] = None

    lower_cols = {c.lower(): c for c in df.columns}

    for candidate in ["termination_date", "term_date", "end_date"]:
        if candidate in lower_cols:
            term_date_col = lower_cols[candidate]
            break

    for candidate in ["final_pay_date", "pay_date", "last_pay_date"]:
        if candidate in lower_cols:
            final_pay_date_col = lower_cols[candidate]
            break

    if term_date_col is None or final_pay_date_col is None:
        # Not enough structure to perform this check; fail quietly.
        return []

    df["__term_date"] = _parse_date(df[term_date_col])
    df["__final_pay_date"] = _parse_date(df[final_pay_date_col])

    # Drop rows where either date is missing or invalid
    df = df[df["__term_date"].notna() & df["__final_pay_date"].notna()]
    if df.empty:
        return []

    # Compute difference in days: final_pay_date - term_date
    df["__days_diff"] = (
        pd.to_datetime(df["__final_pay_date"]) - pd.to_datetime(df["__term_date"])
    ).dt.days

    # Threshold – from rule config if present, otherwise default
    cfg = rule.get("config", {})
    threshold = int(cfg.get("max_days_after_termination", DEFAULT_FINAL_PAY_DAYS_THRESHOLD))

    flagged = df[df["__days_diff"] > threshold]
    if flagged.empty:
        return []

    rule_id = rule["id"]
    severity = rule.get("severity", "HIGH")

    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Final pay appears to have been processed outside the configured timing threshold.",
    )

    findings: list[RkegFinding] = []

    emp_col = "employee_id" if "employee_id" in flagged.columns else None

    for _, row in flagged.iterrows():
        employee_id = str(row[emp_col]) if emp_col and pd.notna(row[emp_col]) else ""
        term_date = row["__term_date"]
        final_pay_date = row["__final_pay_date"]
        days_diff = int(row["__days_diff"])

        detail = (
            f"{base_finding_text} Employee {employee_id or '[unknown]'}: "
            f"termination date {term_date}, final pay date {final_pay_date}, "
            f"gap {days_diff} days (threshold {threshold} days)."
        )

        findings.append(
            RkegFinding(
                rule_code=rule_id,
                severity=severity,
                employee_id=employee_id,
                detail=detail,
            )
        )

    return findings


def run_rule(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[RkegFinding]:
    """
    Entry point for TERM-domain RKEG rules.
    """
    rule_id = rule["id"]

    if rule_id == "RKEG-TERM-001":
        return _term_001_final_pay_outside_threshold(rule, datasets)

    # Safety net: keep this so typos / future rules are caught quickly.
    raise ValueError(f"Unknown TERM rule: {rule_id}")