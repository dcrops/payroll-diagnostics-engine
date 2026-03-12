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