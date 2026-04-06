# Payroll Risk & Evidence Review

**Organisation:** CLT Kaggle Test  
**Review period:** 13 Jan 2022 to 06 May 2024  
**Report prepared as at:** 06 Apr 2026  

**Important note**

This report highlights potential risk signals and process issues based on the data provided. 
It does not constitute legal, accounting, or industrial relations advice.


---

## 1. Executive Summary

- CRC identified 109 findings across the reviewed modules.
- The overall profile is primarily driven by logical integrity failures rather than structural data limitations.
- High-severity findings are concentrated in termination handling and record-keeping controls, indicating the strongest exposure sits in those areas.
- Structural findings are present, but they are not the primary driver of risk in this review.
- A substantial proportion of findings are high severity, indicating meaningful control exposure.

### What this means

The results suggest the main concern is substantive payroll processing and control integrity rather than simple evidentiary or data quality limitations.

### Recommended focus

Prioritise detailed review of termination handling and record-keeping controls first, then address structural data gaps that may weaken evidentiary confidence.

## 2. Highlight Insights

The following points summarise the most important observations from the analysis:

- The strongest concentration of risk sits in **termination handling and record-keeping controls**.
- The overall profile is dominated by **logical** findings rather than primarily structural data issues.
- A meaningful share of findings are **high severity**, indicating that the results warrant targeted follow-up rather than simple monitoring.

---


## 3. Risk Profile Overview

This section summarises the overall risk profile across all included modules using the consolidated CRC summary outputs.

<table class="summary-table">
  <thead>
    <tr><th>Metric</th><th>Value</th></tr>
  </thead>
  <tbody>
    <tr><td>Total findings</td><td>109</td></tr>
    <tr><td>Dominant classification</td><td>LOGICAL</td></tr>
    <tr><td>Dominant severity</td><td>HIGH</td></tr>
    <tr><td>Logical findings</td><td>63 (58%)</td></tr>
    <tr><td>Structural findings</td><td>37 (34%)</td></tr>
    <tr><td>Contextual findings</td><td>9 (8%)</td></tr>
    <tr><td>High severity findings</td><td>63 (58%)</td></tr>
    <tr><td>Medium severity findings</td><td>46 (42%)</td></tr>
    <tr><td>Low severity findings</td><td>0 (0%)</td></tr>
  </tbody>
</table>

**Highest concentration of high-severity findings:** Termination Exposure, Record-Keeping & Evidence Gaps

Classification is used to distinguish between substantive integrity issues, structural data limitations, and contextual items requiring human judgement.

---


## 4. Data Sources

This review was generated from the following analysis outputs within the project `outputs/` directory:

- `leave_leakage_findings.csv`  
- `leakage_report.csv`  
- `lsl_summary_by_severity.csv`  
- `lsl_findings.csv`  
- `term_summary_by_severity.csv`  
- `term_findings.csv`  
- `rkeg_summary_by_severity.csv`  
- `rkeg_findings.csv`  
- `cross_module_summary_by_severity.csv`  
- `cross_module_findings.csv`  
- `executive\executive_summary.md`  
- `executive\executive_summary.json`  

These outputs were produced by rule-based checks over payroll and HR CSV extracts supplied by the organisation for the review period.

---


## 5. Scope & Methodology

Scope & Methodology

**Modules included in this engagement:**

- Leave & Entitlement Leakage (LEAVE)
- Long Service Leave Exposure (LSL)
- Termination Exposure (TERM)
- Record-Keeping & Evidence Gaps (RKEG)
- Cross-Module Integrity (CROSS_MODULE)

---

### 5.1 **Leave & Entitlement Leakage – Scope & Methodology**

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

### 5.2 **Long Service Leave (LSL) Exposure – Scope & Methodology**

**Scope**

The Long Service Leave (LSL) Exposure review identifies risk indicators in LSL balance and service-related data that may warrant further validation. The purpose of this review is to highlight records that appear inconsistent, incomplete, or difficult to substantiate based on the data provided.

This review is designed to support payroll, HR and finance teams in prioritising follow-up effort. Findings are risk signals only and do not, on their own, confirm an entitlement error, underpayment, or non-compliance.

**Data reviewed**

- employee master data relevant to LSL service (where supplied)
- LSL balance snapshot data (where supplied)
- LSL accrual or movement records (where supplied)
- other supporting payroll extracts included in the engagement pack

**Checks performed**

- consistency checks between LSL balances, accrual patterns, and available service-related fields
- identification of missing or incomplete service date records required to support LSL calculations
- detection of unusual balance or movement patterns that may indicate configuration or data issues

**Out of scope**

This review does not:

- interpret awards, enterprise agreements, or employment contracts
- calculate legal LSL entitlement outcomes or confirm the correctness of LSL accrual rules
- provide legal, accounting, or industrial relations advice
- assert contraventions of legislation or confirm non-compliance.

Where any exposure estimates or balance concerns are inferred, they are indicative only and must be validated before remediation or accounting decisions are made.

---

### 5.3 **Termination Exposure – Scope & Methodology**

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

