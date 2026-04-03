from __future__ import annotations

import json
import pandas as pd

from cross_module_integrity.models import Finding, _build_finding
from common.nulls import is_missing

def _get_evidence_series(df: pd.DataFrame) -> pd.Series:
    if "evidence_reference" in df.columns:
        return df["evidence_reference"]
    if "evidence_ref" in df.columns:
        return df["evidence_ref"]
    return pd.Series(index=df.index, dtype="object")
    
def detect_terminated_employee_retains_material_leave_balance(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if terminations.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))
    snapshot_grace_days = int(rule.get("config", {}).get("snapshot_grace_days", 14))
    leave_types = {str(x).strip().upper() for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "LSL"])}

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["leave_type"].isin(leave_types)
        & snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    merged = latest_snap.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["as_of_date"] > merged["termination_date"])
        & ((merged["as_of_date"] - merged["termination_date"]).dt.days >= snapshot_grace_days)
    ].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()),
                    "snapshot_date": str(row["as_of_date"].date()),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                },
                "explanation": "Terminated employee retains a material leave balance after the configured grace period.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["as_of_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_post_termination_leave_movement_recorded(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())

    if terminations.empty or leave_ledger.empty:
        return []

    findings: list[Finding] = []
    leave_types = {str(x).strip().upper() for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "PERSONAL", "LSL"])}

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    led = leave_ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip().str.upper()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
    led["units"] = pd.to_numeric(led["units"], errors="coerce")

    led = led[led["leave_type"].isin(leave_types)].copy()
    if led.empty:
        return []

    merged = led.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["event_date"].notna()
        & (merged["event_date"] > merged["termination_date"])
    ].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()),
                    "event_date": str(row["event_date"].date()),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "event_type": str(row["event_type"]) if "event_type" in row and pd.notna(row["event_type"]) else None,
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                },
                "explanation": "Leave ledger movement was recorded after the employee termination date.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["event_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_open_leave_balance_after_termination_with_no_final_pay(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())

    if terminations.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))
    snapshot_grace_days = int(rule.get("config", {}).get("snapshot_grace_days", 14))
    leave_types = {str(x).strip().upper() for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "LSL"])}

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["leave_type"].isin(leave_types)
        & snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    merged = latest_snap.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    merged = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["as_of_date"] > merged["termination_date"])
        & ((merged["as_of_date"] - merged["termination_date"]).dt.days >= snapshot_grace_days)
    ].copy()

    if merged.empty:
        return []

    pay = pay_events.copy() if not pay_events.empty else pd.DataFrame(columns=["employee_id", "is_final_pay"])
    if not pay.empty:
        pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
        if "is_final_pay" not in pay.columns:
            pay["is_final_pay"] = ""
        pay["is_final_pay_norm"] = (
            pay["is_final_pay"].astype(str).str.strip().str.lower().isin({"y", "yes", "true", "t", "1"})
        )

    for _, row in merged.iterrows():
        employee_id = str(row["employee_id"])
        emp_pays = pay[pay["employee_id"] == employee_id] if not pay.empty else pd.DataFrame()
        has_flagged_final = (
            emp_pays["is_final_pay_norm"].any()
            if not emp_pays.empty and "is_final_pay_norm" in emp_pays.columns
            else False
        )

        if has_flagged_final:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "balances_snapshot.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "termination_date": str(row["termination_date"].date()),
                    "snapshot_date": str(row["as_of_date"].date()),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "has_flagged_final_pay": False,
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                },
                "explanation": "Terminated employee retains a material leave balance after the configured grace period and no final pay event is flagged.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["as_of_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_employee_has_both_post_termination_payroll_and_leave_activity(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())

    if terminations.empty or pay_events.empty or leave_ledger.empty:
        return []

    findings: list[Finding] = []
    allowed_days_after_term = int(rule.get("config", {}).get("allowed_days_after_term", 7))
    leave_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "PERSONAL", "LSL"])
    }

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    pay = pay_events.copy()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
    pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")

    led = leave_ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip().str.upper()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
    led = led[led["leave_type"].isin(leave_types)].copy()

    if led.empty:
        return []

    for _, row in term.iterrows():
        employee_id = str(row["employee_id"]).strip()
        termination_date = row["termination_date"]

        if not employee_id or pd.isna(termination_date):
            continue

        has_post_term_pay = (
            ((pay["employee_id"] == employee_id) & pay["pay_date"].notna()
             & ((pay["pay_date"] - termination_date).dt.days > allowed_days_after_term))
            .any()
        )

        emp_led = led[led["employee_id"] == employee_id]
        has_post_term_leave = (
            emp_led["event_date"].notna() & (emp_led["event_date"] > termination_date)
        ).any() if not emp_led.empty else False

        if not (has_post_term_pay and has_post_term_leave):
            continue

        latest_leave_event = emp_led.loc[
            emp_led["event_date"].notna() & (emp_led["event_date"] > termination_date),
            "event_date"
        ].max()

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "termination_date": str(termination_date.date()),
                },
                "values": {
                    "has_post_term_payroll_activity": True,
                    "has_post_term_leave_activity": True,
                    "latest_post_term_leave_date": str(latest_leave_event.date()) if pd.notna(latest_leave_event) else None,
                },
                "thresholds": {
                    "allowed_days_after_term": allowed_days_after_term,
                },
                "explanation": "Payroll activity and leave ledger movement both continue after the employee termination date.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=None,
                as_of_date=str(latest_leave_event.date()) if pd.notna(latest_leave_event) else str(termination_date.date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_terminated_employee_remains_active_in_employee_master_with_open_leave_balance(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    employee_master = datasets.get("employee_master", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if terminations.empty or employee_master.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))
    snapshot_grace_days = int(rule.get("config", {}).get("snapshot_grace_days", 14))
    leave_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "LSL"])
    }

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    emp = employee_master.copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()

    if "termination_date" in emp.columns:
        emp["termination_date_emp"] = pd.to_datetime(emp["termination_date"], errors="coerce")
    else:
        emp["termination_date_emp"] = pd.NaT

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["leave_type"].isin(leave_types)
        & snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    merged = latest_snap.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    ).merge(
        emp[["employee_id", "termination_date_emp"]],
        on="employee_id",
        how="left",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["as_of_date"] > merged["termination_date"])
        & ((merged["as_of_date"] - merged["termination_date"]).dt.days >= snapshot_grace_days)
        & merged["termination_date_emp"].isna()
    ].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "employees.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()),
                    "snapshot_date": str(row["as_of_date"].date()),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "employee_master_termination_date": None,
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                },
                "explanation": "Employee is terminated in termination records but still appears active in employee master while retaining an open leave balance.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["as_of_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_terminated_employee_retains_balance_with_no_final_pay_and_no_closure_event(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())

    if terminations.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))
    snapshot_grace_days = int(rule.get("config", {}).get("snapshot_grace_days", 14))
    leave_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "LSL"])
    }
    closure_event_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("closure_event_types", ["TAKEN", "ADJUSTMENT", "PAYOUT"])
    }

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["leave_type"].isin(leave_types)
        & snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    merged = latest_snap.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    merged = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["as_of_date"] > merged["termination_date"])
        & ((merged["as_of_date"] - merged["termination_date"]).dt.days >= snapshot_grace_days)
    ].copy()

    if merged.empty:
        return []

    pay = pay_events.copy() if not pay_events.empty else pd.DataFrame(columns=["employee_id", "is_final_pay"])
    if not pay.empty:
        pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
        if "is_final_pay" not in pay.columns:
            pay["is_final_pay"] = ""
        pay["is_final_pay_norm"] = (
            pay["is_final_pay"].astype(str).str.strip().str.lower().isin({"y", "yes", "true", "t", "1"})
        )

    led = leave_ledger.copy() if not leave_ledger.empty else pd.DataFrame(columns=["employee_id", "leave_type", "event_date", "event_type"])
    if not led.empty:
        led["employee_id"] = led["employee_id"].astype(str).str.strip()
        led["leave_type"] = led["leave_type"].astype(str).str.strip().str.upper()
        led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
        led["event_type"] = led["event_type"].astype(str).str.strip().str.upper()

    for _, row in merged.iterrows():
        employee_id = str(row["employee_id"])
        termination_date = row["termination_date"]
        snapshot_date = row["as_of_date"]
        leave_type = str(row["leave_type"])

        emp_pays = pay[pay["employee_id"] == employee_id] if not pay.empty else pd.DataFrame()
        has_flagged_final = (
            emp_pays["is_final_pay_norm"].any()
            if not emp_pays.empty and "is_final_pay_norm" in emp_pays.columns
            else False
        )

        emp_led = led[
            (led["employee_id"] == employee_id)
            & (led["leave_type"] == leave_type)
            & led["event_date"].notna()
            & (led["event_date"] >= termination_date)
            & (led["event_date"] <= snapshot_date)
            & led["event_type"].isin(closure_event_types)
        ] if not led.empty else pd.DataFrame()

        has_closure_event = not emp_led.empty

        if has_flagged_final or has_closure_event:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "balances_snapshot.csv", "pay_events.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "termination_date": str(termination_date.date()),
                    "snapshot_date": str(snapshot_date.date()),
                    "leave_type": leave_type,
                },
                "values": {
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "has_flagged_final_pay": False,
                    "closure_event_count": 0,
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                    "closure_event_types": sorted(closure_event_types),
                },
                "explanation": "Terminated employee retains a material leave balance after the configured grace period, with no final pay flagged and no closure-style ledger activity.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=leave_type,
                as_of_date=str(snapshot_date.date()),
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_leave_payout_without_termination(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())

    if leave_ledger.empty:
        return []

    findings: list[Finding] = []
    payout_event_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("payout_event_types", ["PAYOUT"])
    }

    led = leave_ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip().str.upper()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
    led["event_type"] = led["event_type"].astype(str).str.strip().str.upper()
    led["units"] = pd.to_numeric(led["units"], errors="coerce")

    payout_rows = led[led["event_type"].isin(payout_event_types)].copy()
    if payout_rows.empty:
        return []

    if terminations.empty:
        termination_ids = set()
    else:
        term = terminations.copy()
        term["employee_id"] = term["employee_id"].astype(str).str.strip()
        termination_ids = set(term["employee_id"].dropna().astype(str).str.strip())

    bad = payout_rows[~payout_rows["employee_id"].isin(termination_ids)].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "terminations.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "event_date": str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "event_type": str(row["event_type"]),
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                    "termination_record_found": False,
                },
                "thresholds": {
                    "payout_event_types": sorted(payout_event_types),
                },
                "explanation": "A leave payout ledger event was recorded but no termination record exists for the employee.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_termination_without_leave_payout(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if terminations.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    payout_event_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("payout_event_types", ["PAYOUT"])
    }
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    if leave_ledger.empty:
        led = pd.DataFrame(columns=["employee_id", "leave_type", "event_type", "event_date"])
    else:
        led = leave_ledger.copy()
        led["employee_id"] = led["employee_id"].astype(str).str.strip()
        led["leave_type"] = led["leave_type"].astype(str).str.strip().str.upper()
        led["event_type"] = led["event_type"].astype(str).str.strip().str.upper()
        led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")

    merged = latest_snap.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    for _, row in merged.iterrows():
        employee_id = str(row["employee_id"])
        leave_type = str(row["leave_type"])
        termination_date = row["termination_date"]

        if pd.isna(termination_date):
            continue

        emp_led = led[
            (led["employee_id"] == employee_id)
            & (led["leave_type"] == leave_type)
            & led["event_type"].isin(payout_event_types)
        ].copy()

        has_payout = False
        if not emp_led.empty:
            has_payout = (
                emp_led["event_date"].isna()
                | (emp_led["event_date"] >= termination_date)
            ).any()

        if has_payout:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "leave_ledger.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "termination_date": str(termination_date.date()),
                    "leave_type": leave_type,
                    "snapshot_date": str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                },
                "values": {
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "payout_event_found": False,
                },
                "thresholds": {
                    "payout_event_types": sorted(payout_event_types),
                    "material_balance_units": material_balance_units,
                },
                "explanation": "A termination was recorded but no leave payout event was identified for the employee.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=leave_type,
                as_of_date=str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else str(termination_date.date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_multiple_termination_records(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())

    if terminations.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    grouped = (
        term.groupby("employee_id", as_index=False)
        .agg(
            termination_record_count=("employee_id", "size"),
            earliest_termination_date=("termination_date", "min"),
            latest_termination_date=("termination_date", "max"),
        )
    )

    bad = grouped[grouped["termination_record_count"] > 1].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                },
                "values": {
                    "termination_record_count": int(row["termination_record_count"]),
                    "earliest_termination_date": str(row["earliest_termination_date"].date()) if pd.notna(row["earliest_termination_date"]) else None,
                    "latest_termination_date": str(row["latest_termination_date"].date()) if pd.notna(row["latest_termination_date"]) else None,
                },
                "explanation": "Multiple termination records were identified for the same employee.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=None,
                as_of_date=str(row["latest_termination_date"].date()) if pd.notna(row["latest_termination_date"]) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_leave_activity_after_termination(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())

    if leave_ledger.empty or terminations.empty:
        return []

    findings: list[Finding] = []
    allowed_event_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("allowed_event_types", ["PAYOUT", "ADJUSTMENT"])
    }

    led = leave_ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip().str.upper()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
    led["event_type"] = led["event_type"].astype(str).str.strip().str.upper()
    led["units"] = pd.to_numeric(led["units"], errors="coerce")

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    merged = led.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["event_date"].notna()
        & (merged["event_date"] > merged["termination_date"])
        & ~merged["event_type"].isin(allowed_event_types)
    ].copy()

    for _, row in bad.iterrows():
        days_after = int((row["event_date"] - row["termination_date"]).days)

        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "terminations.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()),
                    "event_date": str(row["event_date"].date()),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "event_type": str(row["event_type"]),
                    "units": float(row["units"]) if pd.notna(row["units"]) else None,
                    "days_after_termination": days_after,
                },
                "thresholds": {
                    "allowed_event_types": sorted(allowed_event_types),
                },
                "explanation": "Leave ledger activity was recorded after the employee termination date.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_final_pay_flagged_but_balance_remains(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if terminations.empty or pay_events.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))
    snapshot_grace_days = int(rule.get("config", {}).get("snapshot_grace_days", 14))
    leave_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "LSL"])
    }

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    pay = pay_events.copy()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
    pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")
    if "is_final_pay" not in pay.columns:
        pay["is_final_pay"] = ""
    pay["is_final_pay_norm"] = (
        pay["is_final_pay"].astype(str).str.strip().str.lower().isin({"y", "yes", "true", "t", "1"})
    )

    final_pays = pay[pay["is_final_pay_norm"]].copy()
    if final_pays.empty:
        return []

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["leave_type"].isin(leave_types)
        & snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    merged = latest_snap.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    merged = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["as_of_date"] > merged["termination_date"])
        & ((merged["as_of_date"] - merged["termination_date"]).dt.days >= snapshot_grace_days)
    ].copy()

    if merged.empty:
        return []

    for _, row in merged.iterrows():
        employee_id = str(row["employee_id"])
        termination_date = row["termination_date"]

        emp_final_pays = final_pays[
            (final_pays["employee_id"] == employee_id)
            & final_pays["pay_date"].notna()
            & (final_pays["pay_date"] >= termination_date)
        ].copy()

        if emp_final_pays.empty:
            continue

        latest_final_pay_date = emp_final_pays["pay_date"].max()

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "termination_date": str(termination_date.date()),
                    "final_pay_date": str(latest_final_pay_date.date()) if pd.notna(latest_final_pay_date) else None,
                    "snapshot_date": str(row["as_of_date"].date()),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "final_pay_flag_found": True,
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                },
                "explanation": "A final pay event was flagged, but a material leave balance remains after termination.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["as_of_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_leave_payout_recorded_but_balance_does_not_reduce(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())

    if leave_ledger.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    payout_event_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("payout_event_types", ["PAYOUT"])
    }
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))

    led = leave_ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip().str.upper()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
    led["event_type"] = led["event_type"].astype(str).str.strip().str.upper()
    led["units"] = pd.to_numeric(led["units"], errors="coerce")

    payout_rows = led[led["event_type"].isin(payout_event_types)].copy()
    if payout_rows.empty:
        return []

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    if terminations.empty:
        term = pd.DataFrame(columns=["employee_id", "termination_date"])
    else:
        term = terminations.copy()
        term["employee_id"] = term["employee_id"].astype(str).str.strip()
        term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    merged = payout_rows.merge(
        latest_snap[["employee_id", "leave_type", "as_of_date", "balance_units"]],
        on=["employee_id", "leave_type"],
        how="inner",
    ).merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="left",
    )

    bad = merged[
        merged["event_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["as_of_date"] >= merged["event_date"])
        & (merged["balance_units"] >= material_balance_units)
    ].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["leave_ledger.csv", "balances_snapshot.csv", "terminations.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "leave_type": str(row["leave_type"]),
                    "payout_event_date": str(row["event_date"].date()) if pd.notna(row["event_date"]) else None,
                    "snapshot_date": str(row["as_of_date"].date()) if pd.notna(row["as_of_date"]) else None,
                },
                "values": {
                    "event_type": str(row["event_type"]),
                    "payout_units": float(row["units"]) if pd.notna(row["units"]) else None,
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "termination_date": str(row["termination_date"].date()) if "termination_date" in row and pd.notna(row["termination_date"]) else None,
                },
                "thresholds": {
                    "payout_event_types": sorted(payout_event_types),
                    "material_balance_units": material_balance_units,
                },
                "explanation": "A leave payout event was recorded, but the employee still retains a material leave balance.",
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


def detect_terminated_employee_continues_receiving_non_final_pay_with_open_balance(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if terminations.empty or pay_events.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))
    snapshot_grace_days = int(rule.get("config", {}).get("snapshot_grace_days", 14))
    allowed_days_after_term = int(rule.get("config", {}).get("allowed_days_after_term", 7))
    leave_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "LSL"])
    }

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    pay = pay_events.copy()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
    pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")
    if "is_final_pay" not in pay.columns:
        pay["is_final_pay"] = ""
    pay["is_final_pay_norm"] = (
        pay["is_final_pay"].astype(str).str.strip().str.lower().isin({"y", "yes", "true", "t", "1"})
    )

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["leave_type"].isin(leave_types)
        & snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    merged = latest_snap.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    merged = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["as_of_date"] > merged["termination_date"])
        & ((merged["as_of_date"] - merged["termination_date"]).dt.days >= snapshot_grace_days)
    ].copy()

    if merged.empty:
        return []

    for _, row in merged.iterrows():
        employee_id = str(row["employee_id"])
        termination_date = row["termination_date"]

        emp_pays = pay[
            (pay["employee_id"] == employee_id)
            & pay["pay_date"].notna()
            & ((pay["pay_date"] - termination_date).dt.days > allowed_days_after_term)
            & (~pay["is_final_pay_norm"])
        ].copy()

        if emp_pays.empty:
            continue

        latest_non_final_pay_date = emp_pays["pay_date"].max()

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "termination_date": str(termination_date.date()),
                    "latest_non_final_pay_date": str(latest_non_final_pay_date.date()) if pd.notna(latest_non_final_pay_date) else None,
                    "snapshot_date": str(row["as_of_date"].date()),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "non_final_pay_event_count": int(len(emp_pays)),
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                    "allowed_days_after_term": allowed_days_after_term,
                },
                "explanation": "A terminated employee continues receiving non-final payroll while retaining a material leave balance.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=str(row["leave_type"]),
                as_of_date=str(row["as_of_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_termination_without_supporting_leave_snapshot(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if terminations.empty:
        return []

    findings: list[Finding] = []
    leave_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "LSL"])
    }

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    if leave_snapshot.empty:
        snapshot_keys = set()
    else:
        snap = leave_snapshot.copy()
        snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
        snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()

        snap = snap[snap["leave_type"].isin(leave_types)].copy()
        snapshot_keys = set(snap["employee_id"].dropna().astype(str).str.strip())

    bad = term[~term["employee_id"].isin(snapshot_keys)].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()) if pd.notna(row["termination_date"]) else None,
                },
                "values": {
                    "leave_snapshot_record_found": False,
                },
                "thresholds": {
                    "leave_types_checked": sorted(leave_types),
                },
                "explanation": "A termination record exists but no supporting leave snapshot record was identified for the employee.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=None,
                as_of_date=str(row["termination_date"].date()) if pd.notna(row["termination_date"]) else None,
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_final_pay_without_termination_evidence(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    pay_events = datasets.get("pay_events", pd.DataFrame())
    terminations = datasets.get("terminations", pd.DataFrame())

    if pay_events.empty or terminations.empty:
        return []

    findings: list[Finding] = []

    pay = pay_events.copy()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
    pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")

    if "is_final_pay" not in pay.columns:
        pay["is_final_pay"] = ""

    pay["is_final_pay_norm"] = (
        pay["is_final_pay"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"y", "yes", "true", "1"})
    )

    final_pays = pay[pay["is_final_pay_norm"]].copy()
    if final_pays.empty:
        return []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()

    evidence_series = _get_evidence_series(term)
    term["evidence_reference_norm"] = (
        evidence_series.fillna("").astype(str).str.strip()
    )

    merged = final_pays.merge(
        term[["employee_id", "evidence_reference_norm"]],
        on="employee_id",
        how="left"
    )

    bad = merged[merged["evidence_reference_norm"].apply(is_missing)]

    for _, row in bad.iterrows():
        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=None,
                as_of_date=str(row["pay_date"].date()) if pd.notna(row["pay_date"]) else None,
                evidence_str=json.dumps(
                    {
                        "issue": "final pay without evidence",
                        "evidence_reference": None,
                    },
                    ensure_ascii=False,
                )
            )
        )

    return findings

