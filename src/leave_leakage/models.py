from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import json
import hashlib


@dataclass
class Finding:
    employee_id: str | None
    leave_type: Optional[str]
    as_of_date: Optional[str]
    rule_code: str
    severity: str
    message: str
    diff_units: Optional[float] = None
    evidence: Optional[str] = None
    finding_id: Optional[str] = None
    next_action: Optional[str] = None


def compute_finding_id(rule_code: str, evidence_json: Optional[str]) -> str:
    """
    Deterministic ID based on rule_code + evidence.primary_keys.
    Stable across runs provided primary_keys remain stable.
    """
    primary_keys = {}
    if evidence_json:
        try:
            payload = json.loads(evidence_json)
            primary_keys = payload.get("primary_keys") or {}
        except Exception:
            primary_keys = {}

    parts = [rule_code]
    for k in sorted(primary_keys.keys()):
        parts.append(f"{k}={primary_keys.get(k)}")

    canonical = "|".join(parts)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]


def _build_finding(
    rule: dict,
    employee_id: str | None,
    leave_type: str | None,
    as_of_date: str | None,
    message: str,
    evidence_str: str,
    diff_units: float | None = None,
) -> Finding:
    return Finding(
        employee_id=employee_id,
        leave_type=leave_type,
        as_of_date=as_of_date,
        rule_code=rule["id"],
        severity=rule["severity"],
        message=message,
        diff_units=diff_units,
        evidence=evidence_str,
        finding_id=compute_finding_id(rule["id"], evidence_str),
        next_action=rule["text"]["remediation"],
    )