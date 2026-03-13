from __future__ import annotations

import json
import pandas as pd

from lsl_exposure.models import Finding, _build_finding
from common.nulls import is_missing


def detect_missing_lsl_balance_record(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    employees = datasets.get("employee_master", pd.DataFrame())
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    state = context.get("state")

    if employees.empty:
        return []

    findings: list[Finding] = []

    snapshot_lsl = (
        snapshot[snapshot["leave_type"].astype(str).str.upper().str.contains("LSL", na=False)].copy()
        if not snapshot.empty
        else pd.DataFrame(columns=["employee_id"])
    )

    lsl_ids = set(snapshot_lsl["employee_id"].astype(str).str.strip()) if not snapshot_lsl.empty else set()

    emp = employees.copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()

    if "employment_type" in emp.columns:
        emp = emp[emp["employment_type"].astype(str).str.upper() != "CASUAL"]

    if state is not None and not state.empty:
        eligible_ids = set(
            state[state["service_years"] >= 1]["employee_id"].astype(str).str.strip()
        )
        bad = emp[
            (~emp["employee_id"].isin(lsl_ids))
            & (emp["employee_id"].isin(eligible_ids))
        ].copy()
    else:
        bad = emp[~emp["employee_id"].isin(lsl_ids)].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["employees.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                },
                "values": {
                    "employment_type": str(row["employment_type"]) if "employment_type" in row else None,
                },
                "explanation": "Employee has no corresponding LSL balance record in snapshot.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type="LSL",
                as_of_date=None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_multiple_lsl_leave_types(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    if snapshot.empty:
        return []

    findings: list[Finding] = []

    snap = snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")

    lsl_rows = snap[snap["leave_type"].str.upper().str.contains("LSL", na=False)].copy()
    if lsl_rows.empty:
        return []

    counts = (
        lsl_rows.groupby("employee_id")["leave_type"]
        .nunique()
        .reset_index(name="lsl_type_count")
    )

    bad_ids = counts[counts["lsl_type_count"] > 1]["employee_id"].tolist()
    if not bad_ids:
        return []

    bad_rows = lsl_rows[lsl_rows["employee_id"].isin(bad_ids)].copy()

    for employee_id, group in bad_rows.groupby("employee_id"):
        leave_types = sorted(group["leave_type"].dropna().astype(str).unique().tolist())
        latest_as_of = group["as_of_date"].max()

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(employee_id),
                    "as_of_date": str(latest_as_of.date()) if pd.notna(latest_as_of) else None,
                },
                "values": {
                    "lsl_leave_types": leave_types,
                    "lsl_type_count": len(leave_types),
                },
                "explanation": "Multiple LSL leave types were identified for the same employee.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(employee_id),
                leave_type="LSL",
                as_of_date=str(latest_as_of.date()) if pd.notna(latest_as_of) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_duplicate_lsl_balance_records(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    if snapshot.empty:
        return []

    findings: list[Finding] = []

    snap = snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")

    lsl_rows = snap[snap["leave_type"].str.upper().str.contains("LSL", na=False)].copy()
    if lsl_rows.empty:
        return []

    dup = lsl_rows[
        lsl_rows.duplicated(
            subset=["employee_id", "leave_type", "as_of_date"],
            keep=False,
        )
    ].copy()

    if dup.empty:
        return []

    grouped = (
        dup.groupby(["employee_id", "leave_type", "as_of_date"], dropna=False)
        .size()
        .reset_index(name="duplicate_count")
    )

    for _, row in grouped.iterrows():
        as_of = row["as_of_date"]

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "duplicate_count": int(row["duplicate_count"]),
                },
                "explanation": "Duplicate LSL balance records were identified for the same employee, leave type and date.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(as_of.date()) if pd.notna(as_of) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_lsl_balance_without_ledger_history(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    ledger = datasets.get("leave_ledger", pd.DataFrame())
    state = context.get("state")

    if snapshot.empty:
        return []

    findings: list[Finding] = []

    snap = snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")

    # Positive LSL balances only
    snap_lsl = snap[
        snap["leave_type"].str.upper().str.contains("LSL", na=False)
        & snap["balance_units"].notna()
        & (snap["balance_units"] > 0)
    ].copy()

    if snap_lsl.empty:
        return []

    # Any employee with any LSL ledger history
    if not ledger.empty and "leave_type" in ledger.columns and "employee_id" in ledger.columns:
        led = ledger.copy()
        led["employee_id"] = led["employee_id"].astype(str).str.strip()
        led["leave_type"] = led["leave_type"].astype(str).str.strip()

        led_lsl = led[
            led["leave_type"].str.upper().str.contains("LSL", na=False)
        ].copy()

        employees_with_lsl_history = set(led_lsl["employee_id"].astype(str).str.strip())
    else:
        employees_with_lsl_history = set()

    # Optional noise reduction: only evaluate employees with >= 1 year service
    eligible_ids = None
    if state is not None and not state.empty and "service_years" in state.columns:
        eligible_ids = set(
            state[state["service_years"] >= 1]["employee_id"].astype(str).str.strip()
        )

    # Collapse to one finding per employee, using their latest positive LSL snapshot row
    latest_snap = (
        snap_lsl.sort_values(["employee_id", "as_of_date"])
        .groupby("employee_id", as_index=False)
        .tail(1)
    )

    for _, row in latest_snap.iterrows():
        employee_id = str(row["employee_id"]).strip()

        if eligible_ids is not None and employee_id not in eligible_ids:
            continue

        if employee_id in employees_with_lsl_history:
            continue

        as_of = row["as_of_date"]

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "lsl_balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "employee_has_any_lsl_ledger_history": False,
                },
                "explanation": "Employee has a positive LSL balance in snapshot but no LSL ledger history was found.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=str(row["leave_type"]),
                as_of_date=str(as_of.date()) if pd.notna(as_of) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_lsl_movement_after_termination(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    employees = datasets.get("employee_master", pd.DataFrame())
    ledger = datasets.get("leave_ledger", pd.DataFrame())

    if employees.empty or ledger.empty:
        return []

    findings: list[Finding] = []

    emp = employees.copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()

    if "termination_date" not in emp.columns:
        return []

    emp["termination_date"] = pd.to_datetime(emp["termination_date"], errors="coerce")

    led = ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")

    lsl_rows = led[led["leave_type"].astype(str).str.upper().str.contains("LSL", na=False)].copy()
    if lsl_rows.empty:
        return []

    merged = lsl_rows.merge(
        emp[["employee_id", "termination_date"]],
        on="employee_id",
        how="left",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["event_date"].notna()
        & (merged["event_date"] > merged["termination_date"])
    ].copy()

    for _, row in bad.iterrows():
        event_date = row["event_date"]
        termination_date = row["termination_date"]

        evidence_str = json.dumps(
            {
                "sources": ["employees.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(event_date.date()) if pd.notna(event_date) else None,
                },
                "values": {
                    "termination_date": str(termination_date.date()) if pd.notna(termination_date) else None,
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                    "event_type": str(row["event_type"]) if "event_type" in row and pd.notna(row["event_type"]) else None,
                },
                "explanation": "LSL movement was recorded after the employee termination date.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(event_date.date()) if pd.notna(event_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_invalid_service_start_basis(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    employees = datasets.get("employee_master", pd.DataFrame())
    state = context.get("state")

    if employees.empty:
        return []

    findings: list[Finding] = []

    emp = employees.copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()
    emp["start_date"] = pd.to_datetime(emp["start_date"], errors="coerce")

    snapshot_date = None
    if state is not None and not state.empty and "snapshot_date" in state.columns:
        snapshot_date = state["snapshot_date"].max()

    bad = emp[emp["start_date"].isna()].copy()

    if snapshot_date is not None and pd.notna(snapshot_date):
        future_start = emp[emp["start_date"].notna() & (emp["start_date"] > snapshot_date)].copy()
        bad = pd.concat([bad, future_start], ignore_index=True).drop_duplicates(subset=["employee_id"])

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["employees.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                },
                "values": {
                    "start_date": str(row["start_date"].date()) if pd.notna(row["start_date"]) else None,
                    "snapshot_date": str(snapshot_date.date()) if snapshot_date is not None and pd.notna(snapshot_date) else None,
                },
                "explanation": "Employee record has a missing or invalid service start basis for LSL calculation.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type="LSL",
                as_of_date=str(snapshot_date.date()) if snapshot_date is not None and pd.notna(snapshot_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_lsl_balance_with_missing_service_start(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

    findings: list[Finding] = []
    min_balance_units = float(rule.get("config", {}).get("min_balance_units", 0.01))

    bad = state[
        state["lsl_balance_units"].notna()
        & (state["lsl_balance_units"] >= min_balance_units)
        & state["start_date"].isna()
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
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "lsl_balance_units": float(row["lsl_balance_units"]) if pd.notna(row["lsl_balance_units"]) else None,
                    "start_date": None,
                    "service_years": float(row["service_years"]) if pd.notna(row["service_years"]) else None,
                },
                "thresholds": {
                    "min_balance_units": min_balance_units,
                },
                "explanation": "Employee has a positive LSL balance but no valid service start date is available.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type="LSL",
                as_of_date=str(as_of.date()) if pd.notna(as_of) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_lsl_ledger_history_without_snapshot_balance(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    ledger = datasets.get("leave_ledger", pd.DataFrame())
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if ledger.empty:
        return []

    findings: list[Finding] = []
    min_event_count = int(rule.get("config", {}).get("min_event_count", 1))

    led = ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")

    led_lsl = led[led["leave_type"].str.upper().str.contains("LSL", na=False)].copy()
    if led_lsl.empty:
        return []

    ledger_summary = (
        led_lsl.groupby("employee_id", as_index=False)
        .agg(
            ledger_event_count=("employee_id", "size"),
            latest_event_date=("event_date", "max"),
            sample_leave_type=("leave_type", "first"),
        )
    )

    if snapshot.empty:
        snapshot_ids = set()
    else:
        snap = snapshot.copy()
        snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
        snap["leave_type"] = snap["leave_type"].astype(str).str.strip()

        snap_lsl = snap[snap["leave_type"].str.upper().str.contains("LSL", na=False)].copy()
        snapshot_ids = set(snap_lsl["employee_id"].astype(str).str.strip())

    bad = ledger_summary[
        (ledger_summary["ledger_event_count"] >= min_event_count)
        & (~ledger_summary["employee_id"].isin(snapshot_ids))
    ].copy()

    for _, row in bad.iterrows():
        latest_event_date = row["latest_event_date"]

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": "LSL",
                    "event_date": str(latest_event_date.date()) if pd.notna(latest_event_date) else None,
                },
                "values": {
                    "ledger_event_count": int(row["ledger_event_count"]),
                    "snapshot_balance_present": False,
                },
                "thresholds": {
                    "min_event_count": min_event_count,
                },
                "explanation": "Employee has LSL ledger history but no corresponding LSL balance record in snapshot.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type="LSL",
                as_of_date=str(latest_event_date.date()) if pd.notna(latest_event_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_lsl_ledger_activity_after_snapshot_date(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    ledger = datasets.get("leave_ledger", pd.DataFrame())

    if snapshot.empty or ledger.empty:
        return []

    findings: list[Finding] = []

    snap = snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")

    led = ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")

    snap_lsl = snap[snap["leave_type"].str.upper().str.contains("LSL", na=False)].copy()
    led_lsl = led[led["leave_type"].str.upper().str.contains("LSL", na=False)].copy()

    if snap_lsl.empty or led_lsl.empty:
        return []

    latest_snap = (
        snap_lsl.sort_values(["employee_id", "as_of_date"])
        .groupby("employee_id", as_index=False)
        .tail(1)[["employee_id", "leave_type", "as_of_date", "balance_units"]]
    )

    ledger_max = (
        led_lsl.groupby("employee_id", as_index=False)
        .agg(max_ledger_event_date=("event_date", "max"))
    )

    merged = latest_snap.merge(ledger_max, on="employee_id", how="left")

    bad = merged[
        merged["as_of_date"].notna()
        & merged["max_ledger_event_date"].notna()
        & (merged["max_ledger_event_date"] > merged["as_of_date"])
    ].copy()

    for _, row in bad.iterrows():
        as_of = row["as_of_date"]
        max_ledger_event_date = row["max_ledger_event_date"]

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "snapshot_balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "snapshot_as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                    "max_ledger_event_date": str(max_ledger_event_date.date()) if pd.notna(max_ledger_event_date) else None,
                },
                "explanation": "LSL ledger activity exists after the snapshot balance date.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(as_of.date()) if pd.notna(as_of) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_lsl_balance_increase_without_supporting_accrual(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    ledger = datasets.get("leave_ledger", pd.DataFrame())

    if snapshot.empty:
        return []

    findings: list[Finding] = []
    accrual_event_types = {
        str(x).upper() for x in rule.get("config", {}).get("accrual_event_types", ["accrual", "adjustment", "opening_balance"])
    }
    min_increase_units = float(rule.get("config", {}).get("min_increase_units", 0.01))

    snap = snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap_lsl = (
        snap[snap["leave_type"].str.upper().str.contains("LSL", na=False)]
        .sort_values(["employee_id", "as_of_date"])
        .copy()
    )

    if snap_lsl.empty:
        return []

    snap_lsl["prior_as_of_date"] = snap_lsl.groupby("employee_id")["as_of_date"].shift(1)
    snap_lsl["prior_balance_units"] = snap_lsl.groupby("employee_id")["balance_units"].shift(1)
    snap_lsl["balance_increase_units"] = snap_lsl["balance_units"] - snap_lsl["prior_balance_units"]

    candidates = snap_lsl[
        snap_lsl["prior_as_of_date"].notna()
        & snap_lsl["balance_increase_units"].notna()
        & (snap_lsl["balance_increase_units"] >= min_increase_units)
    ].copy()

    if candidates.empty:
        return []

    if ledger.empty:
        led_lsl = pd.DataFrame(columns=["employee_id", "event_date", "event_type"])
    else:
        led = ledger.copy()
        led["employee_id"] = led["employee_id"].astype(str).str.strip()
        led["leave_type"] = led["leave_type"].astype(str).str.strip()
        led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
        led["event_type"] = led["event_type"].astype(str).str.strip().str.upper()

        led_lsl = led[
            led["leave_type"].str.upper().str.contains("LSL", na=False)
            & led["event_type"].isin(accrual_event_types)
        ].copy()

    for _, row in candidates.iterrows():
        employee_id = str(row["employee_id"])
        prior_as_of = row["prior_as_of_date"]
        current_as_of = row["as_of_date"]

        period_events = led_lsl[
            (led_lsl["employee_id"] == employee_id)
            & led_lsl["event_date"].notna()
            & (led_lsl["event_date"] > prior_as_of)
            & (led_lsl["event_date"] <= current_as_of)
        ]

        if not period_events.empty:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["balances_snapshot.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(current_as_of.date()) if pd.notna(current_as_of) else None,
                },
                "values": {
                    "prior_as_of_date": str(prior_as_of.date()) if pd.notna(prior_as_of) else None,
                    "prior_balance_units": float(row["prior_balance_units"]) if pd.notna(row["prior_balance_units"]) else None,
                    "current_as_of_date": str(current_as_of.date()) if pd.notna(current_as_of) else None,
                    "current_balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "balance_increase_units": float(row["balance_increase_units"]) if pd.notna(row["balance_increase_units"]) else None,
                    "supporting_accrual_events_found": 0,
                },
                "thresholds": {
                    "min_increase_units": min_increase_units,
                    "accrual_event_types": sorted(accrual_event_types),
                },
                "explanation": "LSL balance increased between snapshots but no supporting accrual-type ledger activity was found in the period.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=str(row["leave_type"]),
                as_of_date=str(current_as_of.date()) if pd.notna(current_as_of) else None,
                evidence_str=evidence_str,
                diff_units=float(row["balance_increase_units"]) if pd.notna(row["balance_increase_units"]) else None,
            )
        )

    return findings


def detect_lsl_accrual_activity_without_balance_change(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    ledger = datasets.get("leave_ledger", pd.DataFrame())

    if snapshot.empty or ledger.empty:
        return []

    findings: list[Finding] = []
    accrual_event_types = {
        str(x).upper() for x in rule.get("config", {}).get("accrual_event_types", ["accrual", "adjustment"])
    }
    balance_tolerance_units = float(rule.get("config", {}).get("balance_tolerance_units", 0.01))

    snap = snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap_lsl = (
        snap[snap["leave_type"].str.upper().str.contains("LSL", na=False)]
        .sort_values(["employee_id", "as_of_date"])
        .copy()
    )

    if snap_lsl.empty:
        return []

    snap_lsl["prior_as_of_date"] = snap_lsl.groupby("employee_id")["as_of_date"].shift(1)
    snap_lsl["prior_balance_units"] = snap_lsl.groupby("employee_id")["balance_units"].shift(1)
    snap_lsl["balance_delta_units"] = snap_lsl["balance_units"] - snap_lsl["prior_balance_units"]

    candidates = snap_lsl[
        snap_lsl["prior_as_of_date"].notna()
        & snap_lsl["balance_delta_units"].notna()
        & (snap_lsl["balance_delta_units"].abs() <= balance_tolerance_units)
    ].copy()

    if candidates.empty:
        return []

    led = ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
    led["event_type"] = led["event_type"].astype(str).str.strip().str.upper()
    led["units"] = pd.to_numeric(led["units"], errors="coerce")

    led_lsl = led[
        led["leave_type"].str.upper().str.contains("LSL", na=False)
        & led["event_type"].isin(accrual_event_types)
    ].copy()

    if led_lsl.empty:
        return []

    for _, row in candidates.iterrows():
        employee_id = str(row["employee_id"])
        prior_as_of = row["prior_as_of_date"]
        current_as_of = row["as_of_date"]

        period_events = led_lsl[
            (led_lsl["employee_id"] == employee_id)
            & led_lsl["event_date"].notna()
            & (led_lsl["event_date"] > prior_as_of)
            & (led_lsl["event_date"] <= current_as_of)
        ].copy()

        if period_events.empty:
            continue

        accrual_units_in_period = float(period_events["units"].fillna(0).sum())

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(current_as_of.date()) if pd.notna(current_as_of) else None,
                },
                "values": {
                    "prior_as_of_date": str(prior_as_of.date()) if pd.notna(prior_as_of) else None,
                    "prior_balance_units": float(row["prior_balance_units"]) if pd.notna(row["prior_balance_units"]) else None,
                    "current_as_of_date": str(current_as_of.date()) if pd.notna(current_as_of) else None,
                    "current_balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "balance_delta_units": float(row["balance_delta_units"]) if pd.notna(row["balance_delta_units"]) else None,
                    "accrual_event_count_in_period": int(len(period_events)),
                    "accrual_units_in_period": accrual_units_in_period,
                },
                "thresholds": {
                    "balance_tolerance_units": balance_tolerance_units,
                    "accrual_event_types": sorted(accrual_event_types),
                },
                "explanation": "Accrual-type LSL ledger activity exists between snapshots but the reported LSL balance did not materially change.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=str(row["leave_type"]),
                as_of_date=str(current_as_of.date()) if pd.notna(current_as_of) else None,
                evidence_str=evidence_str,
                diff_units=float(row["balance_delta_units"]) if pd.notna(row["balance_delta_units"]) else None,
            )
        )

    return findings

def detect_invalid_or_future_dated_lsl_ledger_event(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    ledger = datasets.get("leave_ledger", pd.DataFrame())
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if ledger.empty:
        return []

    findings: list[Finding] = []
    future_days_tolerance = int(rule.get("config", {}).get("future_days_tolerance", 0))

    reporting_cutoff = None
    if not snapshot.empty and "as_of_date" in snapshot.columns:
        snap = snapshot.copy()
        snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
        if snap["as_of_date"].notna().any():
            reporting_cutoff = snap["as_of_date"].max()

    led = ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip()

    original_event_date = led["event_date"].copy()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")

    lsl_rows = led[led["leave_type"].str.upper().str.contains("LSL", na=False)].copy()
    if lsl_rows.empty:
        return []

    invalid_mask = lsl_rows["event_date"].isna()

    if reporting_cutoff is not None and pd.notna(reporting_cutoff):
        future_limit = reporting_cutoff + pd.Timedelta(days=future_days_tolerance)
        future_mask = lsl_rows["event_date"].notna() & (lsl_rows["event_date"] > future_limit)
    else:
        future_limit = None
        future_mask = pd.Series(False, index=lsl_rows.index)

    bad = lsl_rows[invalid_mask | future_mask].copy()

    for idx, row in bad.iterrows():
        parsed_event_date = row["event_date"]
        raw_event_date = original_event_date.loc[idx]

        if pd.isna(parsed_event_date):
            explanation = "LSL ledger event has a missing or invalid event date."
        else:
            explanation = "LSL ledger event date falls after the reporting cut-off."

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(parsed_event_date.date()) if pd.notna(parsed_event_date) else None,
                },
                "values": {
                    "raw_event_date": str(raw_event_date) if pd.notna(raw_event_date) else None,
                    "parsed_event_date": str(parsed_event_date.date()) if pd.notna(parsed_event_date) else None,
                    "event_type": str(row["event_type"]) if "event_type" in row and pd.notna(row["event_type"]) else None,
                    "units": float(row["units"]) if "units" in row and pd.notna(row["units"]) else None,
                    "reporting_cutoff": str(reporting_cutoff.date()) if reporting_cutoff is not None and pd.notna(reporting_cutoff) else None,
                },
                "thresholds": {
                    "future_days_tolerance": future_days_tolerance,
                    "future_limit": str(future_limit.date()) if future_limit is not None and pd.notna(future_limit) else None,
                },
                "explanation": explanation,
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(parsed_event_date.date()) if pd.notna(parsed_event_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_terminated_employee_with_open_lsl_balance(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    employees = datasets.get("employee_master", pd.DataFrame())
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    ledger = datasets.get("leave_ledger", pd.DataFrame())

    if employees.empty or snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 0.01))
    closure_event_types = {
        str(x).upper() for x in rule.get("config", {}).get("closure_event_types", ["TAKEN", "ADJUSTMENT", "PAYOUT"])
    }

    emp = employees.copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()
    if "termination_date" not in emp.columns:
        return []
    emp["termination_date"] = pd.to_datetime(emp["termination_date"], errors="coerce")

    terminated = emp[emp["termination_date"].notna()].copy()
    if terminated.empty:
        return []

    snap = snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap_lsl = snap[
        snap["leave_type"].str.upper().str.contains("LSL", na=False)
        & snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap_lsl.empty:
        return []

    latest_snap = (
        snap_lsl.sort_values(["employee_id", "as_of_date"])
        .groupby("employee_id", as_index=False)
        .tail(1)
    )

    merged = latest_snap.merge(
        terminated[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    if merged.empty:
        return []

    if ledger.empty:
        led_lsl = pd.DataFrame(columns=["employee_id", "event_date", "event_type"])
    else:
        led = ledger.copy()
        led["employee_id"] = led["employee_id"].astype(str).str.strip()
        led["leave_type"] = led["leave_type"].astype(str).str.strip()
        led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
        led["event_type"] = led["event_type"].astype(str).str.strip().str.upper()

        led_lsl = led[
            led["leave_type"].str.upper().str.contains("LSL", na=False)
        ].copy()

    bad_rows = []

    for _, row in merged.iterrows():
        employee_id = str(row["employee_id"])
        termination_date = row["termination_date"]
        snapshot_as_of = row["as_of_date"]

        closure_events = led_lsl[
            (led_lsl["employee_id"] == employee_id)
            & led_lsl["event_date"].notna()
            & (led_lsl["event_date"] >= termination_date)
            & (led_lsl["event_date"] <= snapshot_as_of)
            & led_lsl["event_type"].isin(closure_event_types)
        ].copy()

        if closure_events.empty:
            bad_rows.append((row, 0))
            continue

        if "units" in closure_events.columns:
            closure_units = float(pd.to_numeric(closure_events["units"], errors="coerce").fillna(0).sum())
        else:
            closure_units = 0.0

        if closure_units <= 0:
            bad_rows.append((row, len(closure_events)))

    for row, closure_event_count in bad_rows:
        evidence_str = json.dumps(
            {
                "sources": ["employees.csv", "balances_snapshot.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "as_of_date": str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                },
                "values": {
                    "termination_date": str(row["termination_date"].date()) if pd.notna(row["termination_date"]) else None,
                    "snapshot_balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "closure_event_count": int(closure_event_count),
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "closure_event_types": sorted(closure_event_types),
                },
                "explanation": "Employee is terminated and still holds a material LSL balance without a clear closure indicator between termination and snapshot.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                evidence_str=evidence_str,
            )
        )

    return findings