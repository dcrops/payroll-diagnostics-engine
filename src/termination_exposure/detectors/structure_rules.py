from __future__ import annotations

import json
import pandas as pd

from termination_exposure.models import Finding, _build_finding


def detect_missing_or_inconsistent_termination_type_or_reason(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    employees = datasets.get("employee_master", pd.DataFrame())

    if terminations.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    emp_type_map = {}
    if not employees.empty:
        emp = employees.copy()
        emp["employee_id"] = emp["employee_id"].astype(str).str.strip()
        for _, row in emp.iterrows():
            emp_id = str(row["employee_id"]).strip()
            t_type = str(row.get("termination_type") or row.get("separation_code") or "").strip()
            if emp_id and t_type:
                emp_type_map[emp_id] = t_type

    for _, row in term.iterrows():
        emp_id = str(row["employee_id"]).strip()
        if not emp_id:
            continue

        term_date = row["termination_date"]
        t_type = str(
            row.get("termination_type")
            or row.get("termination_reason")
            or row.get("reason")
            or ""
        ).strip()

        emp_record_type = emp_type_map.get(emp_id)
        inconsistent = bool(emp_record_type and t_type and emp_record_type != t_type)

        if t_type and not inconsistent:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv"] + (["employees.csv"] if emp_record_type else []),
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": str(term_date.date()) if pd.notna(term_date) else None,
                },
                "values": {
                    "termination_type": row.get("termination_type"),
                    "termination_reason": row.get("termination_reason") or row.get("reason"),
                    "employee_master_termination_type": emp_record_type,
                },
                "explanation": "Termination type or reason is missing, or inconsistent with employee master data.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=emp_id,
                leave_type=None,
                as_of_date=str(term_date.date()) if pd.notna(term_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_missing_supporting_termination_evidence_reference(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())

    if terminations.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    for _, row in term.iterrows():
        emp_id = str(row["employee_id"]).strip()
        if not emp_id:
            continue

        evidence_ref = str(
            row.get("evidence_ref")
            or row.get("termination_evidence")
            or row.get("document_id")
            or ""
        ).strip()

        if evidence_ref:
            continue

        term_date = row["termination_date"]

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv"],
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": str(term_date.date()) if pd.notna(term_date) else None,
                },
                "values": {
                    "evidence_ref": None,
                },
                "explanation": "Termination record has no supporting evidence reference.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=emp_id,
                leave_type=None,
                as_of_date=str(term_date.date()) if pd.notna(term_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings