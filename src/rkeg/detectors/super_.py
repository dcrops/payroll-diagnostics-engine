# src/rkeg/detectors/super_.py
from __future__ import annotations

from typing import Iterable, Dict, Optional, List

from uuid import uuid4

import pandas as pd

from rkeg.models import Finding
from common.nulls import is_missing

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

def _pick_earnings_column(pay_events: pd.DataFrame) -> Optional[str]:
    """
    Try to identify the 'superable earnings' column in pay_events.

    Prefer OTE/base earnings style columns, but fall back to gross_amount
    or any earnings-like column if needed.
    """
    if pay_events is None or pay_events.empty:
        return None

    candidates = [
        "ote_amount",
        "ordinary_earnings",
        "ote",
        "base_earnings",
        "superable_earnings",
        "gross_amount",   # common fallback
    ]

    lower_cols = {c.lower(): c for c in pay_events.columns}

    for logical in candidates:
        if logical in lower_cols:
            return lower_cols[logical]

    # Fallback: anything that smells like earnings
    for c in pay_events.columns:
        name = c.lower()
        if "gross" in name or "earn" in name or "wages" in name:
            return c

    return None


def _coerce_month_series(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Convert a date column to a 'YYYY-MM' month bucket string.
    Invalid dates are coerced to NaT and then dropped by groupby later.
    """
    dt = pd.to_datetime(df[col], errors="coerce")
    return dt.dt.to_period("M").astype(str)

def _run_sup_001(
    rule: dict,
    datasets: Dict[str, pd.DataFrame],
) -> Iterable[Finding]:
    """
    RKEG-SUP-001:
    Superannuation rate outside expected tolerance band.

    For each pay_events row, compare super amount vs earnings.
    Flag rows where the effective super rate is outside
    target_rate ± tolerance from the YAML config.
    """
    pay_events = datasets.get("pay_events")
    if pay_events is None or pay_events.empty:
        return []

    super_col = _pick_super_column(pay_events)
    earnings_col = _pick_earnings_column(pay_events)

    # Can't run the rule without both pieces
    if super_col is None or earnings_col is None:
        return []

    cfg = rule.get("config", {})
    target_rate = float(cfg.get("target_rate", 0.11))   # default 11%
    tolerance = float(cfg.get("tolerance", 0.01))       # default ±1%

    min_rate = max(0.0, target_rate - tolerance)
    max_rate = target_rate + tolerance

    df = pay_events.copy()

    # Coerce to numeric
    df[super_col] = pd.to_numeric(df[super_col], errors="coerce")
    df[earnings_col] = pd.to_numeric(df[earnings_col], errors="coerce")

    # Only rows with positive earnings and non-null super
    mask_valid = (df[earnings_col] > 0) & df[super_col].notna()
    df = df[mask_valid]

    if df.empty:
        return []

    # Effective rate = super / earnings
    df["__sup_rate"] = df[super_col] / df[earnings_col]

    # Flag rows outside band (ignore zero super – that's a different rule)
    mask_outside = (
        (df[super_col] > 0)
        & ((df["__sup_rate"] < min_rate) | (df["__sup_rate"] > max_rate))
    )
    flagged = df[mask_outside]

    print(
        f"[SUP-001] candidate rows={len(df)}, "
        f"flagged_out_of_band={len(flagged)}"
    )

    if flagged.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "Superannuation amounts were identified that fall outside the expected tolerance range.",
    )
    remediation = text.get(
        "remediation",
        "Validate super configuration and ensure the correct super rate is applied to earnings.",
    )
    severity = rule.get("severity", "HIGH")

    # Optional: pick a date for evidence
    pay_date_col = _pick_date_column(flagged, ["pay_date", "period_end", "period_start"])
    employee_col = "employee_id" if "employee_id" in flagged.columns else None

    findings: list[Finding] = []

    for _, row in flagged.iterrows():
        emp_id = (
            str(row[employee_col])
            if employee_col and pd.notna(row[employee_col])
            else None
        )
        pay_date = (
            str(row[pay_date_col])
            if pay_date_col and pd.notna(row[pay_date_col])
            else None
        )

        earnings = float(row[earnings_col])
        sup_amt = float(row[super_col])
        rate = float(row["__sup_rate"])

        evidence_str = (
            f"employee_id={emp_id}, pay_date={pay_date}, "
            f"earnings={earnings:.2f}, super_amount={sup_amt:.2f}, "
            f"effective_rate={rate:.4f}, "
            f"expected_band={min_rate:.4f}-{max_rate:.4f}"
        )

        message = (
            f"{base_msg} Effective super rate {rate:.2%} on "
            f"earnings {earnings:.2f} with super {sup_amt:.2f} "
            f"(expected between {min_rate:.2%} and {max_rate:.2%})."
        )

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=pay_date,
                rule_code=rule["id"],
                severity=severity,
                message=message,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

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

def _run_sup_004(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-SUP-004
    Employees without a recorded default superannuation fund.
    """
    print("[SUP-004] Running RKEG-SUP-004 detector")

    employee_master = datasets.get("employee_master")
    employee_super = datasets.get("employee_super")

    if (
        employee_master is None
        or employee_master.empty
        or employee_super is None
        or employee_super.empty
    ):
        print("[SUP-004] Missing employee_master or employee_super; skipping")
        return []

    df_master = employee_master.copy()
    df_super = employee_super.copy()

    if "employee_id" not in df_master.columns or "employee_id" not in df_super.columns:
        print("[SUP-004] employee_id column missing; skipping")
        return []

    # Normalise IDs
    df_master["employee_id"] = df_master["employee_id"].astype(str).str.strip()
    df_super["employee_id"] = df_super["employee_id"].astype(str).str.strip()

    # Find a 'fund'-like column
    fund_col = None
    for c in df_super.columns:
        if "fund" in c.lower():
            fund_col = c
            break

    if fund_col is None:
        print("[SUP-004] No fund column found in employee_super; skipping")
        return []

    # Left join so employees with no employee_super row show up with NaN fund
    merged = df_master.merge(
        df_super[["employee_id", fund_col]],
        on="employee_id",
        how="left",
    )

    # Missing or blank fund
    flagged = merged[merged[fund_col].map(is_missing)].copy()

    print(
        f"[SUP-004] candidate employees={len(merged)}, "
        f"flagged_missing_fund={len(flagged)}"
    )

    if flagged.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "Employees were identified without a recorded default superannuation fund in the data provided.",
    )
    remediation = text.get(
        "remediation",
        "Ensure all employees have a recorded default superannuation fund and align payroll configuration and onboarding processes.",
    )
    severity = rule.get("severity", "MEDIUM")

    findings: List[Finding] = []

    for _, row in flagged.iterrows():
        emp_id = str(row["employee_id"])

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=severity,
                message=base_msg,
                diff_units=None,
                evidence=f"employee_id={emp_id}, fund_missing_or_blank=True",
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

