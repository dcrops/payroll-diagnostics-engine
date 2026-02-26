# src/rkeg/detectors/super_.py
from __future__ import annotations

from typing import Iterable, Dict, Optional

import pandas as pd

from rkeg.rules import Finding
from uuid import uuid4


# You can tweak these if you like
ABS_TOLERANCE = 5.00      # $ difference threshold
REL_TOLERANCE = 0.05      # 5% difference threshold


def _pick_super_column(pay_events: pd.DataFrame) -> Optional[str]:
    """
    Try to identify the superannuation amount column in pay_events.
    This is heuristic but keeps things flexible across clients.
    """
    if pay_events is None or pay_events.empty:
        return None

    candidates = [
        "super_amount",
        "super",
        "superannuation",
        "sg_amount",
        "super_guarantee",
    ]

    lower_cols = {c.lower(): c for c in pay_events.columns}

    for logical in candidates:
        if logical in lower_cols:
            return lower_cols[logical]

    # Fallback: any column that contains 'super' in its name
    for c in pay_events.columns:
        if "super" in c.lower():
            return c

    return None


def _pick_date_column(df: pd.DataFrame, preferred: list[str]) -> Optional[str]:
    """
    Pick a date-like column from the dataframe, preferring the given names.
    """
    if df is None or df.empty:
        return None

    lower_cols = {c.lower(): c for c in df.columns}

    for name in preferred:
        key = name.lower()
        if key in lower_cols:
            return lower_cols[key]

    # Fallback: any column with 'date' in the name
    for c in df.columns:
        if "date" in c.lower():
            return c

    return None


def _coerce_month_series(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Convert a date column to a 'YYYY-MM' month bucket string.
    Invalid dates are coerced to NaT and then dropped by groupby later.
    """
    dt = pd.to_datetime(df[col], errors="coerce")
    return dt.dt.to_period("M").astype(str)


def run_rule(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[RkegFinding]:
    """
    SUP domain rules.

    Currently implements:

    - RKEG-SUP-002: Superannuation accrued does not reconcile
      to superannuation paid (within tolerance) at an
      employee + month level.
    """
    rule_id = rule["id"]
    severity = rule.get("severity", "MEDIUM")

    if rule_id != "RKEG-SUP-002":
        # For now we only implement this rule; others can be added later.
        return []

    print("[SUP-002] Running RKEG-SUP-002 detector") 

    pay_events = datasets.get("pay_events")
    super_payments = datasets.get("super_payments")

    print(
    f"[SUP-002] pay_events shape={None if pay_events is None else pay_events.shape}, "
    f"super_payments shape={None if super_payments is None else super_payments.shape}"
)

    # If we don't have both datasets, we can't perform this check.
    if pay_events is None or pay_events.empty or super_payments is None or super_payments.empty:
        return []

    # Identify super column in pay_events
    super_col = _pick_super_column(pay_events)
    if super_col is None:
        # No usable super column; silently skip – a separate visibility rule could flag this.
        return []

    # Identify date columns
    pay_date_col = _pick_date_column(pay_events, ["pay_date", "period_end", "period_start"])
    sup_period_end_col = _pick_date_column(super_payments, ["period_end_date", "period_end"])
    print(f"[SUP-002] pay_date_col={pay_date_col}, sup_period_end_col={sup_period_end_col}")
    pay_emp_col = "employee_id" if "employee_id" in pay_events.columns else None
    sup_emp_col = "employee_id" if "employee_id" in super_payments.columns else None
    if pay_date_col is None or sup_period_end_col is None or pay_emp_col is None or sup_emp_col is None:
        print("[SUP-002] Bailing: missing employee/date columns")
        return []

    # Build month buckets
    pay_events = pay_events.copy()
    super_payments = super_payments.copy()

    pay_events["__month"] = _coerce_month_series(pay_events, pay_date_col)
    super_payments["__month"] = _coerce_month_series(super_payments, sup_period_end_col)

    # Drop rows where month is NaT-derived "NaT" / "NaN"
    pay_events = pay_events[pay_events["__month"].notna()]
    super_payments = super_payments[super_payments["__month"].notna()]

    if pay_events.empty or super_payments.empty:
        return []

    # Aggregate accrued vs paid super at employee + month
    accrued = (
        pay_events
        .groupby([pay_emp_col, "__month"], as_index=False)[super_col]
        .sum()
        .rename(columns={super_col: "accrued_super"})
    )

    if "super_amount" in super_payments.columns:
        sup_amount_col = "super_amount"
    else:
        # Fallback: any 'super' column in super_payments
        sup_amount_col = _pick_super_column(super_payments)
        if sup_amount_col is None:
            return []

    paid = (
        super_payments
        .groupby([sup_emp_col, "__month"], as_index=False)[sup_amount_col]
        .sum()
        .rename(columns={sup_emp_col: pay_emp_col, sup_amount_col: "paid_super"})
    )

    # Outer join to capture both sides (accrued with no paid, paid with no accrued)
    recon = pd.merge(
        accrued,
        paid,
        on=[pay_emp_col, "__month"],
        how="outer",
    )

    # Fill NaNs with zero for comparison
    recon["accrued_super"] = recon["accrued_super"].fillna(0.0)
    recon["paid_super"] = recon["paid_super"].fillna(0.0)

    if recon.empty:
        # Nothing to compare
        return []

    # Compute differences
    recon["abs_diff"] = (recon["accrued_super"] - recon["paid_super"]).abs()

    def _rel_diff(row) -> float:
        accrued_val = row["accrued_super"]
        if accrued_val <= 0:
            return 0.0
        return row["abs_diff"] / accrued_val

    recon["rel_diff"] = recon.apply(_rel_diff, axis=1)

    # Flag rows where difference exceeds tolerance
    mask = (recon["abs_diff"] > ABS_TOLERANCE) & (recon["rel_diff"] > REL_TOLERANCE)
    flagged = recon[mask]

    findings: list[RkegFinding] = []

    # Text template from YAML (if present)
    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Superannuation payments do not reconcile to superannuation accrued in payroll within the defined tolerance.",
    )

    for _, row in flagged.iterrows():
        employee_id = str(row[pay_emp_col]) if pd.notna(row[pay_emp_col]) else ""
        month = row["__month"]
        accrued_super = float(row["accrued_super"])
        paid_super = float(row["paid_super"])
        abs_diff = float(row["abs_diff"])
        rel_diff_pct = float(row["rel_diff"] * 100.0)

        # Human-readable message
        message = (
            f"{base_finding_text} "
            f"Employee {employee_id}, period {month}: "
            f"accrued super {accrued_super:,.2f}, "
            f"paid super {paid_super:,.2f}, "
            f"difference {abs_diff:,.2f} ({rel_diff_pct:.1f}%)."
        )

        # Evidence string for CSV / audit trail
        evidence_str = (
            f"employee_id={employee_id}, period_month={month}, "
            f"accrued_super={accrued_super:.2f}, "
            f"paid_super={paid_super:.2f}, "
            f"abs_diff={abs_diff:.2f}, "
            f"rel_diff_pct={rel_diff_pct:.1f}%"
        )

        findings.append(
            Finding(
                employee_id=employee_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=severity,
                message=message,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=text_block.get(
                    "remediation",
                    "Reconcile payroll superannuation accruals to clearing house or bank payments.",
                ),
            )
        )

    return findings