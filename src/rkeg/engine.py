# src/rkeg/engine.py
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Set

import yaml
import pandas as pd

from .schemas import RkegFinding
from .detectors import employee, pay, leave, termination, super_, governance  # type: ignore  # noqa: F401


RULES_PATH = Path(__file__).parent / "config" / "rkeg_rules.yml"


def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _filter_rules_by_tier(
    rules: list[dict],
    enabled_tiers: Set[int] | None,
) -> list[dict]:
    """Filter rules by the set of enabled tiers.

    If enabled_tiers is None or empty, all rules are returned.
    Rules with no explicit `tier` are treated as tier 1 by default.
    """
    if not enabled_tiers:
        return rules

    filtered: list[dict] = []
    for rule in rules:
        rule_tier = int(rule.get("tier", 1))
        if rule_tier in enabled_tiers:
            filtered.append(rule)
    return filtered


def run_rkeg_engine(
    datasets: dict[str, pd.DataFrame],
    enabled_tiers: Set[int] | None = None,
) -> Iterable[RkegFinding]:
    """
    Main RKEG engine.

    - Loads rules from YAML
    - Optionally filters by `tier`
    - Delegates execution to the appropriate domain detector.
    """
    config = load_rules()
    all_rules = config.get("rules", [])

    rules = _filter_rules_by_tier(all_rules, enabled_tiers)

    findings: list[RkegFinding] = []

    for rule in rules:
        domain = rule["domain"]
        rule_id = rule["id"]

        if domain == "EMP":
            domain_findings = employee.run_rule(rule, datasets)
        elif domain == "PAY":
            domain_findings = pay.run_rule(rule, datasets)
        elif domain == "LEAVE":
            domain_findings = leave.run_rule(rule, datasets)
        elif domain == "TERM":
            domain_findings = termination.run_rule(rule, datasets)
        elif domain == "SUP":
            # Superannuation integrity / reconciliation rules
            domain_findings = super_.run_rule(rule, datasets)
        elif domain in ("GOV", "GOVERNANCE"):
            # Governance / override rules
            domain_findings = governance.run_rule(rule, datasets)
        else:
            # Unknown or not-yet-implemented domain; skip gracefully
            # (better to ignore than to break the engine)
            continue

        findings.extend(domain_findings)

    return findings