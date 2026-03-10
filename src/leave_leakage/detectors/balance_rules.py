from __future__ import annotations

import json
import pandas as pd

from leave_leakage.models import Finding, _build_finding


def _run_leave_001_negative_balance(rule: dict, snapshot: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    bad = snapshot[snapshot["balance_units"] < 0].copy()
    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                },
                "values": {
                    "snapshot_balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                },
                "thresholds": {
                    "expected": "balance_units >= 0",
                },
                "explanation": f"Snapshot balance is negative ({float(row['balance_units'])}).",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                message=rule["text"]["finding"],
                evidence_str=evidence_str,
            )
        )

    return findings

def _run_leave_005_balance_mismatch(rule: dict, snapshot: pd.DataFrame, ledger_recon: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    tolerance = float(rule.get("config", {}).get("tolerance_units", 0.01))

    mismatches = ledger_recon[(ledger_recon["diff_units"].abs() > tolerance)].copy()

    for _, row in mismatches.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                },
                "values": {
                    "ledger_derived_balance": float(row["ledger_balance_units"]),
                    "snapshot_balance": float(row["balance_units"]),
                    "difference": float(row["diff_units"]),
                },
                "thresholds": {
                    "tolerance_hours": float(tolerance),
                },
                "explanation": (
                    f"Ledger-derived balance differs from snapshot by "
                    f"{abs(float(row['diff_units'])):.2f} hours, "
                    f"exceeding tolerance {float(tolerance):.2f} hours."
                ),
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                message=rule["text"]["finding"],
                evidence_str=evidence_str,
                diff_units=float(row["diff_units"]),
            )
        )

    return findings

def _run_leave_009_extreme_balance(rule: dict, snapshot: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    threshold = 500

    bad = snapshot[snapshot["balance_units"] > threshold]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(row["as_of_date"].date()),
                },
                "values": {
                    "balance_units": float(row["balance_units"]),
                    "threshold": threshold,
                },
                "explanation": "Leave balance exceeds expected threshold.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule,
                str(row["employee_id"]),
                str(row["leave_type"]),
                str(row["as_of_date"].date()),
                rule["text"]["finding"],
                evidence_str,
            )
        )

    return findings

def _run_leave_014_taken_exceeds_balance(rule: dict, snapshot: pd.DataFrame, ledger: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    merged = ledger.merge(
        snapshot[["employee_id", "leave_type", "balance_units"]],
        on=["employee_id", "leave_type"],
        how="left"
    )

    bad = merged[
        (merged["event_type"] == "TAKEN") &
        (merged["units"] < 0) &
        (merged["balance_units"].notna()) &
        (abs(merged["units"]) > merged["balance_units"])
    ]

    for _, row in bad.iterrows():

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                },
                "values": {
                    "leave_taken_units": float(row["units"]),
                    "available_balance": float(row["balance_units"]),
                },
                "thresholds": {
                    "rule": "abs(units_taken) <= balance_units"
                },
                "explanation": "Leave taken exceeds the available balance.",
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