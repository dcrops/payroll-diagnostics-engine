# Leave & Entitlement Leakage – Detailed Report

**Organisation:** Organisation not specified
**Review period:** Period not specified  
**Report prepared as at:** 23 Feb 2026  

> This report highlights potential risk signals and process issues based on the data provided. It does not constitute legal, accounting, or industrial relations advice.

---

## 1. Executive Summary

This Leave & Entitlement Leakage report focuses solely on leave-related risk indicators identified from the supplied payroll and HR data. Findings are risk indicators only and do not, on their own, confirm underpayment, non-compliance, or an entitlement error.

Across the dataset provided, the automated checks identified:

- **High:** 0
- **Medium:** 0
- **Low:** 0

A detailed breakdown by severity is provided in the **Findings Overview** section.

No exposure estimates were available from the current data extract. If required, leakage estimates can be added to this section in future runs.

---

## 2. Data Sources

This review was generated from the following analysis outputs within the project `outputs/` directory:

- `modules\leave_leakage_findings.csv`  
- `leakage_report.csv`  

These outputs were produced by rule-based checks over payroll and HR CSV extracts supplied by the organisation for the review period.

---


## 3. Scope & Methodology

Scope & Methodology

**Modules included in this engagement:**

- Leave & Entitlement Leakage (LEAVE)

---

### 3.1 **Leave & Entitlement Leakage – Scope & Methodology**

**Scope**

The Leave & Entitlement Leakage review identifies potential anomalies and risk indicators in leave balances, accruals and leave usage based on the data provided.

The purpose of this review is to highlight records that may warrant follow-up, such as negative balances, unexpected accrual patterns, mismatches between leave activity and employee status, or inconsistencies between leave movement data and balance snapshots.

This review is designed to support payroll and HR teams in prioritising validation and remediation effort. Findings are risk signals only and do not, on their own, confirm non-compliance, underpayment, or an entitlement error.

**Data reviewed**

- leave balances snapshot data (where supplied)
- leave ledger / leave movement records (where supplied)
- employee master data (where supplied)
- other supporting payroll extracts included in the engagement pack

**Checks performed**

- rule-based detection of unusual leave balance and movement patterns
- identification of negative balances and unexpected accrual behaviour
- consistency checks between employee status and leave activity (for example, terminated employees with ongoing leave movements)
- cross-checks between leave movement data and balance snapshot fields where available

**Out of scope**

This review does not:

- interpret awards, enterprise agreements, or employment contracts
- calculate legal entitlement outcomes or confirm the correctness of leave accrual rules
- provide legal, accounting, or industrial relations advice
- assert contraventions of legislation or confirm non-compliance.

Where exposure estimates are included, they are indicative only and must be validated before remediation or accounting decisions are made.

---


## 4. Findings Overview

The automated checks identified the following potential issues in the leave and entitlement data reviewed. Severity reflects the relative level of risk to payroll accuracy and audit defensibility, not a confirmed breach.

| Severity | Count | Description |
|---------|:-----:|-------------|
| <span class="badge-high">High</span>    | 0   | Absence or weakness of core evidence or entitlement configuration that would materially impair the organisation’s ability to evidence payroll decisions if reviewed by auditors or regulators. |
| <span class="badge-medium">Medium</span>  | 0   | Evidence is incomplete, inconsistent or fragile. Decisions may still be defensible but require greater reliance on manual reconstruction, judgement, or explanation.  |
| <span class="badge-low">Low</span>     | 0   | Record-keeping or data quality weaknesses that are unlikely to be challenged in isolation but should be improved over time to support efficient and reliable payroll operations.  |

---


## 5. Detailed Findings

No findings were identified for the supplied data.

---



## 6. Financial Exposure (Indicative)

No exposure estimates were available from the current data extract. If required, leakage estimates can be added to this section in future runs.

---



## 7. Limitations & Assumptions

This review is subject to the following limitations:


- Calculations assume the underlying pay rates, loadings and multipliers are correct in the source systems.
- Award and enterprise agreement interpretation is not performed by this tool.
- Holiday calendars, leave rules and accrual settings are assumed to reflect the organisation’s intended configuration.
- Data quality issues (missing records, duplicates, inconsistent identifiers) may affect the completeness and accuracy of the results.

---


## 8. Recommended Next Steps

Recommended Next Steps

1. Prioritise validation of **High** severity findings.
2. Review affected employee records and reconstruct balances where necessary.
3. Correct any identified configuration or process issues in payroll and HR systems.
4. Consider remediation where confirmed underpayments have occurred.
5. Re-run the review after corrections to confirm that leakage has been addressed.

---


## 9. Appendices

### Appendix A – Rule Definitions

This review used a set of automated rules to flag evidential and process risk indicators.

#### Leave & Entitlement Leakage

- Negative balance checks
- Casual employees accruing leave
- Inactive or terminated employees with leave movements
- Unusual accrual or usage patterns

---

### Appendix B – Data Fields Used

Key data fields referenced in this engagement include:

**Leave & Entitlement Leakage**

- `employee_id`
- `leave_type`
- `as_of_date`
- `rule_code`
- `severity`
- `message`
- `diff_units`
- `finding_id`
- `next_action`

### Appendix C – Machine-readable outputs

Complete machine-readable outputs are available in the following files:

- `outputs/modules/leave_leakage_findings.csv`
- `outputs/leakage_report.csv`

These files provide row-level detail suitable for operational review, sampling, remediation planning, or incorporation into a broader audit work program.

---

