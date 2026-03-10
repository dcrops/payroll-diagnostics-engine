from __future__ import annotations

from typing import Callable
import pandas as pd

from leave_leakage.models import Finding

from leave_leakage.detectors.balance_rules import (
    _run_leave_001_negative_balance,
    _run_leave_005_balance_mismatch,
    _run_leave_009_extreme_balance,
    _run_leave_014_taken_exceeds_balance,
)
from leave_leakage.detectors.timing_rules import (
    _run_leave_003_taken_before_start_date,
    _run_leave_007_after_termination,
    _run_leave_013_accrual_after_termination,
)
from leave_leakage.detectors.structure_rules import (
    _run_leave_006_missing_ledger,
    _run_leave_010_missing_leave_type,
    _run_leave_011_missing_timestamp,
    _run_leave_016_snapshot_type_not_in_ledger,
    _run_leave_017_unknown_employee_ledger,
    _run_leave_018_unknown_employee_snapshot,
)
from leave_leakage.detectors.anomaly_rules import (
    _run_leave_002_event_sign_anomaly,
    _run_leave_008_duplicate_entries,
    _run_leave_015_zero_unit_event,
    _run_leave_019_invalid_event_type,
)
from leave_leakage.detectors.governance_rules import (
    _run_leave_004_casual_accrual_present,
    _run_leave_012_manual_adjustments,
)
from leave_leakage.detectors.workflow_rules import (
    _run_leave_020_taken_without_approved_request,
    _run_leave_021_taken_before_approval_date,
    _run_leave_022_leave_and_work_same_day,
    _run_leave_023_combined_leave_and_work_exceeds_threshold,
)


Detector = Callable[[dict, dict[str, pd.DataFrame], dict], list[Finding]]


