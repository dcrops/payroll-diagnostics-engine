# src/rkeg/detectors/leave.py
from __future__ import annotations

from typing import Iterable, Dict, List
from uuid import uuid4

import pandas as pd

from rkeg.rules import Finding


def _run_leave_001(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[Finding]:
    """
    RKEG-LEAVE-001
    Leave ledger movement without corresponding pay event.

    Implementation (v1):
    - Look at TAKEN leave events in leave_ledger.
    - For each TAKEN row, check whether there is at least one pay_event
      for the same employee on the same calendar date.
    - If no matching pay event exists, emit a finding.
    """
    leave_ledger = datasets.get("leave_ledger")
    pay_events = datasets.get("pay_events")

    # If we don't have either dataset, we can't do this check.
    if leave_ledger is None or leave_ledger.empty:
        return []
    if pay_events is None or pay_events.empty:
        return []

    ll = leave_ledger.copy()
    pe = pay_events.copy()

    # Normalise column names (case-insensitive)
    ll_cols = {c.lower(): c for c in ll.columns}
    pe_cols = {c.lower(): c for c in pe.columns}

    emp_col_ll = ll_cols.get("employee_id", "employee_id")
    emp_col_pe = pe_cols.get("employee_id", "employee_id")
    event_date_col = ll_cols.get("event_date", "event_date")
    pay_date_col = pe_cols.get("pay_date", "pay_date")
    leave_type_col = ll_cols.get("leave_type", "leave_type")
    units_col = ll_cols.get("units", "units")
    event_type_col = ll_cols.get("event_type", "event_type")

    # Coerce dates
    ll[event_date_col] = pd.to_datetime(ll[event_date_col], errors="coerce")
    pe[pay_date_col] = pd.to_datetime(pe[pay_date_col], errors="coerce")

    # Focus on TAKEN events with valid dates and employee IDs
    taken = ll[
        (ll[event_type_col].astype(str).str.upper() == "TAKEN")
        & ll[event_date_col].notna()
        & ll[emp_col_ll].notna()
    ].copy()

    if taken.empty:
        return []

    pe = pe[pe[pay_date_col].notna() & pe[emp_col_pe].notna()].copy()
    if pe.empty:
        # No usable pay events to match against
        return []

    # Compare on calendar dates (not datetimes)
    taken["__event_date"] = taken[event_date_col].dt.date
    pe["__pay_date"] = pe[pay_date_col].dt.date

    merged = taken.merge(
        pe[[emp_col_pe, "__pay_date"]],
        how="left",
        left_on=[emp_col_ll, "__event_date"],
        right_on=[emp_col_pe, "__pay_date"],
        indicator=True,
    )

    # Rows that have no matching pay_event on the same date
    unmatched = merged[merged["_merge"] == "left_only"]
    if unmatched.empty:
        return []

    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Leave ledger movements were detected without corresponding payroll transactions.",
    )
    remediation_text = text_block.get(
        "remediation",
        "Reconcile leave taken entries to payroll transactions and ensure paid leave is processed through payroll.",
    )
    severity = rule.get("severity", "HIGH")

    findings: List[Finding] = []

    for _, row in unmatched.iterrows():
        employee_id = str(row[emp_col_ll])
        event_date = row[event_date_col]
        leave_type = str(row.get(leave_type_col, "") or "")
        try:
            units = float(row.get(units_col, 0.0) or 0.0)
        except (TypeError, ValueError):
            units = 0.0

        message = (
            f"{base_finding_text} Employee {employee_id}, leave type {leave_type}, "
            f"event date {event_date.date()} (units {units:+.2f}) had no payroll "
            f"event on the same date."
        )

        evidence = (
            f"employee_id={employee_id}, leave_type={leave_type}, "
            f"event_date={event_date.date()}, units={units:.2f}, "
            f"matched_pay_event_on_same_date=False"
        )

        findings.append(
            Finding(
                employee_id=employee_id,
                leave_type=leave_type,
                as_of_date=event_date.date().isoformat(),
                rule_code=rule["id"],
                severity=severity,
                message=message,
                diff_units=None,
                evidence=evidence,
                finding_id=uuid4().hex[:12],
                next_action=remediation_text,
            )
        )

    return findings

