from __future__ import annotations

from typing import Dict

from common.severity import SEVERITY_BY_CODE, SEVERITY_ORDER


def _build_scope_phrase(
    has_emp: bool,
    has_pay: bool,
    has_term: bool,
) -> str:
    """Convert booleans into a readable scope sentence fragment."""
    scopes = []

    if has_emp:
        scopes.append("employee master records (existence, completeness and status)")
    if has_pay:
        scopes.append("pay event records (dates, amounts and traceability)")
    if has_term:
        scopes.append("termination records and finalisation evidence")

    if not scopes:
        return "selected payroll-related records"

    if len(scopes) == 1:
        return scopes[0]

    # Join with commas and "and" for the final item
    return ", ".join(scopes[:-1]) + " and " + scopes[-1]


def build_rkeg_summary_paragraph(
    has_emp: bool = True,
    has_pay: bool = True,
    has_term: bool = False,
) -> str:
    """
    Canonical explanation of what the RKEG assessment does and does not do.

    This text is shared between the detailed module report and the combined
    exposure overview so that the description cannot drift.
    """
    scope_text = _build_scope_phrase(has_emp=has_emp, has_pay=has_pay, has_term=has_term)

    return f"""
As part of this review, a Record-Keeping & Evidence Gaps (RKEG) assessment was performed across {scope_text} to evaluate whether the data is sufficiently complete, consistent and traceable to support payroll decisions if subject to audit or regulatory review.

The RKEG assessment does **not** determine whether payroll outcomes are correct or incorrect, nor does it interpret awards or enterprise agreements. It focuses solely on the strength of the evidential trail available to substantiate decisions that have already been made.
""".strip()


def build_rkeg_severity_overview_table(rkeg_counts: Dict[str, int]) -> str:
    """
    Severity summary table (table-only, no headings).
    """

    counts = {code: int(rkeg_counts.get(code, 0) or 0) for code in SEVERITY_ORDER}

    high = SEVERITY_BY_CODE["HIGH"]
    med = SEVERITY_BY_CODE["MEDIUM"]
    low = SEVERITY_BY_CODE["LOW"]

    lines = [
        "| Severity | Count | Description |",
        "|----------|:-----:|-------------|",
        f"| <span class=\"badge-high\">{high.label}</span> | {counts['HIGH']} | {high.description} |",
        f"| <span class=\"badge-medium\">{med.label}</span> | {counts['MEDIUM']} | {med.description} |",
        f"| <span class=\"badge-low\">{low.label}</span> | {counts['LOW']} | {low.description} |",
        "",
    ]

    return "\n".join(lines)

