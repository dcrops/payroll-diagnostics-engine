from __future__ import annotations

import json
import pandas as pd

from termination_exposure.models import Finding, _build_finding
from common.nulls import is_missing

def _truthy_flag(value) -> bool:
    if value is None:
        return False

    v = str(value).strip().lower()

    return v in {"y", "yes", "true", "t", "1"}

def detect_missing_or_inconsistent_termination_type_or_reason(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    employees = datasets.get("employee_master", pd.DataFrame())

    if terminations.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    emp_type_map = {}
    if not employees.empty:
        emp = employees.copy()
        emp["employee_id"] = emp["employee_id"].astype(str).str.strip()
        for _, row in emp.iterrows():
            emp_id = str(row["employee_id"]).strip()
            t_type = str(row.get("termination_type") or row.get("separation_code") or "").strip()
            if emp_id and t_type:
                emp_type_map[emp_id] = t_type

    for _, row in term.iterrows():
        emp_id = str(row["employee_id"]).strip()
        if not emp_id:
            continue

        term_date = row["termination_date"]
        termination_type = row.get("termination_type")
        termination_reason = row.get("termination_reason") or row.get("reason")

        missing_type = is_missing(termination_type)
        missing_reason = is_missing(termination_reason)

        termination_type_str = "" if missing_type else str(termination_type).strip()
        emp_record_type = emp_type_map.get(emp_id)
        inconsistent = bool(
            emp_record_type
            and termination_type_str
            and emp_record_type != termination_type_str
        )

        if not missing_type and not missing_reason and not inconsistent:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv"] + (["employees.csv"] if emp_record_type else []),
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": str(term_date.date()) if pd.notna(term_date) else None,
                },
                "values": {
                    "termination_type": row.get("termination_type"),
                    "termination_reason": row.get("termination_reason") or row.get("reason"),
                    "employee_master_termination_type": emp_record_type,
                },
                "explanation": "Termination type or reason is missing, or inconsistent with employee master data.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=emp_id,
                leave_type=None,
                as_of_date=str(term_date.date()) if pd.notna(term_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_missing_supporting_termination_evidence_reference(
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

    for _, row in term.iterrows():
        emp_id = str(row["employee_id"]).strip()
        if not emp_id:
            continue

        raw_evidence_ref = row.get("evidence_ref")
        raw_termination_evidence = row.get("termination_evidence")
        raw_document_id = row.get("document_id")

        evidence_ref = None
        if not is_missing(raw_evidence_ref):
            evidence_ref = str(raw_evidence_ref).strip()
        elif not is_missing(raw_termination_evidence):
            evidence_ref = str(raw_termination_evidence).strip()
        elif not is_missing(raw_document_id):
            evidence_ref = str(raw_document_id).strip()

        if evidence_ref:
            continue

        term_date = row["termination_date"]

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv"],
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": str(term_date.date()) if pd.notna(term_date) else None,
                },
                "values": {
                    "evidence_ref": None,
                },
                "explanation": "Termination record has no supporting evidence reference.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=emp_id,
                leave_type=None,
                as_of_date=str(term_date.date()) if pd.notna(term_date) else None,
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_terminated_employee_retains_material_lsl_balance(
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

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    snap = leave_snapshot.copy()
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
                    "lsl_balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                },
                "explanation": "Employee remains terminated and still holds a material LSL balance in the post-termination snapshot.",
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


def detect_post_termination_lsl_movement_recorded(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())

    if terminations.empty or leave_ledger.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    led = leave_ledger.copy()
    led["employee_id"] = led["employee_id"].astype(str).str.strip()
    led["leave_type"] = led["leave_type"].astype(str).str.strip()
    led["event_date"] = pd.to_datetime(led["event_date"], errors="coerce")
    led["units"] = pd.to_numeric(led["units"], errors="coerce")

    lsl_rows = led[led["leave_type"].str.upper().str.contains("LSL", na=False)].copy()
    if lsl_rows.empty:
        return []

    merged = lsl_rows.merge(
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
                "explanation": "LSL ledger movement was recorded after the employee termination date.",
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


def detect_terminated_employee_with_lsl_balance_and_no_closure_trail(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())

    if terminations.empty or leave_snapshot.empty:
        return []

    findings: list[Finding] = []
    material_balance_units = float(rule.get("config", {}).get("material_balance_units", 10))
    snapshot_grace_days = int(rule.get("config", {}).get("snapshot_grace_days", 14))
    closure_event_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("closure_event_types", ["TAKEN", "ADJUSTMENT", "PAYOUT"])
    }

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    snap = leave_snapshot.copy()
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

    if leave_ledger.empty:
        led_lsl = pd.DataFrame(columns=["employee_id", "event_date", "event_type", "leave_type"])
    else:
        led_lsl = leave_ledger.copy()
        led_lsl["employee_id"] = led_lsl["employee_id"].astype(str).str.strip()
        led_lsl["leave_type"] = led_lsl["leave_type"].astype(str).str.strip()
        led_lsl["event_date"] = pd.to_datetime(led_lsl["event_date"], errors="coerce")
        led_lsl["event_type"] = led_lsl["event_type"].astype(str).str.strip().str.upper()
        led_lsl = led_lsl[led_lsl["leave_type"].str.upper().str.contains("LSL", na=False)].copy()

    for _, row in merged.iterrows():
        employee_id = str(row["employee_id"])
        termination_date = row["termination_date"]
        snapshot_date = row["as_of_date"]

        closure_rows = led_lsl[
            (led_lsl["employee_id"] == employee_id)
            & led_lsl["event_date"].notna()
            & (led_lsl["event_date"] >= termination_date)
            & (led_lsl["event_date"] <= snapshot_date)
            & led_lsl["event_type"].isin(closure_event_types)
        ].copy()

        if not closure_rows.empty:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "balances_snapshot.csv", "leave_ledger.csv"],
                "primary_keys": {
                    "employee_id": employee_id,
                    "termination_date": str(termination_date.date()),
                    "snapshot_date": str(snapshot_date.date()),
                    "leave_type": str(row["leave_type"]),
                },
                "values": {
                    "lsl_balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                    "closure_event_count": 0,
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                    "closure_event_types": sorted(closure_event_types),
                },
                "explanation": "Terminated employee retains a material LSL balance but no post-termination closure-style ledger activity was found.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=employee_id,
                leave_type=str(row["leave_type"]),
                as_of_date=str(snapshot_date.date()),
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_multiple_termination_records_for_employee(
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


def detect_termination_without_employee_master_record(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    employee_master = datasets.get("employee_master", pd.DataFrame())

    if terminations.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    if employee_master.empty:
        employee_ids = set()
    else:
        emp = employee_master.copy()
        emp["employee_id"] = emp["employee_id"].astype(str).str.strip()
        employee_ids = set(emp["employee_id"].dropna().astype(str).str.strip())

    bad = term[~term["employee_id"].isin(employee_ids)].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "employees.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()) if pd.notna(row["termination_date"]) else None,
                },
                "values": {
                    "employee_master_record_found": False,
                },
                "explanation": "Termination record exists without a corresponding employee master record.",
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


def detect_final_pay_missing_super_contribution(
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
    pay["is_final_pay_norm"] = pay["is_final_pay"].apply(_truthy_flag)
    if "super_amount" in pay.columns:
        pay["super_amount"] = pd.to_numeric(pay["super_amount"], errors="coerce")
    else:
        pay["super_amount"] = pd.NA

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    merged = pay.merge(
        term[["employee_id", "termination_date"]],
        on="employee_id",
        how="inner",
    )

    bad = merged[
        merged["is_final_pay_norm"]
        & merged["termination_date"].notna()
        & merged["pay_date"].notna()
        & (merged["pay_date"] >= merged["termination_date"])
        & (
            merged["super_amount"].isna()
            | (merged["super_amount"] <= 0)
        )
    ].copy()

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["pay_events.csv", "terminations.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "pay_date": str(row["pay_date"].date()) if pd.notna(row["pay_date"]) else None,
                },
                "values": {
                    "super_amount": float(row["super_amount"]) if pd.notna(row["super_amount"]) else None,
                    "gross_amount": float(row["gross_amount"]) if "gross_amount" in row and pd.notna(row["gross_amount"]) else None,
                    "termination_date": str(row["termination_date"].date()) if pd.notna(row["termination_date"]) else None,
                },
                "explanation": "A final pay event was identified without a corresponding super contribution.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=None,
                as_of_date=str(row["pay_date"].date()) if pd.notna(row["pay_date"]) else None,
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_involuntary_termination_without_reason(
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

    if "termination_type" not in term.columns:
        return []

    term["termination_type_norm"] = term["termination_type"].astype(str).str.strip().str.upper()
    reason_col = "termination_reason" if "termination_reason" in term.columns else "reason" if "reason" in term.columns else None

    involuntary_types = {"REDUNDANCY", "DISMISSAL", "TERMINATION", "INVOLUNTARY"}

    bad = term[
        term["termination_type_norm"].isin(involuntary_types)
    ].copy()

    if reason_col is not None:
        missing_reason_mask = (
            bad[reason_col].isna()
            | (bad[reason_col].astype(str).str.strip() == "")
        )
        bad = bad[missing_reason_mask].copy()

    if bad.empty:
        return []

    for _, row in bad.iterrows():
        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()) if pd.notna(row["termination_date"]) else None,
                },
                "values": {
                    "termination_type": str(row["termination_type"]) if pd.notna(row["termination_type"]) else None,
                    "termination_reason": str(row[reason_col]) if reason_col and pd.notna(row[reason_col]) else None,
                },
                "explanation": "An involuntary termination was identified without a recorded reason.",
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