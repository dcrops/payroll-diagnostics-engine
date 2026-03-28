# Chase Risk & Compliance (CRC)

System for analysing payroll and operational data to surface hidden risks and governance issues

---

## Problem

Payroll and operational systems are designed to process transactions, but they do not identify structural inconsistencies, configuration drift, or hidden risks that accumulate over time.

---

## Solution

CRC is a modular diagnostics system that ingests payroll data, applies rule-based analysis across multiple domains, and generates structured outputs highlighting potential risks and inconsistencies.

---

## Architecture

- Data ingestion and schema validation  
- Rule engine (YAML-driven, domain-based)  
- Multi-module analysis:
  - Leave (LEAVE)
  - Long Service Leave (LSL)
  - Termination (TERM)
  - Record Keeping & Evidence Gaps (RKEG)  
- Findings generation with structured evidence  
- Reporting layer (Markdown → HTML → PDF)  

---

## Architecture Diagram

```mermaid
flowchart LR
    A[Input Data Payroll and HR Extracts] --> B[Data Ingestion]
    B --> C[Schema Validation]
    C --> D[Rule Engine YAML driven]
    D --> E[Module Analysis LEAVE LSL TERM RKEG]
    E --> F[Findings Generation Structured Evidence]
    F --> G[Reporting Layer Markdown to HTML to PDF]
    G --> H[Outputs Executive Reports and CSVs]

## Key Features

- Deterministic rule-based detection of anomalies and inconsistencies  
- Modular design enabling domain-specific diagnostics  
- Structured findings with traceable evidence  
- Executive-ready reporting outputs for business stakeholders  

---

## AI Direction

A prototype internal RAG-based copilot has been developed to support rule exploration and reasoning.

Future development focuses on AI-assisted explanation and decision support layered on top of the rule-based system.

---

## Tech Stack

- Python  
- Pandas  
- YAML (rule configuration)  
- Markdown / HTML / PDF reporting  

---

## Why this project

CRC reflects my approach to engineering: starting from a real-world business problem, designing a system architecture, and building a working solution that produces meaningful, actionable outputs.
