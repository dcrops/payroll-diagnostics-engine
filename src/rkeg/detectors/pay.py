from __future__ import annotations

from typing import List
from uuid import uuid4

import pandas as pd

from rkeg.rules import Finding


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

    # Unknown PAY rule -> no findings
    return []


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



