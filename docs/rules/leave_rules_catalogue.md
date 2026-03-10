# CRC Leave Rule Catalogue

This document provides a complete catalogue of rules implemented in the CRC Leave & Entitlement Leakage module.

Rules are classified by **tier**, **risk dimension**, and **purpose**.

---

# Tier Definitions

Tier 1 – Executive Risk Pack
Tier 2 – Governance & Integrity Diagnostics

### Tier 1 — Executive Risk Pack

High-confidence structural payroll risks that are appropriate for executive reporting.

These findings indicate strong likelihood of payroll governance exposure.

---

### Tier 2 — Governance & Integrity Diagnostics

Additional integrity checks that identify unusual patterns, operational anomalies, or monitoring weaknesses.

These findings are primarily used during deeper investigation.

---

# Tier 1 Rules

| Rule      | Description                                | Risk Dimension          |
| --------- | ------------------------------------------ | ----------------------- |
| LEAVE-001 | Negative leave balance                     | Calculation Integrity   |
| LEAVE-002 | Ledger sign mismatch                       | Calculation Integrity   |
| LEAVE-003 | Leave before employment start              | Timing Integrity        |
| LEAVE-004 | Accrual for casual employee                | Cross-Module Linkage    |
| LEAVE-005 | Ledger vs snapshot reconciliation mismatch | Calculation Integrity   |
| LEAVE-006 | Leave balance without ledger history       | Structural Completeness |
| LEAVE-007 | Leave recorded after termination           | Timing Integrity        |
| LEAVE-010 | Missing leave type identifier              | Structural Completeness |
| LEAVE-011 | Ledger events missing timestamp            | Evidence Traceability   |
| LEAVE-013 | Leave accrual after termination            | Timing Integrity        |
| LEAVE-014 | Leave taken exceeds available balance      | Calculation Integrity   |
| LEAVE-016 | Leave balance exceeds threshold            | Data Anomaly            |
| LEAVE-017 | Leave ledger for inactive employee         | Cross-Module Linkage    |
| LEAVE-018 | Leave event outside reporting window       | Timing Integrity        |
| LEAVE-020 | Leave taken without approved request       | Governance Monitoring   |

---

# Tier 2 Rules

| Rule      | Description                                      | Risk Dimension        |
| --------- | ------------------------------------------------ | --------------------- |
| LEAVE-008 | Duplicate leave ledger entries                   | Data Anomaly          |
| LEAVE-009 | Extreme leave balance                            | Data Anomaly          |
| LEAVE-012 | High proportion of manual adjustments            | Governance Monitoring |
| LEAVE-015 | Zero-unit leave ledger event                     | Data Anomaly          |
| LEAVE-019 | High leave event volume                          | Data Anomaly          |
| LEAVE-021 | Leave recorded before approval date              | Timing Integrity      |
| LEAVE-022 | Leave and worked hours same day                  | Cross-Module Linkage  |
| LEAVE-023 | Combined leave and worked hours exceed threshold | Data Anomaly          |

---

# Total Rule Count

| Tier   | Count |
| ------ | ----- |
| Tier 1 | 15    |
| Tier 2 | 8     |
| Total  | 23    |

---

# Coverage Across CRC Governance Framework

| Risk Dimension          | Coverage |
| ----------------------- | -------- |
| Structural Completeness | ✔        |
| Calculation Integrity   | ✔        |
| Timing Integrity        | ✔        |
| Evidence Traceability   | ✔        |
| Exception Handling      | ✔        |
| Data Anomaly Sanity     | ✔        |
| Governance Monitoring   | ✔        |
| Cross-Module Linkage    | ✔        |

The Leave module provides balanced coverage across all CRC governance risk dimensions.
