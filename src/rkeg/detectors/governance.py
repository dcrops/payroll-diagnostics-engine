# src/rkeg/detectors/governance.py
from __future__ import annotations

from typing import Iterable, Dict

import pandas as pd

from rkeg.schemas import RkegFinding


def run_rule(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[RkegFinding]:
    """
    Governance / override rules (GOV or GOVERNANCE domain).

    Tier 2 logic will be implemented here later, for example:
    - RKEG-GOV-001: no override log provided
    - RKEG-GOV-002: overrides missing reason/approval
    - RKEG-GOV-003: high volume of overrides vs pay events

    Currently returns no findings to keep behaviour stable until the
    detailed implementations are added.
    """
    rule_id = rule["id"]

    # TODO: implement governance rule logic (RKEG-GOV-001..003)
    return []