from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, List, Optional

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
report_date = datetime.now(MELBOURNE_TZ).strftime("%d %b %Y")


# ---------- Paths ----------

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = BASE_DIR / "outputs"
MODULES_DIR = OUTPUTS_DIR / "modules"

LSL_FINDINGS_CSV = MODULES_DIR / "lsl_findings.csv"
LSL_EXPOSURE_CSV = OUTPUTS_DIR / "lsl_exposure_report.csv"
LSL_REPORT_MD_PATH = OUTPUTS_DIR / "lsl_report.md"


# ---------- Data models ----------

@dataclass
class LSLFinding:
    rule_code: str
    severity: str
    employee_id: str
    message: str

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> "LSLFinding":
        return cls(
            rule_code=row.get("rule_code") or row.get("rule_id") or "",
            severity=(row.get("severity") or "").upper(),
            employee_id=row.get("employee_id", ""),
            message=row.get("message") or row.get("description") or "",
        )


@dataclass
class LSLExposureRow:
    label: str
    amount: float

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> Optional["LSLExposureRow"]:
        label = row.get("label") or row.get("bucket") or row.get("rule_code") or ""
        amount_field_candidates = [
            "estimated_exposure",
            "exposure_amount",
            "lsl_liability",
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

def _load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)

def _derive_review_period_from_data(paths: list[Path]) -> str:
    """
    Try to derive a review period (min → max date) from one or more CSV files.

    We look for columns whose names contain 'date' and try common date formats.
    If we can't find anything usable, we fall back to 'Report prepared as at ...'.
    """
    all_dates: list[date] = []

    for path in paths:
        if not path.exists():
            continue

        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for col, raw in row.items():
                    if not col or "date" not in col.lower():
                        continue
                    value = (raw or "").strip()
                    if not value:
                        continue

                    # Try a few common formats
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                        try:
                            d = datetime.strptime(value, fmt).date()
                            all_dates.append(d)
                            break
                        except ValueError:
                            continue

    if all_dates:
        start = min(all_dates)
        end = max(all_dates)
        return f"{start:%d %b %Y} to {end:%d %b %Y}"

    # Fallback if no dates found
    return f"Report prepared as at {date.today():%d %b %Y}"

def load_lsl_findings() -> List[LSLFinding]:
    rows = _load_csv(LSL_FINDINGS_CSV)
    return [LSLFinding.from_row(r) for r in rows]


def dedupe_lsl_findings(findings: List[LSLFinding]) -> List[LSLFinding]:
    """
    Remove Medium 'LSL_BALANCE_SUSPICIOUSLY_LOW' findings where the same employee
    already has a High 'LSL_ZERO_BALANCE_FOR_LONG_TENURE' finding.

    This keeps the clearer, higher-severity message and avoids noisy duplication.
    """
    employees_with_high_zero = {
        f.employee_id
        for f in findings
        if f.rule_code == "LSL_ZERO_BALANCE_FOR_LONG_TENURE" and f.severity == "HIGH"
    }

    deduped: List[LSLFinding] = []
    for f in findings:
        if (
            f.employee_id in employees_with_high_zero
            and f.rule_code == "LSL_BALANCE_SUSPICIOUSLY_LOW"
            and f.severity == "MEDIUM"
        ):
            # Skip this one – it's effectively covered by the High finding
            continue
        deduped.append(f)

    return deduped


def sort_lsl_findings(findings: List[LSLFinding]) -> List[LSLFinding]:
    """
    Sort findings by severity (HIGH → MEDIUM → LOW), then rule_code, then employee_id.
    """
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(
        findings,
        key=lambda f: (
            severity_rank.get(f.severity, 99),
            f.rule_code or "",
            f.employee_id or "",
        ),
    )


def load_lsl_exposure_rows() -> List[LSLExposureRow]:
    rows = _load_csv(LSL_EXPOSURE_CSV)
    exposure_rows: List[LSLExposureRow] = []
    for r in rows:
        er = LSLExposureRow.from_row(r)
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


def _collect_dates_from_csv(path: Path, field_names: List[str]) -> List[date]:
    """
    Collect all valid dates from a CSV for the given list of candidate date fields.
    """
    rows = _load_csv(path)
    dates: List[date] = []
    for r in rows:
        for field in field_names:
            if field in r and r[field]:
                d = _parse_iso_date(r[field])
                if d is not None:
                    dates.append(d)
    return dates


