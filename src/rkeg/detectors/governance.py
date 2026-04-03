from __future__ import annotations

from typing import Iterable, Dict, List
from uuid import uuid4

import pandas as pd

from rkeg.models import Finding
from common.nulls import is_missing


def _run_gov_001(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-GOV-001
    No structured payroll override log provided.
    """

    pay_overrides = datasets.get("pay_overrides")

    # Missing dataset or empty dataset both count as no usable override log.
    if pay_overrides is not None and not pay_overrides.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "No structured override or exception log was provided for manual payroll adjustments.",
    )
    remediation = text.get(
        "remediation",
        "Introduce a basic override register or system-based workflow to record all manual payroll changes, including who made the change, when, and for what reason.",
    )
    severity = rule.get("severity", "MEDIUM")

    evidence_obj = {
        "sources": ["pay_overrides.csv"],
        "primary_keys": {},
        "values": {},
        "explanation": "No structured pay_overrides dataset was provided, or the dataset was empty.",
    }
    evidence_str = str(evidence_obj).replace("'", '"')

    return [
        Finding(
            employee_id=None,
            leave_type=None,
            as_of_date=None,
            rule_code=rule["id"],
            severity=severity,
            classification=rule.get("classification", "UNCLASSIFIED"),
            message=base_msg,
            diff_units=None,
            evidence=evidence_str,
            finding_id=uuid4().hex[:12],
            next_action=remediation,
        )
    ]


def _run_gov_002(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-GOV-002
    Payroll overrides missing reason or approval information.
    """

    pay_overrides = datasets.get("pay_overrides")

    if pay_overrides is None or pay_overrides.empty:
        return []

    df = pay_overrides.copy()

    if "employee_id" not in df.columns:
        return []

    lower_cols = {c.lower(): c for c in df.columns}
    reason_col = lower_cols.get("reason_code") or lower_cols.get("reason")
    approval_col = lower_cols.get("approval_status") or lower_cols.get("approval")

    if reason_col is None and approval_col is None:
        return []

    df["employee_id"] = df["employee_id"].astype(str).str.strip()

    def _is_blank(series: pd.Series) -> pd.Series:
        return series.map(is_missing)

    reason_missing = _is_blank(df[reason_col]) if reason_col is not None else pd.Series(False, index=df.index)
    approval_missing = _is_blank(df[approval_col]) if approval_col is not None else pd.Series(False, index=df.index)

    flagged = df[reason_missing | approval_missing].copy()

    if flagged.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "Payroll overrides were identified with missing or incomplete reason or approval information.",
    )
    remediation = text.get(
        "remediation",
        "Enforce mandatory reason and approval fields for payroll overrides and ensure incomplete records cannot be finalised.",
    )
    severity = rule.get("severity", "MEDIUM")

    findings: List[Finding] = []

    for idx, row in flagged.iterrows():
        emp_id = str(row["employee_id"]).strip()

        issues: List[str] = []
        if reason_col is not None and reason_missing.loc[idx]:
            issues.append(f"missing {reason_col}")
        if approval_col is not None and approval_missing.loc[idx]:
            issues.append(f"missing {approval_col}")

        evidence_obj = {
            "sources": ["pay_overrides.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {
                "pay_date": "" if pd.isna(row.get("pay_date")) else str(row.get("pay_date")),
                "override_type": "" if pd.isna(row.get("override_type")) else str(row.get("override_type")),
                reason_col if reason_col else "reason_code": (
                    "" if reason_col is None or pd.isna(row.get(reason_col)) else str(row.get(reason_col))
                ),
                approval_col if approval_col else "approval_status": (
                    "" if approval_col is None or pd.isna(row.get(approval_col)) else str(row.get(approval_col))
                ),
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
                severity=severity,
                classification=rule.get("classification", "UNCLASSIFIED"),
                message=base_msg,
                diff_units=None,
                evidence=evidence_str,
                finding_id=uuid4().hex[:12],
                next_action=remediation,
            )
        )

    return findings


