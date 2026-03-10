from __future__ import annotations

import json
import pandas as pd

from leave_leakage.models import Finding, _build_finding


def _run_leave_020_taken_without_approved_request(
    rule: dict,
    ledger: pd.DataFrame,
    leave_requests: pd.DataFrame,
) -> list[Finding]:
    findings: list[Finding] = []

    taken = ledger[ledger["event_type"].astype(str).str.upper() == "TAKEN"].copy()
    approved = leave_requests[
        leave_requests["approval_status"].astype(str).str.upper() == "APPROVED"
    ].copy()

    for _, row in taken.iterrows():
        employee_id = str(row["employee_id"]).strip()
        leave_type = str(row["leave_type"]).strip() if pd.notna(row["leave_type"]) else None
        event_date = row["event_date"]

        if pd.isna(event_date) or leave_type is None:
            continue

        matches = approved[
            (approved["employee_id"].astype(str).str.strip() == employee_id)
            & (approved["leave_type"].astype(str).str.strip() == leave_type)
            & (approved["request_start_date"] <= event_date)
            & (approved["request_end_date"] >= event_date)
        ]

        if matches.empty:
            evidence_str = json.dumps(
                {
                    "sources": ["leave_ledger.csv", "leave_requests.csv"],
                    "primary_keys": {
                        "employee_id": employee_id,
                        "leave_type": leave_type,
                        "event_date": str(event_date.date()) if pd.notna(event_date) else None,
                    },
                    "values": {
                        "event_type": str(row["event_type"]),
                        "units": float(row["units"]) if pd.notna(row["units"]) else None,
                        "approved_request_found": False,
                    },
                    "explanation": "Leave TAKEN event has no matching approved leave request covering the event date.",
                },
                ensure_ascii=False,
            )

            findings.append(
                _build_finding(
                    rule=rule,
                    employee_id=employee_id,
                    leave_type=leave_type,
                    as_of_date=str(event_date.date()),
                    message=rule["text"]["finding"],
                    evidence_str=evidence_str,
                )
            )

    return findings


def _run_leave_021_taken_before_approval_date(
    rule: dict,
    ledger: pd.DataFrame,
    leave_requests: pd.DataFrame,
) -> list[Finding]:
    findings: list[Finding] = []

    taken = ledger[ledger["event_type"].astype(str).str.upper() == "TAKEN"].copy()
    approved = leave_requests[
        leave_requests["approval_status"].astype(str).str.upper() == "APPROVED"
    ].copy()

    for _, row in taken.iterrows():
        employee_id = str(row["employee_id"]).strip()
        leave_type = str(row["leave_type"]).strip() if pd.notna(row["leave_type"]) else None
        event_date = row["event_date"]

        if pd.isna(event_date) or leave_type is None:
            continue

        matches = approved[
            (approved["employee_id"].astype(str).str.strip() == employee_id)
            & (approved["leave_type"].astype(str).str.strip() == leave_type)
            & (approved["request_start_date"] <= event_date)
            & (approved["request_end_date"] >= event_date)
            & (approved["approval_date"].notna())
        ]

        for _, req in matches.iterrows():
            approval_date = req["approval_date"]
            if pd.notna(approval_date) and event_date < approval_date:
                evidence_str = json.dumps(
                    {
                        "sources": ["leave_ledger.csv", "leave_requests.csv"],
                        "primary_keys": {
                            "employee_id": employee_id,
                            "leave_type": leave_type,
                            "event_date": str(event_date.date()),
                            "request_id": str(req["request_id"]),
                        },
                        "values": {
                            "leave_event_date": str(event_date.date()),
                            "approval_date": str(approval_date.date()),
                            "units": float(row["units"]) if pd.notna(row["units"]) else None,
                        },
                        "thresholds": {
                            "rule": "event_date >= approval_date",
                        },
                        "explanation": "Leave event occurred before the recorded approval date.",
                    },
                    ensure_ascii=False,
                )

                findings.append(
                    _build_finding(
                        rule=rule,
                        employee_id=employee_id,
                        leave_type=leave_type,
                        as_of_date=str(event_date.date()),
                        message=rule["text"]["finding"],
                        evidence_str=evidence_str,
                    )
                )

    return findings


def _run_leave_022_leave_and_work_same_day(
    rule: dict,
    ledger: pd.DataFrame,
    timesheets: pd.DataFrame,
) -> list[Finding]:
    findings: list[Finding] = []

    taken = ledger[ledger["event_type"].astype(str).str.upper() == "TAKEN"].copy()
    worked = timesheets[timesheets["hours_worked"].fillna(0) > 0].copy()

    merged = taken.merge(
        worked,
        left_on=["employee_id", "event_date"],
        right_on=["employee_id", "work_date"],
        how="inner",
    )

    for _, row in merged.iterrows():
        event_date = row["event_date"]

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "timesheets.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(event_date.date()) if pd.notna(event_date) else None,
                },
                "values": {
                    "leave_units": float(row["units"]) if pd.notna(row["units"]) else None,
                    "hours_worked": float(row["hours_worked"]) if pd.notna(row["hours_worked"]) else None,
                    "timesheet_status": str(row["timesheet_status"]) if pd.notna(row["timesheet_status"]) else None,
                },
                "explanation": "Leave event and worked hours were both recorded on the same day.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(event_date.date()) if pd.notna(event_date) else None,
                message=rule["text"]["finding"],
                evidence_str=evidence_str,
            )
        )

    return findings


def _run_leave_023_combined_leave_and_work_exceeds_threshold(
    rule: dict,
    ledger: pd.DataFrame,
    timesheets: pd.DataFrame,
) -> list[Finding]:
    findings: list[Finding] = []

    max_combined_units = float(rule.get("config", {}).get("max_combined_units", 12.0))

    taken = ledger[ledger["event_type"].astype(str).str.upper() == "TAKEN"].copy()
    worked = timesheets[timesheets["hours_worked"].fillna(0) > 0].copy()

    merged = taken.merge(
        worked,
        left_on=["employee_id", "event_date"],
        right_on=["employee_id", "work_date"],
        how="inner",
    )

    merged["combined_units"] = merged["units"].abs() + merged["hours_worked"]
    bad = merged[merged["combined_units"] > max_combined_units].copy()

    for _, row in bad.iterrows():
        event_date = row["event_date"]

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "timesheets.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(event_date.date()) if pd.notna(event_date) else None,
                },
                "values": {
                    "leave_units_abs": float(abs(row["units"])) if pd.notna(row["units"]) else None,
                    "hours_worked": float(row["hours_worked"]) if pd.notna(row["hours_worked"]) else None,
                    "combined_units": float(row["combined_units"]) if pd.notna(row["combined_units"]) else None,
                },
                "thresholds": {
                    "max_combined_units": max_combined_units,
                },
                "explanation": "Combined leave and worked hours exceeded the configured daily threshold.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(event_date.date()) if pd.notna(event_date) else None,
                message=rule["text"]["finding"],
                evidence_str=evidence_str,
            )
        )

    return findings