### 5.4 **Record-Keeping & Evidence Gaps (RKEG) – Scope & Methodology**

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

### 5.5 **Cross-Module Integrity – Scope & Methodology**

**Scope**

The Cross-Module Integrity review assesses whether related payroll datasets align consistently across employee lifecycle, leave, payroll event, and termination records.

The purpose of this review is to identify inconsistencies between linked datasets that may indicate sequencing issues, lifecycle mismatches, incomplete integrations, or broader payroll data integrity weaknesses.

This review is designed to support payroll, HR, finance, and governance teams in identifying where records may not align cleanly across the broader payroll data environment. Findings are integrity signals only and do not, on their own, confirm non-compliance, underpayment, or payroll error.

**Data reviewed**

- employee master data (where supplied)
- leave balances and leave movement data (where supplied)
- payroll event / payroll transaction extracts (where supplied)
- termination and lifecycle-related records where included in the engagement data pack

**Checks performed**

- consistency checks between employee lifecycle status and payroll activity
- identification of mismatches between leave activity and termination or employment status
- cross-dataset linkage checks for related employee and payroll records
- detection of sequencing anomalies between linked events across modules

**Out of scope**

This review does not:

- calculate entitlements, underpayments or overpayments
- interpret awards, enterprise agreements, or employment contracts
- provide legal, accounting, or industrial relations advice
- assert contraventions of legislation or confirm non-compliance.

Cross-module findings should be interpreted as data integrity and linkage risk indicators. They highlight where records may not align cleanly across datasets and may require investigation before conclusions are drawn.

---


## 6. Module Summary Overview



### 6.1 Leave & Entitlement Leakage (LEAVE) – Summary Overview

The automated checks identified the following potential issues in the leave and entitlement data reviewed. Severity reflects the relative level of risk to payroll accuracy and audit defensibility, not a confirmed breach.

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>12</td>
      <td>Absence or weakness of core evidence or entitlement configuration that would materially impair the organisation’s ability to evidence payroll decisions if reviewed by auditors or regulators.</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>0</td>
      <td>Evidence is incomplete, inconsistent or fragile. Decisions may still be defensible but require greater reliance on manual reconstruction, judgement, or explanation.</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>0</td>
      <td>Record-keeping or data quality weaknesses that are unlikely to be challenged in isolation but should be improved over time to support efficient and reliable payroll operations.</td>
    </tr>
  </tbody>
</table>

---

### 6.2 Termination Exposure – Severity Overview

Where a Termination Exposure review was performed, the table below summarises the number of termination-related evidential issues identified by severity. Counts reflect **evidential risk only** and do not represent confirmed non-compliance or quantified financial exposure, or remediation priority.

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>21</td>
      <td>Absence or weakness of core termination or final pay evidence that would materially impair the organisation’s ability to evidence termination decisions if reviewed by auditors or regulators.</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>9</td>
      <td>Termination evidence exists but is incomplete, delayed or ambiguous and may require additional explanation or manual reconstruction.</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>0</td>
      <td>Minor record-keeping or data quality weaknesses in termination records that should be improved over time to support efficient and reliable payroll operations.</td>
    </tr>
  </tbody>
</table>

---

### 6.3 Record-Keeping & Evidence Gaps (RKEG) – Severity Overview

As part of this review, a Record-Keeping & Evidence Gaps (RKEG) assessment was performed to evaluate whether payroll-related records are sufficiently complete, consistent and traceable to support payroll decisions if subject to audit or regulatory review.

The RKEG assessment focuses on evidential strength only. It does not determine whether payroll outcomes are correct or incorrect, and does not interpret awards, enterprise agreements or employment contracts.

The table below summarises the number of record-keeping and evidence gaps identified by severity. Counts reflect **evidential risk** only and do not represent confirmed non-compliance or quantified financial exposure.

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>18</td>
      <td>Absence or weakness of core evidence or entitlement configuration that would materially impair the organisation’s ability to evidence payroll decisions if reviewed by auditors or regulators.</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>31</td>
      <td>Evidence is incomplete, inconsistent or fragile. Decisions may still be defensible but require greater reliance on manual reconstruction, judgement, or explanation.</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>0</td>
      <td>Record-keeping or data quality weaknesses that are unlikely to be challenged in isolation but should be improved over time to support efficient and reliable payroll operations.</td>
    </tr>
  </tbody>
</table>

---

### 6.4 Cross-Module Integrity – Summary Overview

Where a Cross-Module Integrity review was performed, the table below summarises the number of cross-module inconsistencies identified by severity. Counts reflect **integrity risk indicators only** and do not represent confirmed non-compliance or quantified financial exposure.

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>12</td>
      <td>Cross-dataset inconsistencies that may materially affect confidence in employee lifecycle, payroll sequencing, or linked record integrity.</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>6</td>
      <td>Cross-module mismatches or data linkage issues that warrant review but may be explainable through timing, process, or source-system differences.</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>0</td>
      <td>Lower-impact cross-module inconsistencies that should be monitored and improved over time.</td>
    </tr>
  </tbody>
</table>

---

### 6.5 How to interpret findings

**How to interpret findings across modules**