def _run_gov_003(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-GOV-003
    High volume of manual payroll overrides relative to pay events.
    """

    pay_overrides = datasets.get("pay_overrides")
    pay_events = datasets.get("pay_events")

    if pay_overrides is None or pay_overrides.empty:
        return []
    if pay_events is None or pay_events.empty:
        return []

    override_count = len(pay_overrides)
    pay_event_count = len(pay_events)

    if pay_event_count <= 0:
        return []

    config = rule.get("config", {}) or {}
    threshold_ratio = float(config.get("threshold_ratio", 0.10))

    override_ratio = override_count / pay_event_count

    if override_ratio <= threshold_ratio:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "A high volume of manual overrides was identified relative to the total number of pay events processed.",
    )
    remediation = text.get(
        "remediation",
        "Review the drivers of manual overrides, address underlying configuration or process issues, and reduce reliance on manual adjustments where possible.",
    )
    severity = rule.get("severity", "MEDIUM")

    message = (
        f"{base_msg} Override count {override_count}, pay event count {pay_event_count}, "
        f"override ratio {override_ratio:.2%} exceeded threshold {threshold_ratio:.2%}."
    )

    evidence_obj = {
        "sources": ["pay_overrides.csv", "pay_events.csv"],
        "primary_keys": {},
        "values": {
            "override_count": override_count,
            "pay_event_count": pay_event_count,
            "override_ratio": f"{override_ratio:.4f}",
            "threshold_ratio": f"{threshold_ratio:.4f}",
        },
        "explanation": "Override volume exceeded the configured governance monitoring threshold.",
    }
    evidence_str = str(evidence_obj).replace("'", '"')

    return [
        Finding(
            employee_id=None,
            leave_type=None,
            as_of_date=None,
            rule_code=rule["id"],
            severity=severity,
            classification=rule.get("classification", "UNCLASSIFIED"),
            message=message,
            diff_units="ratio",
            evidence=evidence_str,
            finding_id=uuid4().hex[:12],
            next_action=remediation,
        )
    ]


def _run_gov_004(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-GOV-004
    Payroll overrides missing timestamp information.
    """

    pay_overrides = datasets.get("pay_overrides")

    if pay_overrides is None or pay_overrides.empty:
        return []

    df = pay_overrides.copy()

    if "employee_id" not in df.columns:
        return []

    lower_cols = {c.lower(): c for c in df.columns}
    timestamp_col = (
        lower_cols.get("created_at")
        or lower_cols.get("override_timestamp")
        or lower_cols.get("timestamp")
    )

    if timestamp_col is None:
        return []

    df["employee_id"] = df["employee_id"].astype(str).str.strip()

    raw_ts = df[timestamp_col]
    parsed_ts = pd.to_datetime(raw_ts, errors="coerce")

    blank_mask = raw_ts.isna() | (raw_ts.astype(str).str.strip() == "")
    invalid_mask = (~blank_mask) & parsed_ts.isna()

    flagged = df[blank_mask | invalid_mask].copy()

    if flagged.empty:
        return []

    text = rule.get("text", {})
    base_msg = text.get(
        "finding",
        "Payroll override records were identified without a valid timestamp.",
    )
    remediation = text.get(
        "remediation",
        "Ensure override records include timestamps and enforce system controls to prevent incomplete override records.",
    )
    severity = rule.get("severity", "MEDIUM")

    findings: List[Finding] = []

    for idx, row in flagged.iterrows():
        emp_id = str(row["employee_id"]).strip()

        if blank_mask.loc[idx]:
            issue = f"missing {timestamp_col}"
        else:
            issue = f"invalid {timestamp_col}"

        evidence_obj = {
            "sources": ["pay_overrides.csv"],
            "primary_keys": {"employee_id": emp_id},
            "values": {
                "pay_date": "" if pd.isna(row.get("pay_date")) else str(row.get("pay_date")),
                "override_type": "" if pd.isna(row.get("override_type")) else str(row.get("override_type")),
                "field_overridden": "" if pd.isna(row.get("field_overridden")) else str(row.get("field_overridden")),
                timestamp_col: "" if pd.isna(row.get(timestamp_col)) else str(row.get(timestamp_col)),
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
                classification=rule.get("classification", "UNCLASSIFIED"),
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
    Governance / override rules (GOVERNANCE domain).
    """
    rule_id = rule["id"]

    if rule_id == "RKEG-GOV-001":
        return _run_gov_001(rule, datasets)

    if rule_id == "RKEG-GOV-002":
        return _run_gov_002(rule, datasets)

    if rule_id == "RKEG-GOV-003":
        return _run_gov_003(rule, datasets)

    if rule_id == "RKEG-GOV-004":
        return _run_gov_004(rule, datasets)

    return []