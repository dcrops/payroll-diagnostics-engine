from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
import hashlib
import json


Row = Dict[str, Any]


@dataclass
class Finding:
    employee_id: str | None
    leave_type: Optional[str]
    as_of_date: Optional[str]
    rule_code: str
    severity: str
    message: str
    diff_units: Optional[float] = None
    evidence: Optional[str] = None
    finding_id: Optional[str] = None
    next_action: Optional[str] = None


def _make_finding_id(rule_code: str, employee_id: str, as_of_date: str) -> str:
    raw = f"TERM|{rule_code}|{employee_id}|{as_of_date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _parse_date(value: str | None) -> Optional[date]:
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _truthy_flag(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"y", "yes", "true", "t", "1"}


def _build_finding(
    *,
    rule: dict,
    employee_id: str | None,
    as_of_date: str | None,
    evidence_obj: Dict[str, Any],
    diff_units: float | None = None,
) -> Finding:
    evidence_str = json.dumps(evidence_obj, ensure_ascii=False)

    return Finding(
        employee_id=employee_id,
        leave_type=None,
        as_of_date=as_of_date,
        rule_code=rule["id"],
        severity=rule["severity"],
        message=rule["text"]["finding"],
        diff_units=diff_units,
        evidence=evidence_str,
        finding_id=_make_finding_id(rule["id"], employee_id or "", as_of_date or ""),
        next_action=rule["text"]["remediation"],
    )


def _run_term_001(rule: dict, terminations: List[Row], pay_events: List[Row]) -> List[Finding]:
    findings: List[Finding] = []

    pays_by_emp: Dict[str, List[Row]] = {}
    for p in pay_events:
        emp_id = str(p.get("employee_id", "")).strip()
        if emp_id:
            pays_by_emp.setdefault(emp_id, []).append(p)

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue

        term_date = _parse_date(t.get("termination_date"))
        if term_date is None:
            continue

        has_pay_on_or_after = False
        for p in pays_by_emp.get(emp_id, []):
            pay_date = _parse_date(p.get("pay_date"))
            if pay_date is not None and pay_date >= term_date:
                has_pay_on_or_after = True
                break

        if not has_pay_on_or_after:
            findings.append(
                _build_finding(
                    rule=rule,
                    employee_id=emp_id,
                    as_of_date=term_date.isoformat(),
                    evidence_obj={
                        "sources": ["terminations.csv", "pay_events.csv"],
                        "primary_keys": {
                            "employee_id": emp_id,
                            "termination_date": term_date.isoformat(),
                        },
                        "details": {
                            "has_pay_on_or_after_termination": False,
                        },
                    },
                )
            )

    return findings


def _run_term_002(rule: dict, terminations: List[Row], pay_events: List[Row]) -> List[Finding]:
    findings: List[Finding] = []
    final_pays = [p for p in pay_events if _truthy_flag(p.get("is_final_pay"))]

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        term_date = _parse_date(t.get("termination_date"))
        if not emp_id or term_date is None:
            continue

        for p in final_pays:
            if str(p.get("employee_id", "")).strip() != emp_id:
                continue
            pay_date = _parse_date(p.get("pay_date"))
            if pay_date is None:
                continue
            if pay_date < term_date:
                gap_days = (term_date - pay_date).days
                findings.append(
                    _build_finding(
                        rule=rule,
                        employee_id=emp_id,
                        as_of_date=term_date.isoformat(),
                        evidence_obj={
                            "sources": ["terminations.csv", "pay_events.csv"],
                            "primary_keys": {
                                "employee_id": emp_id,
                                "termination_date": term_date.isoformat(),
                                "final_pay_date": pay_date.isoformat(),
                            },
                            "details": {
                                "gap_days": gap_days,
                            },
                        },
                    )
                )

    return findings


def _run_term_003(rule: dict, terminations: List[Row], pay_events: List[Row]) -> List[Finding]:
    findings: List[Finding] = []
    max_gap_days = int(rule.get("config", {}).get("max_gap_days", 35))

    pays_by_emp: Dict[str, List[Row]] = {}
    for p in pay_events:
        emp_id = str(p.get("employee_id", "")).strip()
        if emp_id:
            pays_by_emp.setdefault(emp_id, []).append(p)

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        term_date = _parse_date(t.get("termination_date"))
        if not emp_id or term_date is None:
            continue

        last_pay_date: Optional[date] = None
        for p in pays_by_emp.get(emp_id, []):
            pay_date = _parse_date(p.get("pay_date"))
            if pay_date is None or pay_date > term_date:
                continue
            if last_pay_date is None or pay_date > last_pay_date:
                last_pay_date = pay_date

        if last_pay_date is None:
            continue

        gap = (term_date - last_pay_date).days
        if gap > max_gap_days:
            findings.append(
                _build_finding(
                    rule=rule,
                    employee_id=emp_id,
                    as_of_date=term_date.isoformat(),
                    evidence_obj={
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
                    },
                )
            )

    return findings


