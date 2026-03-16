from __future__ import annotations

from typing import Callable
import pandas as pd

from cross_module_integrity.models import Finding
from cross_module_integrity.detectors import lifecycle_rules, evidence_rules


Detector = Callable[[dict, dict[str, pd.DataFrame], dict], list[Finding]]


RULE_REGISTRY: dict[str, Detector] = {
    "CM-001": lifecycle_rules.detect_terminated_employee_retains_material_leave_balance,
    "CM-002": lifecycle_rules.detect_post_termination_leave_movement_recorded,
    "CM-003": evidence_rules.detect_termination_without_evidence_and_payroll_continues,
    "CM-004": lifecycle_rules.detect_open_leave_balance_after_termination_with_no_final_pay,
    "CM-005": evidence_rules.detect_termination_lacks_evidence_and_open_leave_balance_remains,
    "CM-006": lifecycle_rules.detect_employee_has_both_post_termination_payroll_and_leave_activity,
    "CM-007": lifecycle_rules.detect_terminated_employee_remains_active_in_employee_master_with_open_leave_balance,
    "CM-008": lifecycle_rules.detect_terminated_employee_retains_balance_with_no_final_pay_and_no_closure_event,
    "CM-009": lifecycle_rules.detect_leave_payout_without_termination,
    "CM-010": lifecycle_rules.detect_termination_without_leave_payout,
    "CM-011": lifecycle_rules.detect_multiple_termination_records,
    "CM-012": lifecycle_rules.detect_leave_activity_after_termination,
    "CM-013": lifecycle_rules.detect_final_pay_flagged_but_balance_remains,
    "CM-014": lifecycle_rules.detect_leave_payout_recorded_but_balance_does_not_reduce,
    "CM-015": lifecycle_rules.detect_terminated_employee_continues_receiving_non_final_pay_with_open_balance,
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