def _detect_leave_001(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    if leave_snapshot.empty:
        return []
    return _run_leave_001_negative_balance(rule, leave_snapshot)


def _detect_leave_002(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_ledger.empty:
        return []
    return _run_leave_002_event_sign_anomaly(rule, leave_ledger)


def _detect_leave_003(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    employee_master = datasets.get("employee_master", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if employee_master.empty or leave_ledger.empty:
        return []
    return _run_leave_003_taken_before_start_date(rule, employee_master, leave_ledger)


def _detect_leave_004(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    employee_master = datasets.get("employee_master", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if employee_master.empty or leave_ledger.empty:
        return []
    return _run_leave_004_casual_accrual_present(rule, employee_master, leave_ledger)


def _detect_leave_005(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    ledger_recon = context.get("ledger_recon")
    if leave_snapshot.empty or ledger_recon is None or ledger_recon.empty:
        return []
    return _run_leave_005_balance_mismatch(rule, leave_snapshot, ledger_recon)


def _detect_leave_006(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_snapshot.empty or leave_ledger.empty:
        return []
    return _run_leave_006_missing_ledger(rule, leave_snapshot, leave_ledger)


def _detect_leave_007(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    employee_master = datasets.get("employee_master", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if employee_master.empty or leave_ledger.empty or "termination_date" not in employee_master.columns:
        return []
    return _run_leave_007_after_termination(rule, employee_master, leave_ledger)


def _detect_leave_008(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_ledger.empty:
        return []
    return _run_leave_008_duplicate_entries(rule, leave_ledger)


def _detect_leave_009(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    if leave_snapshot.empty:
        return []
    return _run_leave_009_extreme_balance(rule, leave_snapshot)


def _detect_leave_010(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_ledger.empty:
        return []
    return _run_leave_010_missing_leave_type(rule, leave_ledger)


def _detect_leave_011(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_ledger.empty:
        return []
    return _run_leave_011_missing_timestamp(rule, leave_ledger)


def _detect_leave_012(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_ledger.empty:
        return []
    return _run_leave_012_manual_adjustments(rule, leave_ledger)


def _detect_leave_013(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    employee_master = datasets.get("employee_master", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if employee_master.empty or leave_ledger.empty or "termination_date" not in employee_master.columns:
        return []
    return _run_leave_013_accrual_after_termination(rule, employee_master, leave_ledger)


def _detect_leave_014(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_snapshot.empty or leave_ledger.empty:
        return []
    return _run_leave_014_taken_exceeds_balance(rule, leave_snapshot, leave_ledger)


def _detect_leave_015(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_ledger.empty:
        return []
    return _run_leave_015_zero_unit_event(rule, leave_ledger)


def _detect_leave_016(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_snapshot.empty or leave_ledger.empty:
        return []
    return _run_leave_016_snapshot_type_not_in_ledger(rule, leave_snapshot, leave_ledger)


def _detect_leave_017(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    employee_master = datasets.get("employee_master", pd.DataFrame())
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if employee_master.empty or leave_ledger.empty:
        return []
    return _run_leave_017_unknown_employee_ledger(rule, employee_master, leave_ledger)


def _detect_leave_018(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    employee_master = datasets.get("employee_master", pd.DataFrame())
    leave_snapshot = datasets.get("leave_snapshot", pd.DataFrame())
    if employee_master.empty or leave_snapshot.empty:
        return []
    return _run_leave_018_unknown_employee_snapshot(rule, employee_master, leave_snapshot)


def _detect_leave_019(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    if leave_ledger.empty:
        return []
    return _run_leave_019_invalid_event_type(rule, leave_ledger)

def _detect_leave_020(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    leave_requests = datasets.get("leave_requests", pd.DataFrame())
    if leave_ledger.empty or leave_requests.empty:
        return []
    return _run_leave_020_taken_without_approved_request(rule, leave_ledger, leave_requests)


def _detect_leave_021(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    leave_requests = datasets.get("leave_requests", pd.DataFrame())
    if leave_ledger.empty or leave_requests.empty:
        return []
    return _run_leave_021_taken_before_approval_date(rule, leave_ledger, leave_requests)


def _detect_leave_022(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    timesheets = datasets.get("timesheets", pd.DataFrame())
    if leave_ledger.empty or timesheets.empty:
        return []
    return _run_leave_022_leave_and_work_same_day(rule, leave_ledger, timesheets)


def _detect_leave_023(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    leave_ledger = datasets.get("leave_ledger", pd.DataFrame())
    timesheets = datasets.get("timesheets", pd.DataFrame())
    if leave_ledger.empty or timesheets.empty:
        return []
    return _run_leave_023_combined_leave_and_work_exceeds_threshold(rule, leave_ledger, timesheets)


RULE_REGISTRY: dict[str, Detector] = {
    "LEAVE-001": _detect_leave_001,
    "LEAVE-002": _detect_leave_002,
    "LEAVE-003": _detect_leave_003,
    "LEAVE-004": _detect_leave_004,
    "LEAVE-005": _detect_leave_005,
    "LEAVE-006": _detect_leave_006,
    "LEAVE-007": _detect_leave_007,
    "LEAVE-008": _detect_leave_008,
    "LEAVE-009": _detect_leave_009,
    "LEAVE-010": _detect_leave_010,
    "LEAVE-011": _detect_leave_011,
    "LEAVE-012": _detect_leave_012,
    "LEAVE-013": _detect_leave_013,
    "LEAVE-014": _detect_leave_014,
    "LEAVE-015": _detect_leave_015,
    "LEAVE-016": _detect_leave_016,
    "LEAVE-017": _detect_leave_017,
    "LEAVE-018": _detect_leave_018,
    "LEAVE-019": _detect_leave_019,
    "LEAVE-020": _detect_leave_020,
    "LEAVE-021": _detect_leave_021,
    "LEAVE-022": _detect_leave_022,
    "LEAVE-023": _detect_leave_023,
}


def run_rule(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict | None = None,
) -> list[Finding]:
    detector = RULE_REGISTRY.get(rule["id"])
    if detector is None:
        return []
    return detector(rule, datasets, context or {})