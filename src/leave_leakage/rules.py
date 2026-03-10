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

    if rule_id == "LEAVE-006":
        if leave_snapshot.empty or leave_ledger.empty:
            return []
        return _run_leave_006_missing_ledger(rule, leave_snapshot, leave_ledger)

    if rule_id == "LEAVE-007":
        if employee_master.empty or leave_ledger.empty or "termination_date" not in employee_master.columns:
            return []
        return _run_leave_007_after_termination(rule, employee_master, leave_ledger)

    if rule_id == "LEAVE-008":
        if leave_ledger.empty:
            return []
        return _run_leave_008_duplicate_entries(rule, leave_ledger)

    if rule_id == "LEAVE-009":
        if leave_snapshot.empty:
            return []
        return _run_leave_009_extreme_balance(rule, leave_snapshot)

    if rule_id == "LEAVE-010":
        if leave_ledger.empty:
            return []
        return _run_leave_010_missing_leave_type(rule, leave_ledger)

    if rule_id == "LEAVE-011":
        if leave_ledger.empty:
            return []
        return _run_leave_011_missing_timestamp(rule, leave_ledger)

    if rule_id == "LEAVE-012":
        if leave_ledger.empty:
            return []
        return _run_leave_012_manual_adjustments(rule, leave_ledger)

    if rule_id == "LEAVE-013":
        if employee_master.empty or leave_ledger.empty or "termination_date" not in employee_master.columns:
            return []
        return _run_leave_013_accrual_after_termination(rule, employee_master, leave_ledger)

    if rule_id == "LEAVE-014":
        if leave_snapshot.empty or leave_ledger.empty:
            return []
        return _run_leave_014_taken_exceeds_balance(rule, leave_snapshot, leave_ledger)

    if rule_id == "LEAVE-015":
        if leave_ledger.empty:
            return []
        return _run_leave_015_zero_unit_event(rule, leave_ledger)

    if rule_id == "LEAVE-016":
        if leave_snapshot.empty or leave_ledger.empty:
            return []
        return _run_leave_016_snapshot_type_not_in_ledger(rule, leave_snapshot, leave_ledger)

    if rule_id == "LEAVE-017":
        if employee_master.empty or leave_ledger.empty:
            return []
        return _run_leave_017_unknown_employee_ledger(rule, employee_master, leave_ledger)

    if rule_id == "LEAVE-018":
        if employee_master.empty or leave_snapshot.empty:
            return []
        return _run_leave_018_unknown_employee_snapshot(rule, employee_master, leave_snapshot)

    if rule_id == "LEAVE-019":
        if leave_ledger.empty:
            return []
        return _run_leave_019_invalid_event_type(rule, leave_ledger)

    return []