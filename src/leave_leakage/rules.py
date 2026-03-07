from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import json
import hashlib


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


def compute_finding_id(rule_code: str, evidence_json: Optional[str]) -> str:
    """
    Deterministic ID based on rule_code + evidence.primary_keys.
    Stable across runs provided primary_keys remain stable.
    """
    primary_keys = {}
    if evidence_json:
        try:
            payload = json.loads(evidence_json)
            primary_keys = payload.get("primary_keys") or {}
        except Exception:
            primary_keys = {}

    parts = [rule_code]
    for k in sorted(primary_keys.keys()):
        parts.append(f"{k}={primary_keys.get(k)}")

    canonical = "|".join(parts)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]


def _build_finding(
    rule: dict,
    employee_id: str | None,
    leave_type: str | None,
    as_of_date: str | None,
    message: str,
    evidence_str: str,
    diff_units: float | None = None,
) -> Finding:
    return Finding(
        employee_id=employee_id,
        leave_type=leave_type,
        as_of_date=as_of_date,
        rule_code=rule["id"],
        severity=rule["severity"],
        message=message,
        diff_units=diff_units,
        evidence=evidence_str,
        finding_id=compute_finding_id(rule["id"], evidence_str),
        next_action=rule["text"]["remediation"],
    )


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


def run_rule(rule: dict, datasets: dict[str, pd.DataFrame], ledger_recon: pd.DataFrame | None = None) -> list[Finding]:
    rule_id = rule["id"]

    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    employee_master = datasets.get("employee_master", pd.DataFrame())

    if rule_id == "LEAVE-001":
        if leave_snapshot.empty:
            return []
        return _run_leave_001_negative_balance(rule, leave_snapshot)

    if rule_id == "LEAVE-002":
        if leave_ledger.empty:
            return []
        return _run_leave_002_event_sign_anomaly(rule, leave_ledger)

    if rule_id == "LEAVE-003":
        if employee_master.empty or leave_ledger.empty:
            return []
        return _run_leave_003_taken_before_start_date(rule, employee_master, leave_ledger)

    if rule_id == "LEAVE-004":
        if employee_master.empty or leave_ledger.empty:
            return []
        return _run_leave_004_casual_accrual_present(rule, employee_master, leave_ledger)

    if rule_id == "LEAVE-005":
        if leave_snapshot.empty or ledger_recon is None or ledger_recon.empty:
            return []
        return _run_leave_005_balance_mismatch(rule, leave_snapshot, ledger_recon)

    return []