- **Leave & LSL findings** highlight potential anomalies in leave balances, accruals and usage. These indicators relate to *payroll outcomes and configuration* and may require remediation if confirmed.
- **Termination Exposure findings** relate to the completeness, sequencing and documentation of termination events and final pay. They indicate how readily the organisation could evidence termination processing if challenged.
- **Cross-Module Integrity findings** highlight inconsistencies between related datasets, such as employee lifecycle status, leave activity, and payroll events. They indicate where linked records may not align cleanly across the broader payroll data environment.
- **Record-Keeping & Evidence Gaps (RKEG) findings** assess the strength of the evidentiary trail supporting payroll decisions. They do **not** indicate incorrect pay outcomes; they highlight where records may be incomplete or difficult to substantiate.

Findings are risk indicators requiring validation and do not, on their own, confirm non-compliance, legislative contravention, or underpayment.

*Traffic light indicators reflect evidential risk only and do not represent confirmed contraventions or quantified exposure.*

## 7. Limitations & Assumptions

This review is subject to the following limitations:

- Calculations assume the underlying pay rates, loadings and multipliers are correct in the source systems.
- Award and enterprise agreement interpretation is not performed by this tool.
- Holiday calendars, leave rules and accrual settings are assumed to reflect the organisation’s intended configuration.
- Data quality issues (missing records, duplicates, inconsistent identifiers) may affect the completeness and accuracy of the results.

---

## 8. Recommended Next Steps

1. Prioritise detailed review of termination handling and record-keeping controls first, as these areas show the strongest concentration of high-severity findings.
2. Confirm whether the identified findings reflect configuration weaknesses, process breakdowns, incomplete records, or isolated data anomalies.
3. Address structural data gaps that may weaken evidentiary confidence and make findings harder to validate.
4. Validate substantive logical integrity findings before remediation decisions are made.
5. Re-run the review after corrective action to confirm that risk indicators have reduced and no new integrity issues have emerged.

---

## 9. Appendices

### Appendix A – Rule Definitions

This review used a set of automated rules to flag evidential and process risk indicators.

#### Leave & Entitlement Leakage

- Negative balance checks
- Casual employees accruing leave
- Inactive or terminated employees with leave movements
- Unusual accrual or usage patterns

#### Long Service Leave (LSL) Exposure

- Inconsistent LSL accrual patterns
- LSL balances inconsistent with service duration
- Missing or incomplete service date records

#### Termination Exposure (TERM)

- Final pay sequencing checks vs termination date
- Missing / inconsistent termination dates
- Missing / inconsistent termination type / reason
- Missing evidence references / artefact identifiers
- Ambiguous identification of final pay events within a window
- Termination events inconsistent with ordinary pay activity patterns

#### Record-Keeping & Evidence Gaps (RKEG)

- Missing employee master data fields
- Orphan pay events and traceability gaps
- Inconsistent employment status records
- Missing or inconsistent termination attributes

#### Cross-Module Integrity (CROSS_MODULE)

- Employee lifecycle mismatches across datasets
- Leave activity inconsistent with employment or termination status
- Payroll events inconsistent with linked employee or termination records
- Cross-dataset linkage or sequencing anomalies

---

### Appendix B – Data Fields Used

Key data fields referenced in this engagement include:

**Leave & Entitlement Leakage**

- `employee_id`
- `leave_type`
- `as_of_date`
- `rule_code`
- `severity`
- `classification`
- `message`
- `diff_units`
- `finding_id`
- `next_action`

**LSL Exposure**

- `employee_id`
- `leave_type`
- `as_of_date`
- `rule_code`
- `severity`
- `classification`
- `message`
- `diff_units`
- `finding_id`
- `next_action`

**Termination Exposure (TERM)**

- `employee_id`
- `termination_date`
- `final_pay_date`
- `rule_code`
- `severity`
- `classification`
- `message`
- `days_gap`
- `evidence`
- `finding_id`
- `next_action`

**Record-Keeping & Evidence Gaps (RKEG)**

- `employee_id`
- `leave_type`
- `as_of_date`
- `rule_code`
- `severity`
- `classification`
- `message`
- `diff_units`
- `evidence`
- `finding_id`
- `next_action`

**Cross Module Integrity (CROSS_MODULE)**

- `employee_id`
- `leave_type`
- `as_of_date`
- `rule_code`
- `severity`
- `classification`
- `message`
- `diff_units`
- `evidence`
- `finding_id`
- `next_action`

---

### Appendix C – Machine-readable outputs

Complete machine-readable outputs are available in the following files:

- `leave_leakage_findings.csv`
- `leakage_report.csv`
- `lsl_findings.csv`
- `lsl_summary_by_severity.csv`
- `term_findings.csv`
- `term_summary_by_severity.csv`
- `term_summary.csv`
- `rkeg_findings.csv`
- `rkeg_summary_by_severity.csv`
- `cross_module_findings.csv`
- `cross_module_summary_by_severity.csv`
- `executive\executive_summary.md`
- `executive\executive_summary.json`

These files provide row-level detail suitable for operational review, sampling, remediation planning, or incorporation into a broader audit work program.

---

