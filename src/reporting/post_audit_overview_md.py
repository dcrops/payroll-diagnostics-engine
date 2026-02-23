from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
report_date = datetime.now(MELBOURNE_TZ).strftime("%d %b %Y")

# ---------- Paths ----------

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = BASE_DIR / "outputs"

POST_AUDIT_MD_PATH = OUTPUTS_DIR / "post_audit_overview.md"


def generate_post_audit_overview(
    organisation_name: str = "Organisation not specified",
    prepared_as_at: str | None = None,
) -> Path:
    """
    Generate outputs/post_audit_overview.md for the Post-Audit Payroll Compliance Review.
    This is a narrative / framing document that sits alongside the detailed module reports.
    """
    if prepared_as_at is None:
        prepared_as_at = f"{date.today():%d %b %Y}"

    md = f"""# Post-Audit Payroll Compliance Review

**Organisation:** {organisation_name}  
**Prepared as at:** {prepared_as_at}  

> This Post-Audit Review provides structured guidance on interpreting the CRC Executive Pack and supporting module reports following an audit, regulatory review, or external assurance activity.

> It summarises how automated risk indicators may align with, extend, or contextualise audit findings. This document does not re-perform audit procedures, validate audit conclusions, or provide legal, accounting, or industrial relations advice.

---

## 1. Purpose of this Review

This Post-Audit Payroll Compliance Review is designed to help the organisation
understand, triage and respond to payroll risk indicators **after** an audit,
regulatory review or external assurance activity.

The review applies automated, data-driven checks to:

- provide an indicative view of residual risk
- identify areas where similar issues may arise beyond audited samples
- support internal decision-making on remediation and control improvements

This review does **not** replace audit conclusions, does not re-perform audit
procedures, and does not provide legal or accounting advice. Its purpose is to
support structured post-audit follow-up and ongoing risk management.

---

## 2. Relationship to Detailed Reviews

This Post-Audit Review summarises residual risk and remediation themes
identified across the following CRC modules:

- **Leave & Entitlement Leakage Review**
- **Long Service Leave (LSL) Exposure Review**
- **Termination Exposure Review**
- **Record-Keeping & Evidence Gaps (RKEG) Review**

These detailed reports contain the underlying findings, rule logic,
employee-level indicators, and recommended remediation actions.

Where commissioned separately, a **Public Holiday Compliance Review**
may also be considered as part of broader payroll risk assessment.
That review is delivered under a standalone tool and is not included
in this CRC report pack unless expressly commissioned.

---

## 3. How to Use This Review

This Post-Audit Review should be read as a **supporting tool**
alongside audit outcomes, not as a replacement for them.

Recommended approach:

1. Consider this review together with:
   - audit findings and recommendations
   - internal reports or management responses
2. Refer to the **CRC Executive Pack** for severity distributions and module-level findings.
3. Compare risk indicators with audit findings to:
   - identify alignment (where indicators match known issues)
   - surface adjacent or similar risks not sampled in detail
4. Prioritise follow-up where indicators suggest:
   - broader population impact
   - similar issues across multiple locations, cohorts or entitlement types
5. Re-run relevant modules after remediation to confirm reduction in residual risk.

---

## 4. Residual Risk Snapshot

This review draws together residual exposure signals identified across:

- **Leave & Entitlement Leakage Review**  
  (operational payroll accuracy and entitlement consistency)

- **Long Service Leave (LSL) Exposure Review**  
  (long-horizon entitlement and provision risk)

- **Termination Exposure Review**  
  (final pay process integrity and evidential defensibility)

- **Record-Keeping & Evidence Gaps (RKEG) Review**  
  (traceability, completeness and audit-readiness of payroll records)

Detailed severity distributions and module-level findings are presented in the **CRC Executive Pack** and supporting module reports.
Post-audit, these should be used to understand where risk indicators remain
and where further follow-up may be required.

If a Public Holiday Compliance Review was conducted separately,
its findings should be considered alongside this report when assessing
overall payroll risk posture.

---

## 5. Alignment with Audit Findings

Where audit findings are available, this review can assist by:

- highlighting areas where automated indicators align with audit issues
- identifying similar patterns in parts of the population not sampled
- providing additional context on the potential spread or persistence of issues

Potential use cases include:

- confirming whether known issues are isolated or widespread
- identifying additional employees, locations or periods that may warrant review
- supporting communication with stakeholders (Payroll, HR, Finance, Audit and Governance)

The presence of risk indicators does not by itself confirm non-compliance,
but it may suggest areas where further analysis, sampling or remediation is appropriate.

This review is intended to complement, not challenge or override, formal audit conclusions.

---

## 6. Recommended Post-Audit Actions

### A. Alignment with Audit Outcomes

- Map automated risk indicators against audit findings and agreed actions.
- Identify where indicators align with audit conclusions.

### B. Residual Risk Assessment

- Assess whether similar issues may exist beyond audited samples.
- Prioritise review where patterns suggest broader population impact.

### C. Ongoing Monitoring

- Re-run modules after remediation.
- Use periodic re-runs to monitor residual and emerging risk.

---

## 7. Supporting Detailed Reports

This Post-Audit Review is supported by the following CRC module reports:

- **Leave & Entitlement Leakage Review**  
  `outputs/leave_report.html`

- **Long Service Leave (LSL) Exposure Review**  
  `outputs/lsl_report.html`

- **Termination Exposure Review**  
  `outputs/term_report.html`

- **Record-Keeping & Evidence Gaps (RKEG) Review**  
  `outputs/rkeg_report.html`

Where commissioned separately, a Public Holiday Compliance Review
will be provided as a standalone artefact outside this CRC report pack.

These reports should be retained alongside audit documentation and
management responses as part of the organisation's payroll governance records.

This Post-Audit Review should be used as a structured governance tool alongside audit documentation, management responses and remediation plans. The **CRC Executive Pack** remains the primary analytical artefact.

---

## 8. Scope, Assumptions & Limitations

This Post-Audit Review is subject to the following limitations:

- The review relies on the accuracy and completeness of the data provided.
- Automated checks are rule-based and may not capture all payroll risks.
- Award, enterprise agreement, and contract interpretation is not performed.
- This review does not provide legal, accounting, or industrial relations advice.
- Audit scope, sampling and methodology are determined by the relevant audit function and are not replicated here.

The review is intended to support informed post-audit follow-up
and should be used alongside professional advice and formal audit outputs.

---
"""

    POST_AUDIT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    POST_AUDIT_MD_PATH.write_text(md, encoding="utf-8")
    return POST_AUDIT_MD_PATH


if __name__ == "__main__":
    path = generate_post_audit_overview()
    print(f"Wrote {path}")