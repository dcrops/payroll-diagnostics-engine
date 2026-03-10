from __future__ import annotations

import json
import pandas as pd

from leave_leakage.models import Finding, _build_finding


def _run_leave_003_taken_before_start_date(rule: dict, employees: pd.DataFrame, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    emp = employees[["employee_id", "start_date"]].copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()
    emp["start_date"] = pd.to_datetime(emp["start_date"], errors="coerce")
    start_map = dict(zip(emp["employee_id"], emp["start_date"]))

    ledger = ledger.copy()
    ledger["employee_id"] = ledger["employee_id"].astype(str).str.strip()
    ledger["event_type"] = ledger["event_type"].astype(str).str.strip().str.upper()

    taken = ledger[ledger["event_type"] == "TAKEN"].copy()

    for _, row in taken.iterrows():
        employee_id = str(row["employee_id"]).strip()
        start_date = start_map.get(employee_id)

        if start_date is None or pd.isna(start_date):
            continue

        event_date = row["event_date"]
        if pd.isna(event_date):
            continue

        if event_date < start_date:
            evidence_str = json.dumps(
                {
                    "sources": ["employees.csv", "leave_ledger.csv"],
                    "primary_keys": {
                        "employee_id": str(employee_id),
                        "leave_type": str(row["leave_type"]),
                        "event_date": str(event_date.date()) if pd.notna(event_date) else None,
                    },
                    "values": {
                        "event_type": str(row["event_type"]),
                        "units": float(row["units"]) if pd.notna(row["units"]) else None,
                        "employee_start_date": str(start_date.date()) if pd.notna(start_date) else None,
                    },
                    "thresholds": {
                        "rule": "event_date < start_date (TAKEN only)",
                    },
                    "explanation": (
                        f"Leave TAKEN on {str(event_date.date())} occurs before employee start date "
                        f"{str(start_date.date())}."
                    ),
                },
                ensure_ascii=False,
            )

            findings.append(
                _build_finding(
                    rule=rule,
                    employee_id=employee_id,
                    leave_type=str(row["leave_type"]),
                    as_of_date=str(event_date.date()),
                    message=rule["text"]["finding"],
                    evidence_str=evidence_str,
                )
            )

    return findings

def _run_leave_007_after_termination(rule: dict, employees: pd.DataFrame, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    emp = employees[["employee_id", "termination_date"]].copy()
    emp["termination_date"] = pd.to_datetime(emp["termination_date"], errors="coerce")

    merged = ledger.merge(emp, on="employee_id", how="left")

    bad = merged[
        (merged["termination_date"].notna()) &
        (merged["event_date"] > merged["termination_date"])
    ]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "employees.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()),
                },
                "values": {
                    "termination_date": str(row["termination_date"].date()),
                    "units": float(row["units"]),
                },
                "explanation": "Leave transaction occurred after termination date.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                str(row["leave_type"]),
                str(row["event_date"].date()),
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings

def _run_leave_013_accrual_after_termination(rule: dict, employees: pd.DataFrame, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    emp = employees[["employee_id", "termination_date"]].copy()
    emp["termination_date"] = pd.to_datetime(emp["termination_date"], errors="coerce")

    merged = ledger.merge(emp, on="employee_id", how="left")

    bad = merged[
        (merged["event_type"] == "ACCRUAL") &
        (merged["termination_date"].notna()) &
        (merged["event_date"] > merged["termination_date"])
    ]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "employees.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()),
                },
                "values": {
                    "termination_date": str(row["termination_date"].date()),
                    "units": float(row["units"]),
                },
                "explanation": "Leave accrual posted after employee termination.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                str(row["leave_type"]),
                str(row["event_date"].date()),
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings