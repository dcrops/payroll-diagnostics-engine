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

# Terms we want to avoid in narrative text. These are not enforced automatically,
# but act as a checklist when drafting new sections.
FORBIDDEN_TERMS = [
    "breach",
    "breaches",
    "non-compliant",
    "non compliant",
    "noncompliant",
    "guarantees",
    "guaranteed",
    "guarantee",
    "fully compliant",
    "underpayment",   # if needed, use 'potential underpayment risk' very carefully
    "overpayment",
]


def contains_forbidden_term(text: str) -> bool:
    """
    Lightweight helper for ad-hoc checks in tests or scripts.
    Not used in core reporting flows yet.
    """
    lower = text.lower()
    return any(term in lower for term in FORBIDDEN_TERMS)
