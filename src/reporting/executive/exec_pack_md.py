from __future__ import annotations

import csv
from dataclasses import dataclass 
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Dict, Optional

from common.severity import SEVERITY_BY_CODE
from reporting.rkeg_text import (
    build_rkeg_summary_paragraph,  # currently unused but fine to keep
    build_rkeg_severity_overview_table,
)
from reporting.structure import ReportStructure
from common.report_text import scan_report_text


report_date = date.today().strftime("%d %b %Y")

# ---------- Engagement scope ----------

MODULE_LEAVE = "LEAVE"   # Leave & Entitlement Leakage findings
MODULE_RKEG = "RKEG"     # Evidence gaps summary
MODULE_TERM = "TERM"     # Termination Exposure severity summary
MODULE_LSL  = "LSL"      # Long Service Leave Exposure

# Canonical CRC module order (used everywhere in reporting)
MODULE_ORDER = [MODULE_LEAVE, MODULE_LSL, MODULE_TERM, MODULE_RKEG]

MODULE_LABELS = {
    MODULE_LEAVE: "Leave & Entitlement Leakage (LEAVE)",
    MODULE_LSL:  "Long Service Leave Exposure (LSL)",
    MODULE_TERM: "Termination Exposure (TERM)",
    MODULE_RKEG: "Record-Keeping & Evidence Gaps (RKEG)",
}

# Default module inclusion for a run (keep as list for predictable ordering)
DEFAULT_MODULES = [MODULE_LEAVE, MODULE_LSL, MODULE_TERM, MODULE_RKEG]

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

EXEC_PACK_MD_PATH = OUTPUTS_DIR / "crc_executive_pack.md"

# ---------- Data models used by exec pack (leave findings) ----------

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


# ---------- CSV helpers (leave findings) ----------

def load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    import csv  # local import to avoid circular headaches elsewhere

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


# ---------- Review period helpers (leave) ----------

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


from datetime import datetime

def _derive_exec_review_period(included_modules: set[str]) -> str:
    """
    Derive a review period across all included modules by scanning
    their findings CSVs for any column containing 'date'.

    Returns min → max date if found, otherwise 'Period not specified'.
    """
    candidate_paths = []

    if MODULE_LEAVE in included_modules:
        candidate_paths.append(LEAVE_FINDINGS_CSV)

    if MODULE_LSL in included_modules:
        candidate_paths.append(LSL_FINDINGS_CSV)

    if MODULE_TERM in included_modules:
        candidate_paths.append(TERM_FINDINGS_CSV)

    if MODULE_RKEG in included_modules:
        candidate_paths.append(RKEG_FINDINGS_CSV)

    all_dates: list[date] = []

    for path in candidate_paths:
        if not path.exists():
            continue

        rows = _load_csv(path)

        for row in rows:
            for col, raw in row.items():
                if not col or "date" not in col.lower():
                    continue

                value = (raw or "").strip()
                if not value:
                    continue

                # Try common formats
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        d = datetime.strptime(value, fmt).date()
                        all_dates.append(d)
                        break
                    except ValueError:
                        continue

    if not all_dates:
        return "Period not specified"

    start = min(all_dates)
    end = max(all_dates)

    if start == end:
        return start.strftime("%d %b %Y")

    return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"

def normalise_modules(included_modules: set[str] | list[str] | None) -> set[str]:
    return {m.strip().upper() for m in (included_modules or [])}


def included_modules_in_order(included_modules: set[str] | list[str] | None) -> list[str]:
    mods = normalise_modules(included_modules)
    return [m for m in MODULE_ORDER if m in mods]


