from __future__ import annotations

import json
import pandas as pd

from lsl_exposure.models import Finding, _build_finding


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