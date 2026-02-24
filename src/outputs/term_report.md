# Termination Exposure – Detailed Report

**Organisation:** Example Client Pty Ltd  
**Review period:** Period not specified  
**Report prepared as at:** 24 Feb 2026  

> This report highlights potential risk signals and process issues based on the data provided. It does not constitute legal, accounting, or industrial relations advice.

---

## 1. Executive Summary

This Termination Exposure report focuses solely on termination-related evidential risk indicators identified from the supplied payroll and HR data. The review assesses how complete, timely and traceable termination records appear for audit and dispute purposes. It does **not** determine whether termination payments are correct under applicable awards, agreements or contracts.

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

- Termination Exposure (TERM)

---

### 3.1 **Termination Exposure – Scope & Methodology**

**Scope**

The Termination Exposure review assesses whether termination events recorded in payroll and related employment data are sufficiently complete, timely, and traceable to support the organisation’s ability to evidence termination-related payroll decisions if reviewed by auditors or regulators.

This review focuses on process and evidential integrity, not on the correctness of termination payments.

Specifically, the review considers whether:

- termination events are recorded consistently across available data sources
- final pay processing occurs in a reasonable and defensible sequence relative to termination dates
- core termination attributes (such as termination date and termination type/reason) are present and internally consistent
- termination-related decisions are supported by basic evidentiary artefacts or references

**Out of scope**

This review does not:

- calculate final pay entitlements or assess payment correctness
- interpret awards, enterprise agreements, or employment contracts
- determine notice, redundancy, or severance obligations
- assert contraventions of legislation or confirm non-compliance.
- provide legal advice or assurance of compliance.

Any potential exposure identified reflects defensibility risk, not confirmed error or liability.

**Methodology**

The review applies a series of rule-based checks to payroll and related employment data to identify termination events that exhibit characteristics commonly associated with audit, regulatory, or dispute risk.

Each finding is assigned a severity based on evidential impact, reflecting how materially the issue could impair the organisation’s ability to explain and support termination-related payroll decisions if reviewed.

Severity does not represent:

- likelihood of underpayment
- magnitude of financial exposure
- remediation priority

---


## 4. Findings Overview



## 5. Detailed Findings

No termination-related findings were identified for the supplied data.

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

#### Termination Exposure (TERM)

- Final pay sequencing checks vs termination date
- Missing / inconsistent termination dates
- Missing / inconsistent termination type / reason
- Missing evidence references / artefact identifiers
- Ambiguous identification of final pay events within a window
- Termination events inconsistent with ordinary pay activity patterns

---

### Appendix B – Data Fields Used

Key data fields referenced in this engagement include:

**Termination Exposure (TERM)**

- `employee_id`
- `termination_date`
- `final_pay_date`
- `rule_code`
- `severity`
- `message`
- `days_gap`
- `evidence`
- `finding_id`
- `next_action`

### Appendix C – Machine-readable outputs

Complete machine-readable outputs are available in the following files:

- `outputs/modules/term_findings.csv`

These files provide row-level detail suitable for operational review, sampling, remediation planning, or incorporation into a broader audit work program.

---