def detect_terminated_employee_retains_both_annual_and_lsl_balances(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())

    if terminations.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))
    snapshot_grace_days = int(rule.get("config", {}).get("snapshot_grace_days", 14))
    required_leave_types = [
        str(x).strip().upper()
        for x in rule.get("config", {}).get("required_leave_types", ["ANNUAL", "LSL"])
    ]

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    snap = leave_snapshot.copy()
    snap["employee_id"] = snap["employee_id"].astype(str).str.strip()
    snap["leave_type"] = snap["leave_type"].astype(str).str.strip().str.upper()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"], errors="coerce")
    snap["balance_units"] = pd.to_numeric(snap["balance_units"], errors="coerce")

    snap = snap[
        snap["leave_type"].isin(required_leave_types)
        & snap["balance_units"].notna()
        & (snap["balance_units"] >= material_balance_units)
    ].copy()

    if snap.empty:
        return []

    latest_snap = (
        snap.sort_values(["employee_id", "leave_type", "as_of_date"])
        .groupby(["employee_id", "leave_type"], as_index=False)
        .tail(1)
    )

    merged = latest_snap.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    merged = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["as_of_date"] > merged["termination_date"])
        & ((merged["as_of_date"] - merged["termination_date"]).dt.days >= snapshot_grace_days)
    ].copy()

    if merged.empty:
        return []

    grouped = (
        merged.groupby("employee_id")
        .agg(
            leave_types_found=("leave_type", lambda x: sorted(set(x))),
            latest_snapshot_date=("as_of_date", "max"),
        )
        .reset_index()
    )

    bad = grouped[
        grouped["leave_types_found"].apply(lambda x: all(t in x for t in required_leave_types))
    ].copy()

    for _, row in bad.iterrows():
        employee_id = str(row["employee_id"])
        employee_rows = merged[merged["employee_id"] == employee_id].copy()

        balance_map = {
            str(r["leave_type"]): float(r["balance_units"])
            for _, r in employee_rows.iterrows()
            if pd.notna(r["balance_units"])
        }

        termination_date = employee_rows["termination_date"].dropna().iloc[0] if not employee_rows["termination_date"].dropna().empty else pd.NaT
        latest_snapshot_date = row["latest_snapshot_date"]

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "balances_snapshot.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "termination_date": str(termination_date.date()) if pd.notna(termination_date) else None,
                    "snapshot_date": str(latest_snapshot_date.date()) if pd.notna(latest_snapshot_date) else None,
                },
                "values": {
                    "leave_types_found": row["leave_types_found"],
                    "balance_units_by_leave_type": balance_map,
                },
                "thresholds": {
                    "required_leave_types": required_leave_types,
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                },
                "explanation": "A terminated employee retains both material annual leave and LSL balances after the configured grace period.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type="MULTI_LEAVE",
                as_of_date=str(latest_snapshot_date.date()) if pd.notna(latest_snapshot_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_silent_termination(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())

    if terminations.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    pay_ids = set(pay_events["employee_id"].astype(str).str.strip()) if not pay_events.empty else set()
    ledger_ids = set(leave_ledger["employee_id"].astype(str).str.strip()) if not leave_ledger.empty else set()

    for _, row in term.iterrows():
        emp = str(row["employee_id"])

        if emp in pay_ids or emp in ledger_ids:
            continue

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=emp,
                leave_type=None,
                as_of_date=str(row["termination_date"].date()) if pd.notna(row["termination_date"]) else None,
                evidence_str=json.dumps({"issue": "no lifecycle activity"}, ensure_ascii=False)
            )
        )

    return findings

def detect_multi_failure_cluster(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:

    findings_df = datasets.get("cross_module_findings", pd.DataFrame())

    if findings_df.empty:
        return []

    findings: list[Finding] = []

    min_findings = int(rule.get("config", {}).get("min_findings", 3))
    min_high = int(rule.get("config", {}).get("min_high_severity", 2))

    grouped = findings_df.groupby("employee_id").agg(
        total=("rule_code","count"),
        high=("severity", lambda x: (x=="HIGH").sum())
    ).reset_index()

    bad = grouped[
        (grouped["total"] >= min_findings) |
        (grouped["high"] >= min_high)
    ]

    for _, row in bad.iterrows():
        findings.append(
            _build_finding(
                rule=rule,
                employee_id=row["employee_id"],
                leave_type=None,
                as_of_date=None,
                evidence_str=json.dumps({
                    "total_findings": int(row["total"]),
                    "high_findings": int(row["high"])
                }, ensure_ascii=False)
            )
        )

    return findings