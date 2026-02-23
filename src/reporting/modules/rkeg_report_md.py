from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from reporting.structure import ReportStructure
from reporting.exec_pack_md import (
    MODULE_RKEG,
    RKEG_FINDINGS_CSV,
    OUTPUTS_DIR,
    sort_findings,
    build_header,
    build_data_sources_section,
    build_scope_and_methodology,
    build_limitations,
    build_next_steps,
    build_appendices,
    load_rkeg_severity_counts,
    build_rkeg_summary,
)

# Where this RKEG-only module report will be written
RKEG_REPORT_MD_PATH = OUTPUTS_DIR / "rkeg_report.md"


# ---------- Data model ----------

@dataclass
class RKEGFinding:
    rule_code: str
    severity: str
    employee_id: str
    leave_type: str
    as_of_date: str
    message: str
    evidence: Optional[str] = None
    finding_id: Optional[str] = None
    next_action: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> "RKEGFinding":
        """
        Map an RKEG findings CSV row into an RKEGFinding.

        Column names are aligned with the RKEG appendices in exec_pack_md, but
        this is defensive against minor header variations.
        """
        return cls(
            rule_code=row.get("rule_code") or row.get("rule_id") or "",
            severity=(row.get("severity", "") or "").upper(),
            employee_id=row.get("employee_id", "") or row.get("employee", "") or "",
            leave_type=row.get("leave_type", "") or row.get("record_type", "") or "",
            as_of_date=row.get("as_of_date", "") or row.get("snapshot_date", "") or "",
            message=row.get("message") or row.get("description") or "",
            evidence=row.get("evidence") or row.get("evidence_ref") or None,
            finding_id=row.get("finding_id") or None,
            next_action=row.get("next_action") or None,
        )


# ---------- CSV helpers ----------

def _load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    import csv  # local import to keep top-level light

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_rkeg_findings() -> List[RKEGFinding]:
    rows = _load_csv(RKEG_FINDINGS_CSV)
    return [RKEGFinding.from_row(r) for r in rows]


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


def _derive_review_period(findings: List[RKEGFinding]) -> str:
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


# ---------- Section builders specific to the RKEG module report ----------

def build_rkeg_module_summary(findings: List[RKEGFinding]) -> str:
    """
    Top-level Executive Summary for the RKEG module report.

    Provides narrative plus a concise severity snapshot. The full severity
    table is presented in the Findings Overview section.
    """
    parts: List[str] = []

    parts.append(
        "This Record-Keeping & Evidence Gaps (RKEG) report focuses solely on evidential "
        "risk indicators identified from the supplied payroll and HR data. "
        "The review assesses how complete, consistent and traceable payroll-related records "
        "appear for audit and dispute purposes. It does **not** determine whether payroll "
        "outcomes are correct or incorrect under applicable legislation, awards or agreements."
    )
    parts.append("")

    # Headline severity counts (table lives in Findings Overview)
    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    parts.append("Across the dataset provided, the automated checks identified:")
    parts.append("")
    parts.append(f"- **High:** {high}")
    parts.append(f"- **Medium:** {med}")
    parts.append(f"- **Low:** {low}")
    parts.append("")
    parts.append(
        "A detailed breakdown by severity is provided in the "
        "**Findings Overview** section."
    )

    return "\n".join(parts).strip()


def build_rkeg_findings_overview() -> str:
    """
    Use the existing RKEG severity summary helper from the exec pack so the
    table and wording stay consistent across reports.
    """
    counts = load_rkeg_severity_counts()
    return build_rkeg_summary(counts)


