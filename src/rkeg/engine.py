# src/rkeg/engine.py
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml
import pandas as pd

from .schemas import RkegFinding
from .detectors import employee, pay, leave, termination  # noqa: F401

from rkeg.detectors import employee, pay


RULES_PATH = Path(__file__).parent / "config" / "rkeg_rules.yml"


def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_rkeg_engine(datasets: dict[str, pd.DataFrame]) -> Iterable[RkegFinding]:
    """
    Main RKEG engine. Iterates rules and delegates to domain detectors.
    """
    config = load_rules()
    rules = config.get("rules", [])

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
        else:
            continue  # unknown domain; ignore for now

        findings.extend(domain_findings)

    return findings
