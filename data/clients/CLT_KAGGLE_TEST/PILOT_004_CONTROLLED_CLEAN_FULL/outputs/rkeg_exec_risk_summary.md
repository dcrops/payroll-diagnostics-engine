# RKEG – Executive Risk Summary

## Execution Context
- **Execution mode:** **full**
- **Include supporting rules:** **False**

## Overview
RKEG produced **4 findings** across the payroll evidence spine.

- **Risk rating:** **MEDIUM**
- **Risk score:** **56**
- **Severity distribution:** **HIGH=3, MEDIUM=1**

## Payroll Evidence Integrity Map
- **Entitlement Evidence  ** ████████████████████████ 4
- **Governance & Controls ** ████████████████████████ 4
- **Workforce Identity    ** ██████ 1

## Top risk dimensions (by linked findings)
- **governance_exposure**: 4 linked findings
- **timing_integrity**: 3 linked findings
- **evidence_traceability**: 1 linked findings

## Interpretation
The dominant exposure is **governance_exposure**, indicating gaps in the organisation's ability to reconstruct and substantiate payroll outcomes.

## Most frequently triggered rules
- `RKEG-TERM-001` (HIGH): 2
- `RKEG-PAY-010` (HIGH): 1
- `RKEG-GOV-001` (MEDIUM): 1

## Recommended actions
- `RKEG-TERM-001`: Review termination processing workflows and ensure final pay is calculated and processed within the required statutory timeframe.
- `RKEG-PAY-010`: Reconcile pay events against employment start and termination dates and investigate any payments recorded outside valid employment periods.
- `RKEG-GOV-001`: Introduce a basic override register or system-based workflow to record all manual payroll changes, including who made the change, when, and for what reason.

## Notes
- Linked findings counts may exceed total findings because a single finding can map to multiple risk dimensions.
- This output is diagnostics-focused and does not constitute legal advice.