def _run_sup_005(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-SUP-005
    Super payment record missing payment date.
    """
    print("[SUP-005] Running RKEG-SUP-005 detector")

    super_payments = datasets.get("super_payments")

    if super_payments is None or super_payments.empty:
        return []

    df = super_payments.copy()

    payment_date_col = _pick_date_column(df, ["payment_date", "paid_date", "transaction_date"])
    if payment_date_col is None:
        print("[SUP-005] No payment date column found; skipping")
        return []

    if "employee_id" not in df.columns:
        print("[SUP-005] employee_id column missing; skipping")
        return []

    df["employee_id"] = df["employee_id"].astype(str).str.strip()

    raw_payment = df[payment_date_col]
    parsed_payment = pd.to_datetime(raw_payment, errors="coerce")

    blank_mask = raw_payment.map(is_missing)
    invalid_mask = (~blank_mask) & parsed_payment.isna()

    flagged = df[blank_mask | invalid_mask].copy()

    if flagged.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "Superannuation payment records were identified without a valid payment date.",
    )
    remediation = text.get(
        "remediation",
        "Ensure all super payment records include valid payment dates and enforce validation before exporting super contribution data.",
    )
    severity = rule.get("severity", "HIGH")

    findings: List[Finding] = []

    for idx, row in flagged.iterrows():
        emp_id = str(row["employee_id"]).strip()

        if blank_mask.loc[idx]:
            issue = f"missing {payment_date_col}"
        else:
            issue = f"invalid {payment_date_col}"

        evidence_obj = {
            "sources": ["super_payments.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {
                payment_date_col: "" if pd.isna(row[payment_date_col]) else str(row[payment_date_col]),
                "period_end_date": "" if pd.isna(row.get("period_end_date")) else str(row.get("period_end_date")),
                "super_amount": "" if pd.isna(row.get("super_amount")) else str(row.get("super_amount")),
            },
            "explanation": issue,
        }
        evidence_str = str(evidence_obj).replace("'", '"')

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=severity,
                message=base_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

def _run_sup_006(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-SUP-006
    Multiple default super funds recorded for an employee.
    """
    print("[SUP-006] Running RKEG-SUP-006 detector")

    employee_super = datasets.get("employee_super")

    if employee_super is None or employee_super.empty:
        return []

    df = employee_super.copy()

    if "employee_id" not in df.columns:
        print("[SUP-006] employee_id column missing; skipping")
        return []

    df["employee_id"] = df["employee_id"].astype(str).str.strip()

    # Find the most likely fund identifier column
    fund_col = None
    preferred_fund_cols = [
        "default_fund_name",
        "fund_name",
        "super_fund_name",
        "fund_id",
    ]
    lower_cols = {c.lower(): c for c in df.columns}

    for logical in preferred_fund_cols:
        if logical.lower() in lower_cols:
            fund_col = lower_cols[logical.lower()]
            break

    if fund_col is None:
        for c in df.columns:
            if "fund" in c.lower():
                fund_col = c
                break

    if fund_col is None:
        print("[SUP-006] No fund column found; skipping")
        return []

    # Optional narrowing to active/default-looking records only
    filtered = df.copy()

    status_col = lower_cols.get("status") or lower_cols.get("record_status")
    if status_col is not None:
        filtered = filtered[
            filtered[status_col].astype(str).str.strip().str.upper().isin(["ACTIVE", "CURRENT", "OPEN"])
        ]

    default_col = (
        lower_cols.get("is_default")
        or lower_cols.get("default_flag")
        or lower_cols.get("fund_type")
    )

    if default_col is not None:
        if default_col.lower() in {"is_default", "default_flag"}:
            filtered = filtered[
                filtered[default_col].astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "1"])
            ]
        elif default_col.lower() == "fund_type":
            filtered = filtered[
                filtered[default_col].astype(str).str.strip().str.upper().eq("DEFAULT")
            ]

    if filtered.empty:
        return []

    grouped = (
        filtered.groupby("employee_id")[fund_col]
        .apply(
            lambda s: sorted(
                {
                    str(v).strip()
                    for v in s
                    if not is_missing(v)
                }
            )
        )
        .reset_index(name="distinct_funds")
    )

    grouped["fund_count"] = grouped["distinct_funds"].apply(len)
    flagged = grouped[grouped["fund_count"] > 1].copy()

    if flagged.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "Employees were identified with multiple default superannuation fund records.",
    )
    remediation = text.get(
        "remediation",
        "Ensure each employee has a single valid default super fund and reconcile conflicting records.",
    )
    severity = rule.get("severity", "MEDIUM")

    findings: List[Finding] = []

    for _, row in flagged.iterrows():
        emp_id = str(row["employee_id"]).strip()
        funds = row["distinct_funds"]

        evidence_obj = {
            "sources": ["employee_super.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {
                "fund_count": int(row["fund_count"]),
                "funds": ", ".join(funds),
            },
            "explanation": "Multiple distinct default super fund records were identified for the employee.",
        }
        evidence_str = str(evidence_obj).replace("'", '"')

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=severity,
                message=base_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

def run_rule(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[Finding]:
    """
    Entry point for SUP domain rules.

    Currently implements:
    - RKEG-SUP-001: superannuation rate outside expected tolerance band
    - RKEG-SUP-002: accrued vs paid reconciliation (employee + month)
    - RKEG-SUP-003: late contributions vs period end + grace days
    - RKEG-SUP-004: employees without a recorded default fund
    - RKEG-SUP-005: Super payment record missing payment date
    - RKEG-SUP-006: Multiple default super funds recorded for an employee
    """
    rule_id = rule["id"]

    if rule_id == "RKEG-SUP-001":
        print("[SUP-001] Running RKEG-SUP-001 detector")
        return _run_sup_001(rule, datasets)

    if rule_id == "RKEG-SUP-002":
        return _run_sup_002(rule, datasets)

    if rule_id == "RKEG-SUP-003":
        return _run_sup_003(rule, datasets)

    if rule_id == "RKEG-SUP-004":
        return _run_sup_004(rule, datasets)

    if rule_id == "RKEG-SUP-005":
        return _run_sup_005(rule, datasets)

    if rule_id == "RKEG-SUP-006":
        return _run_sup_006(rule, datasets)

    # Other SUP rules can be added here later
    return []