from __future__ import annotations

from typing import List, Iterable, Dict
from uuid import uuid4

import pandas as pd

from rkeg.models import Finding


def run_rule(rule: dict, datasets: dict[str, pd.DataFrame]) -> List[Finding]:
    """
    Dispatch PAY-domain rules.
    Currently implements RKEG-PAY-001 only.
    """
    rule_id = rule.get("id")

    if rule_id == "RKEG-PAY-001":
        return _pay_001_missing_or_invalid_pay_date(rule, datasets)
    if rule_id == "RKEG-PAY-002":
        return _pay_002_missing_or_invalid_gross_amount(rule, datasets)
    if rule_id == "RKEG-PAY-003":
        return _pay_003_missing_pay_run_reference(rule, datasets)
    if rule_id == "RKEG-PAY-004":
        return _pay_004_pay_without_employee_record(rule, datasets)
    if rule_id == "RKEG-PAY-005":
        return _pay_005_earnings_adjustment_without_proportional_super_recalculation(rule, datasets)
    if rule_id == "RKEG-PAY-006":
        return _pay_006_ordinary_earnings_without_base_rate(rule, datasets)
    if rule_id == "RKEG-PAY-007":
        return _pay_007_negative_gross_pay_outside_expected_adjustment_patterns(rule, datasets)
    if rule_id == "RKEG-PAY-008":
        return _pay_008_unmatched_rate_history(rule, datasets)
    if rule_id == "RKEG-PAY-009":
        return _pay_009_rate_history_gaps_or_overlaps(rule, datasets)
    if rule_id == "RKEG-PAY-010":
        return _pay_010_pay_events_outside_employment_period(rule, datasets)
    if rule_id == "RKEG-PAY-011":
        return _pay_011_rate_history_missing_effective_date_fields(rule, datasets)

    # Unknown PAY rule -> no findings
    return []

def _pick_rate_history_date_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """
    Pick effective start / end columns for rate history.
    Supports either:
    - effective_from / effective_to
    - start_date / end_date
    """
    cols = {c.lower(): c for c in df.columns}

    start_col = (
        cols.get("effective_from")
        or cols.get("start_date")
    )

    end_col = (
        cols.get("effective_to")
        or cols.get("end_date")
    )

    return start_col, end_col

def _pick_first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """
    Return the first matching column from candidates, case-insensitive.
    """
    cols = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in cols:
            return cols[candidate.lower()]
    return None


def _is_blank(value: object) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() == ""

