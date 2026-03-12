from __future__ import annotations

import json
import pandas as pd

from lsl_exposure.models import Finding, _build_finding


def detect_missing_lsl_balance_for_eligible(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

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
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "service_years": float(row["service_years"]),
                    "lsl_balance_present": False,
                },
                "thresholds": {
                    "eligibility_years": eligibility_years,
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
                as_of_date=str(as_of.date()) if pd.notna(as_of) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_negative_lsl_balance(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

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
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "lsl_balance_units": float(row["lsl_balance_units"]),
                    "service_years": float(row["service_years"]),
                },
                "thresholds": {"expected": "lsl_balance_units >= 0"},
                "explanation": "Negative LSL balance identified in snapshot.",
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


def detect_zero_lsl_balance_for_eligible(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

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
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "service_years": float(row["service_years"]),
                    "lsl_balance_units": float(row["lsl_balance_units"]),
                },
                "thresholds": {
                    "eligibility_years": eligibility_years,
                },
                "explanation": (
                    "Employee is above the configured LSL eligibility threshold but has a zero LSL balance."
                ),
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


def detect_low_lsl_balance_for_long_tenure(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

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
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "service_years": float(row["service_years"]),
                    "lsl_balance_units": float(row["lsl_balance_units"]),
                },
                "thresholds": {
                    "full_years": full_years,
                    "low_floor_units": low_floor_units,
                },
                "explanation": "Long-tenured employee has an unusually low LSL balance.",
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


def detect_lsl_balance_below_eligibility(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

    findings: list[Finding] = []
    eligibility_years = float(rule.get("config", {}).get("eligibility_years", 7.0))

    bad = state[
        (state["service_years"].notna())
        & (state["service_years"] < eligibility_years)
        & (state["lsl_balance_units"].notna())
        & (state["lsl_balance_units"] > 0)
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
                    "service_years": float(row["service_years"]),
                    "lsl_balance_units": float(row["lsl_balance_units"]),
                },
                "thresholds": {
                    "eligibility_years": eligibility_years,
                },
                "explanation": "Employee appears below LSL eligibility threshold but has a positive LSL balance.",
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

def detect_extreme_lsl_balance(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

    findings: list[Finding] = []
    extreme_units = float(rule.get("config", {}).get("extreme_units", 800.0))

    bad = state[
        state["lsl_balance_units"].notna()
        & (state["lsl_balance_units"] > extreme_units)
    ].copy()

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
                    "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
                },
                "values": {
                    "lsl_balance_units": float(row["lsl_balance_units"]),
                    "service_years": float(row["service_years"]) if pd.notna(row["service_years"]) else None,
                },
                "thresholds": {
                    "extreme_units": extreme_units,
                },
                "explanation": "LSL balance exceeds the configured extreme threshold.",
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

def detect_lsl_balance_near_eligibility_threshold(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

    findings: list[Finding] = []

    eligibility_years = float(rule.get("config", {}).get("eligibility_years", 7.0))
    threshold_window_years = float(rule.get("config", {}).get("threshold_window_years", 1.0))

    lower_bound = max(0.0, eligibility_years - threshold_window_years)

    bad = state[
        (state["service_years"].notna())
        & (state["service_years"] >= lower_bound)
        & (state["service_years"] < eligibility_years)
        & (state["lsl_balance_units"].notna())
        & (state["lsl_balance_units"] > 0)
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
                    "service_years": float(row["service_years"]) if pd.notna(row["service_years"]) else None,
                    "lsl_balance_units": float(row["lsl_balance_units"]) if pd.notna(row["lsl_balance_units"]) else None,
                },
                "thresholds": {
                    "eligibility_years": eligibility_years,
                    "threshold_window_years": threshold_window_years,
                },
                "explanation": "Employee below the LSL eligibility threshold has a positive LSL balance within the configured proximity window.",
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


def detect_lsl_balance_inconsistent_with_fte(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

    findings: list[Finding] = []

    eligibility_years = float(rule.get("config", {}).get("eligibility_years", 7.0))
    low_fte_threshold = float(rule.get("config", {}).get("low_fte_threshold", 0.8))
    high_balance_units = float(rule.get("config", {}).get("high_balance_units", 200.0))

    if "fte" not in state.columns:
        return findings

    bad = state[
        (state["service_years"].notna())
        & (state["service_years"] >= eligibility_years)
        & (state["fte"].notna())
        & (state["fte"] < low_fte_threshold)
        & (state["lsl_balance_units"].notna())
        & (state["lsl_balance_units"] > high_balance_units)
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
                    "fte": float(row["fte"]) if pd.notna(row["fte"]) else None,
                    "service_years": float(row["service_years"]) if pd.notna(row["service_years"]) else None,
                    "lsl_balance_units": float(row["lsl_balance_units"]) if pd.notna(row["lsl_balance_units"]) else None,
                },
                "thresholds": {
                    "eligibility_years": eligibility_years,
                    "low_fte_threshold": low_fte_threshold,
                    "high_balance_units": high_balance_units,
                },
                "explanation": "Employee with relatively low FTE has an unusually large LSL balance for the configured sanity threshold.",
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

def detect_lsl_taken_before_eligibility(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    employees = datasets.get("employee_master", pd.DataFrame())
    ledger = datasets.get("leave_ledger", pd.DataFrame())

    if employees.empty or ledger.empty:
        return []

    findings: list[Finding] = []
    eligibility_years = float(rule.get("config", {}).get("eligibility_years", 7.0))

    emp = employees.copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()
    emp["start_date"] = pd.to_datetime(emp["start_date"], errors="coerce")

    led = ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")

    if "event_type" not in led.columns:
        return []

    lsl_taken = led[
        led["leave_type"].astype(str).str.upper().str.contains("LSL", na=False)
        & (led["event_type"].astype(str).str.upper() == "TAKEN")
    ].copy()

    if lsl_taken.empty:
        return []

    merged = lsl_taken.merge(
        emp[["employee_id", "start_date"]],
        on="employee_id",
        how="left",
    )

    merged["service_years_at_event"] = (
        (merged["event_date"] - merged["start_date"]).dt.days.clip(lower=0) / 365.25
    )

    bad = merged[
        merged["start_date"].notna()
        & merged["event_date"].notna()
        & (merged["service_years_at_event"] < eligibility_years)
    ].copy()

    for _, row in bad.iterrows():
        event_date = row["event_date"]

        evidence_str = json.dumps(
            {
                "sources": ["employees.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "event_date": str(event_date.date()) if pd.notna(event_date) else None,
                },
                "values": {
                    "service_years_at_event": float(row["service_years_at_event"]) if pd.notna(row["service_years_at_event"]) else None,
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                },
                "thresholds": {
                    "eligibility_years": eligibility_years,
                },
                "explanation": "LSL taken event occurred before the configured eligibility threshold was reached.",
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


def detect_lsl_ledger_balance_mismatch(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    ledger = datasets.get("leave_ledger", pd.DataFrame())

    if snapshot.empty or ledger.empty:
        return []

    findings: list[Finding] = []
    tolerance_units = float(rule.get("config", {}).get("tolerance_units", 0.01))

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

    merged = snap_lsl.merge(
        led_lsl,
        on=["employee_id", "leave_type"],
        how="left",
    )

    merged = merged[merged["event_date"].isna() | (merged["event_date"] <= merged["as_of_date"])]

    ledger_bal = (
        merged.groupby(["employee_id", "leave_type", "as_of_date"], as_index=False)["units"]
        .sum()
        .rename(columns={"units": "ledger_balance_units"})
    )

    report = snap_lsl.merge(
        ledger_bal,
        on=["employee_id", "leave_type", "as_of_date"],
        how="left",
    )

    report["ledger_balance_units"] = report["ledger_balance_units"].fillna(0.0)
    report["diff_units"] = report["balance_units"] - report["ledger_balance_units"]

    bad = report[report["diff_units"].abs() > tolerance_units].copy()

    for _, row in bad.iterrows():
        as_of = row["as_of_date"]

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
                    "ledger_balance_units": float(row["ledger_balance_units"]) if pd.notna(row["ledger_balance_units"]) else None,
                    "diff_units": float(row["diff_units"]) if pd.notna(row["diff_units"]) else None,
                },
                "thresholds": {
                    "tolerance_units": tolerance_units,
                },
                "explanation": "LSL ledger-derived balance does not reconcile to snapshot balance.",
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
                diff_units=float(row["diff_units"]) if pd.notna(row["diff_units"]) else None,
            )
        )

    return findings

def detect_low_lsl_balance_after_full_entitlement(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

    findings: list[Finding] = []
    full_entitlement_years = float(rule.get("config", {}).get("full_entitlement_years", 10.0))
    low_balance_threshold_units = float(rule.get("config", {}).get("low_balance_threshold_units", 10.0))

    bad = state[
        state["service_years"].notna()
        & (state["service_years"] >= full_entitlement_years)
        & state["lsl_balance_units"].notna()
        & (state["lsl_balance_units"] > 0)
        & (state["lsl_balance_units"] < low_balance_threshold_units)
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
                    "service_years": float(row["service_years"]) if pd.notna(row["service_years"]) else None,
                    "lsl_balance_units": float(row["lsl_balance_units"]) if pd.notna(row["lsl_balance_units"]) else None,
                },
                "thresholds": {
                    "full_entitlement_years": full_entitlement_years,
                    "low_balance_threshold_units": low_balance_threshold_units,
                },
                "explanation": "Employee exceeds the configured full entitlement tenure threshold but has an unusually low LSL balance.",
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