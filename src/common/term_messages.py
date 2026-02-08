"""
Canonical messages and next actions for Termination Exposure (TERM) v1.

These strings are the single source of truth for TERM findings.
They must not imply incorrect payment, non-compliance, or legal breach.
"""

TERM_MESSAGES = {
    "TERM-001": {
        "message": (
            "Termination is recorded, but no identifiable final pay event was found "
            "on or after the termination date."
        ),
        "next_action": (
            "Confirm whether final pay has been processed and, if so, ensure it is "
            "clearly recorded and traceable to this termination."
        ),
    },
    "TERM-002": {
        "message": (
            "A final pay event was identified, but its pay date precedes the recorded "
            "termination date."
        ),
        "next_action": (
            "Review the sequencing of the termination and final pay dates and "
            "document the rationale supporting the current record."
        ),
    },
    "TERM-003": {
        "message": (
            "The termination date occurs significantly after the last recorded "
            "ordinary pay date."
        ),
        "next_action": (
            "Confirm whether the termination date reflects the actual end of employment "
            "and document the basis for the recorded timing."
        ),
    },
    "TERM-004": {
        "message": (
            "Termination is recorded without a clear or internally consistent "
            "termination type or reason."
        ),
        "next_action": (
            "Update termination records with an appropriate termination type or reason, "
            "or document why this information is unavailable."
        ),
    },
    "TERM-005": {
        "message": (
            "Termination is recorded without a referenced termination artefact, such as "
            "a resignation notice or termination letter."
        ),
        "next_action": (
            "Locate and link the underlying termination documentation, or record a "
            "justification where no artefact exists."
        ),
    },
    "TERM-006": {
        "message": (
            "Pay events exist around the termination date, but no pay event is clearly "
            "identifiable as final pay."
        ),
        "next_action": (
            "Clarify which pay event constitutes final pay and update records to ensure "
            "it can be readily identified in future reviews."
        ),
    },
}