from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from reporting.core.structure import ReportStructure
from reporting.executive.exec_pack_md import (
    MODULE_TERM,
    TERM_FINDINGS_CSV,
    OUTPUTS_DIR,
    sort_findings,
    build_header,
    build_data_sources_section,
    build_scope_and_methodology,
    build_limitations,
    build_next_steps,
    build_appendices,
    build_term_severity_summary,
)

# Where this Termination Exposure module report will be written
TERM_REPORT_MD_PATH = OUTPUTS_DIR / "term_report.md"


# ---------- Data model ----------

@dataclass
class TerminationFinding:
    rule_code: str
    severity: str
    employee_id: str
    termination_date: str
    final_pay_date: str
    message: str
    evidence: str | None = None
    days_gap: str | None = None

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> "TerminationFinding":
        """
        Map a TERM findings CSV row into a TerminationFinding.

        Column names are taken from the current TERM module output
        (see appendices in exec_pack_md). This is defensive against
        small header variations.
        """
        return cls(
            rule_code=row.get("rule_code") or row.get("rule_id") or "",
            severity=(row.get("severity", "") or "").upper(),
            employee_id=row.get("employee_id", "") or row.get("employee", "") or "",
            termination_date=row.get("termination_date", "") or row.get("term_date", "") or "",
            final_pay_date=row.get("final_pay_date", "") or row.get("pay_date", "") or "",
            message=row.get("message") or row.get("description") or "",
            evidence=row.get("evidence") or row.get("evidence_ref") or row.get("artefact") or None,
            days_gap=row.get("days_gap") or row.get("gap_days") or None,
        )


# ---------- CSV helpers ----------

def _load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    import csv  # local import to avoid unnecessary top-level dependency

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_term_findings() -> List[TerminationFinding]:
    rows = _load_csv(TERM_FINDINGS_CSV)
    return [TerminationFinding.from_row(r) for r in rows]


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


def _derive_review_period(findings: List[TerminationFinding]) -> str:
    """
    Derive a human-readable review period from termination-related dates.

    Prefers termination_date; falls back to final_pay_date where necessary.
    """
    dates: List[date] = []

    for f in findings:
        d = _parse_iso_date(f.termination_date) or _parse_iso_date(f.final_pay_date)
        if d is not None:
            dates.append(d)

    if not dates:
        return "Review period not clearly identifiable from supplied data"

    start = min(dates)
    end = max(dates)

    if start == end:
        return start.strftime("%d %b %Y")

    return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"


# ---------- Section builders specific to the TERM module report ----------

def build_term_module_summary(findings: List[TerminationFinding]) -> str:
    """
    Top-level Executive Summary for the Termination Exposure module report.

    Provides narrative plus a concise severity snapshot. The full severity
    table is presented in the Findings Overview section.
    """
    parts: List[str] = []

    parts.append(
        "This Termination Exposure report focuses solely on termination-related evidential "
        "risk indicators identified from the supplied payroll and HR data. "
        "The review assesses how complete, timely and traceable termination records appear "
        "for audit and dispute purposes. It does **not** determine whether termination "
        "payments are correct under applicable awards, agreements or contracts."
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


def build_detailed_findings(findings: List[TerminationFinding]) -> str:
    if not findings:
        return """No termination-related findings were identified for the supplied data.

---

"""

    lines: List[str] = []

    lines.append(
        "This section sets out detailed findings for **Termination Exposure** only. "
        "Findings highlight where termination records may be incomplete, inconsistent or "
        "difficult to substantiate if reviewed by auditors, regulators or in the context "
        "of a dispute. They do **not** confirm incorrect pay outcomes."
    )
    lines.append("")
    lines.append(
        "Each finding below follows a consistent **Finding → Evidence → Impact → "
        "Recommended Action** pattern."
    )
    lines.append("")

    for idx, f in enumerate(findings, start=1):
        lines.append(f"### Finding {idx}: {f.rule_code or 'UNSPECIFIED RULE'}")
        lines.append(f"**Severity:** {f.severity or 'UNSPECIFIED'}")
        lines.append("")

        # Finding
        lines.append("**Finding**")
        lines.append(f"{f.message or 'No description provided.'}")
        lines.append("")

        # Evidence
        lines.append("**Evidence**")
        lines.append("")

        evidence_bits: List[str] = []
        if f.employee_id:
            evidence_bits.append(f"Employee ID: `{f.employee_id}`")
        if f.termination_date:
            evidence_bits.append(f"Termination date: `{f.termination_date}`")
        if f.final_pay_date:
            evidence_bits.append(f"Final pay date: `{f.final_pay_date}`")
        if f.days_gap:
            evidence_bits.append(f"Days between termination and final pay: `{f.days_gap}`")
        if f.evidence:
            evidence_bits.append(f"Evidence reference: `{f.evidence}`")

        if evidence_bits:
            lines.append("- " + "\n- ".join(evidence_bits))
        else:
            lines.append("- Not specified in the source data.")
        lines.append("")

        # Impact / Risk
        lines.append("**Impact / Risk**")
        lines.append(
            "Increased evidential and audit risk in relation to termination processing. "
            "Weak or inconsistent records can increase the effort required to explain "
            "termination decisions and may reduce the organisation’s ability to respond "
            "confidently if challenged."
        )
        lines.append("")

        # Recommended Action
        lines.append("**Recommended Action**")
        lines.append("")
        lines.append("- Validate this finding against underlying payroll and HR records.")
        lines.append("- Confirm that termination dates and final pay dates are correctly recorded.")
        lines.append(
            "- Strengthen documentation and evidence capture for termination decisions, "
            "including approval records and artefact references."
        )
        lines.append("- Where process weaknesses are confirmed, update procedures and training.")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_term_appendices() -> str:
    """
    Thin wrapper so the TERM module report can reuse the shared appendices logic,
    scoped to TERM only.
    """
    return build_appendices({MODULE_TERM})


# ---------- Main generator ----------

def generate_term_report(
    organisation_name: str = "Organisation not specified",
    review_period: str | None = None,
) -> Path:
    """
    Generate outputs/term_report.md – a Termination Exposure-only detailed module report.
    """
    included = {MODULE_TERM}  # this is a TERM-only report

    findings = load_term_findings()
    sorted_findings = sort_findings(findings) if findings else []

    if review_period is None:
        review_period = _derive_review_period(sorted_findings) if sorted_findings else "Period not specified"

    parts: List[str] = []
    parts.append(
        build_header(
            "Termination Exposure – Detailed Report",
            organisation_name,
            review_period,
        )
    )

    structure = ReportStructure()
    structure.add("Executive Summary", 1, lambda: build_term_module_summary(sorted_findings))
    structure.add("Data Sources", 1, lambda: build_data_sources_section({MODULE_TERM}))
    structure.add("Scope & Methodology", 1, lambda: build_scope_and_methodology({MODULE_TERM}))
    structure.add("Findings Overview", 1, lambda: build_term_severity_summary())
    structure.add("Detailed Findings", 1, lambda: build_detailed_findings(sorted_findings))
    structure.add("Limitations & Assumptions", 1, lambda: build_limitations())
    structure.add("Recommended Next Steps", 1, lambda: build_next_steps())
    structure.add("Appendices", 1, lambda: build_term_appendices())

    parts.append(structure.render_markdown())
    final_md = "\n".join(parts)

    TERM_REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    TERM_REPORT_MD_PATH.write_text(final_md, encoding="utf-8")
    return TERM_REPORT_MD_PATH


if __name__ == "__main__":
    path = generate_term_report()
    print(f"Generated TERM detailed report at: {path}")