def _run_leave_002(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-LEAVE-002
    Leave snapshot balances do not reconcile to ledger movements.

    Now only applies where there *is* ledger history for the employee/leave_type.
    Cases with no history are handled by LEAVE-003.
    """
    leave_snapshot = datasets.get("leave_snapshot")
    leave_ledger = datasets.get("leave_ledger")

    if leave_snapshot is None or leave_snapshot.empty:
        return []
    if leave_ledger is None or leave_ledger.empty:
        return []

    snapshot = leave_snapshot.copy()
    ledger = leave_ledger.copy()

    # Normalise column names
    snapshot_cols = {c.lower(): c for c in snapshot.columns}
    ledger_cols = {c.lower(): c for c in ledger.columns}

    emp_col_snap = snapshot_cols.get("employee_id", "employee_id")
    lt_col_snap = snapshot_cols.get("leave_type", "leave_type")
    asof_col = snapshot_cols.get("as_of_date", "as_of_date")
    bal_col = snapshot_cols.get("balance_units", "balance_units")

    emp_col_ledger = ledger_cols.get("employee_id", "employee_id")
    lt_col_ledger = ledger_cols.get("leave_type", "leave_type")
    event_date_col = ledger_cols.get("event_date", "event_date")
    units_col = ledger_cols.get("units", "units")

    # Parse dates
    snapshot[asof_col] = pd.to_datetime(snapshot[asof_col], errors="coerce")
    ledger[event_date_col] = pd.to_datetime(ledger[event_date_col], errors="coerce")

    snapshot = snapshot[snapshot[asof_col].notna()]
    ledger = ledger[ledger[event_date_col].notna()]

    if snapshot.empty or ledger.empty:
        return []

    # Ensure numeric
    snapshot[bal_col] = pd.to_numeric(snapshot[bal_col], errors="coerce")
    ledger[units_col] = pd.to_numeric(ledger[units_col], errors="coerce")

    snapshot = snapshot[snapshot[bal_col].notna()]
    ledger = ledger[ledger[units_col].notna()]

    if snapshot.empty:
        return []

    # --- NEW: coverage / first-event detection ---
    coverage = (
        ledger
        .groupby([emp_col_ledger, lt_col_ledger], as_index=False)[event_date_col]
        .min()
        .rename(columns={event_date_col: "__first_event_date",
                         emp_col_ledger: emp_col_snap,
                         lt_col_ledger: lt_col_snap})
    )

    snapshot = snapshot.merge(
        coverage,
        on=[emp_col_snap, lt_col_snap],
        how="left",
    )

    # has_history = we have at least one ledger row and it is on/before the snapshot date
    snapshot["__has_history"] = snapshot["__first_event_date"].notna() & (
        snapshot["__first_event_date"] <= snapshot[asof_col]
    )

    # Only attempt reconstruction where history exists
    snap_with_history = snapshot[snapshot["__has_history"]].copy()
    if snap_with_history.empty:
        return []

    # Sort and compute cumulative units per employee + leave_type over time
    ledger_sorted = ledger.sort_values([event_date_col, emp_col_ledger, lt_col_ledger])
    ledger_sorted["__cum_units"] = (
        ledger_sorted
        .groupby([emp_col_ledger, lt_col_ledger])[units_col]
        .cumsum()
    )

    # Prepare snapshot-with-history for asof merge
    snap_sorted = snap_with_history.sort_values([asof_col, emp_col_snap, lt_col_snap])

    merged = pd.merge_asof(
        snap_sorted,
        ledger_sorted[[emp_col_ledger, lt_col_ledger, event_date_col, "__cum_units"]],
        left_on=asof_col,
        right_on=event_date_col,
        by=[emp_col_snap, lt_col_snap],
        direction="backward",
    )

    # If there *is* history, but only after snapshot (we filtered those out above),
    # merged rows should always have some __cum_units; fill NaN with 0 just in case.
    merged["__cum_units"] = merged["__cum_units"].fillna(0.0)

    merged["__diff"] = merged[bal_col] - merged["__cum_units"]
    merged["__abs_diff"] = merged["__diff"].abs()

    config = rule.get("config", {}) or {}
    tolerance_units = float(config.get("tolerance_units", 2.0))

    flagged = merged[merged["__abs_diff"] > tolerance_units]
    if flagged.empty:
        return []

    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Leave snapshot balances do not reconcile to transactional leave ledger movements within the configured tolerance.",
    )
    remediation_text = text_block.get(
        "remediation",
        "Reconcile leave snapshots to the transactional leave ledger and investigate discrepancies above the tolerance threshold.",
    )
    severity = rule.get("severity", "HIGH")

    findings: List[Finding] = []

    for _, row in flagged.iterrows():
        employee_id = str(row[emp_col_snap])
        leave_type = str(row[lt_col_snap])
        as_of = row[asof_col]
        as_of_str = as_of.date().isoformat() if pd.notna(as_of) else ""

        snapshot_balance = float(row[bal_col])
        reconstructed = float(row["__cum_units"])
        diff = float(row["__diff"])
        abs_diff = float(row["__abs_diff"])

        message = (
            f"{base_finding_text} Employee {employee_id}, leave type {leave_type}, "
            f"as at {as_of_str}: snapshot balance {snapshot_balance:.2f} units, "
            f"reconstructed from ledger {reconstructed:.2f} units, "
            f"difference {diff:.2f} (absolute {abs_diff:.2f})."
        )

        evidence = (
            f"employee_id={employee_id}, leave_type={leave_type}, "
            f"as_of_date={as_of_str}, snapshot_balance={snapshot_balance:.2f}, "
            f"reconstructed_balance={reconstructed:.2f}, "
            f"diff={diff:.2f}, abs_diff={abs_diff:.2f}, "
            f"tolerance_units={tolerance_units:.2f}"
        )

        findings.append(
            Finding(
                employee_id=employee_id,
                leave_type=leave_type,
                as_of_date=as_of_str,
                rule_code=rule["id"],
                severity=severity,
                message=message,
                diff_units="units",
                evidence=evidence,
                finding_id=uuid4().hex[:12],
                next_action=remediation_text,
            )
        )

    return findings

def _run_leave_003(rule: dict, datasets: Dict[str, pd.DataFrame]) -> List[Finding]:
    """
    RKEG-LEAVE-003
    Leave snapshot balances have no matching ledger history.

    Flags employees/leave types where:
    - There is a snapshot balance
    - There are no corresponding ledger rows up to the snapshot date
    - The balance is at least min_balance_units
    """
    leave_snapshot = datasets.get("leave_snapshot")
    leave_ledger = datasets.get("leave_ledger")

    if leave_snapshot is None or leave_snapshot.empty:
        return []

    snapshot = leave_snapshot.copy()

    snapshot_cols = {c.lower(): c for c in snapshot.columns}
    emp_col_snap = snapshot_cols.get("employee_id", "employee_id")
    lt_col_snap = snapshot_cols.get("leave_type", "leave_type")
    asof_col = snapshot_cols.get("as_of_date", "as_of_date")
    bal_col = snapshot_cols.get("balance_units", "balance_units")

    snapshot[asof_col] = pd.to_datetime(snapshot[asof_col], errors="coerce")
    snapshot = snapshot[snapshot[asof_col].notna()]

    snapshot[bal_col] = pd.to_numeric(snapshot[bal_col], errors="coerce")
    snapshot = snapshot[snapshot[bal_col].notna()]

    if snapshot.empty:
        return []

    # If there is no ledger at all, treat all non-trivial balances as incomplete history
    if leave_ledger is None or leave_ledger.empty:
        coverage = snapshot.copy()
        coverage["__has_ledger"] = False
    else:
        ledger = leave_ledger.copy()
        ledger_cols = {c.lower(): c for c in ledger.columns}
        emp_col_ledger = ledger_cols.get("employee_id", "employee_id")
        lt_col_ledger = ledger_cols.get("leave_type", "leave_type")
        event_date_col = ledger_cols.get("event_date", "event_date")

        ledger[event_date_col] = pd.to_datetime(ledger[event_date_col], errors="coerce")
        ledger = ledger[ledger[event_date_col].notna()]

        # Earliest ledger date per employee/leave_type
        coverage = (
            ledger
            .groupby([emp_col_ledger, lt_col_ledger], as_index=False)[event_date_col]
            .min()
            .rename(columns={event_date_col: "__first_event_date",
                             emp_col_ledger: emp_col_snap,
                             lt_col_ledger: lt_col_snap})
        )

        coverage = snapshot.merge(
            coverage,
            on=[emp_col_snap, lt_col_snap],
            how="left",
        )

        coverage["__has_ledger"] = coverage["__first_event_date"].notna() & (
            coverage["__first_event_date"] <= coverage[asof_col]
        )

    config = rule.get("config", {}) or {}
    min_balance_units = float(config.get("min_balance_units", 10.0))

    # No ledger coverage up to snapshot date AND balance is meaningful
    flagged = coverage[
        (~coverage["__has_ledger"]) &
        (coverage[bal_col].abs() >= min_balance_units)
    ]

    if flagged.empty:
        return []

    text_block = rule.get("text", {})
    base_finding_text = text_block.get(
        "finding",
        "Leave snapshot balances were identified with no corresponding transactional leave ledger history for the employee and leave type.",
    )
    remediation_text = text_block.get(
        "remediation",
        "Confirm the source of opening leave balances and ensure that either transactional history is retained or that migration and opening balance documentation is available.",
    )
    severity = rule.get("severity", "HIGH")

    findings: List[Finding] = []

    for _, row in flagged.iterrows():
        employee_id = str(row[emp_col_snap])
        leave_type = str(row[lt_col_snap])
        as_of = row[asof_col]
        as_of_str = as_of.date().isoformat() if pd.notna(as_of) else ""
        balance = float(row[bal_col])

        message = (
            f"{base_finding_text} Employee {employee_id}, leave type {leave_type}, "
            f"as at {as_of_str}: snapshot balance {balance:.2f} units and no "
            f"matching leave ledger history was provided for this balance."
        )

        evidence = (
            f"employee_id={employee_id}, leave_type={leave_type}, "
            f"as_of_date={as_of_str}, snapshot_balance={balance:.2f}, "
            f"min_balance_units={min_balance_units:.2f}"
        )

        findings.append(
            Finding(
                employee_id=employee_id,
                leave_type=leave_type,
                as_of_date=as_of_str,
                rule_code=rule["id"],
                severity=severity,
                message=message,
                diff_units="units",
                evidence=evidence,
                finding_id=uuid4().hex[:12],
                next_action=remediation_text,
            )
        )

    return findings


def run_rule(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[Finding]:
    """
    Entry point for LEAVE-domain RKEG rules.
    """
    rule_id = rule["id"]

    if rule_id == "RKEG-LEAVE-001":
        return _run_leave_001(rule, datasets)

    if rule_id == "RKEG-LEAVE-002":
        return _run_leave_002(rule, datasets)

    if rule_id == "RKEG-LEAVE-003":
        return _run_leave_003(rule, datasets)

    # Unknown rule: be conservative and return no findings rather than crash the engine.
    return []