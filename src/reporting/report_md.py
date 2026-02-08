from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List, Dict, Optional

from common.severity import SEVERITY_BY_CODE
from reporting.rkeg_text import (
    build_rkeg_summary_paragraph,
    build_rkeg_severity_overview_table,
)

report_date = date.today().strftime("%d %b %Y")

# ---------- Paths ----------

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = BASE_DIR / "outputs"
MODULES_DIR = OUTPUTS_DIR / "modules"

LEAVE_FINDINGS_CSV = MODULES_DIR / "leave_leakage_findings.csv"
LEAKAGE_REPORT_CSV = OUTPUTS_DIR / "leakage_report.csv"
RKEG_SUMMARY_BY_SEVERITY_CSV = MODULES_DIR / "rkeg_summary_by_severity.csv"
RKEG_FINDINGS_CSV = MODULES_DIR / "rkeg_findings.csv"
TERM_SUMMARY_BY_SEVERITY_CSV = MODULES_DIR / "term_summary_by_severity.csv"
TERM_FINDINGS_CSV = MODULES_DIR / "term_findings.csv"

REPORT_MD_PATH = OUTPUTS_DIR / "report.md"


# ---------- Data models ----------

@dataclass
class Finding:
    rule_code: str
    severity: str
    employee_id: str
    leave_type: str
    as_of_date: str
    message: str

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> "Finding":
        # Adjust these field names if your CSV uses slightly different headers
        return cls(
            rule_code=row.get("rule_code") or row.get("rule_id") or "",
            severity=(row.get("severity", "") or "").upper(),
            employee_id=row.get("employee_id", ""),
            leave_type=row.get("leave_type", ""),
            as_of_date=row.get("as_of_date", ""),
            message=row.get("message") or row.get("description") or "",
        )


@dataclass
class ExposureRow:
    label: str
    amount: float

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> Optional["ExposureRow"]:
        """
        Try a few common column names for exposure amounts.
        If none are present, return None and the exposure section
        will fall back to a 'not available' message.
        """
        label = row.get("label") or row.get("rule_code") or row.get("bucket") or ""
        amount_field_candidates = [
            "estimated_exposure",
            "exposure_amount",
            "leakage_amount",
            "amount",
            "value",
        ]

        amount_value: Optional[float] = None
        for field in amount_field_candidates:
            if field in row and row[field]:
                try:
                    amount_value = float(row[field])
                    break
                except ValueError:
                    continue

        if amount_value is None:
            return None

        return cls(label=label, amount=amount_value)


# ---------- CSV helpers ----------

def load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_findings() -> List[Finding]:
    rows = load_csv(LEAVE_FINDINGS_CSV)
    return [Finding.from_row(r) for r in rows]


def load_exposure_rows() -> List[ExposureRow]:
    rows = load_csv(LEAKAGE_REPORT_CSV)
    exposure_rows: List[ExposureRow] = []
    for r in rows:
        er = ExposureRow.from_row(r)
        if er is not None:
            exposure_rows.append(er)
    return exposure_rows


def load_rkeg_severity_counts() -> Dict[str, int]:
    """
    Load simple HIGH / MEDIUM / LOW counts for RKEG.

    First preference: outputs/modules/rkeg_summary_by_severity.csv
    Fallback:        outputs/modules/rkeg_findings.csv (count severity column)
    """
    # Default all severities to zero
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    # --- 1) Try the summary_by_severity CSV ---
    summary_rows = load_csv(RKEG_SUMMARY_BY_SEVERITY_CSV)
    if summary_rows:
        sev_candidates = ["severity", "Severity"]
        # 👇 this now includes 'finding_count'
        count_candidates = ["finding_count", "count", "Count", "n", "N", "value", "Value"]

        first = summary_rows[0]
        sev_col = next((c for c in sev_candidates if c in first), None)
        count_col = next((c for c in count_candidates if c in first), None)

        if sev_col and count_col:
            for r in summary_rows:
                sev = (r.get(sev_col) or "").strip().upper()
                if not sev:
                    continue
                try:
                    n = int(float((r.get(count_col) or "0") or "0"))
                except ValueError:
                    n = 0
                if sev in counts:
                    counts[sev] += n

            return counts  # we got usable data, no need to fall back

    # --- 2) Fallback: count from rkeg_findings.csv ---
    finding_rows = load_csv(RKEG_FINDINGS_CSV)
    if not finding_rows:
        return counts  # still all zeros, nothing we can do

    for r in finding_rows:
        sev = (r.get("severity") or r.get("Severity") or "").strip().upper()
        if sev in counts:
            counts[sev] += 1

    return counts

