from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

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
    evidence_str: str,
    diff_units: float | None = None,
) -> Finding:
    return Finding(
        employee_id=employee_id,
        leave_type=leave_type,
        as_of_date=as_of_date,
        rule_code=rule["id"],
        severity=rule["severity"],
        message=rule["text"]["finding"],
        diff_units=diff_units,
        evidence=evidence_str,
        finding_id=compute_finding_id(rule["id"], evidence_str),
        next_action=rule["text"]["remediation"],
    )


def _heuristic_gap_hours(
    service_years: float,
    eligibility_years: float,
    full_years: float,
    hours_per_day: float,
) -> Tuple[float, float]:
    """
    Indicative-only exposure sizing (NOT a statutory entitlement calc).
    Returns (low_hours, high_hours).
    """
    if service_years < eligibility_years:
        return 0.0, 0.0

    if service_years >= full_years:
        low = hours_per_day * 5 * 3
        high = hours_per_day * 5 * 5
        return low, high

    span = full_years - eligibility_years
    if span <= 0:
        return 0.0, 0.0

    factor = (service_years - eligibility_years) / span
    base_low = hours_per_day * 5 * 1
    base_high = hours_per_day * 5 * 3
    return base_low * factor, base_high * factor


def prepare_lsl_state(
    employees: pd.DataFrame,
    snapshot: pd.DataFrame,
    pay_rates: Optional[pd.DataFrame],
    snapshot_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Returns per-employee rows with:
    - service_years
    - latest LSL balance_units (if any)
    - lsl_as_of_date
    - hourly_rate (optional)
    """
    emp = employees.copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()

    emp["start_date"] = pd.to_datetime(emp["start_date"], errors="coerce")

    if "end_date" in emp.columns:
        emp["end_date"] = pd.to_datetime(emp["end_date"], errors="coerce")
    else:
        emp["end_date"] = pd.NaT

    effective_end = emp["end_date"].where(emp["end_date"].notna(), snapshot_date)
    effective_end = effective_end.clip(upper=snapshot_date)

    service_days = (effective_end - emp["start_date"]).dt.days
    emp["service_years"] = service_days.clip(lower=0).astype(float) / 365.25

    snap = snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")

    snap_lsl = snap[snap["leave_type"].astype(str).str.upper().str.contains("LSL", na=False)].copy()

    if not snap_lsl.empty:
        snap_lsl = snap_lsl.sort_values(["employee_id", "as_of_date"])
        latest_lsl = (
            snap_lsl.groupby("employee_id")
            .tail(1)[["employee_id", "as_of_date", "balance_units"]]
            .rename(columns={"as_of_date": "lsl_as_of_date", "balance_units": "lsl_balance_units"})
        )
    else:
        latest_lsl = pd.DataFrame(columns=["employee_id", "lsl_as_of_date", "lsl_balance_units"])

    state = emp.merge(latest_lsl, on="employee_id", how="left")

    if pay_rates is not None and not pay_rates.empty:
        rates = pay_rates.copy()
        rates["employee_id"] = rates["employee_id"].astype(str).str.strip()

        if "as_of_date" in rates.columns:
            rates["as_of_date"] = pd.to_datetime(rates["as_of_date"], errors="coerce")
            rates = rates.sort_values(["employee_id", "as_of_date"])
            rates = rates.groupby("employee_id").tail(1)

        hours_per_year = 38.0 * 52.0
        if "hourly_rate" not in rates.columns:
            rates["hourly_rate"] = pd.NA

        if "annual_salary" in rates.columns:
            mask = rates["hourly_rate"].isna() & rates["annual_salary"].notna()
            rates.loc[mask, "hourly_rate"] = rates.loc[mask, "annual_salary"] / hours_per_year

        rates = rates[["employee_id", "hourly_rate"]]
        state = state.merge(rates, on="employee_id", how="left")
    else:
        state["hourly_rate"] = pd.NA

    state["snapshot_date"] = snapshot_date
    return state


def _run_lsl_001_missing_for_eligible(rule: dict, state: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    eligibility_years = float(rule.get("config", {}).get("eligibility_years", 7.0))

    eligible = state[state["service_years"] >= eligibility_years].copy()
    missing = eligible[eligible["lsl_balance_units"].isna()].copy()

    for _, row in missing.iterrows():
        as_of = row["snapshot_date"]
        evidence_str = json.dumps(
            {
                "sources": ["employees.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": "LSL",
                    "as_of_date": str(as_of.date()),
                },
                "values": {
                    "service_years": float(row["service_years"]),
                    "lsl_balance_present": False,
                },
                "thresholds": {
                    "eligibility_years": float(eligibility_years),
                },
                "explanation": (
                    "Employee has reached the configured LSL eligibility milestone, "
                    "but no LSL balance record was found in the snapshot."
                ),
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type="LSL",
                as_of_date=str(as_of.date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def _run_lsl_002_negative_balance(rule: dict, state: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    bad = state[state["lsl_balance_units"].notna() & (state["lsl_balance_units"] < 0)].copy()
    for _, row in bad.iterrows():
        as_of = row["lsl_as_of_date"]
        if pd.isna(as_of):
            as_of = row["snapshot_date"]

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": "LSL",
                    "as_of_date": str(as_of.date()),
                },
                "values": {
                    "lsl_balance_units": float(row["lsl_balance_units"]),
                    "service_years": float(row["service_years"]),
                },
                "thresholds": {"expected": "lsl_balance_units >= 0"},
                "explanation": (
                    "Negative LSL balances are usually invalid and indicate data or configuration issues."
                ),
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type="LSL",
                as_of_date=str(as_of.date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def _run_lsl_003_zero_balance_for_long_tenure(rule: dict, state: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    eligibility_years = float(rule.get("config", {}).get("eligibility_years", 7.0))

    eligible = state[state["service_years"] >= eligibility_years].copy()
    bad = eligible[eligible["lsl_balance_units"].notna() & (eligible["lsl_balance_units"] == 0)].copy()

    for _, row in bad.iterrows():
        as_of = row["lsl_as_of_date"]
        if pd.isna(as_of):
            as_of = row["snapshot_date"]

        evidence_str = json.dumps(
            {
                "sources": ["employees.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": "LSL",
                    "as_of_date": str(as_of.date()),
                },
                "values": {
                    "service_years": float(row["service_years"]),
                    "lsl_balance_units": float(row["lsl_balance_units"]),
                },
                "thresholds": {
                    "eligibility_years": float(eligibility_years),
                },
                "explanation": (
                    "Eligible employees typically accrue some LSL over time; "
                    "a zero balance may indicate missing configuration or tracking."
                ),
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type="LSL",
                as_of_date=str(as_of.date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def _run_lsl_004_balance_suspiciously_low(rule: dict, state: pd.DataFrame) -> list[Finding]:
    findings: list[Finding] = []

    full_years = float(rule.get("config", {}).get("full_years", 10.0))
    low_floor_units = float(rule.get("config", {}).get("low_floor_units", 20.0))

    bad = state[
        (state["service_years"] >= full_years)
        & state["lsl_balance_units"].notna()
        & (state["lsl_balance_units"] < low_floor_units)
    ].copy()

    for _, row in bad.iterrows():
        as_of = row["lsl_as_of_date"]
        if pd.isna(as_of):
            as_of = row["snapshot_date"]

        evidence_str = json.dumps(
            {
                "sources": ["employees.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": "LSL",
                    "as_of_date": str(as_of.date()),
                },
                "values": {
                    "service_years": float(row["service_years"]),
                    "lsl_balance_units": float(row["lsl_balance_units"]),
                },
                "thresholds": {
                    "full_entitlement_reference_years": float(full_years),
                    "low_balance_floor_units": float(low_floor_units),
                },
                "explanation": (
                    "Long-tenured employees usually hold more LSL. "
                    "A very low balance may indicate configuration or data issues."
                ),
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type="LSL",
                as_of_date=str(as_of.date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def compute_exposure_band(
    state: pd.DataFrame,
    eligibility_years: float,
    full_years: float,
    hours_per_day: float,
) -> Tuple[float, float]:
    """
    Sum indicative exposure band (AUD) across employees where hourly_rate is available.
    Uses the same heuristic gap hours function.
    """
    total_low = 0.0
    total_high = 0.0

    for _, row in state.iterrows():
        if pd.isna(row.get("hourly_rate")):
            continue

        hourly = float(row["hourly_rate"])
        service_years = float(row["service_years"]) if pd.notna(row["service_years"]) else 0.0
        lsl_units = float(row["lsl_balance_units"]) if pd.notna(row["lsl_balance_units"]) else None

        gap_low, gap_high = _heuristic_gap_hours(service_years, eligibility_years, full_years, hours_per_day)

        if lsl_units is not None:
            gap_low = max(0.0, gap_low - lsl_units)
            gap_high = max(0.0, gap_high - lsl_units)

        total_low += gap_low * hourly
        total_high += gap_high * hourly

    return total_low, total_high


def run_rule(rule: dict, datasets: dict[str, pd.DataFrame], state: pd.DataFrame | None = None) -> list[Finding]:
    rule_id = rule["id"]

    if state is None or state.empty:
        return []

    if rule_id == "LSL-001":
        return _run_lsl_001_missing_for_eligible(rule, state)

    if rule_id == "LSL-002":
        return _run_lsl_002_negative_balance(rule, state)

    if rule_id == "LSL-003":
        return _run_lsl_003_zero_balance_for_long_tenure(rule, state)

    if rule_id == "LSL-004":
        return _run_lsl_004_balance_suspiciously_low(rule, state)

    return []