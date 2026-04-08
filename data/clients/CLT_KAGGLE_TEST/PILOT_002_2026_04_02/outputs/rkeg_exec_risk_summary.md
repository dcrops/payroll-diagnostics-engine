# RKEG – Executive Risk Summary

## Overview
RKEG produced **3 findings** across the payroll evidence spine.

- **Risk rating:** **MEDIUM**
- **Risk score:** **44**
- **Severity distribution:** **HIGH=2, MEDIUM=1**

## Payroll Evidence Integrity Map
- **Entitlement Evidence  ** ████████████████████████ 3
- **Governance & Controls ** ████████████████ 2
- **Workforce Identity    ** ████████████████ 2

## Top risk dimensions (by linked findings)
- **cross_module_linkage_risk**: 2 linked findings
- **evidence_traceability**: 2 linked findings
- **governance_exposure**: 2 linked findings

## Interpretation
The dominant exposure is **cross_module_linkage_risk**, indicating gaps in the organisation's ability to reconstruct and substantiate payroll outcomes.

## Most frequently triggered rules
- `RKEG-LEAVE-001` (HIGH): 1
- `RKEG-PAY-010` (HIGH): 1
- `RKEG-GOV-001` (MEDIUM): 1

## Recommended actions
- `RKEG-LEAVE-001`: Reconcile leave ledger movements to payroll transactions and ensure all leave adjustments are system-generated and documented.
- `RKEG-PAY-010`: Reconcile pay events against employment start and termination dates and investigate any payments recorded outside valid employment periods.
- `RKEG-GOV-001`: Introduce a basic override register or system-based workflow to record all manual payroll changes, including who made the change, when, and for what reason.

## Notes
- Linked findings counts may exceed total findings because a single finding can map to multiple risk dimensions.
- This output is diagnostics-focused and does not constitute legal advice.