def _derive_lsl_review_period() -> str:
    """
    Derive a human-readable review period for the LSL report by scanning
    the LSL findings and exposure CSVs for common date fields.
    """
    dates: List[date] = []

    # Typical candidates; harmless to include extras if absent
    dates += _collect_dates_from_csv(LSL_FINDINGS_CSV, ["as_of_date", "snapshot_date", "period_start", "period_end"])
    dates += _collect_dates_from_csv(LSL_EXPOSURE_CSV, ["as_of_date", "snapshot_date", "period_start", "period_end"])

    if not dates:
        return "Period not specified"

    start = min(dates)
    end = max(dates)

    if start == end:
        return start.strftime("%d %b %Y")

    return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"


# ---------- Markdown section builders ----------

def build_lsl_header(organisation_name: str, review_period: str) -> str:
    return f"""# Long Service Leave (LSL) Exposure Review

**Organisation:** {organisation_name}  
**Review period:** {review_period}  
**Report prepared as at:** {report_date}  

> This review provides an indicative view of Long Service Leave (LSL) exposure based on the data provided. It highlights potential areas of risk and imbalance but does not constitute legal, accounting or industrial relations advice.

---
"""


def build_lsl_executive_summary(findings: List[LSLFinding]) -> str:
    total_findings = len(findings)
    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    distinct_employees = len({f.employee_id for f in findings if f.employee_id})

    paragraph = (
        f"This review analysed Long Service Leave balances and related employee data to "
        f"identify potential areas of exposure and imbalance. A total of {total_findings} "
        f"potential issues were identified across approximately {distinct_employees} employees. "
        "These findings range from likely LSL under- or over-provisioning risk through to "
        "data and configuration issues that may affect the reliability of reported LSL liabilities."
    )

    return f"""## 1. Executive Summary

{paragraph}

**Summary of findings**

- **High:** {high}
- **Medium:** {med}
- **Low:** {low}

A detailed breakdown by severity is provided in the **Key Findings Overview** section.

---
"""