def build_interpretation_block_exec(included_modules: set[str]) -> str:
    mods = {m.strip().upper() for m in (included_modules or set())}

    lines: list[str] = []
    lines.append("**How to interpret findings across modules**")
    lines.append("")

    # Leave / LSL (bundle only if either is present)
    if MODULE_LEAVE in mods or MODULE_LSL in mods:
        if MODULE_LEAVE in mods and MODULE_LSL in mods:
            label = "Leave & LSL findings"
        elif MODULE_LEAVE in mods:
            label = "Leave findings"
        else:
            label = "LSL findings"

        lines.append(
            f"- **{label}** highlight potential anomalies in leave balances, accruals and usage. "
            "These indicators relate to *payroll outcomes and configuration* and may require remediation if confirmed."
        )

    # Termination
    if MODULE_TERM in mods:
        lines.append(
            "- **Termination Exposure findings** relate to the completeness, sequencing and documentation of termination "
            "events and final pay. They indicate how readily the organisation could evidence termination processing if challenged."
        )

    # RKEG
    if MODULE_RKEG in mods:
        lines.append(
            "- **Record-Keeping & Evidence Gaps (RKEG) findings** assess the strength of the evidentiary trail supporting "
            "payroll decisions. They do **not** indicate incorrect pay outcomes; they highlight where records may be incomplete "
            "or difficult to substantiate."
        )

    lines.append("")
    lines.append(
        "Findings are risk indicators requiring validation and do not, on their own, confirm non-compliance, legislative contravention, or underpayment."
    )
    lines.append("")
    lines.append(
        "*Traffic light indicators reflect evidential risk only and do not represent confirmed contraventions or quantified exposure.*"
    )

    return "\n".join(lines).strip()


def load_rkeg_severity_counts() -> Dict[str, int]:
    """
    Load simple HIGH / MEDIUM / LOW counts for RKEG.

    First preference: outputs/modules/rkeg_summary_by_severity.csv
    Fallback:        outputs/modules/rkeg_findings.csv (count severity column)
    """
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    summary_rows = _load_csv(RKEG_SUMMARY_BY_SEVERITY_CSV)
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

            return counts

    # fallback: count from findings
    finding_rows = _load_csv(RKEG_FINDINGS_CSV)
    if not finding_rows:
        return counts

    for r in finding_rows:
        sev = (r.get("severity") or r.get("Severity") or "").strip().upper()
        if sev in counts:
            counts[sev] += 1

    return counts


def load_lsl_severity_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    summary_rows = _load_csv(LSL_SUMMARY_BY_SEVERITY_CSV)
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
    finding_rows = _load_csv(LSL_FINDINGS_CSV)
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

    summary_rows = _load_csv(TERM_SUMMARY_BY_SEVERITY_CSV)
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

            return counts

    finding_rows = _load_csv(TERM_FINDINGS_CSV)
    if not finding_rows:
        return counts

    for r in finding_rows:
        sev = (r.get("severity") or r.get("Severity") or "").strip().upper()
        if sev in counts:
            counts[sev] += 1

    return counts


def _load_csv(path: Path) -> List[Dict[str, str]]:
    """Tiny internal helper so we don't re-import csv + dataclasses here."""
    if not path.exists():
        return []
    import csv  # local import to avoid unused top-level dependency

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def sort_findings(findings: List) -> List:
    """Sort findings by severity (HIGH→MEDIUM→LOW), then rule_code, then employee/date."""
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(
        findings,
        key=lambda f: (
            severity_rank.get(getattr(f, "severity", ""), 99),
            getattr(f, "rule_code", "") or "",
            getattr(f, "employee_id", "") or "",
            getattr(f, "as_of_date", "") or "",
        ),
    )


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
    if modules == {MODULE_LSL}:
        return "Long Service Leave Exposure Review"
    if modules == {MODULE_TERM}:
        return "Termination Exposure Review"
    if modules == {MODULE_RKEG}:
        return "Record-Keeping & Evidence Gaps Review"
    if MODULE_LEAVE in modules and len(modules) == 1:
        return "Leave & Entitlement Leakage Review"

    return "Payroll Risk & Evidence Review"


