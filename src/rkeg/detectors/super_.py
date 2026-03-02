# src/rkeg/detectors/super_.py
from __future__ import annotations

from typing import Iterable, Dict, Optional, List

from uuid import uuid4

import pandas as pd

from rkeg.rules import Finding

# You can tweak these if you like
ABS_TOLERANCE = 5.00      # $ difference threshold for SUP-002
REL_TOLERANCE = 0.05      # 5% difference threshold for SUP-002


def _pick_super_column(pay_events: pd.DataFrame) -> Optional[str]:
    """
    Try to identify the superannuation amount column in a dataframe.
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


def _pick_date_column(df: pd.DataFrame, preferred: List[str]) -> Optional[str]:
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


def _run_sup_002(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-SUP-002
    Superannuation accrued does not reconcile to superannuation paid
    (within tolerance) at an employee + month level.
    """
    print("[SUP-002] Running RKEG-SUP-002 detector")

    pay_events = datasets.get("pay_events")
    super_payments = datasets.get("super_payments")

    print(
        f"[SUP-002] pay_events shape={None if pay_events is None else pay_events.shape}, "
        f"super_payments shape={None if super_payments is None else super_payments.shape}"
    )

    # If we don't have both datasets, we can't perform this check.
    if (
        pay_events is None
        or pay_events.empty
        or super_payments is None
        or super_payments.empty
    ):
        return []

    # Identify super column in pay_events
    super_col = _pick_super_column(pay_events)
    if super_col is None:
        # No usable super column; silently skip – a separate visibility rule could flag this.
        print("[SUP-002] No super column found in pay_events; skipping.")
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
            print("[SUP-002] No super column found in super_payments; skipping.")
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

    if flagged.empty:
        return []

    findings: List[Finding] = []

    # Text template from YAML (if present)
    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Superannuation payments do not reconcile to superannuation accrued in payroll within the defined tolerance.",
    )
    remediation_text = text_block.get(
        "remediation",
        "Reconcile superannuation accruals in payroll to clearing house or bank payments.",
    )
    severity = rule.get("severity", "MEDIUM")

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
                next_action=remediation_text,
            )
        )

    return findings


def _run_sup_003(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-SUP-003
    Superannuation contributions paid after a configured due date.

    Logic:
    - Use super_payments dataset.
    - Identify period end column and payment date column.
    - Compute due_date = period_end + days_after_period_end (from config, default 30).
    - Flag rows where payment_date > due_date.
    """
    print("[SUP-003] Running RKEG-SUP-003 detector")

    super_payments = datasets.get("super_payments")

    print(
        f"[SUP-003] super_payments shape={None if super_payments is None else super_payments.shape}"
    )

    if super_payments is None or super_payments.empty:
        # Could also be flagged by a separate "missing dataset" rule if you want.
        return []

    df = super_payments.copy()

    # Identify columns
    period_end_col = _pick_date_column(df, ["period_end_date", "period_end", "accrual_period_end"])
    payment_date_col = _pick_date_column(df, ["payment_date", "paid_date", "transaction_date"])

    if period_end_col is None or payment_date_col is None:
        print(
            f"[SUP-003] Missing period_end/payment_date columns; "
            f"period_end_col={period_end_col}, payment_date_col={payment_date_col}"
        )
        return []

    emp_col = "employee_id" if "employee_id" in df.columns else None

    # Convert to datetime
    period_end_dt = pd.to_datetime(df[period_end_col], errors="coerce")
    payment_dt = pd.to_datetime(df[payment_date_col], errors="coerce")

    # Drop rows where either date can't be parsed
    mask_valid = period_end_dt.notna() & payment_dt.notna()
    df = df[mask_valid].copy()
    period_end_dt = period_end_dt[mask_valid]
    payment_dt = payment_dt[mask_valid]

    if df.empty:
        return []

    # Config: how many days after period end before we call it "late"
    config = rule.get("config", {}) or {}
    days_after_period_end = int(config.get("days_after_period_end", 30))

    due_date = period_end_dt + pd.to_timedelta(days_after_period_end, unit="D")

    # Calculate days late
    days_late = (payment_dt - due_date).dt.days
    df["__days_late"] = days_late

    # Flag only genuinely late payments (days_late > 0)
    flagged = df[df["__days_late"] > 0].copy()

    if flagged.empty:
        return []

    findings: List[Finding] = []

    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Superannuation payments were identified with payment dates after the configured due date for the relevant contribution period.",
    )
    remediation_text = text_block.get(
        "remediation",
        "Review superannuation payment scheduling and ensure contributions are processed and cleared before statutory due dates.",
    )
    severity = rule.get("severity", "HIGH")

    for idx, row in flagged.iterrows():
        employee_id = str(row[emp_col]) if emp_col and pd.notna(row[emp_col]) else ""
        period_end_val = pd.to_datetime(row[period_end_col], errors="coerce")
        payment_val = pd.to_datetime(row[payment_date_col], errors="coerce")
        days_late_val = int(row["__days_late"])

        period_end_str = period_end_val.date().isoformat() if pd.notna(period_end_val) else ""
        payment_str = payment_val.date().isoformat() if pd.notna(payment_val) else ""

        message = (
            f"{base_finding_text} "
            f"Employee {employee_id or '[not supplied]'}, "
            f"period end {period_end_str}, payment date {payment_str} "
            f"was {days_late_val} days after the configured due date "
            f"(period end + {days_after_period_end} days)."
        )

        evidence_str = (
            f"employee_id={employee_id}, "
            f"period_end_date={period_end_str}, "
            f"payment_date={payment_str}, "
            f"days_after_period_end={days_after_period_end}, "
            f"days_late={days_late_val}"
        )

        findings.append(
            Finding(
                employee_id=employee_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=severity,
                message=message,
                diff_units="days_late",
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation_text,
            )
        )

    return findings


def run_rule(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[Finding]:
    """
    Entry point for SUP domain rules.

    Currently implements:
    - RKEG-SUP-002: accrued vs paid reconciliation (employee + month)
    - RKEG-SUP-003: late contributions vs period end + grace days
    """
    rule_id = rule["id"]

    if rule_id == "RKEG-SUP-002":
        return _run_sup_002(rule, datasets)
    elif rule_id == "RKEG-SUP-003":
        return _run_sup_003(rule, datasets)

    # Other SUP rules can be added here later
    return []