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

from reporting.structure import ReportStructure

report_date = date.today().strftime("%d %b %Y")

# ---------- Engagement scope ----------

MODULE_LEAVE = "LEAVE"   # Leave & Entitlement Leakage findings + exposure section
MODULE_RKEG = "RKEG"     # Evidence gaps summary
MODULE_TERM = "TERM"     # Termination Exposure severity summary
MODULE_LSL  = "LSL"      # (if/when you add LSL sections to this report)

DEFAULT_MODULES = {MODULE_LEAVE, MODULE_RKEG, MODULE_TERM}

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
LSL_FINDINGS_CSV = MODULES_DIR / "lsl_findings.csv"
LSL_SUMMARY_BY_SEVERITY_CSV = MODULES_DIR / "lsl_summary_by_severity.csv"  # if you have / add it

REPORT_MD_PATH = OUTPUTS_DIR / "report.md"


def _module_ran(module: str) -> bool:
    """
    Returns True if the module has produced outputs we can render.
    Keeps the report clean (no blank tables / no '0' sections).
    """
    if module == MODULE_LEAVE:
        return LEAVE_FINDINGS_CSV.exists() or LEAKAGE_REPORT_CSV.exists()
    if module == MODULE_RKEG:
        return RKEG_SUMMARY_BY_SEVERITY_CSV.exists() or RKEG_FINDINGS_CSV.exists()
    if module == MODULE_TERM:
        return TERM_SUMMARY_BY_SEVERITY_CSV.exists() or TERM_FINDINGS_CSV.exists()
    if module == MODULE_LSL:
        return LSL_SUMMARY_BY_SEVERITY_CSV.exists() or LSL_FINDINGS_CSV.exists()
    return False

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

def load_lsl_severity_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    summary_rows = load_csv(LSL_SUMMARY_BY_SEVERITY_CSV)
    if summary_rows:
        sev_candidates = ["severity", "Severity"]
        count_candidates = ["finding_count", "count", "Count", "n", "N", "value", "Value"]

        first = summary_rows[0]
        sev_col = next((c for c in sev_candidates if c in first), None)
        count_col = next((c for c in count_candidates if c in first), None)

        if sev_col and count_col:
            for r in summary_rows:
                sev = (r.get(sev_col) or "").strip().upper()
                try:
                    n = int(float((r.get(count_col) or "0") or "0"))
                except ValueError:
                    n = 0
                if sev in counts:
                    counts[sev] += n
            return counts

    # fallback: count from findings
    finding_rows = load_csv(LSL_FINDINGS_CSV)
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

def build_header(report_title: str, organisation_name: str, review_period: str) -> str:
    return f"""# {report_title}

**Organisation:** {organisation_name}  
**Review period:** {review_period}  
**Report prepared as at:** {report_date}  

> This report highlights potential risk signals and process issues based on the data provided. It does not constitute legal, accounting, or industrial relations advice.

---
"""

def _build_report_title(modules: set[str]) -> str:
    # You can refine naming later; keep it simple and defensible for now.
    if modules == {MODULE_LSL}:
        return "Long Service Leave Exposure Review"
    if modules == {MODULE_TERM}:
        return "Termination Exposure Review"
    if modules == {MODULE_RKEG}:
        return "Record-Keeping & Evidence Gaps Review"
    if MODULE_LEAVE in modules and len(modules) == 1:
        return "Leave & Entitlement Leakage Review"

    # Multi-module
    return "Payroll Risk & Evidence Review"


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

    return f"""{paragraph}

**Findings identified**

- High severity: {high}
- Medium severity: {med}
- Low severity: {low}

**Who should read this**

This report is intended for payroll managers and related stakeholders responsible for leave, entitlement and payroll compliance.

---"""

