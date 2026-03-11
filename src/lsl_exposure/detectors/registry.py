from __future__ import annotations

from typing import Callable
import pandas as pd

from lsl_exposure.models import Finding
from lsl_exposure.detectors import accrual_rules, structure_rules


Detector = Callable[[dict, dict[str, pd.DataFrame], dict], list[Finding]]


RULE_REGISTRY: dict[str, Detector] = {
    "LSL-001": accrual_rules.detect_missing_lsl_balance_for_eligible,
    "LSL-002": accrual_rules.detect_negative_lsl_balance,
    "LSL-003": accrual_rules.detect_zero_lsl_balance_for_eligible,
    "LSL-004": accrual_rules.detect_low_lsl_balance_for_long_tenure,
    "LSL-005": accrual_rules.detect_lsl_balance_below_eligibility,
    "LSL-006": structure_rules.detect_missing_lsl_balance_record,
    "LSL-007": accrual_rules.detect_extreme_lsl_balance,
    "LSL-008": structure_rules.detect_multiple_lsl_leave_types,
    "LSL-009": structure_rules.detect_duplicate_lsl_balance_records,
    "LSL-010": accrual_rules.detect_lsl_balance_near_eligibility_threshold,
    "LSL-011": accrual_rules.detect_lsl_balance_inconsistent_with_fte,
    "LSL-012": structure_rules.detect_lsl_balance_without_ledger_history,
    "LSL-013": accrual_rules.detect_lsl_taken_before_eligibility,
    "LSL-014": accrual_rules.detect_lsl_ledger_balance_mismatch,
    "LSL-015": structure_rules.detect_lsl_movement_after_termination,
    "LSL-016": structure_rules.detect_invalid_service_start_basis,
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