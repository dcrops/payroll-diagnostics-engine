from __future__ import annotations

import json
import pandas as pd

from cross_module_integrity.models import Finding, _build_finding


def detect_termination_without_evidence_and_payroll_continues(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())

    if terminations.empty or pay_events.empty:
        return []

    findings: list[Finding] = []
    allowed_days_after_term = int(rule.get("config", {}).get("allowed_days_after_term", 7))

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    term["evidence_ref_norm"] = (
        term.get("evidence_ref", pd.Series(index=term.index, dtype="object"))
        .fillna("")
        .astype(str)
        .str.strip()
    )

    pay = pay_events.copy()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
    pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")

    merged = pay.merge(
        term[["employee_id", "termination_date", "evidence_ref_norm"]],
        on="employee_id",
        how="inner",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["pay_date"].notna()
        & (merged["evidence_ref_norm"] == "")
        & ((merged["pay_date"] - merged["termination_date"]).dt.days > allowed_days_after_term)
    ].copy()

    for _, row in bad.iterrows():
        days_after = int((row["pay_date"] - row["termination_date"]).days)

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()),
                    "pay_date": str(row["pay_date"].date()),
                },
                "values": {
                    "evidence_ref": None,
                    "days_after_termination": days_after,
                    "gross_amount": float(row["gross_amount"]) if "gross_amount" in row and pd.notna(row["gross_amount"]) else None,
                },
                "thresholds": {
                    "allowed_days_after_term": allowed_days_after_term,
                },
                "explanation": "Termination evidence reference is missing and payroll activity continues after termination beyond the allowed window.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=None,
                as_of_date=str(row["pay_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings

def detect_termination_lacks_evidence_and_open_leave_balance_remains(
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
    leave_types = {
        str(x).strip().upper()
        for x in rule.get("config", {}).get("leave_types", ["ANNUAL", "LSL"])
    }

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    evidence_series = term["evidence_ref"] if "evidence_ref" in term.columns else pd.Series(index=term.index, dtype="object")
    term["evidence_ref_norm"] = evidence_series.fillna("").astype(str).str.strip()

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
        term[["employee_id", "termination_date", "evidence_ref_norm"]],
        on="employee_id",
        how="inner",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["evidence_ref_norm"] == "")
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
                    "evidence_ref": None,
                    "balance_units": float(row["balance_units"]) if pd.notna(row["balance_units"]) else None,
                },
                "thresholds": {
                    "material_balance_units": material_balance_units,
                    "snapshot_grace_days": snapshot_grace_days,
                },
                "explanation": "Termination evidence reference is missing and a material leave balance remains after the configured grace period.",
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