from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Any

from common.term_messages import TERM_MESSAGES
from common.severity import SEVERITY_BY_CODE


Row = Dict[str, Any]


# ---------- Helpers ----------


def _parse_date(value: str | None) -> Optional[date]:
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None

    # Try a couple of common formats; fail quietly if we can't parse
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _truthy_flag(value: str | None) -> bool:
    if value is None:
        return False
    v = str(value).strip().lower()
    return v in {"y", "yes", "true", "t", "1"}


def _normalise_severity(code: str) -> str:
    """
    Ensure severity codes align with the shared severity contract.
    Defaults to HIGH or MEDIUM where appropriate; TERM v1 does not use LOW.
    """
    code_upper = (code or "").strip().upper()
    if code_upper in SEVERITY_BY_CODE:
        return code_upper
    # Fallbacks – TERM v1 is HIGH / MEDIUM only
    if code_upper in {"H", "HI"}:
        return "HIGH"
    if code_upper in {"M", "MED"}:
        return "MEDIUM"
    return "HIGH"


def _build_finding(
    *,
    rule_code: str,
    severity: str,
    employee_id: str,
    termination_date: Optional[date],
    final_pay_date: Optional[date] = None,
    days_gap: Optional[int] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Row:
    sev = _normalise_severity(severity)
    msg_pack = TERM_MESSAGES.get(rule_code, {})
    message = msg_pack.get("message", "")
    next_action = msg_pack.get("next_action", "")

    term_date_str = termination_date.isoformat() if isinstance(termination_date, date) else ""
    final_date_str = final_pay_date.isoformat() if isinstance(final_pay_date, date) else ""

    finding_id = f"{rule_code}:{employee_id}:{term_date_str or 'UNKNOWN'}"

    return {
        "employee_id": employee_id,
        "termination_date": term_date_str,
        "final_pay_date": final_date_str,
        "rule_code": rule_code,
        "severity": sev,
        "message": message,
        "days_gap": days_gap if days_gap is not None else "",
        "evidence": evidence or {},
        "finding_id": finding_id,
        "next_action": next_action,
    }


# ---------- Core TERM rules ----------


def term_001_no_final_pay(
    terminations: List[Row],
    pay_events: List[Row],
) -> List[Row]:
    """
    TERM-001 — Termination recorded with no final pay event.

    Condition (v1):
    - Termination date is recorded
    - No pay events exist on or after the termination date for that employee

    This deliberately focuses on clear absence of pay after termination.
    Ambiguous / unlabelled final pay is handled by TERM-006.
    """
    findings: List[Row] = []

    # Index pay events by employee for quick lookup
    pays_by_emp: Dict[str, List[Row]] = {}
    for p in pay_events:
        emp_id = str(p.get("employee_id", "")).strip()
        if not emp_id:
            continue
        pays_by_emp.setdefault(emp_id, []).append(p)

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue

        term_date = _parse_date(str(t.get("termination_date", "")))
        if term_date is None:
            # If we can't parse the date, we don't apply termination-timing rules
            continue

        emp_pays = pays_by_emp.get(emp_id, [])
        has_pay_on_or_after = False
        for p in emp_pays:
            pay_date = _parse_date(str(p.get("pay_date", "")))
            if pay_date is None:
                continue
            if pay_date >= term_date:
                has_pay_on_or_after = True
                break

        if not has_pay_on_or_after:
            evidence = {
                "sources": ["terminations.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": term_date.isoformat(),
                },
                "details": {
                    "has_pay_on_or_after_termination": False,
                },
            }
            findings.append(
                _build_finding(
                    rule_code="TERM-001",
                    severity="HIGH",
                    employee_id=emp_id,
                    termination_date=term_date,
                    final_pay_date=None,
                    days_gap=None,
                    evidence=evidence,
                )
            )

    return findings


def term_002_final_pay_before_termination(
    terminations: List[Row],
    pay_events: List[Row],
) -> List[Row]:
    """
    TERM-002 — Final pay processed before termination date.

    Condition:
    - A pay event is explicitly marked as final pay
    - pay_date < termination_date
    """
    findings: List[Row] = []

    # We don't pre-index here because we filter by final-pay flag first
    final_pays = [
        p for p in pay_events if _truthy_flag(str(p.get("is_final_pay", "")))
    ]

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue
        term_date = _parse_date(str(t.get("termination_date", "")))
        if term_date is None:
            continue

        for p in final_pays:
            if str(p.get("employee_id", "")).strip() != emp_id:
                continue
            pay_date = _parse_date(str(p.get("pay_date", "")))
            if pay_date is None:
                continue
            if pay_date < term_date:
                gap_days = (term_date - pay_date).days
                evidence = {
                    "sources": ["terminations.csv", "pay_events.csv"],
                    "primary_keys": {
                        "employee_id": emp_id,
                        "termination_date": term_date.isoformat(),
                        "final_pay_date": pay_date.isoformat(),
                    },
                    "details": {
                        "gap_days": gap_days,
                    },
                }
                findings.append(
                    _build_finding(
                        rule_code="TERM-002",
                        severity="HIGH",
                        employee_id=emp_id,
                        termination_date=term_date,
                        final_pay_date=pay_date,
                        days_gap=gap_days,
                        evidence=evidence,
                    )
                )

    return findings


def term_003_gap_since_last_pay(
    terminations: List[Row],
    pay_events: List[Row],
    max_gap_days: int = 35,
) -> List[Row]:
    """
    TERM-003 — Termination date significantly after last ordinary pay.

    Condition:
    - Termination date exists
    - There is at least one pay event on/before termination
    - Difference between termination_date and last pay_date > max_gap_days
    """
    findings: List[Row] = []

    pays_by_emp: Dict[str, List[Row]] = {}
    for p in pay_events:
        emp_id = str(p.get("employee_id", "")).strip()
        if not emp_id:
            continue
        pays_by_emp.setdefault(emp_id, []).append(p)

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue

        term_date = _parse_date(str(t.get("termination_date", "")))
        if term_date is None:
            continue

        emp_pays = pays_by_emp.get(emp_id, [])
        if not emp_pays:
            continue

        # Last pay on/before termination
        last_pay_date: Optional[date] = None
        for p in emp_pays:
            pay_date = _parse_date(str(p.get("pay_date", "")))
            if pay_date is None or pay_date > term_date:
                continue
            if last_pay_date is None or pay_date > last_pay_date:
                last_pay_date = pay_date

        if last_pay_date is None:
            continue

        gap = (term_date - last_pay_date).days
        if gap > max_gap_days:
            evidence = {
                "sources": ["terminations.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": term_date.isoformat(),
                },
                "details": {
                    "last_pay_date": last_pay_date.isoformat(),
                    "gap_days": gap,
                    "threshold_days": max_gap_days,
                },
            }
            findings.append(
                _build_finding(
                    rule_code="TERM-003",
                    severity="MEDIUM",
                    employee_id=emp_id,
                    termination_date=term_date,
                    final_pay_date=last_pay_date,
                    days_gap=gap,
                    evidence=evidence,
                )
            )

    return findings


def term_004_missing_or_inconsistent_type(
    terminations: List[Row],
    employees: Optional[List[Row]] = None,
) -> List[Row]:
    """
    TERM-004 — Missing or inconsistent termination type / reason.

    v1 implementation:
    - Flags terminations where type/reason is blank.
    - If employee data provided, can be extended to detect inconsistencies.
    """
    findings: List[Row] = []

    # Optional cross-check map: employee_id -> type from employees.csv
    emp_type_map: Dict[str, str] = {}
    if employees:
        for e in employees:
            emp_id = str(e.get("employee_id", "")).strip()
            if not emp_id:
                continue
            # Use whichever field is available
            t_type = (
                str(e.get("termination_type") or e.get("separation_code") or "")
                .strip()
            )
            if t_type:
                emp_type_map[emp_id] = t_type

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue

        term_date = _parse_date(str(t.get("termination_date", "")))
        # Lack of date isn't the focus here, but we still want a string in the output
        # so we keep term_date possibly None and let _build_finding handle it.

        t_type = str(
            t.get("termination_type") or t.get("termination_reason") or ""
        ).strip()

        inconsistent_with_emp = False
        emp_record_type = emp_type_map.get(emp_id)
        if emp_record_type and t_type and emp_record_type != t_type:
            inconsistent_with_emp = True

        if not t_type or inconsistent_with_emp:
            evidence_details: Dict[str, Any] = {
                "termination_type": t.get("termination_type"),
                "termination_reason": t.get("termination_reason"),
            }
            if emp_record_type:
                evidence_details["employee_master_termination_type"] = emp_record_type

            evidence = {
                "sources": ["terminations.csv"]
                + (["employees.csv"] if emp_record_type else []),
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": term_date.isoformat()
                    if isinstance(term_date, date)
                    else "",
                },
                "details": evidence_details,
            }
            findings.append(
                _build_finding(
                    rule_code="TERM-004",
                    severity="MEDIUM",
                    employee_id=emp_id,
                    termination_date=term_date,
                    final_pay_date=None,
                    days_gap=None,
                    evidence=evidence,
                )
            )

    return findings


