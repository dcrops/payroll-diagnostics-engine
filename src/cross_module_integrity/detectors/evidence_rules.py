from __future__ import annotations

import json
import pandas as pd

from cross_module_integrity.models import Finding, _build_finding


def _get_evidence_series(df: pd.DataFrame) -> pd.Series:
    if "evidence_reference" in df.columns:
        return df["evidence_reference"]
    if "evidence_ref" in df.columns:
        return df["evidence_ref"]
    return pd.Series(index=df.index, dtype="object")


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
    config = rule.get("config", {}) or {}
    allowed_days_after_term = int(config.get("allowed_days_after_term", 14))
    high_severity_cutoff_days = int(config.get("high_severity_cutoff_days", 30))

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    evidence_series = _get_evidence_series(term)
    term["evidence_reference_norm"] = (
        evidence_series.fillna("").astype(str).str.strip()
    )

    pay = pay_events.copy()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
    pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")

    merged = pay.merge(
        term[["employee_id", "termination_date", "evidence_reference_norm"]],
        on="employee_id",
        how="inner",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["pay_date"].notna()
        & (merged["evidence_reference_norm"] == "")
        & ((merged["pay_date"] - merged["termination_date"]).dt.days > allowed_days_after_term)
    ].copy()

    for _, row in bad.iterrows():
        days_after = int((row["pay_date"] - row["termination_date"]).days)

        if days_after <= high_severity_cutoff_days:
            calibrated_severity = "MEDIUM"
            calibrated_classification = "CONTEXTUAL"
            explanation = (
                "Termination evidence reference is missing and payroll activity continues after termination "
                "beyond the configured tolerance window. This may reflect delayed finalisation or incomplete record-keeping and should be reviewed."
            )
        else:
            calibrated_severity = "HIGH"
            calibrated_classification = "LOGICAL"
            explanation = (
                "Termination evidence reference is missing and payroll activity continues significantly after termination, "
                "indicating a likely lifecycle control breakdown."
            )

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()),
                    "pay_date": str(row["pay_date"].date()),
                },
                "values": {
                    "evidence_reference": None,
                    "days_after_termination": days_after,
                    "gross_amount": float(row["gross_amount"]) if "gross_amount" in row and pd.notna(row["gross_amount"]) else None,
                },
                "thresholds": {
                    "allowed_days_after_term": allowed_days_after_term,
                    "high_severity_cutoff_days": high_severity_cutoff_days,
                },
                "explanation": explanation,
            },
            ensure_ascii=False,
        )

        finding = _build_finding(
            rule=rule,
            employee_id=str(row["employee_id"]),
            leave_type=None,
            as_of_date=str(row["pay_date"].date()),
            evidence_str=evidence_str,
        )
        finding.severity = calibrated_severity
        if hasattr(finding, "classification"):
            finding.classification = calibrated_classification

        findings.append(finding)

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

    evidence_series = _get_evidence_series(term)
    term["evidence_reference_norm"] = evidence_series.fillna("").astype(str).str.strip()

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
        term[["employee_id", "termination_date", "evidence_reference_norm"]],
        on="employee_id",
        how="inner",
    )

    bad = merged[
        merged["termination_date"].notna()
        & merged["as_of_date"].notna()
        & (merged["evidence_reference_norm"] == "")
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
                    "evidence_reference": None,
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