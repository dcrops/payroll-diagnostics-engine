from __future__ import annotations

import json
import pandas as pd

from leave_leakage.models import Finding, _build_finding
from common.nulls import is_missing


def _run_leave_002_event_sign_anomaly(rule: dict, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    bad = ledger[
        ((ledger["event_type"] == "ACCRUAL") & (ledger["units"] < 0)) |
        ((ledger["event_type"] == "TAKEN") & (ledger["units"] > 0))
    ].copy()

    if bad.empty:
        return findings

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                },
                "values": {
                    "event_type": str(row["event_type"]),
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                    "observed_sign": (
                        "positive" if float(row["units"]) > 0 else "negative" if float(row["units"]) < 0 else "zero"
                    ) if pd.notna(row["units"]) else None,
                    "expected_sign": "negative" if str(row["event_type"]).upper() == "TAKEN" else "positive",
                },
                "thresholds": {
                    "expected": "TAKEN units < 0, ACCRUAL units > 0",
                },
                "explanation": f"{str(row['event_type']).upper()} event has unexpected sign.",
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

def _run_leave_008_duplicate_entries(rule: dict, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    dup = ledger[ledger.duplicated(
        subset=["employee_id", "leave_type", "event_date", "units", "event_type"],
        keep=False
    )]

    for _, row in dup.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()),
                },
                "values": {
                    "units": float(row["units"]),
                    "event_type": str(row["event_type"]),
                },
                "explanation": "Duplicate ledger event detected.",
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

def _run_leave_015_zero_unit_event(rule: dict, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    bad = ledger[ledger["units"] == 0]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                },
                "values": {
                    "event_type": str(row["event_type"]),
                    "units": float(row["units"]),
                },
                "explanation": "Leave ledger event recorded with zero units.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                str(row["leave_type"]),
                str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings

def _run_leave_019_invalid_event_type(rule: dict, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    allowed = {"ACCRUAL", "TAKEN", "ADJUSTMENT"}

    bad = ledger[~ledger["event_type"].astype(str).str.upper().isin(allowed)]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                },
                "values": {
                    "event_type": str(row["event_type"]),
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                },
                "thresholds": {
                    "allowed_event_types": list(sorted(allowed)),
                },
                "explanation": "Leave ledger event type is not recognised.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                str(row["leave_type"]),
                str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings