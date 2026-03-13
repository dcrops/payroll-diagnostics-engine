from __future__ import annotations

from uuid import uuid4
from typing import Dict, Iterable, List
import pandas as pd

from rkeg.models import Finding
from common.nulls import is_missing


def run_rule(rule: dict, datasets: dict[str, pd.DataFrame]) -> List[Finding]:
    """
    Dispatch EMP-domain rules.
    Currently only implements RKEG-EMP-001.
    """
    rule_id = rule["id"]

    if rule_id == "RKEG-EMP-001":
        return _emp_001_missing_employee_master(rule, datasets)
    if rule_id == "RKEG-EMP-002":
        return _emp_002_missing_start_date(rule, datasets)
    if rule_id == "RKEG-EMP-003":
        return _emp_003_missing_or_invalid_status(rule, datasets)
    if rule_id == "RKEG-EMP-004":
        return _emp_004_terminated_but_active(rule, datasets)
    elif rule_id == "RKEG-EMP-005":
        return _run_emp_005(rule, datasets)
        # Tier 2 – Employees without a complete rate history record
        # Placeholder for now so enabling Tier 2 doesn't break the engine.
        # We'll implement the actual logic when rate_history rules are ready.
    return []


def _emp_001_missing_employee_master(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-EMP-001:
    Pay or leave records exist without an employee master record.
    """

    employees = datasets.get("employee_master", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())

    findings: list[Finding] = []

    # Collect all employee_ids referenced outside employee_master
    referenced_ids: set[str] = set()

    for df in (pay_events, leave_ledger, leave_snapshot, terminations):
        if not df.empty and "employee_id" in df.columns:
            ids = df["employee_id"].dropna().astype(str).str.strip()
            referenced_ids |= set(ids)

    if employees.empty or "employee_id" not in employees.columns:
        master_ids: set[str] = set()
    else:
        master_ids = set(
            employees["employee_id"].dropna().astype(str).str.strip()
        )

    missing_ids = referenced_ids - master_ids

    # --- debug: see what the rule is seeing ---
    print("[RKEG-EMP-001] referenced_ids:", len(referenced_ids))
    print("[RKEG-EMP-001] master_ids:", len(master_ids))
    print("[RKEG-EMP-001] missing_ids:", len(missing_ids))

    if not missing_ids:
        return findings

    finding_msg = rule["text"]["finding"]
    remediation = rule["text"]["remediation"]

    for emp_id in sorted(missing_ids):
        evidence_obj = {
            "sources": [
                "pay_events.csv",
                "leave_ledger.csv",
                "balances_snapshot.csv",
                "terminations.csv",
            ],
            "primary_keys": {"employee_id": emp_id},
            "explanation": (
                "Employee appears in payroll or leave data but has no "
                "corresponding employee master record."
            ),
        }
        # quick-and-dirty JSON-ish string to match your existing style
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

def _emp_002_missing_start_date(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-EMP-002:
    Employment start date missing.
    """

    employees = datasets.get("employee_master", pd.DataFrame())
    findings: list[Finding] = []

    if employees.empty:
        return findings

    if "employee_id" not in employees.columns or "start_date" not in employees.columns:
        return findings

    # Treat blank or unparseable dates as missing
    start_dates = pd.to_datetime(employees["start_date"], errors="coerce")

    missing_mask = start_dates.isna()

    print("[RKEG-EMP-002] employee rows:", len(employees))
    print("[RKEG-EMP-002] rows with missing/invalid start_date:", missing_mask.sum())

    if not missing_mask.any():
        return findings

    finding_msg = rule["text"]["finding"]
    remediation = rule["text"]["remediation"]

    for _, row in employees[missing_mask].iterrows():
        emp_id = str(row["employee_id"]).strip()

        raw_start = row.get("start_date")
        start_display = "" if pd.isna(raw_start) else str(raw_start)

        evidence_obj = {
            "sources": ["employees.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {"start_date": start_display},
            "explanation": "Employee record has no valid employment start date.",
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

def _emp_003_missing_or_invalid_status(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-EMP-003:
    Employment status/type missing or invalid.

    In this implementation we use the `employment_type` field from employees.csv
    as a proxy for status (e.g. FULL_TIME, PART_TIME, CASUAL, FIXED_TERM, etc.).
    """

    employees = datasets.get("employee_master", pd.DataFrame())
    findings: list[Finding] = []

    if employees.empty:
        return findings

    if "employee_id" not in employees.columns:
        return findings

    # Prefer an explicit status column if present, otherwise fall back to employment_type
    status_col = None
    if "employment_status" in employees.columns:
        status_col = "employment_status"
    elif "employment_type" in employees.columns:
        status_col = "employment_type"
    else:
        # No usable column for this rule
        return findings

    # Define what we consider "valid" values – adjust over time if needed
    valid_statuses = {
        "FULL_TIME",
        "PART_TIME",
        "CASUAL",
        "FIXED_TERM",
        "CONTRACTOR",
        "TEMPORARY",
    }

    for _, row in employees.iterrows():
        emp_id = str(row["employee_id"]).strip()
        raw_status = row.get(status_col)

        # Normalise
        if pd.isna(raw_status):
            status = ""
        else:
            status = str(raw_status).strip().upper()

        # Missing or not in our controlled list → finding
        if status == "" or status not in valid_statuses:
            evidence_obj = {
                "sources": ["employees.csv"],
                "primary_keys": {"employee_id": emp_id},
                "values": {status_col: status},
                "explanation": "Employee record has a missing or non-standard employment status/type value.",
            }
            evidence_str = str(evidence_obj).replace("'", '"')

            findings.append(
                Finding(
                    employee_id=emp_id,
                    leave_type=None,
                    as_of_date=None,
                    rule_code=rule["id"],
                    severity=rule["severity"],
                    message=rule["text"]["finding"],
                    diff_units=None,
                    evidence=evidence_str,
                    finding_id=uuid4().hex[:12],
                    next_action=rule["text"]["remediation"],
                )
            )

    return findings

def _emp_004_terminated_but_active(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
) -> list[Finding]:
    """
    RKEG-EMP-004:
    Termination exists but employee record still indicates active employment.
    """

    employees = datasets.get("employee_master", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())
    findings: list[Finding] = []

    if employees.empty or terminations.empty:
        return findings

    if "employee_id" not in employees.columns or "employee_id" not in terminations.columns:
        return findings

    # Determine which column represents status/type
    status_col = None
    if "employment_status" in employees.columns:
        status_col = "employment_status"
    elif "employment_type" in employees.columns:
        status_col = "employment_type"
    else:
        return findings

    # Normalise termination employee IDs
    terminated_ids = set(
        terminations["employee_id"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    for _, row in employees.iterrows():
        emp_id = str(row["employee_id"]).strip()

        if emp_id not in terminated_ids:
            continue

        raw_status = row.get(status_col)
        status = "" if pd.isna(raw_status) else str(raw_status).strip().upper()

        # What we consider "active"
        active_markers = {"ACTIVE", "FULL_TIME", "PART_TIME", "CASUAL", "FIXED_TERM"}

        if status in active_markers or status == "":
            evidence_obj = {
                "sources": ["employees.csv", "terminations.csv"],
                "primary_keys": {"employee_id": emp_id},
                "values": {status_col: status},
                "explanation": (
                    "A termination record exists for this employee, "
                    "but the employee master record still reflects an active status/type."
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
                    message=rule["text"]["finding"],
                    diff_units=None,
                    evidence=evidence_str,
                    finding_id=uuid4().hex[:12],
                    next_action=rule["text"]["remediation"],
                )
            )

    return findings

def _run_emp_005(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    employee_master = datasets.get("employee_master")
    rate_history = datasets.get("rate_history")
    pay_events = datasets.get("pay_events")  # NEW

    if employee_master is None or employee_master.empty:
        return []
    if rate_history is None or rate_history.empty:
        return []

    emp_df = employee_master.copy()
    rh_df = rate_history.copy()

    emp_cols = {c.lower(): c for c in emp_df.columns}
    rh_cols = {c.lower(): c for c in rh_df.columns}

    emp_id_col_emp = emp_cols.get("employee_id", "employee_id")
    emp_id_col_rh = rh_cols.get("employee_id", "employee_id")

    # Start from employees who actually appear in pay_events (if provided)
    emp_ids = emp_df[emp_id_col_emp].astype(str)

    if pay_events is not None and not pay_events.empty:
        pe_cols = {c.lower(): c for c in pay_events.columns}
        emp_id_col_pe = pe_cols.get("employee_id", "employee_id")
        paid_emp_ids = set(pay_events[emp_id_col_pe].astype(str).unique())
        emp_ids = emp_ids[emp_ids.isin(paid_emp_ids)]

    # If no one’s been paid in this window, nothing to do
    if emp_ids.empty:
        return []

    rh_emp_ids = rh_df[emp_id_col_rh].astype(str)
    emp_ids_with_history = set(rh_emp_ids.unique())

    # Employees we pay, but with no rate history rows
    mask_no_history = ~emp_ids.isin(emp_ids_with_history)

    missing = emp_df[emp_df[emp_id_col_emp].astype(str).isin(emp_ids[mask_no_history])].copy()
    if missing.empty:
        return []

    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Employees were identified without a corresponding rate history record.",
    )
    remediation_text = text_block.get(
        "remediation",
        "Ensure all employees have rate history records that evidence how their base rates were set or changed.",
    )
    severity = rule.get("severity", "HIGH")

    findings: List[Finding] = []

    for _, row in missing.iterrows():
        employee_id = str(row[emp_id_col_emp])

        message = (
            f"{base_finding_text} Employee {employee_id} has no rate history "
            f"records in the data provided."
        )

        evidence = f"employee_id={employee_id}, rate_history_records=0"

        findings.append(
            Finding(
                employee_id=employee_id,
                leave_type=None,
                as_of_date=None,
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