def build_detailed_findings(findings: List[RKEGFinding]) -> str:
    if not findings:
        return """No record-keeping or evidence gaps were identified for the supplied data.

---

"""

    lines: List[str] = []

    lines.append(
        "This section sets out detailed findings for **Record-Keeping & Evidence Gaps (RKEG)** only. "
        "Findings highlight where payroll-related records may be incomplete, inconsistent or difficult "
        "to substantiate if reviewed by auditors, regulators or in the context of a dispute. "
        "They do **not** confirm incorrect pay outcomes."
    )
    lines.append("")
    lines.append(
        "Each finding below follows a consistent **Finding → Evidence → Impact / Risk → Recommended Action** pattern."
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

        evidence_bits: List[str] = []
        if f.employee_id:
            evidence_bits.append(f"Employee ID: `{f.employee_id}`")
        if f.leave_type:
            evidence_bits.append(f"Record type: `{f.leave_type}`")
        if f.as_of_date:
            evidence_bits.append(f"As at: `{f.as_of_date}`")
        if f.evidence:
            evidence_bits.append(f"Evidence reference: `{f.evidence}`")
        if f.finding_id:
            evidence_bits.append(f"Finding ID: `{f.finding_id}`")
        if f.next_action:
            evidence_bits.append(f"Suggested next action (from data): `{f.next_action}`")

        if evidence_bits:
            lines.append("- " + "\n- ".join(evidence_bits))
        else:
            lines.append("- Not specified in the source data.")
        lines.append("")

        lines.append("**Impact / Risk**")
        lines.append(
            "Increased evidential and audit risk in relation to payroll records. "
            "Weak or incomplete records can increase the effort required to explain pay decisions "
            "and may reduce the organisation’s ability to respond confidently if challenged."
        )
        lines.append("")

        lines.append("**Recommended Action**")
        lines.append("")
        lines.append("- Validate this finding against underlying payroll, HR and source system records.")
        lines.append(
            "- Strengthen documentation and evidence capture for the affected record types "
            "(for example, by ensuring key identifiers and dates are consistently populated)."
        )
        lines.append(
            "- Where systemic patterns are identified, update data capture processes, templates "
            "and training to reduce recurrence."
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_rkeg_appendices() -> str:
    """
    Thin wrapper so the RKEG module report can reuse the shared appendices logic,
    scoped to RKEG only.
    """
    return build_appendices({MODULE_RKEG})


# ---------- Main generator ----------

def generate_rkeg_report(
    organisation_name: str = "Organisation not specified",
    review_period: str | None = None,
) -> Path:
    """
    Generate outputs/rkeg_report.md – a RKEG-only, detailed module report.
    """
    included = {MODULE_RKEG}  # this is an RKEG-only report

    findings = load_rkeg_findings()
    sorted_findings = sort_findings(findings) if findings else []

    if review_period is None:
        review_period = _derive_review_period(sorted_findings) if sorted_findings else "Period not specified"

    parts: List[str] = []
    parts.append(
        build_header(
            "Record-Keeping & Evidence Gaps (RKEG) – Detailed Report",
            organisation_name,
            review_period,
        )
    )

    structure = ReportStructure()
    structure.add("Executive Summary", 1, lambda: build_rkeg_module_summary(sorted_findings))
    structure.add("Data Sources", 1, lambda: build_data_sources_section({MODULE_RKEG}))
    structure.add("Scope & Methodology", 1, lambda: build_scope_and_methodology({MODULE_RKEG}))
    structure.add("Findings Overview", 1, lambda: build_rkeg_findings_overview())
    structure.add("Detailed Findings", 1, lambda: build_detailed_findings(sorted_findings))
    structure.add("Limitations & Assumptions", 1, lambda: build_limitations())
    structure.add("Recommended Next Steps", 1, lambda: build_next_steps())
    structure.add("Appendices", 1, lambda: build_rkeg_appendices())

    parts.append(structure.render_markdown())
    final_md = "\n".join(parts)

    RKEG_REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    RKEG_REPORT_MD_PATH.write_text(final_md, encoding="utf-8")
    return RKEG_REPORT_MD_PATH


if __name__ == "__main__":
    path = generate_rkeg_report(organisation_name="Example Client Pty Ltd")
    print(f"Generated RKEG detailed report at: {path}")