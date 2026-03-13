from __future__ import annotations

import json
import pandas as pd

from leave_leakage.models import Finding, _build_finding
from common.nulls import is_missing


def _run_leave_006_missing_ledger(rule: dict, snapshot: pd.DataFrame, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    ledger_pairs = set(zip(ledger["employee_id"], ledger["leave_type"]))

    for _, row in snapshot.iterrows():
        key = (str(row["employee_id"]), str(row["leave_type"]))

        if key not in ledger_pairs and float(row["balance_units"]) != 0:
            evidence_str = json.dumps(
                {
                    "sources": ["balances_snapshot.csv", "leave_ledger.csv"],
                    "primary_keys": {
                        "employee_id": str(row["employee_id"]),
                        "leave_type": str(row["leave_type"]),
                        "as_of_date": str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                    },
                    "values": {
                        "snapshot_balance_units": float(row["balance_units"]),
                        "ledger_records_found": False,
                    },
                    "explanation": "Snapshot balance exists but no ledger records were found.",
                },
                ensure_ascii=False,
            )

            findings.append(
                _build_finding(
                    rule,
                    str(row["employee_id"]),
                    str(row["leave_type"]),
                    str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                    rule["text"]["finding"],
                    evidence_str,
                )
            )

    return findings

def _run_leave_010_missing_leave_type(rule: dict, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    bad = ledger[ledger["leave_type"].isna()]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "event_date": str(row["event_date"].date()),
                },
                "values": {
                    "units": float(row["units"]),
                    "event_type": str(row["event_type"]),
                },
                "explanation": "Ledger entry missing leave type.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                None,
                str(row["event_date"].date()),
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings

def _run_leave_011_missing_timestamp(rule: dict, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    bad = ledger[ledger["event_date"].isna()]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "units": float(row["units"]),
                    "event_type": str(row["event_type"]),
                },
                "explanation": "Ledger event missing timestamp.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                str(row["leave_type"]),
                None,
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings

def _run_leave_016_snapshot_type_not_in_ledger(rule: dict, snapshot: pd.DataFrame, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    ledger_types = set(ledger["leave_type"].dropna().unique())

    bad = snapshot[~snapshot["leave_type"].isin(ledger_types)]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                },
                "values": {
                    "snapshot_leave_type": str(row["leave_type"]),
                    "ledger_leave_types": list(sorted(ledger_types)),
                },
                "explanation": "Leave type present in snapshot but absent from ledger dataset.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                str(row["leave_type"]),
                str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings

def _run_leave_017_unknown_employee_ledger(rule: dict, employees: pd.DataFrame, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    known_ids = set(employees["employee_id"].astype(str).str.strip())

    bad = ledger[~ledger["employee_id"].astype(str).str.strip().isin(known_ids)]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "employees.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                },
                "values": {
                    "event_type": str(row["event_type"]),
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                },
                "explanation": "Leave ledger event references an employee not present in the employee master dataset.",
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

def _run_leave_018_unknown_employee_snapshot(rule: dict, employees: pd.DataFrame, snapshot: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    known_ids = set(employees["employee_id"].astype(str).str.strip())

    bad = snapshot[~snapshot["employee_id"].astype(str).str.strip().isin(known_ids)]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv", "employees.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                },
                "values": {
                    "balance_units": float(row["balance_units"]),
                },
                "explanation": "Leave balance exists for an employee not present in the employee master dataset.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                str(row["leave_type"]),
                str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings