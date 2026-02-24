# Record-Keeping & Evidence Gaps (RKEG) – Detailed Report

**Organisation:** Example Client Pty Ltd  
**Review period:** Period not specified  
**Report prepared as at:** 24 Feb 2026  

> This report highlights potential risk signals and process issues based on the data provided. It does not constitute legal, accounting, or industrial relations advice.

---

## 1. Executive Summary

This Record-Keeping & Evidence Gaps (RKEG) report focuses solely on evidential risk indicators identified from the supplied payroll and HR data. The review assesses how complete, consistent and traceable payroll-related records appear for audit and dispute purposes. It does **not** determine whether payroll outcomes are correct or incorrect under applicable legislation, awards or agreements.

Across the dataset provided, the automated checks identified:

- **High:** 0
- **Medium:** 0
- **Low:** 0

A detailed breakdown by severity is provided in the **Findings Overview** section.

## 2. Data Sources

This review was generated from the following analysis outputs within the project `outputs/` directory:


These outputs were produced by rule-based checks over payroll and HR CSV extracts supplied by the organisation for the review period.

---


## 3. Scope & Methodology

Scope & Methodology

**Modules included in this engagement:**

- Record-Keeping & Evidence Gaps (RKEG)

---

### 3.1 **Record-Keeping & Evidence Gaps (RKEG) – Scope & Methodology**

**Scope**

The Record-Keeping & Evidence Gaps (RKEG) review assesses whether payroll-related records are sufficiently complete, consistent and traceable to support the organisation’s ability to evidence payroll decisions if reviewed by auditors or regulators.

RKEG focuses on evidential strength, not on determining whether payroll outcomes are correct or incorrect. Findings highlight where records may be incomplete, inconsistent, or difficult to substantiate if challenged.

This review is intended to support risk-aware payroll operations by identifying evidence weaknesses that can increase audit effort, increase dispute risk, or reduce the organisation’s ability to confidently explain pay decisions.

**Data reviewed**

- employee master data (where supplied)
- pay event / payroll transaction extracts (where supplied)
- termination and employment status fields where included in the engagement data pack

**Checks performed**

- completeness checks for key employee master fields required for traceability and defensibility
- identification of orphan or untraceable pay events (for example, pay events with missing or inconsistent identifiers)
- consistency checks across employee status and payroll activity where possible
- identification of gaps that may require manual reconstruction to support an audit trail

**Out of scope**

This review does not:

- calculate entitlements, underpayments or overpayments
- interpret awards, enterprise agreements, or employment contracts
- provide legal, accounting, or industrial relations advice
- assert contraventions of legislation or confirm non-compliance.

RKEG findings should be interpreted as evidential risk indicators. Addressing them improves defensibility and reduces audit effort, but does not necessarily imply a payroll outcome is incorrect.

---


## 4. Findings Overview



## 5. Detailed Findings

No record-keeping or evidence gaps were identified for the supplied data.

---



## 6. Limitations & Assumptions

This review is subject to the following limitations:


- Calculations assume the underlying pay rates, loadings and multipliers are correct in the source systems.
- Award and enterprise agreement interpretation is not performed by this tool.
- Holiday calendars, leave rules and accrual settings are assumed to reflect the organisation’s intended configuration.
- Data quality issues (missing records, duplicates, inconsistent identifiers) may affect the completeness and accuracy of the results.

---


## 7. Recommended Next Steps

Recommended Next Steps

1. Prioritise validation of **High** severity findings.
2. Review affected employee records and reconstruct balances where necessary.
3. Correct any identified configuration or process issues in payroll and HR systems.
4. Consider remediation where confirmed underpayments have occurred.
5. Re-run the review after corrections to confirm that leakage has been addressed.

---


## 8. Appendices

### Appendix A – Rule Definitions

This review used a set of automated rules to flag evidential and process risk indicators.

#### Record-Keeping & Evidence Gaps (RKEG)

- Missing employee master data fields
- Orphan pay events and traceability gaps
- Inconsistent employment status records
- Missing or inconsistent termination attributes

---

### Appendix B – Data Fields Used

Key data fields referenced in this engagement include:

**Record-Keeping & Evidence Gaps (RKEG)**

- `employee_id`
- `leave_type`
- `as_of_date`
- `rule_code`
- `severity`
- `message`
- `diff_units`
- `evidence`
- `finding_id`
- `next_action`

---

### Appendix C – Machine-readable outputs

Complete machine-readable outputs are available in the following files:

- `outputs/modules/rkeg_findings.csv`

These files provide row-level detail suitable for operational review, sampling, remediation planning, or incorporation into a broader audit work program.

---