def _pay_001_missing_or_invalid_pay_date(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-PAY-001:
    Pay events without a valid pay date.
    """

    pay_events = datasets.get("pay_events", pd.DataFrame())
    findings: list[Finding] = []

    if pay_events.empty:
        return findings

    # We at least need employee_id and some pay date column
    if "employee_id" not in pay_events.columns or "pay_date" not in pay_events.columns:
        return findings

    # Normalise IDs
    pay_events = pay_events.copy()
    pay_events["employee_id"] = (
        pay_events["employee_id"].astype(str).str.strip()
    )

    # Parse pay_date; invalid/unparseable -> NaT
    parsed_dates = pd.to_datetime(
        pay_events["pay_date"],
        errors="coerce",
        dayfirst=True,  # align with how you've done other dates
    )

    invalid_mask = parsed_dates.isna()

    if not invalid_mask.any():
        return findings

    finding_msg = rule["text"]["finding"]
    remediation = rule["text"]["remediation"]

    for _, row in pay_events[invalid_mask].iterrows():
        emp_id = str(row["employee_id"]).strip()
        raw_date = row.get("pay_date")

        evidence_obj = {
            "sources": ["pay_events.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {"pay_date": "" if pd.isna(raw_date) else str(raw_date)},
            "explanation": "Pay event has a missing or invalid pay date that could not be parsed.",
        }
        evidence_str = str(evidence_obj).replace("'", '"')

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=rule["severity"],
                message=finding_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

def _pay_002_missing_or_invalid_gross_amount(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-PAY-002:
    Pay events without a valid gross amount.
    """

    pay_events = datasets.get("pay_events", pd.DataFrame())
    findings: list[Finding] = []

    if pay_events.empty:
        return findings

    if "employee_id" not in pay_events.columns or "gross_amount" not in pay_events.columns:
        return findings

    pay_events = pay_events.copy()
    pay_events["employee_id"] = pay_events["employee_id"].astype(str).str.strip()

    # Try to coerce gross_amount to numeric; invalid -> NaN
    gross_numeric = pd.to_numeric(pay_events["gross_amount"], errors="coerce")
    invalid_mask = gross_numeric.isna()

    if not invalid_mask.any():
        return findings

    finding_msg = rule["text"]["finding"]
    remediation = rule["text"]["remediation"]

    for _, row in pay_events[invalid_mask].iterrows():
        emp_id = str(row["employee_id"]).strip()
        raw_gross = row.get("gross_amount")

        evidence_obj = {
            "sources": ["pay_events.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {"gross_amount": "" if pd.isna(raw_gross) else str(raw_gross)},
            "explanation": "Pay event has a missing or non-numeric gross amount value.",
        }
        evidence_str = str(evidence_obj).replace("'", '"')

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=rule["severity"],
                message=finding_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

def _pay_003_missing_pay_run_reference(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-PAY-003:
    Pay events without a pay run or batch reference.
    """

    pay_events = datasets.get("pay_events", pd.DataFrame())
    findings: list[Finding] = []

    if pay_events.empty:
        return findings

    if "employee_id" not in pay_events.columns or "run_id" not in pay_events.columns:
        return findings

    pay_events = pay_events.copy()
    pay_events["employee_id"] = pay_events["employee_id"].astype(str).str.strip()

    # Treat blank / whitespace as missing
    def _is_missing_run(val: object) -> bool:
        if pd.isna(val):
            return True
        s = str(val).strip()
        return s == ""

    missing_mask = pay_events["run_id"].map(_is_missing_run)

    if not missing_mask.any():
        return findings

    finding_msg = rule["text"]["finding"]
    remediation = rule["text"]["remediation"]

    for _, row in pay_events[missing_mask].iterrows():
        emp_id = str(row["employee_id"]).strip()
        raw_run = row.get("run_id")

        display_run = "" if pd.isna(raw_run) else str(raw_run).strip()

        evidence_obj = {
            "sources": ["pay_events.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {"run_id": display_run},
            "explanation": "Pay event has no pay run or batch reference recorded.",
        }
        evidence_str = str(evidence_obj).replace("'", '"')

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=rule["severity"],
                message=finding_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

def _pay_004_pay_without_employee_record(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-PAY-004:
    Pay events for employees not present in employee master.
    """

    pay_events = datasets.get("pay_events", pd.DataFrame())
    employees = datasets.get("employee_master", pd.DataFrame())
    findings: list[Finding] = []

    if pay_events.empty or employees.empty:
        return findings

    if "employee_id" not in pay_events.columns or "employee_id" not in employees.columns:
        return findings

    pay_ids = set(
        pay_events["employee_id"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    emp_ids = set(
        employees["employee_id"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    orphan_ids = pay_ids - emp_ids

    if not orphan_ids:
        return findings

    finding_msg = rule["text"]["finding"]
    remediation = rule["text"]["remediation"]

    for emp_id in orphan_ids:
        evidence_obj = {
            "sources": ["pay_events.csv", "employees.csv"],
            "primary_keys": {"employee_id": emp_id},
            "explanation": (
                "Pay events exist for this employee identifier, "
                "but no corresponding employee master record was found."
            ),
        }
        evidence_str = str(evidence_obj).replace("'", '"')

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=rule["severity"],
                message=finding_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

def _pay_005_earnings_adjustment_without_proportional_super_recalculation(rule: dict, datasets: dict) -> List[Finding]:
    """
    RKEG-PAY-005
    Earnings adjustment without proportional super recalculation.
    """

    print("[PAY-005] Running RKEG-PAY-005 detector")

    pay_events = datasets.get("pay_events")

    if pay_events is None or pay_events.empty:
        return []

    df = pay_events.copy()

    if "gross_amount" not in df.columns:
        return []

    # Identify super column
    super_col = None
    for c in df.columns:
        if "super" in c.lower():
            super_col = c
            break

    if super_col is None:
        return []

    # Coerce numeric
    df["gross_amount"] = pd.to_numeric(df["gross_amount"], errors="coerce")
    df[super_col] = pd.to_numeric(df[super_col], errors="coerce")

    # Negative earnings but zero super adjustment
    flagged = df[
        (df["gross_amount"] < 0) &
        (df[super_col].fillna(0) == 0)
    ]

    if flagged.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "Earnings adjustment without proportional super recalculation detected."
    )
    remediation = text.get(
        "remediation",
        "Review adjustment logic and ensure super recalculation occurs."
    )
    severity = rule.get("severity", "HIGH")

    findings: List[Finding] = []

    for _, row in flagged.iterrows():
        emp_id = str(row.get("employee_id", ""))

        evidence = (
            f"employee_id={emp_id}, "
            f"gross_amount={row['gross_amount']}, "
            f"{super_col}={row[super_col]}"
        )

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=severity,
                message=base_msg,
                diff_units=None,
                evidence=evidence,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings

def _pay_006_ordinary_earnings_without_base_rate(rule: dict, datasets: dict) -> List[Finding]:
    """
    RKEG-PAY-006
    Ordinary earnings present without recorded base rate.

    Logic:
    - Find employees with positive gross_amount in pay_events.
    - Join to employee_master.
    - Flag employees where base_rate is missing/blank.
    """
    print("[PAY-006] Running RKEG-PAY-006 detector")

    pay_events = datasets.get("pay_events")
    employees = datasets.get("employee_master")

    if pay_events is None or pay_events.empty:
        return []
    if employees is None or employees.empty:
        return []

    if "gross_amount" not in pay_events.columns:
        return []
    if "employee_id" not in employees.columns:
        return []
    if "base_rate" not in employees.columns:
        # In v1 we just skip if the column isn't there at all
        return []

    pe = pay_events.copy()
    emps = employees.copy()

    # Normalise IDs
    pe["employee_id"] = pe["employee_id"].astype(str).str.strip()
    emps["employee_id"] = emps["employee_id"].astype(str).str.strip()

    # Coerce numeric
    pe["gross_amount"] = pd.to_numeric(pe["gross_amount"], errors="coerce")
    emps["base_rate"] = emps["base_rate"].astype(str)

    # Employees who actually have earnings
    earners = (
        pe[pe["gross_amount"] > 0]
        .dropna(subset=["employee_id"])
        .groupby("employee_id", as_index=False)["gross_amount"]
        .sum()
        .rename(columns={"gross_amount": "total_gross"})
    )

    if earners.empty:
        return []

    merged = earners.merge(
        emps[["employee_id", "base_rate"]],
        on="employee_id",
        how="left",
    )

    # base_rate missing or blank
    missing_mask = merged["base_rate"].isna() | (merged["base_rate"].str.strip() == "")
    flagged = merged[missing_mask]

    if flagged.empty:
        return []

    text_block = rule.get("text", {})
    base_msg = text_block.get(
        "finding",
        "Ordinary earnings were recorded without an associated base rate value.",
    )
    remediation = text_block.get(
        "remediation",
        "Ensure base rate fields are populated and aligned with earnings calculations.",
    )
    severity = rule.get("severity", rule.get("severity", "MEDIUM"))

    findings: List[Finding] = []

    for _, row in flagged.iterrows():
        emp_id = str(row["employee_id"])
        total_gross = float(row["total_gross"])

        evidence_str = (
            f"employee_id={emp_id}, total_gross={total_gross:.2f}, "
            f"base_rate={row['base_rate']!r}"
        )

        message = (
            f"{base_msg} Employee {emp_id} received ordinary earnings "
            f"totalling {total_gross:.2f} but has no recorded base rate."
        )

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
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

def _pay_007_negative_gross_pay_outside_expected_adjustment_patterns(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-PAY-007
    Negative gross pay identified outside expected adjustment patterns.

    Approach:
    - Look for rows with gross_amount < 0.
    - Group by (employee_id, run_id) and see if the *net* gross for that
      employee+run is effectively zero (i.e. clean reversal).
    - If the net is not ~0, treat that negative as suspicious.
    """
    print("[PAY-007] Running RKEG-PAY-007 detector")

    pay_events = datasets.get("pay_events")
    if pay_events is None or pay_events.empty:
        return []

    if "gross_amount" not in pay_events.columns:
        return []
    if "employee_id" not in pay_events.columns:
        return []

    df = pay_events.copy()

    # Normalise and coerce
    df["employee_id"] = df["employee_id"].astype("string").str.strip()
    df["gross_amount"] = pd.to_numeric(df["gross_amount"], errors="coerce")

    # Only rows with a numeric gross
    df = df[df["gross_amount"].notna()]
    if df.empty:
        return []

    # Identify negative rows
    neg = df[df["gross_amount"] < 0].copy()
    if neg.empty:
        return []

    # We use run_id if present, otherwise just group by employee_id
    key_cols: list[str] = ["employee_id"]
    if "run_id" in df.columns:
        key_cols.append("run_id")

    # Net gross per employee/run
    net_by_group = (
        df.groupby(key_cols, as_index=False)["gross_amount"]
        .sum()
        .rename(columns={"gross_amount": "__net_gross"})
    )

    merged = neg.merge(net_by_group, on=key_cols, how="left")

    # Anything with net gross effectively 0 (within tiny epsilon) looks like
    # an intentional reversal; we ignore those.
    EPS = 0.01
    suspicious = merged[merged["__net_gross"].abs() > EPS]

    if suspicious.empty:
        return []

    text_block = rule.get("text", {})
    base_msg = text_block.get(
        "finding",
        "Negative gross pay amounts were identified that may indicate configuration errors or payroll reversals.",
    )
    remediation = text_block.get(
        "remediation",
        "Review payroll adjustment controls and ensure negative entries are properly authorised and documented.",
    )
    severity = rule.get("severity", "MEDIUM")

    pay_date_col = "pay_date" if "pay_date" in suspicious.columns else None

    findings: List[Finding] = []

    for _, row in suspicious.iterrows():
        emp_id = str(row["employee_id"])
        gross = float(row["gross_amount"])
        net = float(row["__net_gross"])
        run_id = str(row["run_id"]) if "run_id" in row and pd.notna(row["run_id"]) else None
        pay_date = (
            str(row[pay_date_col]) if pay_date_col and pd.notna(row[pay_date_col]) else None
        )

        run_label = f", run_id={run_id}" if run_id else ""
        date_label = f", pay_date={pay_date}" if pay_date else ""

        evidence_str = (
            f"employee_id={emp_id}{run_label}{date_label}, "
            f"gross_amount={gross:.2f}, net_gross_for_run={net:.2f}"
        )

        message = (
            f"{base_msg} Employee {emp_id}{run_label} has a negative gross "
            f"amount {gross:.2f} with net gross for that run {net:.2f}."
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

def _pay_008_unmatched_rate_history(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[Finding]:
    """
    RKEG-PAY-008
    Pay events cannot be matched to a valid rate history record.
    """

    pay_events = datasets.get("pay_events")
    rate_history = datasets.get("rate_history")

    if pay_events is None or pay_events.empty:
        return []
    if rate_history is None or rate_history.empty:
        return []

    pe = pay_events.copy()
    rh = rate_history.copy()

    # Required columns
    required_pe_cols = {"employee_id", "pay_date"}
    required_rh_cols = {"employee_id", "effective_from"}

    if not required_pe_cols.issubset(pe.columns):
        return []
    if not required_rh_cols.issubset(rh.columns):
        return []

    # Coerce dates
    pe["pay_date"] = pd.to_datetime(pe["pay_date"], errors="coerce")
    rh["effective_from"] = pd.to_datetime(rh["effective_from"], errors="coerce")

    if "effective_to" in rh.columns:
        rh["effective_to"] = pd.to_datetime(rh["effective_to"], errors="coerce")
    else:
        rh["effective_to"] = pd.NaT

    # Treat NULL effective_to as open-ended
    rh["effective_to"] = rh["effective_to"].fillna(pd.Timestamp.max)

    findings = []

    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Pay events could not be matched to a valid rate history record.",
    )
    remediation_text = text_block.get(
        "remediation",
        "Reconcile pay events to rate history and ensure effective date coverage.",
    )
    severity = rule.get("severity", "HIGH")

    for _, pay_row in pe.iterrows():
        employee_id = pay_row["employee_id"]
        pay_date = pay_row["pay_date"]

        if pd.isna(pay_date) or pd.isna(employee_id):
            continue

        emp_rates = rh[rh["employee_id"] == employee_id]

        if emp_rates.empty:
            continue  # EMP-005 handles no history at all

        match = emp_rates[
            (emp_rates["effective_from"] <= pay_date)
            & (emp_rates["effective_to"] >= pay_date)
        ]

        if match.empty:
            message = (
                f"{base_finding_text} Employee {employee_id}, "
                f"pay date {pay_date.date()} is outside any "
                f"effective rate history window."
            )

            evidence = (
                f"employee_id={employee_id}, "
                f"pay_date={pay_date.date()}, "
                f"rate_history_rows={len(emp_rates)}"
            )

            findings.append(
                Finding(
                    employee_id=str(employee_id),
                    leave_type=None,
                    as_of_date=pay_date.date().isoformat(),
                    rule_code=rule["id"],
                    severity=severity,
                    message=message,
                    diff_units=None,
                    evidence=evidence,
                    finding_id=uuid4().hex[:12],
                    next_action=remediation_text,
                )
            )

    return findings

def _pay_009_rate_history_gaps_or_overlaps(rule, datasets):
    """
    RKEG-PAY-009
    Rate history records contain gaps or overlapping effective dates.
    """
    rate_history = datasets.get("rate_history")

    if rate_history is None or rate_history.empty:
        return []

    df = rate_history.copy()

    if "employee_id" not in df.columns:
        return []

    start_col, end_col = _pick_rate_history_date_columns(df)
    if start_col is None or end_col is None:
        return []

    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df[start_col] = pd.to_datetime(df[start_col], errors="coerce")
    df[end_col] = pd.to_datetime(df[end_col], errors="coerce")

    findings = []
    text = rule.get("text", {})
    severity = rule.get("severity", "MEDIUM")

    for employee_id, grp in df.groupby("employee_id"):
        grp = grp.sort_values(start_col).reset_index(drop=True)

        # 1) Invalid ranges
        invalid = grp[
            grp[start_col].isna()
            | grp[end_col].isna()
            | (grp[end_col] < grp[start_col])
        ]

        for _, row in invalid.iterrows():
            evidence = (
                f"employee_id={employee_id}, "
                f"{start_col}={row[start_col]}, "
                f"{end_col}={row[end_col]}, "
                f"issue=invalid_date_range"
            )

            findings.append(
                Finding(
                    employee_id=employee_id,
                    leave_type=None,
                    as_of_date=None,
                    rule_code=rule["id"],
                    severity=severity,
                    message=(
                        f"{text.get('finding')} Employee {employee_id} has an invalid "
                        f"rate history effective date range."
                    ),
                    diff_units=None,
                    evidence=evidence,
                    finding_id=uuid4().hex[:12],
                    next_action=text.get("remediation", ""),
                )
            )

        # 2) Gaps / overlaps between adjacent records
        for i in range(1, len(grp)):
            prev = grp.iloc[i - 1]
            curr = grp.iloc[i]

            if pd.isna(prev[start_col]) or pd.isna(prev[end_col]):
                continue
            if pd.isna(curr[start_col]) or pd.isna(curr[end_col]):
                continue
            if prev[end_col] < prev[start_col]:
                continue
            if curr[end_col] < curr[start_col]:
                continue

            # Overlap: current starts on/before previous ends
            if curr[start_col] <= prev[end_col]:
                evidence = (
                    f"employee_id={employee_id}, "
                    f"previous_start={prev[start_col].date()}, "
                    f"previous_end={prev[end_col].date()}, "
                    f"current_start={curr[start_col].date()}, "
                    f"current_end={curr[end_col].date()}, "
                    f"issue=overlap"
                )

                findings.append(
                    Finding(
                        employee_id=employee_id,
                        leave_type=None,
                        as_of_date=None,
                        rule_code=rule["id"],
                        severity=severity,
                        message=(
                            f"{text.get('finding')} Employee {employee_id} has overlapping "
                            f"rate history periods."
                        ),
                        diff_units="days",
                        evidence=evidence,
                        finding_id=uuid4().hex[:12],
                        next_action=text.get("remediation", ""),
                    )
                )

            # Gap: current starts more than 1 day after previous ends
            elif curr[start_col] > (prev[end_col] + pd.Timedelta(days=1)):
                gap_days = (curr[start_col] - prev[end_col]).days - 1

                evidence = (
                    f"employee_id={employee_id}, "
                    f"previous_start={prev[start_col].date()}, "
                    f"previous_end={prev[end_col].date()}, "
                    f"current_start={curr[start_col].date()}, "
                    f"current_end={curr[end_col].date()}, "
                    f"issue=gap, "
                    f"gap_days={gap_days}"
                )

                findings.append(
                    Finding(
                        employee_id=employee_id,
                        leave_type=None,
                        as_of_date=None,
                        rule_code=rule["id"],
                        severity=severity,
                        message=(
                            f"{text.get('finding')} Employee {employee_id} has a gap of "
                            f"{gap_days} day(s) between adjacent rate history periods."
                        ),
                        diff_units="days",
                        evidence=evidence,
                        finding_id=uuid4().hex[:12],
                        next_action=text.get("remediation", ""),
                    )
                )
    return findings

def _pay_010_pay_events_outside_employment_period(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-PAY-010:
    Pay events recorded before employee commencement or after termination.
    """

    pay_events = datasets.get("pay_events", pd.DataFrame())
    employees = datasets.get("employee_master", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())

    findings: list[Finding] = []

    if pay_events.empty or employees.empty:
        return findings

    if "employee_id" not in pay_events.columns or "employee_id" not in employees.columns:
        return findings

    pay_date_col = _pick_first_existing_column(
        pay_events,
        ["pay_date", "payment_date", "event_date"],
    )
    start_date_col = _pick_first_existing_column(
        employees,
        ["start_date", "commencement_date", "employment_start_date"],
    )
    employee_term_col = _pick_first_existing_column(
        employees,
        ["termination_date", "end_date", "employment_end_date"],
    )

    if pay_date_col is None or start_date_col is None:
        return findings

    pe = pay_events.copy()
    emps = employees.copy()

    pe["employee_id"] = pe["employee_id"].astype(str).str.strip()
    emps["employee_id"] = emps["employee_id"].astype(str).str.strip()

    pe["_pay_date"] = pd.to_datetime(pe[pay_date_col], errors="coerce")
    emps["_start_date"] = pd.to_datetime(emps[start_date_col], errors="coerce")

    if employee_term_col is not None:
        emps["_termination_date"] = pd.to_datetime(emps[employee_term_col], errors="coerce")
    else:
        emps["_termination_date"] = pd.NaT

    merged = pe.merge(
        emps[["employee_id", "_start_date", "_termination_date"]],
        on="employee_id",
        how="left",
    )

    # If employee master has no termination date, optionally fill from terminations dataset
    if not terminations.empty and "employee_id" in terminations.columns:
        term_date_col = _pick_first_existing_column(
            terminations,
            ["termination_date", "end_date", "termination_effective_date"],
        )

        if term_date_col is not None:
            terms = terminations.copy()
            terms["employee_id"] = terms["employee_id"].astype(str).str.strip()
            terms["_term_from_terminations"] = pd.to_datetime(terms[term_date_col], errors="coerce")

            terms = (
                terms[["employee_id", "_term_from_terminations"]]
                .drop_duplicates(subset=["employee_id"], keep="first")
            )

            merged = merged.merge(terms, on="employee_id", how="left")
            merged["_termination_date"] = merged["_termination_date"].combine_first(
                merged["_term_from_terminations"]
            )

    findings_mask = (
        (
            merged["_pay_date"].notna()
            & merged["_start_date"].notna()
            & (merged["_pay_date"] < merged["_start_date"])
        )
        |
        (
            merged["_pay_date"].notna()
            & merged["_termination_date"].notna()
            & (merged["_pay_date"] > merged["_termination_date"])
        )
    )

    flagged = merged[findings_mask].copy()

    print("[PAY-010] dataset keys:", list(datasets.keys()))
    print("[PAY-010] pay_events shape:", pe.shape)
    print("[PAY-010] employee_master shape:", emps.shape)
    print("[PAY-010] terminations shape:", terminations.shape if terminations is not None else None)

    debug_cols = ["employee_id", "_pay_date", "_start_date", "_termination_date"]
    print("[PAY-010] merged rows:")
    print(merged[debug_cols].to_string(index=False))

    print("[PAY-010] before-start matches:")
    print(
        merged[
            merged["_pay_date"].notna()
            & merged["_start_date"].notna()
            & (merged["_pay_date"] < merged["_start_date"])
        ][debug_cols].to_string(index=False)
    )

    print("[PAY-010] after-termination matches:")
    print(
        merged[
            merged["_pay_date"].notna()
            & merged["_termination_date"].notna()
            & (merged["_pay_date"] > merged["_termination_date"])
        ][debug_cols].to_string(index=False)
    )

    if flagged.empty:
        return findings

    finding_msg = rule["text"]["finding"]
    remediation = rule["text"]["remediation"]

    for _, row in flagged.iterrows():
        emp_id = str(row["employee_id"]).strip()

        if pd.notna(row["_termination_date"]) and row["_pay_date"] > row["_termination_date"]:
            explanation = "Pay event occurred after recorded termination date."
        else:
            explanation = "Pay event occurred before recorded employment start date."

        evidence_obj = {
            "sources": ["pay_events.csv", "employees.csv", "terminations.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {
                "pay_date": row["_pay_date"].date().isoformat() if pd.notna(row["_pay_date"]) else "",
                "start_date": row["_start_date"].date().isoformat() if pd.notna(row["_start_date"]) else "",
                "termination_date": (
                    row["_termination_date"].date().isoformat()
                    if pd.notna(row["_termination_date"])
                    else ""
                ),
            },
            "explanation": explanation,
        }
        evidence_str = str(evidence_obj).replace("'", '"')

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=row["_pay_date"].date().isoformat() if pd.notna(row["_pay_date"]) else None,
                rule_code=rule["id"],
                severity=rule["severity"],
                message=finding_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )
    print("[PAY-010] findings returned:", len(findings))
    for f in findings:
        print("[PAY-010] finding:", f.rule_code, f.employee_id, f.as_of_date)

    return findings

def _pay_011_rate_history_missing_effective_date_fields(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-PAY-011:
    Rate history record missing effective date fields.
    """

    rate_history = datasets.get("rate_history", pd.DataFrame())
    findings: list[Finding] = []

    if rate_history.empty:
        return findings

    if "employee_id" not in rate_history.columns:
        return findings

    start_col, end_col = _pick_rate_history_date_columns(rate_history)
    if start_col is None or end_col is None:
        return findings

    df = rate_history.copy()
    df["employee_id"] = df["employee_id"].astype(str).str.strip()

    parsed_start = pd.to_datetime(df[start_col], errors="coerce")
    parsed_end = pd.to_datetime(df[end_col], errors="coerce")

    start_blank = df[start_col].map(_is_blank)
    end_blank = df[end_col].map(_is_blank)

    start_invalid = (~start_blank) & parsed_start.isna()
    end_invalid = (~end_blank) & parsed_end.isna()

    flagged = df[start_blank | end_blank | start_invalid | end_invalid].copy()

    if flagged.empty:
        return findings

    finding_msg = rule["text"]["finding"]
    remediation = rule["text"]["remediation"]

    for idx, row in flagged.iterrows():
        emp_id = str(row["employee_id"]).strip()

        issues: list[str] = []

        if start_blank.loc[idx]:
            issues.append(f"missing {start_col}")
        elif start_invalid.loc[idx]:
            issues.append(f"invalid {start_col}")

        if end_blank.loc[idx]:
            issues.append(f"missing {end_col}")
        elif end_invalid.loc[idx]:
            issues.append(f"invalid {end_col}")

        evidence_obj = {
            "sources": ["rate_history.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {
                start_col: "" if pd.isna(row[start_col]) else str(row[start_col]),
                end_col: "" if pd.isna(row[end_col]) else str(row[end_col]),
                "base_rate": "" if pd.isna(row.get("base_rate")) else str(row.get("base_rate")),
                "classification": "" if pd.isna(row.get("classification")) else str(row.get("classification")),
            },
            "explanation": ", ".join(issues),
        }
        evidence_str = str(evidence_obj).replace("'", '"')

        findings.append(
            Finding(
                employee_id=emp_id,
                leave_type=None,
                as_of_date=None,
                rule_code=rule["id"],
                severity=rule["severity"],
                message=finding_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings



