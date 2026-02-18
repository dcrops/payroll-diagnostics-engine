from __future__ import annotations

from datetime import date
from pathlib import Path

report_date = date.today().strftime("%d %b %Y")

# ---------- Paths ----------

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = BASE_DIR / "outputs"

PRE_AUDIT_MD_PATH = OUTPUTS_DIR / "pre_audit_overview.md"


def generate_pre_audit_overview(
    organisation_name: str = "Organisation not specified",
    prepared_as_at: str | None = None,
) -> Path:
    """
    Generate outputs/pre_audit_overview.md for the Pre-Audit Payroll Compliance Review.
    This is a narrative / framing document that sits alongside the detailed module reports.
    """
    if prepared_as_at is None:
        prepared_as_at = f"{date.today():%d %b %Y}"

    md = f"""# Pre-Audit Payroll Compliance Review

**Organisation:** {organisation_name}  
**Prepared as at:** {prepared_as_at}  

> This Pre-Audit Review is intended to support internal payroll and compliance preparation. It identifies potential areas of risk based on the data provided but does not constitute legal, accounting, or industrial relations advice.

> This review is designed to identify potential payroll risk indicators prior to audit activity and support proactive remediation. It does not replace an audit or provide assurance.

---

## 1. Purpose of this Review

This Pre-Audit Payroll Compliance Review is designed to help the organisation identify and prioritise potential payroll compliance risks **before** the commencement of a formal audit, regulatory review, or external assurance activity.

The review applies automated, data-driven checks across key payroll risk areas to surface indicators that may warrant further investigation, validation, or remediation.

This review reflects the status of payroll compliance based on module outputs generated as at the report date. Each underlying module may analyse different data periods depending on the nature of the check performed.

This review:

- supports internal preparation and risk reduction
- highlights areas likely to attract audit attention
- assists with prioritisation of follow-up work

It does **not** replace an audit, provide legal or accounting advice, or guarantee audit outcomes.

---

## 2. Relationship to Detailed Reviews

This Pre-Audit Review provides a consolidated, high-level view of potential payroll risk indicators derived from the following CRC modules:

- **Leave & Entitlement Leakage Review**
- **Long Service Leave (LSL) Exposure Review**
- **Termination Exposure Review**
- **Record-Keeping & Evidence Gaps (RKEG) Review**

These detailed reports contain the underlying evidence, rule logic, employee-level findings, and recommended remediation actions.

This overview does not independently reassess payroll calculations or confirm compliance outcomes.

Where commissioned separately, a **Public Holiday Compliance Review** may also be considered as part of broader payroll risk assessment. That review is delivered under a standalone tool and is not included in this engagement unless expressly commissioned.

---

## 3. How to Use This Review

This Pre-Audit Review should be read as a **preparatory tool**, not a definitive assessment.

Recommended approach:

1. Review the **Executive Summary** and **Module Severity Overview** sections to understand overall exposure levels.
2. Prioritise **High severity** findings for validation and remediation.
3. Use the detailed module reports to:
   - understand the nature of each finding
   - review supporting evidence
   - identify potential root causes
4. Where issues are confirmed, address them before audit commencement where practicable.
5. Re-run relevant modules after remediation to confirm risk reduction.

---

## 4. Key Risk Snapshot

This review draws together exposure signals identified across the following CRC modules:

- **Leave & Entitlement Leakage Review**  
  (operational payroll accuracy and entitlement consistency)

- **Long Service Leave (LSL) Exposure Review**  
  (long-horizon entitlement and provision risk)

- **Termination Exposure Review**  
  (final pay process integrity and evidential defensibility)

- **Record-Keeping & Evidence Gaps (RKEG) Review**  
  (traceability, completeness, and audit-readiness of payroll records)

Severity distribution and thematic patterns are presented within the Executive Summary and Module Overview sections and should be used as the primary reference for risk prioritisation.

---

## 5. Areas Likely to Attract Audit Attention

Based on common payroll audit and regulatory review patterns, findings in the following categories are more likely to attract scrutiny:

- **Negative leave balances** or unexplained balance movements  
- **Leave accruals for ineligible employee types** (for example, casual employees accruing leave)
- **Inconsistencies between ledger movements and balance snapshots**
- **Long-serving employees with low or zero Long Service Leave balances**
- **Termination events with incomplete or weak evidential support**
- **Gaps in employee master data or traceability fields required to evidence payroll decisions**

The presence of findings in these areas does not by itself imply non-compliance, but they are typically considered higher-risk and should be prioritised for validation.

---

## 6. Recommended Pre-Audit Actions (Before Audit Commencement)

The following actions are recommended to reduce payroll risk prior to audit activity.

### A. Triage and Validation

1. Prioritise validation of **High severity** findings across all modules.
2. Confirm whether identified issues reflect:
   - data quality problems
   - configuration or system issues
   - policy interpretation differences

### B. Remediation (Where Issues Are Confirmed)

- Correct underlying configuration or process issues.
- Assess whether remediation is required.
- Document actions taken and the rationale where findings are deemed acceptable.

### C. Re-assessment

- Re-run the relevant modules after changes.
- Confirm that key risk indicators have reduced prior to audit commencement.

---

## 7. Supporting Detailed Reports

This Pre-Audit Review is supported by the following detailed CRC module reports, which contain full findings, evidence, and recommended actions:

- **Leave & Entitlement Leakage Review**  
  `outputs/leave_report.html`

- **Long Service Leave (LSL) Exposure Review**  
  `outputs/lsl_report.html`

- **Termination Exposure Review**  
  `outputs/term_report.html`

- **Record-Keeping & Evidence Gaps (RKEG) Review**  
  `outputs/rkeg_report.html`

Where commissioned separately, a Public Holiday Compliance Review will be provided as a standalone artefact outside this CRC report pack.

These reports should be retained as supporting documentation for internal review and audit preparation.

---

## 8. Scope, Assumptions & Limitations

This Pre-Audit Review is subject to the following limitations:

- The review relies on the accuracy and completeness of the data provided.
- Automated checks are rule-based and may not capture all payroll risks.
- Award, enterprise agreement, and contract interpretation is not performed by this tool.
- This review does not provide legal, accounting, or industrial relations advice.

The review is intended to support informed preparation and prioritisation and should be used alongside professional advice where appropriate.

---
"""

    PRE_AUDIT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRE_AUDIT_MD_PATH.write_text(md, encoding="utf-8")
    return PRE_AUDIT_MD_PATH


if __name__ == "__main__":
    path = generate_pre_audit_overview()
    print(f"Wrote {path}")