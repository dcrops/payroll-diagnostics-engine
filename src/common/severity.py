from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class SeverityDefinition:
    """
    Canonical definition of a severity level.

    These definitions are deliberately conservative and framed around
    evidential strength and potential impact, not dollar value.
    """
    code: str
    label: str
    description: str


SEVERITY_HIGH = SeverityDefinition(
    code="HIGH",
    label="High",
    description=(
        "Absence or weakness of core evidence or entitlement configuration that "
        "would materially impair the organisation’s ability to evidence payroll "
        "decisions if reviewed by auditors or regulators."
    ),
)

SEVERITY_MEDIUM = SeverityDefinition(
    code="MEDIUM",
    label="Medium",
    description=(
        "Evidence is incomplete, inconsistent or fragile. Decisions may still be "
        "defensible but require greater reliance on manual reconstruction, "
        "judgement, or explanation."
    ),
)

SEVERITY_LOW = SeverityDefinition(
    code="LOW",
    label="Low",
    description=(
        "Record-keeping or data quality weaknesses that are unlikely to be "
        "challenged in isolation but should be improved over time to support "
        "efficient and reliable payroll operations."
    ),
)

# Explicit ordering for tables / overviews
SEVERITY_ORDER: List[str] = ["HIGH", "MEDIUM", "LOW"]

# Look-up by code, used throughout reporting
SEVERITY_BY_CODE: Dict[str, SeverityDefinition] = {
    s.code: s for s in (SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW)
}
