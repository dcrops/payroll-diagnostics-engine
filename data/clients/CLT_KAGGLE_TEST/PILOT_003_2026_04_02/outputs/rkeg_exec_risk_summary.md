# RKEG – Executive Risk Summary

## Overview
RKEG produced **49 findings** across the payroll evidence spine.

- **Risk rating:** **HIGH**
- **Risk score:** **99**
- **Severity distribution:** **MEDIUM=31, HIGH=18**

## Payroll Evidence Integrity Map
- **Workforce Identity    ** ████████████████████████ 61
- **Entitlement Evidence  ** █████████████ 33
- **Pay Construction      ** ████████████ 30
- **Governance & Controls ** ███████ 19

## Top risk dimensions (by linked findings)
- **evidence_traceability**: 31 linked findings
- **calculation_integrity**: 30 linked findings
- **structural_completeness**: 30 linked findings

## Interpretation
The dominant exposure is **evidence_traceability**, indicating gaps in the organisation's ability to reconstruct and substantiate payroll outcomes.

## Most frequently triggered rules
- `RKEG-PAY-006` (MEDIUM): 30
- `RKEG-PAY-010` (HIGH): 15
- `RKEG-TERM-001` (HIGH): 3
- `RKEG-GOV-001` (MEDIUM): 1

## Recommended actions
- `RKEG-PAY-006`: Ensure base rate fields are populated and aligned with earnings calculations.
- `RKEG-PAY-010`: Reconcile pay events against employment start and termination dates and investigate any payments recorded outside valid employment periods.
- `RKEG-TERM-001`: Review termination processing workflows and ensure final pay is calculated and processed within the required statutory timeframe.
- `RKEG-GOV-001`: Introduce a basic override register or system-based workflow to record all manual payroll changes, including who made the change, when, and for what reason.

## Notes
- Linked findings counts may exceed total findings because a single finding can map to multiple risk dimensions.
- This output is diagnostics-focused and does not constitute legal advice.
