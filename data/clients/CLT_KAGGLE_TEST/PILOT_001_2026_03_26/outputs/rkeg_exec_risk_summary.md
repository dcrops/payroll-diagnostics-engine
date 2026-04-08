# RKEG – Executive Risk Summary

## Overview
RKEG produced **794 findings** across the payroll evidence spine.

- **Risk rating:** **HIGH**
- **Risk score:** **95**
- **Severity distribution:** **HIGH=793, MEDIUM=1**

## Payroll Evidence Integrity Map
- **Entitlement Evidence  ** ████████████████████████ 774
- **Workforce Identity    ** █████████████████ 557
- **Pay Construction      ** ████████ 256
- **Governance & Controls ** ███████ 238

## Top risk dimensions (by linked findings)
- **evidence_traceability**: 557 linked findings
- **cross_module_linkage_risk**: 537 linked findings
- **calculation_integrity**: 256 linked findings

## Interpretation
The dominant exposure is **evidence_traceability**, indicating gaps in the organisation's ability to reconstruct and substantiate payroll outcomes.

## Most frequently triggered rules
- `RKEG-LEAVE-001` (HIGH): 300
- `RKEG-LEAVE-002` (HIGH): 256
- `RKEG-PAY-010` (HIGH): 237
- `RKEG-GOV-001` (MEDIUM): 1

## Recommended actions
- `RKEG-LEAVE-001`: Reconcile leave ledger movements to payroll transactions and ensure all leave adjustments are system-generated and documented.
- `RKEG-LEAVE-002`: Reconcile leave snapshots to the transactional leave ledger, investigate discrepancies above the tolerance threshold and address configuration or processing gaps that prevent balances from being reconstructed from system movements.
- `RKEG-PAY-010`: Reconcile pay events against employment start and termination dates and investigate any payments recorded outside valid employment periods.
- `RKEG-GOV-001`: Introduce a basic override register or system-based workflow to record all manual payroll changes, including who made the change, when, and for what reason.

## Notes
- Linked findings counts may exceed total findings because a single finding can map to multiple risk dimensions.
- This output is diagnostics-focused and does not constitute legal advice.