def load_term_severity_counts() -> Dict[str, int]:
    """
    Load simple HIGH / MEDIUM / LOW counts for Termination Exposure.

    First preference: outputs/modules/term_summary_by_severity.csv
    Fallback:        outputs/modules/term_findings.csv (count severity column)
    """
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    # --- 1) Try the summary_by_severity CSV ---
    summary_rows = load_csv(TERM_SUMMARY_BY_SEVERITY_CSV)
    if summary_rows:
        sev_candidates = ["severity", "Severity"]
        count_candidates = ["finding_count", "count", "Count", "n", "N", "value", "Value"]

        first = summary_rows[0]
        sev_col = next((c for c in sev_candidates if c in first), None)
        count_col = next((c for c in count_candidates if c in first), None)

        if sev_col and count_col:
            for r in summary_rows:
                sev = (r.get(sev_col) or "").strip().upper()
                if not sev:
                    continue
                try:
                    n = int(float((r.get(count_col) or "0") or "0"))
                except ValueError:
                    n = 0
                if sev in counts:
                    counts[sev] += n

            return counts  # we got usable data, no need to fall back

    # --- 2) Fallback: count from term_findings.csv ---
    finding_rows = load_csv(TERM_FINDINGS_CSV)
    if not finding_rows:
        return counts

    for r in finding_rows:
        sev = (r.get("severity") or r.get("Severity") or "").strip().upper()
        if sev in counts:
            counts[sev] += 1

    return counts

def sort_findings(findings: List[Finding]) -> List[Finding]:
    """Sort findings by severity (HIGH→MEDIUM→LOW), then rule_code, then employee/date."""
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(
        findings,
        key=lambda f: (
            severity_rank.get(f.severity, 99),
            f.rule_code or "",
            f.employee_id or "",
            f.as_of_date or "",
        ),
    )


# ---------- Review period helpers ----------

def _parse_iso_date(s: str | None) -> Optional[date]:
    """Parse a simple YYYY-MM-DD string into a date, or return None."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _derive_review_period(findings: List[Finding]) -> str:
    """
    Derive a human-readable review period from the findings' as_of_date values.
    Uses the earliest and latest valid dates found.
    """
    dates: List[date] = []
    for f in findings:
        d = _parse_iso_date(f.as_of_date)
        if d is not None:
            dates.append(d)

    if not dates:
        return "Period not specified"

    start = min(dates)
    end = max(dates)

    if start == end:
        return start.strftime("%d %b %Y")

    return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"


# ---------- Markdown section builders ----------

def build_header(organisation_name: str, review_period: str) -> str:
    return f"""# Leave & Entitlement Leakage Review

**Organisation:** {organisation_name}  
**Review period:** {review_period}  
**Report prepared as at:** {report_date}  

> This report identifies potential leave and entitlement leakage based on the data provided. It highlights potential risk signals and process issues but does not constitute legal, accounting, or industrial relations advice.

---
"""


def build_executive_summary(findings: List[Finding]) -> str:
    total_findings = len(findings)
    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    distinct_employees = len({f.employee_id for f in findings if f.employee_id})

    paragraph = (
        f"This review analysed leave and entitlement records and identified "
        f"{total_findings} potential issues across approximately "
        f"{distinct_employees} employees. "
        "Findings highlight areas where leave- and entitlement-related records may warrant further review, "
        "ranging from material record-keeping and entitlement concerns through to data quality and process issues. "
        "The presence of a finding does not, on its own, confirm non-compliance or underpayment."
    )

    return f"""## 1. Executive Summary

{paragraph}

**Findings identified**

- High severity: {high}
- Medium severity: {med}
- Low severity: {low}

