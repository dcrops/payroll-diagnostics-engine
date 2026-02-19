# Payroll Compliance Tools (Australia)

A set of batch-style payroll compliance checks designed to help payroll, HR, and finance teams identify data issues, compliance risks, and potential exposure before audits or remediation work.

This project focuses on explainable findings with evidence and next actions.  
It does not provide legal advice or statutory entitlement calculations.

---

## What this project does

This repository includes two independent compliance modules, plus a unified reporting layer.

---

## Leave Leakage Detection

Identifies discrepancies and data risks in leave balances by comparing leave event ledgers, snapshot balances, and employee master data.

### Examples of issues flagged

- Negative leave balances
- Ledger-derived balances not matching snapshot balances
- Leave taken before employment start date
- Casual employees accruing leave
- Event sign anomalies (TAKEN vs ACCRUAL)

Each finding includes severity, evidence, and a recommended next action.

---

## Long Service Leave (LSL) Exposure Review

Flags potential Long Service Leave risks using tenure-based heuristics and balance checks.

### Examples of issues flagged

- Negative LSL balances
- Missing LSL balances for long-tenured employees
- Zero or suspiciously low LSL balances
- Indicative exposure bands

LSL outputs are heuristic and indicative only.  
This module does not calculate statutory entitlements.

---

## How to run

From the repository root, run the following commands in order:

```bash
python -m leave_leakage.run
python -m lsl_exposure.run
python -m reporting.run
python -m reporting.report_md
```

After running, open the consolidated report:

```text
outputs/crc_executive_pack.md
```

---

## Design principles

- **Explainable** – every finding includes evidence and rationale
- **Audit-friendly** – deterministic IDs and reproducible runs
- **Non-invasive** – read-only analysis of existing payroll data
- **Batch-first** – designed for CSV-in / report-out workflows
- **No legal claims** – flags risk, not statutory entitlements

---

## Known limitations

- Jurisdiction-specific award and agreement rules are not modelled
- LSL exposure estimates are heuristic and indicative only
- Continuous service assumptions may not reflect all enterprise agreements
- Accuracy depends on the quality and completeness of source data

---

## Intended audience

- Payroll managers
- HR operations teams
- Finance and internal audit teams
- Data and analytics practitioners working in payroll compliance

---

## Status

This is an independent side project and portfolio project, not a commercial SaaS product.

The codebase is intentionally kept simple, transparent, and extensible.

## Quick demo

After running the pipeline, open:

- `outputs/crc_executive_pack.md`

## Repository structure (key files)

- `src/leave_leakage/` — leave leakage rules + runner
- `src/lsl_exposure/` — LSL heuristic checks + runner
- `src/reporting/` — combines findings and generates `outputs/crc_executive_pack.md`
- `outputs/modules/` — per-module outputs

> Disclaimer: Outputs are indicative risk flags and should be validated against your organisation’s policies and applicable legislation/agreements.
