from __future__ import annotations

import json
import pandas as pd

from termination_exposure.models import Finding, _build_finding


def _truthy_flag(value) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"y", "yes", "true", "t", "1"}


def detect_termination_with_no_final_pay_event(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())

    if terminations.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    pay = pay_events.copy() if not pay_events.empty else pd.DataFrame(columns=["employee_id", "pay_date"])
    if not pay.empty:
        pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
        pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")

    for _, row in term.iterrows():
        emp_id = str(row["employee_id"]).strip()
        term_date = row["termination_date"]

        if not emp_id or pd.isna(term_date):
            continue

        emp_pays = pay[pay["employee_id"] == emp_id] if not pay.empty else pd.DataFrame()

        has_pay_on_or_after = (
            emp_pays["pay_date"].notna() & (emp_pays["pay_date"] >= term_date)
        ).any() if not emp_pays.empty else False

        if has_pay_on_or_after:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": str(term_date.date()),
                },
                "values": {
                    "has_pay_on_or_after_termination": False,
                },
                "explanation": "Termination was recorded but no pay event on or after the termination date was found.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=emp_id,
                leave_type=None,
                as_of_date=str(term_date.date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_final_pay_before_termination_date(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())

    if terminations.empty or pay_events.empty:
        return []

    findings: list[Finding] = []

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    pay = pay_events.copy()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
    pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")
    pay["is_final_pay_norm"] = pay["is_final_pay"].apply(_truthy_flag) if "is_final_pay" in pay.columns else False

    final_pays = pay[pay["is_final_pay_norm"]].copy()
    if final_pays.empty:
        return []

    merged = term.merge(final_pays[["employee_id", "pay_date"]], on="employee_id", how="inner")
    bad = merged[
        merged["termination_date"].notna()
        & merged["pay_date"].notna()
        & (merged["pay_date"] < merged["termination_date"])
    ].copy()

    for _, row in bad.iterrows():
        gap_days = int((row["termination_date"] - row["pay_date"]).days)

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()),
                    "final_pay_date": str(row["pay_date"].date()),
                },
                "values": {
                    "gap_days": gap_days,
                },
                "explanation": "Final pay date occurs before the recorded termination date.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=None,
                as_of_date=str(row["termination_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_significant_gap_between_last_pay_and_termination(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    state = context.get("state")
    if state is None or state.empty:
        return []

    findings: list[Finding] = []
    max_gap_days = int(rule.get("config", {}).get("max_gap_days", 35))

    bad = state[
        state["termination_date"].notna()
        & state["last_pay_date"].notna()
        & ((state["termination_date"] - state["last_pay_date"]).dt.days > max_gap_days)
    ].copy()

    for _, row in bad.iterrows():
        gap_days = int((row["termination_date"] - row["last_pay_date"]).days)

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": str(row["employee_id"]),
                    "termination_date": str(row["termination_date"].date()),
                },
                "values": {
                    "last_pay_date": str(row["last_pay_date"].date()),
                    "gap_days": gap_days,
                },
                "thresholds": {
                    "max_gap_days": max_gap_days,
                },
                "explanation": "Gap between last pay date and termination date exceeds the configured threshold.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=str(row["employee_id"]),
                leave_type=None,
                as_of_date=str(row["termination_date"].date()),
                evidence_str=evidence_str,
            )
        )

    return findings


def detect_final_pay_not_clearly_identifiable(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    terminations = datasets.get("terminations", pd.DataFrame())
    pay_events = datasets.get("pay_events", pd.DataFrame())

    if terminations.empty or pay_events.empty:
        return []

    findings: list[Finding] = []
    cfg = rule.get("config", {}) or {}
    window_before_days = int(cfg.get("window_before_days", 14))
    window_after_days = int(cfg.get("window_after_days", 30))

    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    pay = pay_events.copy()
    pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
    pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")
    pay["is_final_pay_norm"] = pay["is_final_pay"].apply(_truthy_flag) if "is_final_pay" in pay.columns else False

    for _, row in term.iterrows():
        emp_id = str(row["employee_id"]).strip()
        term_date = row["termination_date"]

        if not emp_id or pd.isna(term_date):
            continue

        emp_pays = pay[pay["employee_id"] == emp_id].copy()
        if emp_pays.empty:
            continue

        window_start = term_date - pd.Timedelta(days=window_before_days)
        window_end = term_date + pd.Timedelta(days=window_after_days)

        candidate_pays = emp_pays[
            emp_pays["pay_date"].notna()
            & (emp_pays["pay_date"] >= window_start)
            & (emp_pays["pay_date"] <= window_end)
        ].copy()

        has_flagged_final = (
            candidate_pays["is_final_pay_norm"].any()
            if not candidate_pays.empty else False
        )

        if candidate_pays.empty or has_flagged_final:
            continue

        evidence_str = json.dumps(
            {
                "sources": ["terminations.csv", "pay_events.csv"],
                "primary_keys": {
                    "employee_id": emp_id,
                    "termination_date": str(term_date.date()),
                },
                "values": {
                    "candidate_pay_dates": [
                        str(d.date()) for d in candidate_pays["pay_date"].dropna().tolist()
                    ],
                },
                "thresholds": {
                    "window_before_days": window_before_days,
                    "window_after_days": window_after_days,
                },
                "explanation": "Nearby pay events exist around termination but none is clearly flagged as final pay.",
            },
            ensure_ascii=False,
        )

        findings.append(
            _build_finding(
                rule=rule,
                employee_id=emp_id,
                leave_type=None,
                as_of_date=str(term_date.date()),
                evidence_str=evidence_str,
            )
        )

    return findings