**Who should read this**

This report is intended for payroll managers and related stakeholders responsible for leave, entitlement and payroll compliance.

---
"""


def build_data_sources_section() -> str:
    return f"""## 2. Data sources

This review was generated from the following analysis outputs within the project `outputs/` directory:

- `{LEAVE_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  
- `{LEAKAGE_REPORT_CSV.relative_to(OUTPUTS_DIR)}`  

These outputs were produced by the Leave & Entitlement Leakage engine from payroll and HR CSV extracts supplied by the organisation for the review period.

---
"""


def build_scope_and_methodology() -> str:
    return """## 3. Scope & Methodology

### 3.1 Leave & Entitlement Leakage – Scope & Methodology

**Data reviewed**

- Leave ledger records
- Leave balances snapshot
- Employee master data
- Other CSV files supplied by the organisation

**Checks performed**

- Rule-based detection of leave and entitlement leakage
- Comparison of ledger movements against balances snapshots
- Identification of negative balances and unexpected accrual patterns
- Consistency checks between employee status and leave activity

**Out of scope**

- Interpretation of awards and enterprise agreements
- Review of employment contracts
- Detailed payroll system configuration

---

### 3.2 Record-Keeping & Evidence Gaps (RKEG) – Scope & Methodology

The Record-Keeping & Evidence Gaps (RKEG) review assesses whether payroll-related records are **sufficiently complete, consistent, and traceable** to support the organisation’s ability to evidence payroll decisions if reviewed by auditors or regulators.

RKEG focuses on **evidential strength**, not on determining whether payroll outcomes are correct or incorrect. Findings highlight areas where decisions may be difficult to substantiate due to missing, inconsistent, or fragile records.

Detailed RKEG findings are provided in machine-readable form and summarised later in this report to provide context on evidential defensibility.

---

### 3.3 Termination Exposure – Scope & Methodology

#### Scope

The Termination Exposure review assesses whether termination events recorded in payroll and related employment data are **sufficiently complete, timely, and traceable** to support the organisation’s ability to evidence termination-related payroll decisions if reviewed by auditors or regulators.

This review focuses on **process and evidential integrity**, not on the correctness of termination payments.

Specifically, the review considers whether:

- termination events are recorded consistently and coherently across available data sources
- final pay processing occurs in a reasonable and defensible sequence relative to termination dates
- core termination attributes (such as termination date and termination type) are present and internally consistent
- termination-related decisions are supported by basic evidentiary artefacts or references

The review is designed to identify termination scenarios that may be difficult to substantiate if challenged, even where payroll outcomes may ultimately be correct.

---

#### Out of Scope

This review does **not**:

- calculate final pay entitlements or assess payment correctness
- interpret awards, enterprise agreements, or employment contracts
- determine notice, redundancy, or severance obligations
- assert breaches of legislation or confirm non-compliance
- provide legal advice or compliance guarantees

Any potential exposure identified reflects **defensibility risk**, not confirmed error or liability.

---

#### Methodology

The Termination Exposure review applies a series of rule-based checks to payroll and related employment data to identify termination events that exhibit characteristics commonly associated with audit, regulatory, or dispute risk.

Rules are designed to assess:

- the presence and sequencing of termination dates and final pay events
- alignment between termination records and pay processing
- completeness and consistency of termination metadata
- indicators of delayed, missing, or inconsistent termination finalisation

Each finding is assigned a severity based on **evidential impact**, reflecting how materially the issue could impair the organisation’s ability to explain and support termination-related payroll decisions if reviewed.

Severity does **not** reflect:

- likelihood of underpayment
- magnitude of financial exposure
- remediation priority

Termination Exposure findings should be read alongside Record-Keeping & Evidence Gaps (RKEG) results, as termination risk is frequently driven by underlying evidence and process weaknesses rather than calculation error alone.
"""


def build_rkeg_summary(rkeg_counts: Dict[str, int]) -> str:
    """
    RKEG summary section for the module report.

    Uses shared text helpers so the description of RKEG is consistent
    across this report and the combined overview.
    """
    interpretation_block = """
**How to interpret RKEG vs Leave Findings**

This report contains two different types of findings, which serve different purposes:

- **Leave & Entitlement Findings** (Sections 5–6) identify potential issues with leave balances, accruals, and usage patterns. These findings relate to *what may be incorrect* and may require remediation if confirmed.

- **Record-Keeping & Evidence Gaps (RKEG)** findings assess the *strength of the underlying evidence* supporting payroll decisions. RKEG findings do **not** indicate incorrect pay outcomes. They highlight where records may be incomplete, inconsistent, or difficult to substantiate if reviewed by auditors or regulators.

RKEG findings should be read as **context for defensibility**, not as confirmation of non-compliance. Detailed, record-level RKEG findings are provided separately in machine-readable form to support operational review and remediation planning.
""".strip()

    body = build_rkeg_summary_paragraph(
        has_emp=True,
        has_pay=True,
        has_term=False,
    )

    severity_overview = build_rkeg_severity_overview_table(rkeg_counts)

    return f"""## 4. Evidence & Defensibility Overview

### 4.1 Record-Keeping & Evidence Gaps (RKEG) Summary

{interpretation_block}

{body}

{severity_overview}
"""

def build_term_severity_summary() -> str:
    """
    Termination Exposure severity overview.

    This is intentionally high-level and evidential only.
    Detailed termination findings are provided separately in CSV form.
    """
    term_counts = load_term_severity_counts()

    if not any(term_counts.values()):
        return ""  # no TERM review performed

    return f"""### 4.2 Termination Exposure – Severity Overview

Where a Termination Exposure review was performed, the table below summarises the number of termination-related evidential issues identified by severity. Counts reflect **evidential risk only** and do not represent confirmed breaches, quantified exposure, or remediation priority.

| Severity | Count | Description |
|---------|:-------------:|---------------------------|
| <span class="badge-high">High</span>    | {term_counts["HIGH"]}   | Absence or weakness of core termination or final pay evidence that would materially impair the organisation’s ability to evidence termination decisions if reviewed by auditors or regulators. |
| <span class="badge-medium">Medium</span>  | {term_counts["MEDIUM"]} | Termination evidence exists but is incomplete, delayed or ambiguous and may require additional explanation or manual reconstruction. |
| <span class="badge-low">Low</span>     | {term_counts["LOW"]}    | Minor record-keeping or data quality weaknesses in termination records that should be improved over time to support efficient and reliable payroll operations. |

*Traffic light indicators reflect evidential risk only and do not represent confirmed breaches, quantified exposure, or remediation priority.*

---
"""

def build_key_findings_overview(findings: List[Finding]) -> str:
    """Section 5 – Key findings across leave / LSL only."""
    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    high_def = SEVERITY_BY_CODE.get("HIGH")
    med_def = SEVERITY_BY_CODE.get("MEDIUM")
    low_def = SEVERITY_BY_CODE.get("LOW")

    high_desc = (
        high_def.description
        if high_def
        else "Higher-risk record-keeping or entitlement concern."
    )
    med_desc = (
        med_def.description
        if med_def
        else "Material configuration, process, or data concern."
    )
    low_desc = (
        low_def.description
        if low_def
        else "Lower-impact data quality or minor process issue."
    )

    # Build per-rule summary (counts + severity mix) for leave / LSL rules
    rule_summary_lines: List[str] = []
    if findings:
        rule_counts: Dict[str, Dict[str, int]] = {}

        for f in findings:
            code = f.rule_code or "UNSPECIFIED_RULE"
            if code not in rule_counts:
                rule_counts[code] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "TOTAL": 0}

            if f.severity in ("HIGH", "MEDIUM", "LOW"):
                rule_counts[code][f.severity] += 1
            rule_counts[code]["TOTAL"] += 1

        rule_summary_lines.append("")
        rule_summary_lines.append("**Finding types (by rule)**")
        rule_summary_lines.append("")
        rule_summary_lines.append(
            "This table summarises how many findings were raised for each leave/LSL rule and the mix of severities."
        )
        rule_summary_lines.append("")
        rule_summary_lines.append("| Rule code | Count | Severity mix (H/M/L) |")
        rule_summary_lines.append("|----------|-------|----------------------|")

        for code in sorted(rule_counts.keys()):
            h = rule_counts[code]["HIGH"]
            m = rule_counts[code]["MEDIUM"]
            l = rule_counts[code]["LOW"]
            total = rule_counts[code]["TOTAL"]
            mix = f"{h}H / {m}M / {l}L"
            rule_summary_lines.append(f"| `{code}` | {total} | {mix} |")

    rule_summary = "\n".join(rule_summary_lines)

    interpretation_block = """

**How to interpret leave, RKEG and termination findings**

- **Leave leakage and LSL exposure findings** highlight potential issues in leave balances, accruals and usage. These findings are primarily about *payroll outcomes and configuration* and may indicate areas where entitlements or balances require remediation if confirmed.
- **Record-Keeping & Evidence Gaps (RKEG)** findings assess the *strength of the evidence trail* supporting payroll decisions (for example, missing start dates or orphan pay events). RKEG findings do **not** by themselves mean that amounts paid are wrong; they highlight how difficult it may be to substantiate decisions if reviewed.
- **Termination Exposure** findings focus on the completeness, sequencing and documentation of termination events and final pay. They indicate how readily the organisation could explain and support terminations if challenged by auditors, regulators, or employees.

Individually, these findings are indicators of risk and areas for further review, not determinations of breach, non-compliance, or underpayment.
""".strip()

    return f"""## 5. Key Findings Overview

The automated checks identified the following potential issues in the leave and entitlement data reviewed. Severity reflects the relative level of risk to payroll accuracy and audit defensibility, not a confirmed breach.

| Severity | Count | Description |
|---------|:-----:|-------------|
| <span class="badge-high">High</span>    | {high}   | {high_desc} |
| <span class="badge-medium">Medium</span>  | {med}   | {med_desc}  |
| <span class="badge-low">Low</span>     | {low}   | {low_desc}   |

{interpretation_block}

{rule_summary}

---
"""

def build_detailed_findings(findings: List[Finding]) -> str:
    if not findings:
        return """## 6. Detailed Findings

No findings were identified for the supplied data.

---

"""

    lines: List[str] = ["## 6. Detailed Findings", ""]

    lines.append(
        "This section sets out detailed findings for **leave and entitlement leakage** only. "
        "Record-Keeping & Evidence Gaps (RKEG) and Termination Exposure findings are available "
        "in machine-readable form (see Appendix C) and are intended to support operational review, "
        "sampling and remediation planning rather than narrative reporting."
    )
    lines.append("")
    lines.append(
        "Each leave/LSL finding below follows a consistent **Finding → Evidence → Impact → Recommended Action** pattern."
    )
    lines.append("")

    for idx, f in enumerate(findings, start=1):
        lines.append(f"### Finding {idx}: {f.rule_code or 'UNSPECIFIED RULE'}")
        lines.append(f"**Severity:** {f.severity or 'UNSPECIFIED'}")
        lines.append("")
        lines.append("**Finding**")
        lines.append(f"{f.message or 'No description provided.'}")
        lines.append("")
        lines.append("**Evidence**")
        lines.append("")  # ensure bullets render as a proper list

        evidence_bits = []
        if f.employee_id:
            evidence_bits.append(f"Employee ID: `{f.employee_id}`")
        if f.leave_type:
            evidence_bits.append(f"Leave type: `{f.leave_type}`")
        if f.as_of_date:
            evidence_bits.append(f"As at: `{f.as_of_date}`")

        if evidence_bits:
            lines.append("- " + "\n- ".join(evidence_bits))
        else:
            lines.append("- Not specified in the source data.")
        lines.append("")
        lines.append("**Impact / Risk**")
        lines.append(
            "Potential leave or entitlement imbalance and/or record-keeping weakness. "
            "The actual impact will depend on the underlying award or agreement, "
            "actual pay outcomes, and the period over which the issue has occurred."
        )
        lines.append("")
        lines.append("**Recommended Action**")
        lines.append("")  # blank line so the list renders properly

        lines.append(
            "- Validate this finding against source payroll records and employee entitlements."
        )
        lines.append(
            "- Correct any confirmed configuration, data or process issues."
        )
        lines.append(
            "- Consider remediation where underpayments are confirmed."
        )

        lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_financial_exposure_section(exposure_rows: List[ExposureRow]) -> str:
    if not exposure_rows:
        return """## 7. Financial Exposure (Indicative)

No exposure estimates were available from the current data extract. If required, leakage estimates can be added to this section in future runs.

---
"""

    total = sum(r.amount for r in exposure_rows)
    lines = [
        "## 7. Financial Exposure (Indicative)",
        "",
        f"- Number of findings with exposure estimates: {len(exposure_rows)}",
        f"- Indicative total exposure (all severities): {total:,.2f}",
        "",
        "> These figures are indicative only and rely on the provided data and simplifying assumptions. "
        "They should be validated before any remediation or accounting decisions are made.",
        "",
        "---",
        "",
    ]

    return "\n".join(lines)


def build_limitations() -> str:
    return """## 8. Limitations & Assumptions

This review is subject to the following limitations:

- Calculations assume the underlying pay rates, loadings and multipliers are correct in the source systems.
- Award and enterprise agreement interpretation is not performed by this tool.
- Holiday calendars, leave rules and accrual settings are assumed to reflect the organisation’s intended configuration.
- Data quality issues (missing records, duplicates, inconsistent identifiers) may affect the completeness and accuracy of the results.

---
"""


def build_next_steps() -> str:
    return """## 9. Recommended Next Steps

1. Prioritise validation of **High** severity findings.
2. Review affected employee records and reconstruct balances where necessary.
3. Correct any identified configuration or process issues in payroll and HR systems.
4. Consider remediation where confirmed underpayments have occurred.
5. Re-run the review after corrections to confirm that leakage has been addressed.

---
"""


def build_appendices() -> str:
    return """## 10. Appendix A – Rule Definitions

This review used a set of automated rules to flag potential leave and entitlement leakage. Examples include:

- Negative balance checks
- Casual employees accruing leave
- Inactive or terminated employees with leave movements
- Unusual accrual or usage patterns

(Expand this list over time to match your `rules.py` definitions for each module.)

---

## 11. Appendix B – Data Fields Used

Key fields used in this analysis include:

- `employee_id`
- `leave_type`
- `as_of_date`
- `balance_units`
- `movement_units`
- `employment_status`
- Termination-related fields such as `termination_date`, `termination_type`, `final_pay_date` and any termination evidence references

(Additional fields from the supplied CSV files may also be used.)

---

## 12. Appendix C – Machine-readable outputs

Complete machine-readable versions of the findings are available in:

- `outputs/modules/leave_leakage_findings.csv`
- `outputs/modules/lsl_findings.csv`
- `outputs/modules/rkeg_findings.csv`
- `outputs/modules/term_findings.csv`
- `outputs/leakage_report.csv`

These files provide row-level detail that can be used for remediation planning, sampling, or incorporation into a broader audit work program.

"""

# ---------- Orchestrator ----------

def generate_leave_leakage_report(
    organisation_name: str = "Organisation not specified",
    review_period: str | None = None,
) -> Path:
    """Generate outputs/report.md for the Leave & Entitlement Leakage Review."""
    findings = load_findings()
    sorted_findings = sort_findings(findings)
    exposure_rows = load_exposure_rows()
    rkeg_counts = load_rkeg_severity_counts()

    if review_period is None:
        review_period = _derive_review_period(sorted_findings)

    parts = [
        build_header(organisation_name, review_period),
        build_executive_summary(sorted_findings),
        build_data_sources_section(),
        build_scope_and_methodology(),
        build_rkeg_summary(rkeg_counts),
        build_term_severity_summary(),
        build_key_findings_overview(sorted_findings),
        build_detailed_findings(sorted_findings),
        build_financial_exposure_section(exposure_rows),
        build_limitations(),
        build_next_steps(),
        build_appendices(),
    ]

    REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD_PATH.write_text("\n".join(parts), encoding="utf-8")

    return REPORT_MD_PATH


if __name__ == "__main__":
    generate_leave_leakage_report()
    print(f"Generated Markdown report at {REPORT_MD_PATH}")
