from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import pandas as pd
import json
import hashlib


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


