# Termination Exposure – Final Pay Identification Contract (v1)

## Scope
- Files: `terminations.csv`, `pay_events.csv`, `employees.csv` (optional)
- Purpose: evidence of termination pay traceability, not entitlement correctness.

## Date Parsing Rules
- Accepted formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
- Unparseable dates are excluded from timing-based rules.

## Definitions
- Termination event
- Pay event
- Pay on/after termination
- Explicit final pay flag (`is_final_pay`)
- Last ordinary pay before termination
- Gap calculation (`gap_days`)
- Ambiguous final pay window (−14, +30 days)
- Thresholds:
  - `MAX_FINAL_PAY_GAP_DAYS = 35`
  - `AMBIGUOUS_WINDOW_BEFORE_DAYS = 14`
  - `AMBIGUOUS_WINDOW_AFTER_DAYS = 30`

## Rule Mapping
- TERM-001 uses: pay on/after termination
- TERM-002 uses: explicit final pay flag before termination
- TERM-003 uses: last ordinary pay + `MAX_FINAL_PAY_GAP_DAYS`
- TERM-006 uses: ambiguity window + explicit final pay flag