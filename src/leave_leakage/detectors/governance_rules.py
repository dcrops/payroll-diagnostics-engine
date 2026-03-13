from __future__ import annotations

import json
import pandas as pd

from leave_leakage.models import Finding, _build_finding
from common.nulls import is_missing


def _run_leave_004_casual_accrual_present(rule: dict, employees: pd.DataFrame, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    merged = ledger.merge(
        employees[["employee_id", "employment_type"]],
        on="employee_id",
        how="left",
    )

    merged["employment_type"] = merged["employment_type"].astype(str)

    accruals = merged[
        (merged["employment_type"] == "CASUAL")
        & (merged["event_type"] == "ACCRUAL")
        & (merged["leave_type"].isin(["ANNUAL", "PERSONAL"]))
    ]

    for _, row in accruals.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["employees.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                },
                "values": {
                    "employment_type": str(row["employment_type"]),
                    "event_type": str(row["event_type"]),
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                },
                "thresholds": {
                    "expected": "CASUAL employees should not have leave ACCRUAL events",
                },
                "explanation": (
                    f"Employee is CASUAL but has an ACCRUAL event "
                    f"on {str(row['event_date'].date())} for {float(row['units'])} units."
                ),
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                message=rule["text"]["finding"],
                evidence_str=evidence_str,
            )
        )

    return findings

def _run_leave_012_manual_adjustments(rule: dict, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    if "event_type" not in ledger.columns:
        return findings

    adj = ledger[ledger["event_type"] == "ADJUSTMENT"].copy()

    if adj.empty:
        return findings

    counts = adj.groupby("employee_id").size()
    bad = counts[counts > 5]

    for emp_id, adjustment_count in bad.items():
        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(emp_id),
                },
                "values": {
                    "adjustment_count": int(adjustment_count),
                },
                "thresholds": {
                    "rule": "adjustment_count > 5",
                },
                "explanation": "High number of manual leave adjustments detected for employee.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(emp_id),
                leave_type=None,
                as_of_date=None,
                message=rule["text"]["finding"],
                evidence_str=evidence_str,
            )
        )

    return findings