def build_executive_summary(
    included_modules: set[str],
    leave_findings: List,
    rkeg_counts: Dict[str, int],
    term_counts: Dict[str, int] | None = None,
    lsl_counts: Dict[str, int] | None = None,
) -> str:
    # ---- Leave totals ----
    leave_high = sum(1 for f in leave_findings if getattr(f, "severity", "") == "HIGH")
    leave_med = sum(1 for f in leave_findings if getattr(f, "severity", "") == "MEDIUM")
    leave_low = sum(1 for f in leave_findings if getattr(f, "severity", "") == "LOW")

    # ---- RKEG totals ----
    rkeg_high = rkeg_counts.get("HIGH", 0)
    rkeg_med = rkeg_counts.get("MEDIUM", 0)
    rkeg_low = rkeg_counts.get("LOW", 0)

    # ---- TERM totals ----
    term_high = (term_counts or {}).get("HIGH", 0)
    term_med = (term_counts or {}).get("MEDIUM", 0)
    term_low = (term_counts or {}).get("LOW", 0)

    # ---- LSL totals ----
    lsl_high = (lsl_counts or {}).get("HIGH", 0)
    lsl_med = (lsl_counts or {}).get("MEDIUM", 0)
    lsl_low = (lsl_counts or {}).get("LOW", 0)

    module_labels = {
        MODULE_LEAVE: "Leave & Entitlement Leakage",
        MODULE_LSL: "Long Service Leave (LSL) Exposure",
        MODULE_TERM: "Termination Exposure",
        MODULE_RKEG: "Record-Keeping & Evidence Gaps (RKEG)",
    }

    order = [MODULE_LEAVE, MODULE_LSL, MODULE_TERM, MODULE_RKEG]
    ordered_labels = [module_labels[m] for m in order if m in included_modules]

    if ordered_labels:
        module_block = "\n".join(f"- **{label}**" for label in ordered_labels)
    else:
        module_block = "- None"

    risk_lines = []

    if MODULE_LEAVE in included_modules:
        risk_lines.append(
            f"**Leave & Entitlement Leakage** – High: {leave_high} | Medium: {leave_med} | Low: {leave_low}"
        )

    if MODULE_LSL in included_modules:
        risk_lines.append(
            f"**Long Service Leave (LSL)** – High: {lsl_high} | Medium: {lsl_med} | Low: {lsl_low}"
        )

    if MODULE_TERM in included_modules:
        risk_lines.append(
            f"**Termination Exposure** – High: {term_high} | Medium: {term_med} | Low: {term_low}"
        )

    if MODULE_RKEG in included_modules:
        risk_lines.append(
            f"**Record-Keeping & Evidence Gaps (RKEG)** – High: {rkeg_high} | Medium: {rkeg_med} | Low: {rkeg_low}"
        )

    risk_summary_block = "\n\n".join(risk_lines)

    return f"""
This engagement reviewed payroll and HR data across the following modules:

{module_block}

The review identified risk indicators across payroll outcomes, termination processing and record-keeping defensibility.

Severity reflects relative evidential or payroll risk only. Findings are indicators requiring validation and do not, on their own, confirm underpayment, non-compliance, or legislative contravention.

---

**Summary of Risk Indicators**

{risk_summary_block}

---

**Who should read this**

This report is intended for:

- Payroll leaders
- HR managers
- Finance stakeholders
- Risk and compliance personnel responsible for payroll governance and evidential integrity
"""


