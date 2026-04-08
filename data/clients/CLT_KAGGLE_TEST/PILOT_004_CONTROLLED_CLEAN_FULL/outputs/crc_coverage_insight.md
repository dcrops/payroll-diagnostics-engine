# CRC Coverage Insight

## Overview

- Payroll-only findings: **21**
- Full analysis findings: **28**
- Additional findings unlocked: **7 (33%)**

**TERM** shows the largest uplift, with **6 additional findings** (150% increase).

## Module Breakdown

### LEAVE

- Payroll-only: 2 findings (core=2, supporting=0, extended=0)
- Full: 2 findings (core=2, supporting=0, extended=0)
- No additional findings were identified with full data. This module is largely assessable using payroll-only data.

### TERM

- Payroll-only: 4 findings (core=4, supporting=0, extended=0)
- Full: 10 findings (core=4, supporting=0, extended=6)
- Additional findings: 6 (150% increase)

Termination-related risks show the strongest dependency on additional datasets. These issues are often not fully visible in payroll-only analysis and represent the primary source of hidden exposure.

### LSL

- Payroll-only: 0 findings (core=0, supporting=0, extended=0)
- Full: 0 findings (core=0, supporting=0, extended=0)
- No additional findings were identified with full data. This module is largely assessable using payroll-only data.

### RKEG

- Payroll-only: 3 findings (core=0, supporting=3, extended=0)
- Full: 4 findings (core=0, supporting=3, extended=1)
- Additional findings: 1 (33% increase)

Governance and evidence-related risks are partially visible in payroll data, but additional datasets improve coverage and confidence.

### CROSS_MODULE

- Payroll-only: 12 findings (core=1, supporting=11, extended=0)
- Full: 12 findings (core=1, supporting=11, extended=0)
- No additional findings were identified with full data. This module is fully assessable using payroll-only data and provides strong visibility into cross-dataset inconsistencies.

## Interpretation

Payroll-only analysis provides strong visibility into balance integrity, lifecycle sequencing, and cross-dataset consistency.

However, certain risk categories—particularly termination handling and governance controls—are not fully observable without broader system context. These areas represent the primary source of hidden exposure.

This supports a tiered diagnostic approach:

- Payroll-only → fast, low-friction, high-confidence baseline
- Full analysis → deeper risk discovery, particularly for termination and governance-related risks
