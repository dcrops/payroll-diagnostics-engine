from __future__ import annotations

from typing import Callable
import pandas as pd

from termination_exposure.models import Finding
from termination_exposure.detectors import timing_rules, structure_rules


Detector = Callable[[dict, dict[str, pd.DataFrame], dict], list[Finding]]


RULE_REGISTRY: dict[str, Detector] = {
    "TERM-001": timing_rules.detect_termination_with_no_final_pay_event,
    "TERM-002": timing_rules.detect_final_pay_before_termination_date,
    "TERM-003": timing_rules.detect_significant_gap_between_last_pay_and_termination,
    "TERM-004": structure_rules.detect_missing_or_inconsistent_termination_type_or_reason,
    "TERM-005": structure_rules.detect_missing_supporting_termination_evidence_reference,
    "TERM-006": timing_rules.detect_final_pay_not_clearly_identifiable,
    "TERM-007": structure_rules.detect_terminated_employee_retains_material_lsl_balance,
    "TERM-008": structure_rules.detect_post_termination_lsl_movement_recorded,
    "TERM-009": structure_rules.detect_terminated_employee_with_lsl_balance_and_no_closure_trail,
    "TERM-010": timing_rules.detect_payroll_activity_recorded_after_termination,
    "TERM-011": structure_rules.detect_multiple_termination_records_for_employee,
    "TERM-012": structure_rules.detect_termination_without_employee_master_record,
    "TERM-013": structure_rules.detect_final_pay_missing_super_contribution,
    "TERM-014": structure_rules.detect_involuntary_termination_without_reason,
    "TERM-015": timing_rules.detect_employee_paid_after_termination_across_multiple_runs,
    "TERM-016": timing_rules.detect_termination_without_any_flagged_final_pay_event,
    "TERM-017": timing_rules.detect_termination_date_precedes_last_recorded_payroll_activity,
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