def build_lsl_data_sources_section() -> str:
    lines: list[str] = [
        "## 2. Data sources",
        "",
        "This review is based on the following data extracts (relative to the `outputs/` folder):",
        "",
        f"- `modules/{LSL_FINDINGS_CSV.name}` – rule-based LSL findings",
    ]

    if LSL_EXPOSURE_CSV.exists():
        lines.append(
            f"- `{LSL_EXPOSURE_CSV.name}` – indicative LSL exposure by rule or bucket"
        )

    lines += [
        "",
        "> These files are generated by the Long Service Leave exposure tool as part of the batch run.",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def build_lsl_scope_and_methodology() -> str:
    return """## 3. Scope & Methodology

**Data reviewed**

- LSL balance records
- Employee service dates and employment status
- Other LSL-related data supplied by the organisation

**Checks performed**

- Rule-based checks over LSL balances and service history
- Identification of unusual or inconsistent LSL balances
- Flags for employees with long service and low or zero LSL balances
- Checks for negative or unusually high LSL balances

**Out of scope**

- Interpretation of awards, enterprise agreements or contracts
- Detailed accounting treatment of LSL under relevant standards
- Validation of external actuarial or provisioning calculations

---
"""


def build_lsl_key_findings_overview(findings: List[LSLFinding]) -> str:
    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    # Build per-rule summary (counts + severity mix)
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
            "This table summarises how many findings were raised for each rule and the mix of severities."
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

    return f"""## 4. Key Findings Overview

The automated checks identified the following potential issues in LSL balances and related data:

| Severity | Count | Description |
|---------|-------|-------------|
| <span class="badge-high">High</span>    | {high}   | Likely LSL exposure or provision risk |
| <span class="badge-medium">Medium</span>  | {med}   | Material inconsistency or configuration issue |
| <span class="badge-low">Low</span>     | {low}   | Data quality or minor process issue |

{rule_summary}

---
"""


def build_lsl_detailed_findings(findings: List[LSLFinding]) -> str:
    if not findings:
        return """## 5. Detailed Findings

No LSL-related findings were identified for the supplied data.

---
"""

    lines: List[str] = ["## 5. Detailed Findings", ""]
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
        lines.append("")  # ensure bullets render as a proper list

        evidence_bits: List[str] = []
        if f.employee_id:
            evidence_bits.append(f"Employee ID: `{f.employee_id}`")

        if evidence_bits:
            for bit in evidence_bits:
                lines.append(f"- {bit}")
        else:
            lines.append("- Not specified in the source data.")

        lines.append("")
        lines.append("**Impact / Risk**")
        lines.append(
            "Potential misstatement of Long Service Leave entitlements or provisions. "
            "Depending on the nature of the issue, this may result in incorrect LSL balances for individual employees, "
            "and potentially an understatement or overstatement of overall LSL exposure."
        )
        lines.append("")
        lines.append("**Recommended Action**")
        lines.append("")  # blank line so the list renders properly

        lines.append(
            "- Review the underlying LSL balance, service history and entitlement settings for the affected employee(s)."
        )
        lines.append(
            "- Confirm whether the balance aligns with applicable legislation, awards or agreements."
        )
        lines.append(
            "- Correct any confirmed configuration or data issues and assess whether broader remediation is required."
        )

        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_lsl_exposure_section(exposure_rows: List[LSLExposureRow]) -> str:
    if not exposure_rows:
        return """## 6. Financial Exposure (Indicative)

No LSL exposure estimates were available from the current data extract. If required, aggregated LSL exposure figures can be added to this section in future runs.

---
"""

    total = sum(r.amount for r in exposure_rows)
    lines = [
        "## 6. Financial Exposure (Indicative)",
        "",
        f"- Number of exposure rows: {len(exposure_rows)}",
        f"- Indicative total LSL exposure (all categories): {total:,.2f}",
        "",
        "> These figures are indicative only and rely on the provided data and simplifying assumptions. "
        "They do not replace formal actuarial or accounting assessments.",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def build_lsl_limitations() -> str:
    return """## 7. Limitations & Assumptions

This review is subject to the following limitations:

- Calculations assume that LSL balances and service dates are correctly recorded in the source systems.
- The review does not interpret awards, enterprise agreements or employment contracts, and does not provide accounting advice.
- Findings are generated using automated, rule-based checks and may require contextual validation.
- Data quality issues such as missing start dates, inconsistent identifiers or historical changes in conditions may affect the completeness or accuracy of results.

This report is intended to support internal review and prioritisation and should be used in conjunction with professional payroll, legal, accounting or industrial relations advice where required.

---
"""


def build_lsl_next_steps() -> str:
    return """## 8. Recommended Next Steps

1. Prioritise review of **High** severity findings affecting LSL balances or exposure.
2. Validate affected employee records, including service history and entitlement calculations.
3. Correct any identified configuration or data issues in payroll and HR systems.
4. Engage internal or external advisors where significant LSL exposure or provision changes are indicated.
5. Re-run the review after corrections to confirm that LSL exposure has been addressed.

---
"""


def build_lsl_appendices() -> str:
    return """## 9. Appendices

### Appendix A – Rule Definitions

This review used a set of automated rules to flag potential LSL exposure and imbalance. Examples include:

- Employees with long service and low or zero LSL balances
- Negative or unusually large LSL balances
- Inconsistent LSL balances relative to service history

(The exact rules can be expanded over time to match your LSL rule definitions.)

---

### Appendix B – Data Fields Used

Key fields used in this analysis include:

- `employee_id`
- `lsl_balance`
- `service_start_date`
- `employment_status`
- Any additional LSL-related fields present in the supplied data.

(Additional fields from the supplied CSV files may also be used.)

---

### Appendix C – Full Findings Table

A complete machine-readable version of the LSL findings is available in:

- `outputs/modules/lsl_findings.csv`
- `outputs/lsl_exposure_report.csv` (if present)
"""


def generate_lsl_exposure_report(
    organisation_name: str = "Organisation not specified",
    review_period: Optional[str] = None,
) -> Path:
    """Generate outputs/lsl_report.md for the LSL Exposure Review."""
    raw_findings = load_lsl_findings()
    # deduped_findings = dedupe_lsl_findings(raw_findings)
    # findings = sort_lsl_findings(deduped_findings)
    findings = sort_lsl_findings(raw_findings)
    exposure_rows = load_lsl_exposure_rows()

    # If not explicitly supplied, derive review period from the data
    if review_period is None:
        review_period = _derive_review_period_from_data(
            [LSL_FINDINGS_CSV, LSL_EXPOSURE_CSV]
        )

    parts = [
        build_lsl_header(organisation_name, review_period),
        build_lsl_executive_summary(findings),
        build_lsl_data_sources_section(),
        build_lsl_scope_and_methodology(),
        build_lsl_key_findings_overview(findings),
        build_lsl_detailed_findings(findings),
        build_lsl_exposure_section(exposure_rows),
        build_lsl_limitations(),
        build_lsl_next_steps(),
        build_lsl_appendices(),
    ]

    LSL_REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    LSL_REPORT_MD_PATH.write_text("\n".join(parts), encoding="utf-8")
    return LSL_REPORT_MD_PATH



if __name__ == "__main__":
    path = generate_lsl_exposure_report()
    print(f"Generated LSL Markdown report at {path}")
