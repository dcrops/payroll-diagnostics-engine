from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Dict, Optional

from reporting.structure import ReportStructure
from reporting.exec_pack_md import (
    MODULE_LEAVE,
    LEAVE_FINDINGS_CSV,
    LEAKAGE_REPORT_CSV,
    OUTPUTS_DIR,
    sort_findings,
    build_header,
    build_data_sources_section,
    build_scope_and_methodology,
    build_key_findings_overview,
    build_limitations,
    build_next_steps,
    build_appendices,
)

# Where this leave-only module report will be written
LEAVE_REPORT_MD_PATH = OUTPUTS_DIR / "leave_report.md"


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


# ---------- Section builders specific to the LEAVE module report ----------

def build_leave_module_summary(
    findings: List[Finding],
    exposure_rows: List[ExposureRow],
) -> str:
    """
    Top-level Executive Summary for the leave-only module report.

    Reuses the existing severity overview + exposure section to keep things consistent
    with the exec pack, but written as a module-focused summary.
    """
    parts: List[str] = []

    # High-level narrative
    parts.append(
        "This Leave & Entitlement Leakage report focuses solely on leave-related risk "
        "indicators identified from the supplied payroll and HR data. "
        "Findings are risk indicators only and do not, on their own, confirm underpayment, "
        "non-compliance, or an entitlement error."
    )
    parts.append("")

    # Severity snapshot (reuses shared helper)
    parts.append(build_key_findings_overview(findings))

    # Exposure (indicative)
    parts.append(build_financial_exposure_section(exposure_rows))

    return "\n".join(parts).strip()


def build_leave_appendices() -> str:
    """
    Thin wrapper so the leave module report can reuse the shared appendices logic,
    scoped to LEAVE only.
    """
    return build_appendices({MODULE_LEAVE})


# ---------- Main generator ----------

def generate_leave_report(
    organisation_name: str = "Organisation not specified",
    review_period: str | None = None,
) -> Path:
    """
    Generate outputs/leave_report.md – a LEAVE-only, detailed module report.
    """
    included = {MODULE_LEAVE}  # this is a LEAVE-only report

    findings = load_findings()
    sorted_findings = sort_findings(findings) if findings else []
    exposure_rows = load_exposure_rows()

    if review_period is None:
        review_period = _derive_review_period(sorted_findings) if sorted_findings else "Period not specified"

    parts: List[str] = []
    parts.append(
        build_header(
            "Leave & Entitlement Leakage – Detailed Report",
            organisation_name,
            review_period,
        )
    )

    structure = ReportStructure()
    structure.add("Executive Summary", 1, lambda: build_leave_module_summary(sorted_findings, exposure_rows))
    structure.add("Data Sources", 1, lambda: build_data_sources_section({MODULE_LEAVE}))
    structure.add("Scope & Methodology", 1, lambda: build_scope_and_methodology({MODULE_LEAVE}))
    structure.add("Findings Overview", 1, lambda: build_key_findings_overview(sorted_findings))
    structure.add("Detailed Findings", 1, lambda: build_detailed_findings(sorted_findings))
    structure.add("Financial Exposure (Indicative)", 1, lambda: build_financial_exposure_section(exposure_rows))
    structure.add("Limitations & Assumptions", 1, lambda: build_limitations())
    structure.add("Recommended Next Steps", 1, lambda: build_next_steps())
    structure.add("Appendices", 1, lambda: build_leave_appendices())

    parts.append(structure.render_markdown())
    final_md = "\n".join(parts)

    LEAVE_REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEAVE_REPORT_MD_PATH.write_text(final_md, encoding="utf-8")
    return LEAVE_REPORT_MD_PATH


# ---------- Detailed findings + exposure sections ----------

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
        "Each leave finding below follows a consistent **Finding → Evidence → Impact → Recommended Action** pattern."
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
        lines.append("- Validate this finding against source payroll records and employee entitlements.")
        lines.append("- Correct any confirmed configuration, data or process issues.")
        lines.append("- Consider remediation where underpayments are confirmed.")
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