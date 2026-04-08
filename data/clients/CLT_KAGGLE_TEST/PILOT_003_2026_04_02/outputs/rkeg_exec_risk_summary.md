# RKEG – Executive Risk Summary

## Overview
RKEG produced **16 findings** across the payroll evidence spine.

- **Risk rating:** **HIGH**
- **Risk score:** **91**
- **Severity distribution:** **HIGH=12, MEDIUM=4**

## Payroll Evidence Integrity Map
- **Entitlement Evidence  ** ████████████████████████ 27
- **Governance & Controls ** ██████████████ 16
- **Workforce Identity    ** █ 1

## Top risk dimensions (by linked findings)
- **governance_exposure**: 16 linked findings
- **timing_integrity**: 15 linked findings
- **cross_module_linkage_risk**: 12 linked findings

## Interpretation
The dominant exposure is **governance_exposure**, indicating gaps in the organisation's ability to reconstruct and substantiate payroll outcomes.

## Most frequently triggered rules
- `RKEG-PAY-010` (HIGH): 9
- `RKEG-TERM-001` (HIGH): 3
- `RKEG-PAY-010` (MEDIUM): 3
- `RKEG-GOV-001` (MEDIUM): 1

## Recommended actions
- `RKEG-PAY-010`: Reconcile pay events against employment start and termination dates and investigate any payments recorded outside valid employment periods.
- `RKEG-TERM-001`: Review termination processing workflows and ensure final pay is calculated and processed within the required statutory timeframe.
- `RKEG-PAY-010`: Reconcile pay events against employment start and termination dates and investigate any payments recorded outside valid employment periods.
- `RKEG-GOV-001`: Introduce a basic override register or system-based workflow to record all manual payroll changes, including who made the change, when, and for what reason.

## Notes
- Linked findings counts may exceed total findings because a single finding can map to multiple risk dimensions.
- This output is diagnostics-focused and does not constitute legal advice.
