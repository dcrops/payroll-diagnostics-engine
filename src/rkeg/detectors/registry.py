from __future__ import annotations

from typing import Callable
import pandas as pd

from rkeg.models import Finding
from rkeg.detectors import employee, pay, leave, termination, super_, governance


Detector = Callable[[dict, dict[str, pd.DataFrame], dict], list[Finding]]


def _detect_emp(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    return employee.run_rule(rule, datasets)


def _detect_pay(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    return pay.run_rule(rule, datasets)


def _detect_leave(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    return leave.run_rule(rule, datasets)


def _detect_term(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    return termination.run_rule(rule, datasets)


def _detect_sup(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    return super_.run_rule(rule, datasets)


def _detect_gov(rule: dict, datasets: dict[str, pd.DataFrame], context: dict) -> list[Finding]:
    return governance.run_rule(rule, datasets)


DOMAIN_REGISTRY: dict[str, Detector] = {
    "EMP": _detect_emp,
    "PAY": _detect_pay,
    "LEAVE": _detect_leave,
    "TERM": _detect_term,
    "SUP": _detect_sup,
    "GOV": _detect_gov,
    "GOVERNANCE": _detect_gov,
}


def run_rule(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict | None = None,
) -> list[Finding]:
    detector = DOMAIN_REGISTRY.get(str(rule.get("domain", "")).strip().upper())
    if detector is None:
        return []
    return detector(rule, datasets, context or {})