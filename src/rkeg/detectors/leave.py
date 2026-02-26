# src/rkeg/detectors/leave.py
from __future__ import annotations

from typing import Iterable, Dict

import pandas as pd

from rkeg.schemas import RkegFinding


def run_rule(rule: dict, datasets: Dict[str, pd.DataFrame]) -> Iterable[RkegFinding]:
    """
    Entry point for LEAVE-domain RKEG rules.

    For now we only recognise RKEG-LEAVE-001 and return an empty list
    as a safe placeholder, so enabling Tier 2 / new rules doesn't break
    the engine. We'll implement the full logic later.
    """
    rule_id = rule["id"]

    if rule_id == "RKEG-LEAVE-001":
        # TODO: implement logic for:
        # "Leave ledger movement without corresponding pay event"
        # using leave_ledger + pay_events + employee_master.
        return []

    # Safety net for typos / future rules
    raise ValueError(f"Unknown LEAVE rule: {rule_id}")