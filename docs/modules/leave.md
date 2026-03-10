# CRC Module Documentation

## Leave & Entitlement Leakage

### Module ID

LEAVE

### Purpose

The Leave module identifies structural payroll governance risks related to employee leave balances, leave accrual processes, leave usage, and the integrity of underlying leave records.

The module evaluates whether leave balances and leave transactions are mathematically coherent, operationally plausible, and supported by sufficient evidence and workflow records.

The objective is not to re-calculate leave entitlements, but to detect **structural anomalies and governance weaknesses** that may expose an organisation to payroll risk, financial misstatement, or regulatory scrutiny.

---

# Governance Risk Dimensions

All CRC rules are mapped to the CRC Governance Risk Framework.

The Leave module evaluates risks across the following dimensions:

1. Structural Completeness
2. Calculation Integrity
3. Timing Integrity
4. Evidence Traceability
5. Exception Handling
6. Data Anomaly Sanity
7. Governance / Monitoring Exposure
8. Cross-Module Linkage Risk

---

# Required Datasets

Minimum dataset set:

| Dataset               | Description                                                         |
| --------------------- | ------------------------------------------------------------------- |
| employees.csv         | Employee master data including employment type and employment dates |
| leave_ledger.csv      | Leave transactions including accrual and leave taken events         |
| balances_snapshot.csv | Leave balance snapshots used for reconciliation                     |

Optional datasets:

| Dataset            | Description                                 |
| ------------------ | ------------------------------------------- |
| leave_requests.csv | Leave request and approval workflow records |
| timesheets.csv     | Daily worked hours for employees            |

When optional datasets are supplied, additional governance rules are executed.

---

# Key Diagnostics Performed

The Leave module performs several categories of diagnostic checks.

### Balance Integrity

Detects whether leave balances are mathematically coherent.

Examples:

* Negative leave balances
* Leave taken exceeding available balances
* Ledger vs snapshot reconciliation failures

---

### Structural Record Integrity

Ensures the underlying records required to reconstruct leave balances exist.

Examples:

* Leave balances without ledger history
* Missing leave type identifiers
* Ledger events without timestamps

---

### Timing Integrity

Evaluates whether leave events occur within valid employment and operational timeframes.

Examples:

* Leave before employment start
* Leave after termination
* Leave accrual after termination

---

### Operational Anomaly Detection

Identifies values that are unusual or implausible.

Examples:

* Extremely large leave balances
* Duplicate leave ledger entries
* Zero-unit leave transactions

---

### Governance & Workflow Controls

Evaluates whether leave processes follow expected governance practices.

Examples:

* Leave taken without approved leave request
* Leave recorded before approval date
* High manual adjustment volumes

---

### Cross-System Integrity

Compares leave events with related operational datasets.

Examples:

* Leave recorded on days where work hours are also recorded
* Combined leave and worked hours exceeding expected daily limits

---

# Outputs Produced

The Leave module produces the following outputs.

### Findings File

```
outputs/modules/leave_leakage_findings.csv
```

Contains all rule findings including evidence metadata.

Key fields:

| Field       | Description                     |
| ----------- | ------------------------------- |
| employee_id | Employee identifier             |
| leave_type  | Leave category                  |
| as_of_date  | Date relevant to the finding    |
| rule_code   | CRC rule identifier             |
| severity    | Risk severity                   |
| message     | Human readable explanation      |
| evidence    | Structured JSON evidence object |
| next_action | Suggested investigation step    |

---

### Rule Summary

```
outputs/modules/leave_leakage_summary.csv
```

Counts findings by rule and severity.

---

### Severity Summary

```
outputs/modules/leave_leakage_summary_by_severity.csv
```

Counts findings by severity level.

---

### Ledger Reconciliation Report

```
outputs/leakage_report.csv
```

Detailed comparison between leave snapshot balances and ledger-derived balances.

---

# Interpretation Guidance

CRC findings do **not automatically indicate payroll errors**.

Instead they identify:

• potential control failures
• data integrity anomalies
• structural payroll risks
• evidence gaps

Each finding should be reviewed alongside payroll records and organisational policies.

---

# Intended Audience

The module is designed for:

• Payroll managers
• Finance leadership
• Internal audit teams
• Compliance and governance functions

---

# Position Within CRC Platform

The Leave module forms part of the CRC **Executive Payroll Risk Pack** and can operate independently or alongside other CRC diagnostics modules including:

• LSL Exposure
• Termination Exposure
• Record-Keeping & Evidence Gaps (RKEG)