def build_scope_and_methodology(included_modules: set[str] | list[str] | None) -> str:
    """
    Build the shared Scope & Methodology section for the EXEC pack.

    - The parent heading "3. Scope & Methodology" is handled by ReportStructure.
    - This function renders:
        * A short intro + list of included modules
        * One 3.x subsection per module actually included (LEAVE, LSL, TERM, RKEG)
        * A fallback message if no modules are in scope
    """
    # Normalise to avoid case/whitespace mismatches
    mods = normalise_modules(included_modules)
    subsection_no = 1

    ordered = included_modules_in_order(mods)

    lines: List[str] = []
    lines.append("Scope & Methodology")
    lines.append("")
    lines.append("**Modules included in this engagement:**")
    lines.append("")

    for m in ordered:
        lines.append(f"- {MODULE_LABELS[m]}")
    if not ordered:
        lines.append("- None specified")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1️⃣ LEAVE
    if MODULE_LEAVE in mods:
        lines.append(f"### 3.{subsection_no} **Leave & Entitlement Leakage – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Leave & Entitlement Leakage review identifies potential anomalies and risk indicators "
            "in leave balances, accruals and leave usage based on the data provided."
        )
        lines.append("")
        lines.append(
            "The purpose of this review is to highlight records that may warrant follow-up, such as negative "
            "balances, unexpected accrual patterns, mismatches between leave activity and employee status, or "
            "inconsistencies between leave movement data and balance snapshots."
        )
        lines.append("")
        lines.append(
            "This review is designed to support payroll and HR teams in prioritising validation and remediation "
            "effort. Findings are risk signals only and do not, on their own, confirm non-compliance, "
            "underpayment, or an entitlement error."
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
            "- consistency checks between employee status and leave activity "
            "(for example, terminated employees with ongoing leave movements)"
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
        lines.append("- assert contraventions of legislation or confirm non-compliance.")
        lines.append("")
        lines.append(
            "Where exposure estimates are included, they are indicative only and must be validated before "
            "remediation or accounting decisions are made."
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        subsection_no += 1

    # 2️⃣ LSL
    if MODULE_LSL in mods:
        lines.append(f"### 3.{subsection_no} **Long Service Leave (LSL) Exposure – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Long Service Leave (LSL) Exposure review identifies risk indicators in LSL balance and "
            "service-related data that may warrant further validation. The purpose of this review is to "
            "highlight records that appear inconsistent, incomplete, or difficult to substantiate based on "
            "the data provided."
        )
        lines.append("")
        lines.append(
            "This review is designed to support payroll, HR and finance teams in prioritising follow-up effort. "
            "Findings are risk signals only and do not, on their own, confirm an entitlement error, "
            "underpayment, or non-compliance."
        )
        lines.append("")
        lines.append("**Data reviewed**")
        lines.append("")
        lines.append("- employee master data relevant to LSL service (where supplied)")
        lines.append("- LSL balance snapshot data (where supplied)")
        lines.append("- LSL accrual or movement records (where supplied)")
        lines.append("- other supporting payroll extracts included in the engagement pack")
        lines.append("")
        lines.append("**Checks performed**")
        lines.append("")
        lines.append("- consistency checks between LSL balances, accrual patterns, and available service-related fields")
        lines.append("- identification of missing or incomplete service date records required to support LSL calculations")
        lines.append("- detection of unusual balance or movement patterns that may indicate configuration or data issues")
        lines.append("")
        lines.append("**Out of scope**")
        lines.append("")
        lines.append("This review does not:")
        lines.append("")
        lines.append("- interpret awards, enterprise agreements, or employment contracts")
        lines.append("- calculate legal LSL entitlement outcomes or confirm the correctness of LSL accrual rules")
        lines.append("- provide legal, accounting, or industrial relations advice")
        lines.append("- assert contraventions of legislation or confirm non-compliance.")
        lines.append("")
        lines.append(
            "Where any exposure estimates or balance concerns are inferred, they are indicative only and must be "
            "validated before remediation or accounting decisions are made."
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        subsection_no += 1

    # 3️⃣ TERM
    if MODULE_TERM in mods:
        lines.append(f"### 3.{subsection_no} **Termination Exposure – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Termination Exposure review assesses whether termination events recorded in payroll and "
            "related employment data are sufficiently complete, timely, and traceable to support the "
            "organisation’s ability to evidence termination-related payroll decisions if reviewed by "
            "auditors or regulators."
        )
        lines.append("")
        lines.append(
            "This review focuses on process and evidential integrity, not on the correctness of termination payments."
        )
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
        lines.append("- assert contraventions of legislation or confirm non-compliance.")
        lines.append("- provide legal advice or assurance of compliance.")
        lines.append("")
        lines.append("Any potential exposure identified reflects defensibility risk, not confirmed error or liability.")
        lines.append("")
        lines.append("**Methodology**")
        lines.append("")
        lines.append(
            "The review applies a series of rule-based checks to payroll and related employment data to "
            "identify termination events that exhibit characteristics commonly associated with audit, "
            "regulatory, or dispute risk."
        )
        lines.append("")
        lines.append(
            "Each finding is assigned a severity based on evidential impact, reflecting how materially the "
            "issue could impair the organisation’s ability to explain and support termination-related payroll "
            "decisions if reviewed."
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
        subsection_no += 1

    # 4️⃣ RKEG
    if MODULE_RKEG in mods:
        lines.append(f"### 3.{subsection_no} **Record-Keeping & Evidence Gaps (RKEG) – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Record-Keeping & Evidence Gaps (RKEG) review assesses whether payroll-related records are "
            "sufficiently complete, consistent and traceable to support the organisation’s ability to evidence "
            "payroll decisions if reviewed by auditors or regulators."
        )
        lines.append("")
        lines.append(
            "RKEG focuses on evidential strength, not on determining whether payroll outcomes are correct or "
            "incorrect. Findings highlight where records may be incomplete, inconsistent, or difficult to "
            "substantiate if challenged."
        )
        lines.append("")
        lines.append(
            "This review is intended to support risk-aware payroll operations by identifying evidence weaknesses "
            "that can increase audit effort, increase dispute risk, or reduce the organisation’s ability to "
            "confidently explain pay decisions."
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
            "- identification of orphan or untraceable pay events (for example, pay events with missing or "
            "inconsistent identifiers)"
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
        lines.append("- assert contraventions of legislation or confirm non-compliance.")
        lines.append("")
        lines.append(
            "RKEG findings should be interpreted as evidential risk indicators. Addressing them improves "
            "defensibility and reduces audit effort, but does not necessarily imply a payroll outcome is incorrect."
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        subsection_no += 1

    # If somehow nothing was in scope
    if not mods:
        lines.append("No scoped modules were included in this run.")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def build_data_sources_section(included_modules: set[str] | list[str] | None) -> str:
    lines: List[str] = []

    lines.append(
        "This review was generated from the following analysis outputs within the project `outputs/` directory:"
    )
    lines.append("")

    mods = normalise_modules(included_modules)
    for m in included_modules_in_order(mods):

        if m == MODULE_LEAVE:
            lines.append(f"- `{LEAVE_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  ")
            lines.append(f"- `{LEAKAGE_REPORT_CSV.relative_to(OUTPUTS_DIR)}`  ")

        elif m == MODULE_LSL:
            if LSL_SUMMARY_BY_SEVERITY_CSV.exists():
                lines.append(f"- `{LSL_SUMMARY_BY_SEVERITY_CSV.relative_to(OUTPUTS_DIR)}`  ")
            if LSL_FINDINGS_CSV.exists():
                lines.append(f"- `{LSL_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  ")

        elif m == MODULE_TERM:
            if TERM_SUMMARY_BY_SEVERITY_CSV.exists():
                lines.append(f"- `{TERM_SUMMARY_BY_SEVERITY_CSV.relative_to(OUTPUTS_DIR)}`  ")
            if TERM_FINDINGS_CSV.exists():
                lines.append(f"- `{TERM_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  ")

        elif m == MODULE_RKEG:
            if RKEG_SUMMARY_BY_SEVERITY_CSV.exists():
                lines.append(f"- `{RKEG_SUMMARY_BY_SEVERITY_CSV.relative_to(OUTPUTS_DIR)}`  ")
            if RKEG_FINDINGS_CSV.exists():
                lines.append(f"- `{RKEG_FINDINGS_CSV.relative_to(OUTPUTS_DIR)}`  ")

    lines.append("")
    lines.append(
        "These outputs were produced by rule-based checks over payroll and HR CSV extracts supplied by the organisation for the review period."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def build_rkeg_summary(rkeg_counts: Dict[str, int]) -> str:
    if not any(rkeg_counts.values()):
        return ""

    severity_overview = build_rkeg_severity_overview_table(rkeg_counts)

    return f"""
As part of this review, a Record-Keeping & Evidence Gaps (RKEG) assessment was performed to evaluate whether payroll-related records are sufficiently complete, consistent and traceable to support payroll decisions if subject to audit or regulatory review.

The RKEG assessment focuses on evidential strength only. It does not determine whether payroll outcomes are correct or incorrect, and does not interpret awards, enterprise agreements or employment contracts.

The table below summarises the number of record-keeping and evidence gaps identified by severity. Counts reflect **evidential risk** only and do not represent confirmed non-compliance or quantified financial exposure.

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


---
"""


def build_term_severity_summary() -> str:
    term_counts = load_term_severity_counts()

    if not any(term_counts.values()):
        return ""

    return f"""Where a Termination Exposure review was performed, the table below summarises the number of termination-related evidential issues identified by severity. Counts reflect **evidential risk** only and do not represent confirmed non-compliance or quantified financial exposure, or remediation priority.

| Severity | Count | Description |
|---------|:-------------:|---------------------------|
| <span class="badge-high">High</span>    | {term_counts["HIGH"]}   | Absence or weakness of core termination or final pay evidence that would materially impair the organisation’s ability to evidence termination decisions if reviewed by auditors or regulators. |
| <span class="badge-medium">Medium</span>  | {term_counts["MEDIUM"]} | Termination evidence exists but is incomplete, delayed or ambiguous and may require additional explanation or manual reconstruction. |
| <span class="badge-low">Low</span>     | {term_counts["LOW"]}    | Minor record-keeping or data quality weaknesses in termination records that should be improved over time to support efficient and reliable payroll operations. |


---
"""


def build_key_findings_overview(findings: List) -> str:
    high = sum(1 for f in findings if getattr(f, "severity", "") == "HIGH")
    med = sum(1 for f in findings if getattr(f, "severity", "") == "MEDIUM")
    low = sum(1 for f in findings if getattr(f, "severity", "") == "LOW")

    high_def = SEVERITY_BY_CODE.get("HIGH")
    med_def = SEVERITY_BY_CODE.get("MEDIUM")
    low_def = SEVERITY_BY_CODE.get("LOW")

    high_desc = high_def.description if high_def else "Higher-risk record-keeping or entitlement concern."
    med_desc = med_def.description if med_def else "Material configuration, process, or data concern."
    low_desc = low_def.description if low_def else "Lower-impact data quality or minor process issue."

    return f"""The automated checks identified the following potential issues in the leave and entitlement data reviewed. Severity reflects the relative level of risk to payroll accuracy and audit defensibility, not a confirmed breach.

| Severity | Count | Description |
|---------|:-----:|-------------|
| <span class="badge-high">High</span>    | {high}   | {high_desc} |
| <span class="badge-medium">Medium</span>  | {med}   | {med_desc}  |
| <span class="badge-low">Low</span>     | {low}   | {low_desc}  |

---
"""


def build_limitations() -> str:
    return """This review is subject to the following limitations:


- Calculations assume the underlying pay rates, loadings and multipliers are correct in the source systems.
- Award and enterprise agreement interpretation is not performed by this tool.
- Holiday calendars, leave rules and accrual settings are assumed to reflect the organisation’s intended configuration.
- Data quality issues (missing records, duplicates, inconsistent identifiers) may affect the completeness and accuracy of the results.

---
"""


def build_next_steps() -> str:
    return """Recommended Next Steps

1. Prioritise validation of **High** severity findings.
2. Review affected employee records and reconstruct balances where necessary.
3. Correct any identified configuration or process issues in payroll and HR systems.
4. Consider remediation where confirmed underpayments have occurred.
5. Re-run the review after corrections to confirm that leakage has been addressed.

---
"""


def build_appendices(included_modules: set[str]) -> str:
    mods = {m.strip().upper() for m in (included_modules or set())}

    lines: List[str] = []

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

    if MODULE_RKEG in mods:
        lines.append("#### Record-Keeping & Evidence Gaps (RKEG)")
        lines.append("")
        lines.append("- Missing employee master data fields")
        lines.append("- Orphan pay events and traceability gaps")
        lines.append("- Inconsistent employment status records")
        lines.append("- Missing or inconsistent termination attributes")
        lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("### Appendix B – Data Fields Used")
    lines.append("")
    lines.append("Key data fields referenced in this engagement include:")
    lines.append("")

    if MODULE_LEAVE in mods:
        lines.append("**Leave & Entitlement Leakage**")
        lines.append("")
        lines.append("- `employee_id`")
        lines.append("- `leave_type`")
        lines.append("- `as_of_date`")
        lines.append("- `rule_code`")
        lines.append("- `severity`")
        lines.append("- `message`")
        lines.append("- `diff_units`")
        lines.append("- `finding_id`")
        lines.append("- `next_action`")
        lines.append("")

    if MODULE_LSL in mods:
        lines.append("**LSL Exposure**")
        lines.append("")
        lines.append("- `employee_id`")
        lines.append("- `leave_type`")
        lines.append("- `as_of_date`")
        lines.append("- `rule_code`")
        lines.append("- `severity`")
        lines.append("- `message`")
        lines.append("- `diff_units`")
        lines.append("- `finding_id`")
        lines.append("- `next_action`")
        lines.append("")

    if MODULE_TERM in mods:
        lines.append("**Termination Exposure (TERM)**")
        lines.append("")
        lines.append("- `employee_id`")
        lines.append("- `termination_date`")
        lines.append("- `final_pay_date`")
        lines.append("- `rule_code`")
        lines.append("- `severity`")
        lines.append("- `message`")
        lines.append("- `days_gap`")
        lines.append("- `evidence`")
        lines.append("- `finding_id`")
        lines.append("- `next_action`")
        lines.append("")

    if MODULE_RKEG in mods:
        lines.append("**Record-Keeping & Evidence Gaps (RKEG)**")
        lines.append("")
        lines.append("- `employee_id`")
        lines.append("- `leave_type`")
        lines.append("- `as_of_date`")
        lines.append("- `rule_code`")
        lines.append("- `severity`")
        lines.append("- `message`")
        lines.append("- `diff_units`")
        lines.append("- `evidence`")
        lines.append("- `finding_id`")
        lines.append("- `next_action`")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("### Appendix C – Machine-readable outputs")
    lines.append("")
    lines.append("Complete machine-readable outputs are available in the following files:")
    lines.append("")

    if MODULE_LEAVE in mods:
        lines.append("- `outputs/modules/leave_leakage_findings.csv`")
        lines.append("- `outputs/leakage_report.csv`")

    if MODULE_LSL in mods:
        lines.append("- `outputs/modules/lsl_findings.csv`")
        if LSL_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append("- `outputs/modules/lsl_summary_by_severity.csv`")

    if MODULE_TERM in mods:
        lines.append("- `outputs/modules/term_findings.csv`")
        if TERM_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append("- `outputs/modules/term_summary_by_severity.csv`")
        term_summary_path = OUTPUTS_DIR / "modules" / "term_summary.csv"
        if term_summary_path.exists():
            lines.append("- `outputs/modules/term_summary.csv`")

    if MODULE_RKEG in mods:
        lines.append("- `outputs/modules/rkeg_findings.csv`")
        if RKEG_SUMMARY_BY_SEVERITY_CSV.exists():
            lines.append("- `outputs/modules/rkeg_summary_by_severity.csv`")

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
    Generate outputs/crc_executive_pack.md.

    modules controls which sections are included.
    Sections are also suppressed if their underlying module outputs do not exist.
    """
    
    requested: set[str] = {m.strip().upper() for m in (modules or DEFAULT_MODULES)}

    # Only include modules that actually ran (keeps report clean)
    included: set[str] = {m for m in requested if _module_ran(m)}

    # If nothing ran, fall back to leave title but show a clean "no data" report.
    report_title: str = _build_report_title(included or requested)

    # Load data only if relevant
    findings = load_findings() if MODULE_LEAVE in included else []
    sorted_findings = sort_findings(findings) if findings else []
    rkeg_counts = load_rkeg_severity_counts() if MODULE_RKEG in included else {}

    if review_period is None:
        review_period = _derive_exec_review_period(included)

    parts: List[str] = []
    parts.append(build_header(report_title, organisation_name, review_period))

    structure = ReportStructure()

    # --- Section 1: Executive Summary (level 1) ---
    def exec_summary_content() -> str:
        return build_executive_summary(
            included_modules=included,
            leave_findings=sorted_findings,
            rkeg_counts=rkeg_counts,
            term_counts=load_term_severity_counts() if MODULE_TERM in included else {},
            lsl_counts=load_lsl_severity_counts() if MODULE_LSL in included else {},
        )

    structure.add("Executive Summary", 1, exec_summary_content)
    structure.add("Data Sources", 1, lambda: build_data_sources_section(included))
    structure.add("Scope & Methodology", 1, lambda: build_scope_and_methodology(included))

    # ---------------- Module Summary Overview (Exec report) ----------------
    summary_modules = {MODULE_LEAVE, MODULE_LSL, MODULE_TERM, MODULE_RKEG}

    if any(m in included for m in summary_modules):
        structure.add("Module Summary Overview", 1, lambda: "")

        if MODULE_LEAVE in included:
            structure.add(
                "Leave & Entitlement Leakage (LEAVE) – Summary Overview",
                2,
                lambda: build_key_findings_overview(sorted_findings),
            )

        if MODULE_LSL in included:
            structure.add(
                "Long Service Leave (LSL) Exposure – Severity Overview",
                2,
                lambda: build_lsl_severity_summary(),
            )

        if MODULE_TERM in included:
            structure.add(
                "Termination Exposure – Severity Overview",
                2,
                lambda: build_term_severity_summary(),
            )

        if MODULE_RKEG in included:
            structure.add(
                "Record-Keeping & Evidence Gaps (RKEG) – Severity Overview",
                2,
                lambda: build_rkeg_summary(rkeg_counts),
            )

        if any(m in included for m in {MODULE_LEAVE, MODULE_LSL, MODULE_TERM, MODULE_RKEG}):
            structure.add(
                "How to interpret findings",
                2,
                lambda: build_interpretation_block_exec(included),
            )

    # No detailed leave sections here anymore – those now live in leave_report_md.py

    structure.add("Limitations & Assumptions", 1, lambda: build_limitations())
    structure.add("Recommended Next Steps", 1, lambda: build_next_steps())
    structure.add("Appendices", 1, lambda: build_appendices(included_modules=included))

    parts.append(structure.render_markdown())
    final_md = "\n".join(parts)

    scan_result = scan_report_text(final_md)

    if scan_result["hard"]:
        print("⚠ HARD forbidden terms detected in report:")
        print(sorted(set(scan_result["hard"])))

    if scan_result["soft"]:
        print("ℹ Soft-flag terms detected in report:")
        print(sorted(set(scan_result["soft"])))

    EXEC_PACK_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXEC_PACK_MD_PATH.write_text(final_md, encoding="utf-8")
    return EXEC_PACK_MD_PATH


if __name__ == "__main__":
    path = generate_leave_leakage_report(modules=["TERM"])
    print(f"Generated at: {path}")