def build_scope_and_methodology(included_modules: set[str]) -> str:
    # Normalise to avoid case/whitespace mismatches
    mods = {m.strip().upper() for m in (included_modules or set())}

    module_labels = {
        MODULE_LEAVE: "Leave & Entitlement Leakage (LEAVE)",
        MODULE_RKEG: "Record-Keeping & Evidence Gaps (RKEG)",
        MODULE_TERM: "Termination Exposure (TERM)",
        MODULE_LSL:  "Long Service Leave Exposure (LSL)",
    }

    lines: List[str] = []
    lines.append(
        "**Modules included in this engagement:** "
        + (", ".join(module_labels[m] for m in mods if m in module_labels) or "None")
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    if MODULE_LEAVE in mods:
        lines.append("**Leave & Entitlement Leakage – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Leave & Entitlement Leakage review identifies potential anomalies and risk indicators in leave balances, accruals and leave usage based on the data provided."
        )
        lines.append("")
        lines.append(
            "The purpose of this review is to highlight records that may warrant follow-up, such as negative balances, unexpected accrual patterns, mismatches between leave activity and employee status, or inconsistencies between leave movement data and balance snapshots."
        )
        lines.append("")
        lines.append(
            "This review is designed to support payroll and HR teams in prioritising validation and remediation effort. Findings are risk signals only and do not, on their own, confirm non-compliance, underpayment, or an entitlement error."
        )
        lines.append("")
        lines.append("**Data reviewed**")
        lines.append("")
        lines.append("- leave balances snapshot data (where supplied)")
        lines.append("- leave ledger / leave movement records (where supplied)")
        lines.append("- employee master data (where supplied)")
        lines.append("- other supporting payroll extracts included in the engagement pack")
        lines.append("")
        lines.append("**Checks performed**")
        lines.append("")
        lines.append("- rule-based detection of unusual leave balance and movement patterns")
        lines.append("- identification of negative balances and unexpected accrual behaviour")
        lines.append(
            "- consistency checks between employee status and leave activity (for example, terminated employees with ongoing leave movements)"
        )
        lines.append("- cross-checks between leave movement data and balance snapshot fields where available")
        lines.append("")
        lines.append("**Out of scope**")
        lines.append("")
        lines.append("This review does not:")
        lines.append("")
        lines.append("- interpret awards, enterprise agreements, or employment contracts")
        lines.append("- calculate legal entitlement outcomes or confirm the correctness of leave accrual rules")
        lines.append("- provide legal, accounting, or industrial relations advice")
        lines.append("- assert breaches of legislation or confirm non-compliance")
        lines.append("")
        lines.append(
            "Where exposure estimates are included, they are indicative only and must be validated before remediation or accounting decisions are made."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

    if MODULE_RKEG in mods:
        lines.append("**Record-Keeping & Evidence Gaps (RKEG) – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Record-Keeping & Evidence Gaps (RKEG) review assesses whether payroll-related records are sufficiently complete, consistent and traceable to support the organisation’s ability to evidence payroll decisions if reviewed by auditors or regulators."
        )
        lines.append("")
        lines.append(
            "RKEG focuses on evidential strength, not on determining whether payroll outcomes are correct or incorrect. Findings highlight where records may be incomplete, inconsistent, or difficult to substantiate if challenged."
        )
        lines.append("")
        lines.append(
            "This review is intended to support risk-aware payroll operations by identifying evidence weaknesses that can increase audit effort, increase dispute risk, or reduce the organisation’s ability to confidently explain pay decisions."
        )
        lines.append("")
        lines.append("**Data reviewed**")
        lines.append("")
        lines.append("- employee master data (where supplied)")
        lines.append("- pay event / payroll transaction extracts (where supplied)")
        lines.append("- termination and employment status fields where included in the engagement data pack")
        lines.append("")
        lines.append("**Checks performed**")
        lines.append("")
        lines.append("- completeness checks for key employee master fields required for traceability and defensibility")
        lines.append(
            "- identification of orphan or untraceable pay events (for example, pay events with missing or inconsistent identifiers)"
        )
        lines.append("- consistency checks across employee status and payroll activity where possible")
        lines.append("- identification of gaps that may require manual reconstruction to support an audit trail")
        lines.append("")
        lines.append("**Out of scope**")
        lines.append("")
        lines.append("This review does not:")
        lines.append("")
        lines.append("- calculate entitlements, underpayments or overpayments")
        lines.append("- interpret awards, enterprise agreements, or employment contracts")
        lines.append("- provide legal, accounting, or industrial relations advice")
        lines.append("- assert breaches of legislation or confirm non-compliance")
        lines.append("")
        lines.append(
            "RKEG findings should be interpreted as evidential risk indicators. Addressing them improves defensibility and reduces audit effort, but does not necessarily imply a payroll outcome is incorrect."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

    if MODULE_TERM in mods:
        lines.append("**Termination Exposure – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Termination Exposure review assesses whether termination events recorded in payroll and related employment data are sufficiently complete, timely, and traceable to support the organisation’s ability to evidence termination-related payroll decisions if reviewed by auditors or regulators."
        )
        lines.append("")
        lines.append("This review focuses on process and evidential integrity, not on the correctness of termination payments.")
        lines.append("")
        lines.append("Specifically, the review considers whether:")
        lines.append("")
        lines.append("- termination events are recorded consistently across available data sources")
        lines.append("- final pay processing occurs in a reasonable and defensible sequence relative to termination dates")
        lines.append("- core termination attributes (such as termination date and termination type/reason) are present and internally consistent")
        lines.append("- termination-related decisions are supported by basic evidentiary artefacts or references")
        lines.append("")
        lines.append("**Out of scope**")
        lines.append("")
        lines.append("This review does not:")
        lines.append("")
        lines.append("- calculate final pay entitlements or assess payment correctness")
        lines.append("- interpret awards, enterprise agreements, or employment contracts")
        lines.append("- determine notice, redundancy, or severance obligations")
        lines.append("- assert breaches of legislation or confirm non-compliance")
        lines.append("- provide legal advice or compliance guarantees")
        lines.append("")
        lines.append("Any potential exposure identified reflects defensibility risk, not confirmed error or liability.")
        lines.append("")
        lines.append("**Methodology**")
        lines.append("")
        lines.append(
            "The review applies a series of rule-based checks to payroll and related employment data to identify termination events that exhibit characteristics commonly associated with audit, regulatory, or dispute risk."
        )
        lines.append("")
        lines.append(
            "Each finding is assigned a severity based on evidential impact, reflecting how materially the issue could impair the organisation’s ability to explain and support termination-related payroll decisions if reviewed."
        )
        lines.append("")
        lines.append("Severity does not represent:")
        lines.append("")
        lines.append("- likelihood of underpayment")
        lines.append("- magnitude of financial exposure")
        lines.append("- remediation priority")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Only show this if mods is genuinely empty
    if not mods:
        lines.append("No scoped modules were included in this run.")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)

def build_data_sources_section(included_modules: set[str]) -> str:
    lines: List[str] = []

    lines.append(
        "This review was generated from the following analysis outputs within the project `outputs/` directory:"
    )
    lines.append("")

    # Only list outputs relevant to what was actually included
    if MODULE_LEAVE in included_modules:
        lines.append(f"- `{LEAVE_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  ")
        lines.append(f"- `{LEAKAGE_REPORT_CSV.relative_to(OUTPUTS_DIR)}`  ")

    if MODULE_RKEG in included_modules:
        if RKEG_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append(f"- `{RKEG_SUMMARY_BY_SEVERITY_CSV.relative_to(OUTPUTS_DIR)}`  ")
        if RKEG_FINDINGS_CSV.exists():
            lines.append(f"- `{RKEG_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  ")

    if MODULE_TERM in included_modules:
        if TERM_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append(f"- `{TERM_SUMMARY_BY_SEVERITY_CSV.relative_to(OUTPUTS_DIR)}`  ")
        if TERM_FINDINGS_CSV.exists():
            lines.append(f"- `{TERM_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  ")

    if MODULE_LSL in included_modules:
        if LSL_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append(f"- `{LSL_SUMMARY_BY_SEVERITY_CSV.relative_to(OUTPUTS_DIR)}`  ")
        if LSL_FINDINGS_CSV.exists():
            lines.append(f"- `{LSL_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  ")

    lines.append("")
    lines.append(
        "These outputs were produced by rule-based checks over payroll and HR CSV extracts supplied by the organisation for the review period."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)

def build_rkeg_summary(rkeg_counts: Dict[str, int]) -> str:
    """
    RKEG summary section content (no headings / no numbering).

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

    return f"""{interpretation_block}

{body}

{severity_overview}
"""

def build_lsl_severity_summary() -> str:
    lsl_counts = load_lsl_severity_counts()
    if not any(lsl_counts.values()):
        return ""

    return f"""Where an LSL Exposure review was performed, the table below summarises the number of LSL-related risk indicators identified by severity. Counts reflect **risk indicators only** and do not represent confirmed underpayments, quantified exposure, or remediation priority.

| Severity | Count | Description |
|---------|:-------------:|---------------------------|
| <span class="badge-high">High</span>    | {lsl_counts["HIGH"]}   | Indicators likely to require prompt validation due to potential material impact or audit defensibility concerns. |
| <span class="badge-medium">Medium</span>  | {lsl_counts["MEDIUM"]} | Indicators that may reflect configuration, data quality, or timing weaknesses requiring review. |
| <span class="badge-low">Low</span>     | {lsl_counts["LOW"]}    | Lower-impact indicators that should be improved over time. |

*Traffic light indicators reflect risk indicators only and do not represent confirmed breaches or quantified exposure.*

---
"""

def build_term_severity_summary() -> str:
    term_counts = load_term_severity_counts()

    if not any(term_counts.values()):
        return ""

    return f"""Where a Termination Exposure review was performed, the table below summarises the number of termination-related evidential issues identified by severity. Counts reflect **evidential risk only** and do not represent confirmed breaches, quantified exposure, or remediation priority.

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

    return f"""The automated checks identified the following potential issues in the leave and entitlement data reviewed. Severity reflects the relative level of risk to payroll accuracy and audit defensibility, not a confirmed breach.

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
        return """No findings were identified for the supplied data.

---

"""

    lines: List[str] = []

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
        lines.append("")

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
        lines.append("")

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
        return """No exposure estimates were available from the current data extract. If required, leakage estimates can be added to this section in future runs.

---
"""

    total = sum(r.amount for r in exposure_rows)

    lines = [
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
    return f"""This review is subject to the following limitations:

This review is subject to the following limitations:

- Calculations assume the underlying pay rates, loadings and multipliers are correct in the source systems.
- Award and enterprise agreement interpretation is not performed by this tool.
- Holiday calendars, leave rules and accrual settings are assumed to reflect the organisation’s intended configuration.
- Data quality issues (missing records, duplicates, inconsistent identifiers) may affect the completeness and accuracy of the results.

---
"""


def build_next_steps() -> str:
    return f"""Recommended Next Steps

1. Prioritise validation of **High** severity findings.
2. Review affected employee records and reconstruct balances where necessary.
3. Correct any identified configuration or process issues in payroll and HR systems.
4. Consider remediation where confirmed underpayments have occurred.
5. Re-run the review after corrections to confirm that leakage has been addressed.

---
"""


def build_appendices(included_modules: set[str]) -> str:
    """
    Build appendices dynamically (content-only).

    Numbering is controlled by the ReportStructure orchestrator.
    Inside this section we use lettered appendix headings (A/B/C) to keep structure clear
    without introducing conflicting numeric section numbers.
    """
    mods = {m.strip().upper() for m in (included_modules or set())}

    lines: List[str] = []

    # -------------------------
    # Appendix A – Rule Definitions
    # -------------------------
    lines.append("### Appendix A – Rule Definitions")
    lines.append("")
    lines.append("This review used a set of automated rules to flag evidential and process risk indicators.")
    lines.append("")

    if MODULE_LEAVE in mods:
        lines.append("#### Leave & Entitlement Leakage")
        lines.append("")
        lines.append("- Negative balance checks")
        lines.append("- Casual employees accruing leave")
        lines.append("- Inactive or terminated employees with leave movements")
        lines.append("- Unusual accrual or usage patterns")
        lines.append("")

    if MODULE_LSL in mods:
        lines.append("#### Long Service Leave (LSL) Exposure")
        lines.append("")
        lines.append("- Inconsistent LSL accrual patterns")
        lines.append("- LSL balances inconsistent with service duration")
        lines.append("- Missing or incomplete service date records")
        lines.append("")

    if MODULE_RKEG in mods:
        lines.append("#### Record-Keeping & Evidence Gaps (RKEG)")
        lines.append("")
        lines.append("- Missing employee master data fields")
        lines.append("- Orphan pay events and traceability gaps")
        lines.append("- Inconsistent employment status records")
        lines.append("- Missing or inconsistent termination attributes")
        lines.append("")

    if MODULE_TERM in mods:
        lines.append("#### Termination Exposure (TERM)")
        lines.append("")
        lines.append("- Final pay sequencing checks vs termination date")
        lines.append("- Missing / inconsistent termination dates")
        lines.append("- Missing / inconsistent termination type / reason")
        lines.append("- Missing evidence references / artefact identifiers")
        lines.append("- Ambiguous identification of final pay events within a window")
        lines.append("- Termination events inconsistent with ordinary pay activity patterns")
        lines.append("")

    lines.append("---")
    lines.append("")

    # -------------------------
    # Appendix B – Data Fields Used
    # -------------------------
    lines.append("### Appendix B – Data Fields Used")
    lines.append("")
    lines.append("Key fields used in this review may include:")
    lines.append("")
    lines.append("- `employee_id`")

    if MODULE_LEAVE in mods or MODULE_LSL in mods:
        lines.append("- `leave_type`")
        lines.append("- `balance_units`")
        lines.append("- `movement_units`")

    if MODULE_TERM in mods:
        lines.append("- `termination_date`")
        lines.append("- `termination_type` / `termination_reason`")
        lines.append("- `pay_date` (for sequencing checks)")
        lines.append("- `is_final_pay` (where available)")
        lines.append("- Termination evidence reference fields (e.g. `evidence_ref`, `document_id`)")

    if MODULE_RKEG in mods:
        lines.append("- Employee master fields (e.g. start date, employment type, status)")
        lines.append("- Pay event traceability identifiers (run IDs, event IDs where supplied)")

    lines.append("")
    lines.append("---")
    lines.append("")

    # -------------------------
    # Appendix C – Machine-readable outputs
    # -------------------------
    lines.append("### Appendix C – Machine-readable outputs")
    lines.append("")
    lines.append("Complete machine-readable outputs are available in the following files:")
    lines.append("")

    if MODULE_LEAVE in mods:
        lines.append("- `outputs/modules/leave_leakage_findings.csv`")
        lines.append("- `outputs/leakage_report.csv`")

    if MODULE_LSL in mods:
        lines.append("- `outputs/modules/lsl_findings.csv`")
        # optional summary if you have it
        if "LSL_SUMMARY_BY_SEVERITY_CSV" in globals() and LSL_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append("- `outputs/modules/lsl_summary_by_severity.csv`")

    if MODULE_RKEG in mods:
        lines.append("- `outputs/modules/rkeg_findings.csv`")
        if RKEG_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append("- `outputs/modules/rkeg_summary_by_severity.csv`")

    if MODULE_TERM in mods:
        lines.append("- `outputs/modules/term_findings.csv`")
        if TERM_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append("- `outputs/modules/term_summary_by_severity.csv`")
        # optional term summary table
        term_summary_path = OUTPUTS_DIR / "modules" / "term_summary.csv"
        if term_summary_path.exists():
            lines.append("- `outputs/modules/term_summary.csv`")

    lines.append("")
    lines.append(
        "These files provide row-level detail suitable for operational review, sampling, remediation planning, or incorporation into a broader audit work program."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)

# ---------- Orchestrator ----------

def generate_leave_leakage_report(
    organisation_name: str = "Organisation not specified",
    review_period: str | None = None,
    modules: Optional[Iterable[str]] = None,
) -> Path:
    """
    Generate outputs/report.md.

    modules controls which sections are included.
    Sections are also suppressed if their underlying module outputs do not exist.
    """
    requested: set[str] = {m.strip().upper() for m in (modules or DEFAULT_MODULES)}

    # Only include modules that actually ran (keeps report clean)
    included: set[str] = {m for m in requested if _module_ran(m)}

    # If nothing ran, fall back to leave title but show a clean "no data" report.
    report_title: str = _build_report_title(included or requested)

    # Load data only if relevant
    findings: List[Finding] = load_findings() if MODULE_LEAVE in included else []
    sorted_findings = sort_findings(findings) if findings else []
    exposure_rows = load_exposure_rows() if MODULE_LEAVE in included else []
    rkeg_counts = load_rkeg_severity_counts() if MODULE_RKEG in included else {}

    if review_period is None:
        # Derive from leave findings only when leave is included; otherwise use generic.
        review_period = _derive_review_period(sorted_findings) if sorted_findings else "Period not specified"

    parts: List[str] = []
    final_review_period: str = review_period if review_period is not None else "Period not specified"
    parts.append(build_header(report_title, organisation_name, final_review_period))

    structure = ReportStructure()

    # --- Section 1: Executive Summary (level 1) ---
    def exec_summary_content() -> str:
        if MODULE_LEAVE in included:
            return build_executive_summary(sorted_findings)  # will become content-only in Step 2
        return (
            f"This review produced outputs for the following modules: "
            f"{', '.join(sorted(included)) or 'None'}.\n"
            "Findings reflect evidential and process risk indicators only and do not, on their own, "
            "confirm non-compliance or underpayment.\n\n---"
        )

    structure.add("Executive Summary", 1, exec_summary_content)
    structure.add("Data Sources", 1, lambda: build_data_sources_section(included))
    structure.add("Scope & Methodology", 1, lambda: build_scope_and_methodology(included))

    # ---------------- Evidence & Defensibility Overview ----------------
    evidence_modules = {MODULE_RKEG, MODULE_TERM, MODULE_LSL}

    if any(m in included for m in evidence_modules):
        structure.add("Evidence & Defensibility Overview", 1, lambda: "")

        if MODULE_RKEG in included:
            structure.add(
                "Record-Keeping & Evidence Gaps (RKEG) – Severity Overview",
                2,
                lambda: build_rkeg_summary(rkeg_counts),  # temp
            )

        if MODULE_TERM in included:
            structure.add(
                "Termination Exposure – Severity Overview",
                2,
                lambda: build_term_severity_summary(),  # temp
            )

        if MODULE_LSL in included:
            structure.add(
                "Long Service Leave (LSL) Exposure – Severity Overview",
                2,
                lambda: build_lsl_severity_summary(),  # temp
            )

    # ---------------- Leave-only sections ----------------
    if MODULE_LEAVE in included:
        structure.add("Key Findings Overview", 1, lambda: build_key_findings_overview(sorted_findings))
        structure.add("Detailed Findings", 1, lambda: build_detailed_findings(sorted_findings))
        structure.add("Financial Exposure (Indicative)", 1, lambda: build_financial_exposure_section(exposure_rows))

    # ---------------- Trailing sections ----------------
    structure.add("Limitations & Assumptions", 1, lambda: build_limitations())
    structure.add("Recommended Next Steps", 1, lambda: build_next_steps())
    structure.add("Appendices", 1, lambda: build_appendices(included_modules=included))

    # ---------------- Render + write ----------------
    parts.append(structure.render_markdown())

    REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD_PATH.write_text("\n".join(parts), encoding="utf-8")
    return REPORT_MD_PATH


if __name__ == "__main__":
    path = generate_leave_leakage_report(modules=["TERM"])
    print(f"Generated at: {path}")