def _run_term_004(rule: dict, terminations: List[Row], employees: List[Row]) -> List[Finding]:
    findings: List[Finding] = []

    emp_type_map: Dict[str, str] = {}
    for e in employees:
        emp_id = str(e.get("employee_id", "")).strip()
        if not emp_id:
            continue
        t_type = str(e.get("termination_type") or e.get("separation_code") or "").strip()
        if t_type:
            emp_type_map[emp_id] = t_type

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue

        term_date = _parse_date(t.get("termination_date"))
        t_type = str(
            t.get("termination_type")
            or t.get("termination_reason")
            or t.get("reason")
            or ""
        ).strip()

        emp_record_type = emp_type_map.get(emp_id)
        inconsistent = bool(emp_record_type and t_type and emp_record_type != t_type)

        if not t_type or inconsistent:
            findings.append(
                _build_finding(
                    rule=rule,
                    employee_id=emp_id,
                    as_of_date=term_date.isoformat() if term_date else None,
                    evidence_obj={
                        "sources": ["terminations.csv"] + (["employees.csv"] if emp_record_type else []),
                        "primary_keys": {
                            "employee_id": emp_id,
                            "termination_date": term_date.isoformat() if term_date else "",
                        },
                        "details": {
                            "termination_type": t.get("termination_type"),
                            "termination_reason": t.get("termination_reason") or t.get("reason"),
                            "employee_master_termination_type": emp_record_type,
                        },
                    },
                )
            )

    return findings


def _run_term_005(rule: dict, terminations: List[Row]) -> List[Finding]:
    findings: List[Finding] = []

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        if not emp_id:
            continue

        term_date = _parse_date(t.get("termination_date"))
        evidence_ref = str(
            t.get("evidence_ref")
            or t.get("termination_evidence")
            or t.get("document_id")
            or ""
        ).strip()

        if not evidence_ref:
            findings.append(
                _build_finding(
                    rule=rule,
                    employee_id=emp_id,
                    as_of_date=term_date.isoformat() if term_date else None,
                    evidence_obj={
                        "sources": ["terminations.csv"],
                        "primary_keys": {
                            "employee_id": emp_id,
                            "termination_date": term_date.isoformat() if term_date else "",
                        },
                        "details": {
                            "evidence_ref": None,
                        },
                    },
                )
            )

    return findings


def _run_term_006(rule: dict, terminations: List[Row], pay_events: List[Row]) -> List[Finding]:
    findings: List[Finding] = []
    cfg = rule.get("config", {}) or {}
    window_before_days = int(cfg.get("window_before_days", 14))
    window_after_days = int(cfg.get("window_after_days", 30))

    pays_by_emp: Dict[str, List[Row]] = {}
    for p in pay_events:
        emp_id = str(p.get("employee_id", "")).strip()
        if emp_id:
            pays_by_emp.setdefault(emp_id, []).append(p)

    for t in terminations:
        emp_id = str(t.get("employee_id", "")).strip()
        term_date = _parse_date(t.get("termination_date"))
        if not emp_id or term_date is None:
            continue

        emp_pays = pays_by_emp.get(emp_id, [])
        if not emp_pays:
            continue

        window_start = term_date - timedelta(days=window_before_days)
        window_end = term_date + timedelta(days=window_after_days)

        candidate_pays: List[Dict[str, Any]] = []
        has_flagged_final = False

        for p in emp_pays:
            pay_date = _parse_date(p.get("pay_date"))
            if pay_date is None:
                continue

            if _truthy_flag(p.get("is_final_pay")) and pay_date >= term_date:
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

        if has_flagged_final or not candidate_pays:
            continue

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=emp_id,
                as_of_date=term_date.isoformat(),
                evidence_obj={
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
                },
            )
        )

    return findings


def run_rule(rule: dict, datasets: Dict[str, List[Row]]) -> List[Finding]:
    rule_id = rule["id"]

    terminations = datasets.get("terminations", [])
    pay_events = datasets.get("pay_events", [])
    employees = datasets.get("employee_master", [])

    if rule_id == "TERM-001":
        return _run_term_001(rule, terminations, pay_events)

    if rule_id == "TERM-002":
        return _run_term_002(rule, terminations, pay_events)

    if rule_id == "TERM-003":
        return _run_term_003(rule, terminations, pay_events)

    if rule_id == "TERM-004":
        return _run_term_004(rule, terminations, employees)

    if rule_id == "TERM-005":
        return _run_term_005(rule, terminations)

    if rule_id == "TERM-006":
        return _run_term_006(rule, terminations, pay_events)

    return []