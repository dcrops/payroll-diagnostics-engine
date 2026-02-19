from __future__ import annotations

"""
Shared, conservative wording used across reports.

This is intentionally small and boring. The goal is to:

- Encourage reuse of safe phrases
- Make it easy to avoid accidentally using over-strong language
"""

RISK_PHRASES = {
    # Used when evidence is missing or weak
    "audit_impairment": (
        "may impair the organisation’s ability to evidence payroll decisions if "
        "subject to audit or regulatory review."
    ),
    # Used when decisions could be defended but only with effort
    "relies_on_manual": (
        "increases reliance on manual reconstruction and explanation of "
        "historical decisions."
    ),
    # Used when we want to emphasise that this is about evidence, not a proven breach
    "record_keeping_weakness": (
        "represents a record-keeping weakness rather than a confirmed "
        "non-compliance."
    ),
}

# Terms that must never appear in executive narrative
HARD_FORBIDDEN_TERMS = [
    "non-compliant",
    "non compliant",
    "noncompliant",
    "guarantees",
    "guaranteed",
    "guarantee",
    "fully compliant",
]

# Terms that require careful context (warn-only)
SOFT_FLAG_TERMS = [
    "underpayment",
    "overpayment",
]


def scan_report_text(text: str) -> dict[str, list[str]]:
    """
    Scan report text for hard-forbidden and soft-flag terms.

    Returns:
        {
            "hard": [...],
            "soft": [...]
        }
    """
    lower = text.lower()

    hard_hits = [term for term in HARD_FORBIDDEN_TERMS if term in lower]
    soft_hits = [term for term in SOFT_FLAG_TERMS if term in lower]

    return {
        "hard": hard_hits,
        "soft": soft_hits,
    }

def contains_forbidden_term(text: str) -> bool:
    """Backwards-compatible helper. True if any hard-forbidden term is present."""
    return len(scan_report_text(text)["hard"]) > 0