def term_005_missing_evidence_reference(
    terminations: List[Row],
) -> List[Row]:
    """
    TERM-005 — Termination recorded with no supporting artefact reference.

    Condition:
    - Termination is recorded
    - No reference to a termination artefact (e.g. resignation notice, termination letter)
    """
    findings: List[Row] = []

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue

        term_date = _parse_date(str(t.get("termination_date", "")))

        evidence_ref = (
            t.get("evidence_ref")
            or t.get("termination_evidence")
            or t.get("document_id")
            or ""
        )
        evidence_ref = str(evidence_ref).strip()

        if not evidence_ref:
            evidence = {
                "sources": ["terminations.csv"],
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": term_date.isoformat()
                    if isinstance(term_date, date)
                    else "",
                },
                "details": {
                    "evidence_ref": evidence_ref or None,
                },
            }
            findings.append(
                _build_finding(
                    rule_code="TERM-005",
                    severity="HIGH",
                    employee_id=emp_id,
                    termination_date=term_date,
                    final_pay_date=None,
                    days_gap=None,
                    evidence=evidence,
                )
            )

    return findings


def term_006_ambiguous_final_pay(
    terminations: List[Row],
    pay_events: List[Row],
    window_before_days: int = 14,
    window_after_days: int = 30,
) -> List[Row]:
    """
    TERM-006 — Final pay event not clearly identifiable.

    Condition (v1):
    - Termination date exists
    - There are pay events in a window around/after termination
    - No pay event is explicitly flagged as final pay
    """
    findings: List[Row] = []

    pays_by_emp: Dict[str, List[Row]] = {}
    for p in pay_events:
        emp_id = str(p.get("employee_id", "")).strip()
        if not emp_id:
            continue
        pays_by_emp.setdefault(emp_id, []).append(p)

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue

        term_date = _parse_date(str(t.get("termination_date", "")))
        if term_date is None:
            continue

        emp_pays = pays_by_emp.get(emp_id, [])
        if not emp_pays:
            # No pays at all – TERM-001 handles clear absence
            continue

        window_start = term_date.replace()  # copy
        window_start = term_date.fromordinal(term_date.toordinal() - window_before_days)
        window_end = term_date.fromordinal(term_date.toordinal() + window_after_days)

        candidate_pays: List[Dict[str, Any]] = []
        has_flagged_final = False

        for p in emp_pays:
            pay_date = _parse_date(str(p.get("pay_date", "")))
            if pay_date is None:
                continue

            if _truthy_flag(str(p.get("is_final_pay", ""))):
                if pay_date >= term_date:
                    has_flagged_final = True

            if window_start <= pay_date <= window_end:
                gross_raw = p.get("gross_amount") or p.get("gross") or ""
                try:
                    gross_amount = float(gross_raw) if str(gross_raw).strip() else None
                except ValueError:
                    gross_amount = None

                candidate_pays.append(
                    {
                        "pay_date": pay_date.isoformat(),
                        "gross_amount": gross_amount,
                    }
                )

        if has_flagged_final:
            # If we have a clear final-pay flag, this rule does not apply.
            continue

        if not candidate_pays:
            # No pays in the window – either handled by TERM-001 or not interesting
            continue

        evidence = {
            "sources": ["terminations.csv", "pay_events.csv"],
            "primary_keys": {
                "employee_id": emp_id,
                "termination_date": term_date.isoformat(),
            },
            "details": {
                "candidate_final_pays": candidate_pays,
                "window_before_days": window_before_days,
                "window_after_days": window_after_days,
            },
        }

        findings.append(
            _build_finding(
                rule_code="TERM-006",
                severity="MEDIUM",
                employee_id=emp_id,
                termination_date=term_date,
                final_pay_date=None,
                days_gap=None,
                evidence=evidence,
            )
        )

    return findings


# ---------- Convenience orchestrator ----------


def run_all_term_rules(
    *,
    terminations: List[Row],
    pay_events: List[Row],
    employees: Optional[List[Row]] = None,
    max_gap_days: int = 35,
) -> List[Row]:
    """
    Convenience function to run all TERM v1 rules and return a flat list of findings.
    File I/O belongs in a separate run.py module.
    """
    findings: List[Row] = []

    findings.extend(term_001_no_final_pay(terminations, pay_events))
    findings.extend(term_002_final_pay_before_termination(terminations, pay_events))
    findings.extend(
        term_003_gap_since_last_pay(terminations, pay_events, max_gap_days=max_gap_days)
    )
    findings.extend(term_004_missing_or_inconsistent_type(terminations, employees))
    findings.extend(term_005_missing_evidence_reference(terminations))
    findings.extend(
        term_006_ambiguous_final_pay(
            terminations,
            pay_events,
        )
    )

    return findings