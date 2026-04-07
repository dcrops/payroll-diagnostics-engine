from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Dict, Optional

import json
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from common.severity import SEVERITY_BY_CODE
from common.report_text import scan_report_text
from reporting.core.paths import get_repo_root, get_default_outputs_dir
from reporting.core.review_period import derive_review_period_from_windows
from reporting.core.structure import ReportStructure
from reporting.rkeg_text import build_rkeg_severity_overview_table


MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
report_date = datetime.now(MELBOURNE_TZ).strftime("%d %b %Y")

# ---------- Engagement scope ----------

MODULE_LEAVE = "LEAVE"
MODULE_RKEG = "RKEG"
MODULE_TERM = "TERM"
MODULE_LSL = "LSL"
MODULE_CROSS = "CROSS_MODULE"

MODULE_ORDER = [MODULE_LEAVE, MODULE_LSL, MODULE_TERM, MODULE_RKEG, MODULE_CROSS]

MODULE_LABELS = {
    MODULE_LEAVE: "Leave & Entitlement Leakage (LEAVE)",
    MODULE_LSL: "Long Service Leave Exposure (LSL)",
    MODULE_TERM: "Termination Exposure (TERM)",
    MODULE_RKEG: "Record-Keeping & Evidence Gaps (RKEG)",
    MODULE_CROSS: "Cross-Module Integrity (CROSS_MODULE)",
}

DEFAULT_MODULES = [MODULE_LEAVE, MODULE_LSL, MODULE_TERM, MODULE_RKEG, MODULE_CROSS]

# ---------- Paths ----------

BASE_DIR = get_repo_root()
OUTPUTS_DIR = get_default_outputs_dir()

LEAVE_FINDINGS_CSV = OUTPUTS_DIR / "leave_leakage_findings.csv"
LEAKAGE_REPORT_CSV = OUTPUTS_DIR / "leakage_report.csv"

RKEG_SUMMARY_BY_SEVERITY_CSV = OUTPUTS_DIR / "rkeg_summary_by_severity.csv"
RKEG_FINDINGS_CSV = OUTPUTS_DIR / "rkeg_findings.csv"

TERM_SUMMARY_BY_SEVERITY_CSV = OUTPUTS_DIR / "term_summary_by_severity.csv"
TERM_FINDINGS_CSV = OUTPUTS_DIR / "term_findings.csv"

LSL_FINDINGS_CSV = OUTPUTS_DIR / "lsl_findings.csv"
LSL_SUMMARY_BY_SEVERITY_CSV = OUTPUTS_DIR / "lsl_summary_by_severity.csv"

LEAVE_DATA_WINDOW_CSV = OUTPUTS_DIR / "leave_data_window.csv"
LSL_DATA_WINDOW_CSV = OUTPUTS_DIR / "lsl_data_window.csv"
TERM_DATA_WINDOW_CSV = OUTPUTS_DIR / "term_data_window.csv"
RKEG_DATA_WINDOW_CSV = OUTPUTS_DIR / "rkeg_data_window.csv"

EXEC_PACK_MD_PATH = OUTPUTS_DIR / "crc_executive_pack.md"

# ---------- Data models ----------

@dataclass
class Finding:
    rule_code: str
    severity: str
    classification: str
    employee_id: str
    leave_type: str
    as_of_date: str
    message: str

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> "Finding":
        return cls(
            rule_code=row.get("rule_code") or row.get("rule_id") or "",
            severity=(row.get("severity", "") or "").upper(),
            classification=(row.get("classification", "") or "").upper(),
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

    import csv

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _load_csv(path: Path) -> List[Dict[str, str]]:
    return load_csv(path)


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
    dates: List[date] = []
    for f in findings:
        d = _parse_iso_date(f.as_of_date)
        if d is not None:
            dates.append(d)

    if not dates:
        return "Review period not clearly identifiable from supplied data"

    start = min(dates)
    end = max(dates)

    if start == end:
        return start.strftime("%d %b %Y")

    return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"


def _module_ran(module: str, base_output_dir: Path) -> bool:
    if module == MODULE_LEAVE:
        return (
            (base_output_dir / "leave_leakage_findings.csv").exists()
            or (base_output_dir / "leakage_report.csv").exists()
        )
    if module == MODULE_RKEG:
        return (
            (base_output_dir / "rkeg_summary_by_severity.csv").exists()
            or (base_output_dir / "rkeg_findings.csv").exists()
        )
    if module == MODULE_TERM:
        return (
            (base_output_dir / "term_summary_by_severity.csv").exists()
            or (base_output_dir / "term_findings.csv").exists()
        )
    if module == MODULE_LSL:
        return (
            (base_output_dir / "lsl_summary_by_severity.csv").exists()
            or (base_output_dir / "lsl_findings.csv").exists()
        )
    if module == MODULE_CROSS:
        return (
            (base_output_dir / "cross_module_findings.csv").exists()
            or (base_output_dir / "cross_module_summary.csv").exists()
        )
    return False


def _derive_exec_review_period(included_modules: set[str], base_output_dir: Path) -> str:
    modules_dir = base_output_dir

    candidate_paths = []

    if MODULE_LEAVE in included_modules:
        candidate_paths.append(modules_dir / "leave_leakage_findings.csv")
    if MODULE_LSL in included_modules:
        candidate_paths.append(modules_dir / "lsl_findings.csv")
    if MODULE_TERM in included_modules:
        candidate_paths.append(modules_dir / "term_findings.csv")
    if MODULE_RKEG in included_modules:
        candidate_paths.append(modules_dir / "rkeg_findings.csv")

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

                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        d = datetime.strptime(value, fmt).date()
                        all_dates.append(d)
                        break
                    except ValueError:
                        continue

    if not all_dates:
        return "Review period not clearly identifiable from supplied module outputs"

    start = min(all_dates)
    end = max(all_dates)

    if start == end:
        return start.strftime("%d %b %Y")

    return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"


def derive_exec_review_period_from_data(included_modules: set[str], base_output_dir: Path) -> str:
    modules_dir = base_output_dir

    window_paths: list[Path] = []

    if MODULE_LEAVE in included_modules:
        window_paths.append(modules_dir / "leave_data_window.csv")
    if MODULE_LSL in included_modules:
        window_paths.append(modules_dir / "lsl_data_window.csv")
    if MODULE_TERM in included_modules:
        window_paths.append(modules_dir / "term_data_window.csv")
    if MODULE_RKEG in included_modules:
        window_paths.append(modules_dir / "rkeg_data_window.csv")

    period_from_windows = derive_review_period_from_windows(
        window_paths,
        fallback=None,
    )

    if period_from_windows:
        return period_from_windows

    return _derive_exec_review_period(included_modules, base_output_dir)


# ---------- Module helpers ----------

def normalise_modules(included_modules: set[str] | list[str] | None) -> set[str]:
    return {m.strip().upper() for m in (included_modules or [])}


def included_modules_in_order(included_modules: set[str] | list[str] | None) -> list[str]:
    mods = normalise_modules(included_modules)
    return [m for m in MODULE_ORDER if m in mods]


def _friendly_module_label(module_code: str) -> str:
    labels = {
        "TERM": "Termination Exposure",
        "RKEG": "Record-Keeping & Evidence Gaps",
        "LEAVE": "Leave & Entitlement Leakage",
        "LSL": "Long Service Leave Exposure",
        "CROSS_MODULE": "Cross-Module Integrity",
    }
    return labels.get((module_code or "").upper(), module_code or "Unknown")


# ---------- Executive summary / risk profile ----------

def print_exec_pack_preflight(base_output_dir: Path, included_modules: set[str]) -> None:
    executive_md = base_output_dir / "executive" / "executive_summary.md"
    executive_json = base_output_dir / "executive" / "executive_summary.json"

    print("Exec Pack preflight:")
    print(f" - output_dir: {base_output_dir}")
    print(f" - executive_summary.md: {executive_md.exists()}")
    print(f" - executive_summary.json: {executive_json.exists()}")
    print(f" - included modules: {sorted(included_modules)}")

    modules_dir = base_output_dir
    for module in sorted(included_modules):
        if module == "LEAVE":
            print(f" - LEAVE findings: {(modules_dir / 'leave_leakage_findings.csv').exists()}")
        elif module == "LSL":
            print(f" - LSL findings: {(modules_dir / 'lsl_findings.csv').exists()}")
            print(f" - LSL severity summary: {(modules_dir / 'lsl_summary_by_severity.csv').exists()}")
        elif module == "TERM":
            print(f" - TERM findings: {(modules_dir / 'term_findings.csv').exists()}")
            print(f" - TERM severity summary: {(modules_dir / 'term_summary_by_severity.csv').exists()}")
        elif module == "RKEG":
            print(f" - RKEG findings: {(modules_dir / 'rkeg_findings.csv').exists()}")
            print(f" - RKEG severity summary: {(modules_dir / 'rkeg_summary_by_severity.csv').exists()}")

def load_executive_summary_md(base_output_dir: Path) -> str:
    path = base_output_dir / "executive" / "executive_summary.md"

    if not path.exists():
        print(f"⚠ Missing executive summary markdown: {path}")
        return (
            "_Executive summary not available for this run. "
            "Generate the executive summary layer before building the Exec Pack._"
        )

    text = path.read_text(encoding="utf-8").strip()

    lines = text.splitlines()

    # 🔥 Remove top-level header if present (prevents duplicate headings)
    if lines and lines[0].strip().startswith("#"):
        lines = lines[1:]

        # Also remove empty line after header if it exists
        if lines and not lines[0].strip():
            lines = lines[1:]

    return "\n".join(lines).strip()


def load_executive_summary_json(base_output_dir: Path) -> Dict:
    path = base_output_dir / "executive" / "executive_summary.json"
    if not path.exists():
        print(f"⚠ Missing executive summary JSON: {path}")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_executive_summary(base_output_dir: Path) -> str:
    return load_executive_summary_md(base_output_dir)

def build_highlight_insights(base_output_dir: Path) -> str:
    summary = load_executive_summary_json(base_output_dir)
    if not summary:
        return "_Highlight insights not available for this run._"

    total_findings = summary.get("total_findings", 0)
    dominant_classification = summary.get("dominant_classification", "Unknown")
    top_high_modules = summary.get("top_high_modules", [])
    severity_summary = summary.get("severity_summary", {})

    high_count = severity_summary.get("HIGH", 0)
    medium_count = severity_summary.get("MEDIUM", 0)

    narrative_labels = {
        "TERM": "termination handling",
        "RKEG": "record-keeping controls",
        "LEAVE": "leave calculation and balance integrity",
        "LSL": "long service leave eligibility and accrual",
        "CROSS_MODULE": "cross-module lifecycle consistency",
    }

    friendly_modules = [narrative_labels.get(m, m) for m in top_high_modules[:2]]

    if len(friendly_modules) >= 2:
        module_text = f"{friendly_modules[0]} and {friendly_modules[1]}"
    elif len(friendly_modules) == 1:
        module_text = friendly_modules[0]
    else:
        module_text = "the highest-severity areas identified"

    if total_findings > 0:
        high_pct = round((high_count / total_findings) * 100)
        medium_pct = round((medium_count / total_findings) * 100)

        severity_line = (
            f"- Findings are split between **high ({high_pct}%)** and **medium ({medium_pct}%) severity**, "
            "indicating a mix of immediate control concerns and broader process weaknesses."
        )
    else:
        severity_line = (
            "- Severity distribution could not be determined from the available results."
        )

    lines: List[str] = []
    lines.append("The following points summarise the most important observations from the analysis:")
    lines.append("")
    lines.append(f"- The strongest concentration of risk sits in **{module_text}**.")
    lines.append(
        f"- The overall profile is dominated by **{dominant_classification.lower()}** findings rather than primarily structural data issues."
    )
    lines.append(severity_line)
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)

def _fmt_count_pct(count: int, total: int) -> str:
    if not total:
        return str(count)
    pct = round((count / total) * 100)
    return f"{count} ({pct}%)"

def build_risk_profile_overview(base_output_dir: Path) -> str:
    summary = load_executive_summary_json(base_output_dir)
    if not summary:
        return "_Risk profile overview not available for this run._"

    total_findings = summary.get("total_findings", 0)
    class_summary = summary.get("class_summary", {})
    severity_summary = summary.get("severity_summary", {})
    dominant_classification = summary.get("dominant_classification", "Unknown")
    dominant_severity = summary.get("dominant_severity", "Unknown")
    top_high_modules = summary.get("top_high_modules", [])

    logical_count = class_summary.get("LOGICAL", 0)
    structural_count = class_summary.get("STRUCTURAL", 0)
    contextual_count = class_summary.get("CONTEXTUAL", 0)

    high_count = severity_summary.get("HIGH", 0)
    medium_count = severity_summary.get("MEDIUM", 0)
    low_count = severity_summary.get("LOW", 0)

    friendly_modules = [_friendly_module_label(m) for m in top_high_modules]
    module_text = (
        ", ".join(friendly_modules)
        if friendly_modules
        else "No dominant module concentration identified"
    )

    lines: List[str] = []
    lines.append(
        "This section summarises the overall risk profile across all included modules using the consolidated CRC summary outputs."
    )
    lines.append("")

    lines.append('<table class="summary-table">')
    lines.append("  <thead>")
    lines.append("    <tr><th>Metric</th><th>Value</th></tr>")
    lines.append("  </thead>")
    lines.append("  <tbody>")
    lines.append(f"    <tr><td>Total findings</td><td>{total_findings}</td></tr>")
    lines.append(f"    <tr><td>Dominant classification</td><td>{dominant_classification}</td></tr>")
    lines.append(f"    <tr><td>Dominant severity</td><td>{dominant_severity}</td></tr>")
    lines.append(f"    <tr><td>Logical findings</td><td>{_fmt_count_pct(logical_count, total_findings)}</td></tr>")
    lines.append(f"    <tr><td>Structural findings</td><td>{_fmt_count_pct(structural_count, total_findings)}</td></tr>")
    lines.append(f"    <tr><td>Contextual findings</td><td>{_fmt_count_pct(contextual_count, total_findings)}</td></tr>")
    lines.append(f"    <tr><td>High severity findings</td><td>{_fmt_count_pct(high_count, total_findings)}</td></tr>")
    lines.append(f"    <tr><td>Medium severity findings</td><td>{_fmt_count_pct(medium_count, total_findings)}</td></tr>")
    lines.append(f"    <tr><td>Low severity findings</td><td>{_fmt_count_pct(low_count, total_findings)}</td></tr>")
    lines.append("  </tbody>")
    lines.append("</table>")
    lines.append("")

    lines.append(f"**Highest concentration of high-severity findings:** {module_text}")
    lines.append("")
    lines.append(
        "Classification is used to distinguish between substantive integrity issues, structural data limitations, and contextual items requiring human judgement."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


# ---------- Severity loaders ----------

def load_rkeg_severity_counts(base_output_dir: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    modules_dir = base_output_dir

    summary_path = modules_dir / "rkeg_summary_by_severity.csv"
    findings_path = modules_dir / "rkeg_findings.csv"

    summary_rows = _load_csv(summary_path)
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

    finding_rows = _load_csv(findings_path)
    for r in finding_rows:
        sev = (r.get("severity") or r.get("Severity") or "").strip().upper()
        if sev in counts:
            counts[sev] += 1

    return counts


def load_lsl_severity_counts(base_output_dir: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    modules_dir = base_output_dir

    summary_path = modules_dir / "lsl_summary_by_severity.csv"
    findings_path = modules_dir / "lsl_findings.csv"

    summary_rows = _load_csv(summary_path)
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

    finding_rows = _load_csv(findings_path)
    for r in finding_rows:
        sev = (r.get("severity") or r.get("Severity") or "").strip().upper()
        if sev in counts:
            counts[sev] += 1

    return counts


def load_term_severity_counts(base_output_dir: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    modules_dir = base_output_dir

    summary_path = modules_dir / "term_summary_by_severity.csv"
    findings_path = modules_dir / "term_findings.csv"

    summary_rows = _load_csv(summary_path)
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

    finding_rows = _load_csv(findings_path)
    for r in finding_rows:
        sev = (r.get("severity") or r.get("Severity") or "").strip().upper()
        if sev in counts:
            counts[sev] += 1

    return counts

def load_cross_module_severity_counts(base_output_dir: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    summary_path = base_output_dir / "cross_module_summary_by_severity.csv"
    findings_path = base_output_dir / "cross_module_findings.csv"

    summary_rows = _load_csv(summary_path)
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

    finding_rows = _load_csv(findings_path)
    for r in finding_rows:
        sev = (r.get("severity") or r.get("Severity") or "").strip().upper()
        if sev in counts:
            counts[sev] += 1

    return counts


# ---------- Sorting ----------

def sort_findings(findings: List[Finding]) -> List[Finding]:
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

**Important note**

This report highlights potential risk signals and process issues based on the data provided. 
It does not constitute legal, accounting, or industrial relations advice.


---
"""


def _build_report_title(modules: set[str]) -> str:
    if modules == {MODULE_LSL}:
        return "Long Service Leave Exposure Review"
    if modules == {MODULE_TERM}:
        return "Termination Exposure Review"
    if modules == {MODULE_RKEG}:
        return "Record-Keeping & Evidence Gaps Review"
    if modules == {MODULE_LEAVE}:
        return "Leave & Entitlement Leakage Review"
    return "Payroll Risk & Evidence Review"


def build_interpretation_block_exec(included_modules: set[str]) -> str:
    mods = {m.strip().upper() for m in (included_modules or set())}

    lines: list[str] = []
    lines.append("**How to interpret findings across modules**")
    lines.append("")

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

    if MODULE_TERM in mods:
        lines.append(
            "- **Termination Exposure findings** relate to the completeness, sequencing and documentation of termination "
            "events and final pay. They indicate how readily the organisation could evidence termination processing if challenged."
        )

    if MODULE_RKEG in mods:
        lines.append(
            "- **Record-Keeping & Evidence Gaps (RKEG) findings** assess the strength of the evidentiary trail supporting "
            "payroll decisions. They do **not** indicate incorrect pay outcomes; they highlight where records may be incomplete "
            "or difficult to substantiate."
        )

    if MODULE_CROSS in mods:
        lines.append(
            "- **Cross-Module Integrity findings** highlight inconsistencies between related datasets, such as employee lifecycle status, "
            "leave activity, and payroll events. They indicate where linked records may not align cleanly across the broader payroll data environment."
        )

    lines.append("")
    lines.append(
        "Findings are risk indicators requiring validation and do not, on their own, confirm non-compliance, legislative contravention, or underpayment."
    )
    lines.append("")
    lines.append(
        "*Severity levels reflect evidential risk and control strength, and do not represent confirmed contraventions or quantified financial exposure.*"
    )

    return "\n".join(lines).strip()


def build_scope_and_methodology(included_modules: set[str] | list[str] | None) -> str:
    mods = normalise_modules(included_modules)
    subsection_no = 1
    ordered = included_modules_in_order(mods)

    lines: List[str] = []
    lines.append("**Modules included in this engagement:**")
    lines.append("")

    for m in ordered:
        lines.append(f"- {MODULE_LABELS[m]}")
    if not ordered:
        lines.append("- None specified")
    lines.append("")
    lines.append("---")
    lines.append("")

    if MODULE_LEAVE in mods:
        lines.append(f"### 5.{subsection_no} **Leave & Entitlement Leakage – Scope & Methodology**")
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
        lines.append("- consistency checks between employee status and leave activity (for example, terminated employees with ongoing leave movements)")
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
            "Where exposure estimates are included, they are indicative only and must be validated before remediation or accounting decisions are made."
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        subsection_no += 1

    if MODULE_LSL in mods:
        lines.append(f"### 5.{subsection_no} **Long Service Leave (LSL) Exposure – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Long Service Leave (LSL) Exposure review identifies risk indicators in LSL balance and service-related data that may warrant further validation. The purpose of this review is to highlight records that appear inconsistent, incomplete, or difficult to substantiate based on the data provided."
        )
        lines.append("")
        lines.append(
            "This review is designed to support payroll, HR and finance teams in prioritising follow-up effort. Findings are risk signals only and do not, on their own, confirm an entitlement error, underpayment, or non-compliance."
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
            "Where any exposure estimates or balance concerns are inferred, they are indicative only and must be validated before remediation or accounting decisions are made."
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        subsection_no += 1

    if MODULE_TERM in mods:
        lines.append(f"### 5.{subsection_no} **Termination Exposure – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Termination Exposure review assesses whether termination events recorded in payroll and related employment data are sufficiently complete, timely, and traceable to support the organisation’s ability to evidence termination-related payroll decisions if reviewed by auditors or regulators."
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
        subsection_no += 1

    if MODULE_RKEG in mods:
        lines.append(f"### 5.{subsection_no} **Record-Keeping & Evidence Gaps (RKEG) – Scope & Methodology**")
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
        lines.append("- identification of orphan or untraceable pay events (for example, pay events with missing or inconsistent identifiers)")
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
            "RKEG findings should be interpreted as evidential risk indicators. Addressing them improves defensibility and reduces audit effort, but does not necessarily imply a payroll outcome is incorrect."
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        subsection_no += 1

    if MODULE_CROSS in mods:
        lines.append(f"### 5.{subsection_no} **Cross-Module Integrity – Scope & Methodology**")
        lines.append("")
        lines.append("**Scope**")
        lines.append("")
        lines.append(
            "The Cross-Module Integrity review assesses whether related payroll datasets align consistently across employee lifecycle, leave, payroll event, and termination records."
        )
        lines.append("")
        lines.append(
            "The purpose of this review is to identify inconsistencies between linked datasets that may indicate sequencing issues, lifecycle mismatches, incomplete integrations, or broader payroll data integrity weaknesses."
        )
        lines.append("")
        lines.append(
            "This review is designed to support payroll, HR, finance, and governance teams in identifying where records may not align cleanly across the broader payroll data environment. Findings are integrity signals only and do not, on their own, confirm non-compliance, underpayment, or payroll error."
        )
        lines.append("")
        lines.append("**Data reviewed**")
        lines.append("")
        lines.append("- employee master data (where supplied)")
        lines.append("- leave balances and leave movement data (where supplied)")
        lines.append("- payroll event / payroll transaction extracts (where supplied)")
        lines.append("- termination and lifecycle-related records where included in the engagement data pack")
        lines.append("")
        lines.append("**Checks performed**")
        lines.append("")
        lines.append("- consistency checks between employee lifecycle status and payroll activity")
        lines.append("- identification of mismatches between leave activity and termination or employment status")
        lines.append("- cross-dataset linkage checks for related employee and payroll records")
        lines.append("- detection of sequencing anomalies between linked events across modules")
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
            "Cross-module findings should be interpreted as data integrity and linkage risk indicators. They highlight where records may not align cleanly across datasets and may require investigation before conclusions are drawn."
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        subsection_no += 1

    if not mods:
        lines.append("No scoped modules were included in this run.")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def build_data_sources_section(included_modules: set[str] | list[str] | None, base_output_dir: Path) -> str:
    modules_dir = base_output_dir

    lines: List[str] = []
    lines.append(
        "This review was generated from the following analysis outputs within the project `outputs/` directory:"
    )
    lines.append("")

    mods = normalise_modules(included_modules)
    for m in included_modules_in_order(mods):
        if m == MODULE_LEAVE:
            leave_findings = modules_dir / "leave_leakage_findings.csv"
            leakage_report = base_output_dir / "leakage_report.csv"
            if leave_findings.exists():
                lines.append(f"- `{leave_findings.relative_to(base_output_dir)}`  ")
            if leakage_report.exists():
                lines.append(f"- `{leakage_report.relative_to(base_output_dir)}`  ")

        elif m == MODULE_LSL:
            lsl_summary = modules_dir / "lsl_summary_by_severity.csv"
            lsl_findings = modules_dir / "lsl_findings.csv"
            if lsl_summary.exists():
                lines.append(f"- `{lsl_summary.relative_to(base_output_dir)}`  ")
            if lsl_findings.exists():
                lines.append(f"- `{lsl_findings.relative_to(base_output_dir)}`  ")

        elif m == MODULE_TERM:
            term_summary = modules_dir / "term_summary_by_severity.csv"
            term_findings = modules_dir / "term_findings.csv"
            if term_summary.exists():
                lines.append(f"- `{term_summary.relative_to(base_output_dir)}`  ")
            if term_findings.exists():
                lines.append(f"- `{term_findings.relative_to(base_output_dir)}`  ")

        elif m == MODULE_RKEG:
            rkeg_summary = modules_dir / "rkeg_summary_by_severity.csv"
            rkeg_findings = modules_dir / "rkeg_findings.csv"
            if rkeg_summary.exists():
                lines.append(f"- `{rkeg_summary.relative_to(base_output_dir)}`  ")
            if rkeg_findings.exists():
                lines.append(f"- `{rkeg_findings.relative_to(base_output_dir)}`  ")

        elif m == MODULE_CROSS:
            cross_findings = modules_dir / "cross_module_findings.csv"
            cross_summary = modules_dir / "cross_module_summary_by_severity.csv"
            if cross_summary.exists():
                rel_path = str(cross_summary.relative_to(base_output_dir)).replace("\\", "/")
                lines.append(f"- `{rel_path}`  ")
            if cross_findings.exists():
                rel_path = str(cross_findings.relative_to(base_output_dir)).replace("\\", "/")
                lines.append(f"- `{rel_path}`  ")

    exec_summary_md = base_output_dir / "executive" / "executive_summary.md"
    exec_summary_json = base_output_dir / "executive" / "executive_summary.json"
    if exec_summary_md.exists():
        lines.append(f"- `{exec_summary_md.relative_to(base_output_dir)}`  ")
    if exec_summary_json.exists():
        lines.append(f"- `{exec_summary_json.relative_to(base_output_dir)}`  ")

    lines.append("")
    lines.append(
        "These outputs were produced by rule-based checks over payroll and HR CSV extracts supplied by the organisation for the review period."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)

def build_leave_no_findings_message() -> str:
    return "No material leave and entitlement findings were identified in the current dataset.\n\n---"

def build_term_no_findings_message() -> str:
    return "No material termination-related findings were identified in the current dataset.\n\n---"

def build_rkeg_no_findings_message() -> str:
    return "No material record-keeping or evidence gaps were identified in the current dataset.\n\n---"

def build_cross_no_findings_message() -> str:
    return "No material cross-module integrity findings were identified in the current dataset.\n\n---"

def build_lsl_no_findings_message() -> str:
    return "No material long service leave findings were identified in the current dataset.\n\n---"

def build_lsl_coverage_note() -> str:
    return """No Long Service Leave (LSL) activity was identified in the dataset provided for this review.

Accordingly, LSL-related diagnostics were not performed.

This reflects a data coverage limitation rather than a confirmed absence of LSL risk. Assessment of LSL exposure typically requires service history, eligibility thresholds, and accrual data that may not be present in payroll-only extracts.

---""".strip()

def build_rkeg_summary(rkeg_counts: Dict[str, int]) -> str:
    if not any(rkeg_counts.values()):
        return "No material record-keeping or evidence gaps were identified in the current dataset.\n\n---"

    return f"""
As part of this review, a Record-Keeping & Evidence Gaps (RKEG) assessment was performed to evaluate whether payroll-related records are sufficiently complete, consistent and traceable to support payroll decisions if subject to audit or regulatory review.

The RKEG assessment focuses on evidential strength only. It does not determine whether payroll outcomes are correct or incorrect, and does not interpret awards, enterprise agreements or employment contracts.

The table below summarises the number of record-keeping and evidence gaps identified by severity. Counts reflect **evidential risk** only and do not represent confirmed non-compliance or quantified financial exposure.

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>{rkeg_counts["HIGH"]}</td>
      <td>Absence or weakness of core evidence or entitlement configuration that would materially impair the organisation’s ability to evidence payroll decisions if reviewed by auditors or regulators.</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>{rkeg_counts["MEDIUM"]}</td>
      <td>Evidence is incomplete, inconsistent or fragile. Decisions may still be defensible but require greater reliance on manual reconstruction, judgement, or explanation.</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>{rkeg_counts["LOW"]}</td>
      <td>Record-keeping or data quality weaknesses that are unlikely to be challenged in isolation but should be improved over time to support efficient and reliable payroll operations.</td>
    </tr>
  </tbody>
</table>

---
""".strip()


def build_lsl_severity_summary(lsl_counts: Dict[str, int]) -> str:
    if not any(lsl_counts.values()):
        return ""

    return f"""Where an LSL Exposure review was performed, the table below summarises the number of LSL-related risk indicators identified by severity. Counts reflect **risk indicators only** and do not represent confirmed underpayments, quantified exposure, or remediation priority.

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>{lsl_counts["HIGH"]}</td>
      <td>Indicators likely to require prompt validation due to potential material impact or audit defensibility concerns.</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>{lsl_counts["MEDIUM"]}</td>
      <td>Indicators that may reflect configuration, data quality, or timing weaknesses requiring review.</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>{lsl_counts["LOW"]}</td>
      <td>Lower-impact indicators that should be improved over time.</td>
    </tr>
  </tbody>
</table>

---
""".strip()


def build_term_severity_summary(term_counts: Dict[str, int]) -> str:
    if not any(term_counts.values()):
        return "No material termination-related findings were identified in the current dataset.\n\n---"

    return f"""
Where a Termination Exposure review was performed, the table below summarises the number of termination-related evidential issues identified by severity. Counts reflect **evidential risk only** and do not represent confirmed non-compliance or quantified financial exposure, or remediation priority.

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>{term_counts["HIGH"]}</td>
      <td>Absence or weakness of core termination or final pay evidence that would materially impair the organisation’s ability to evidence termination decisions if reviewed by auditors or regulators.</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>{term_counts["MEDIUM"]}</td>
      <td>Termination evidence exists but is incomplete, delayed or ambiguous and may require additional explanation or manual reconstruction.</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>{term_counts["LOW"]}</td>
      <td>Minor record-keeping or data quality weaknesses in termination records that should be improved over time to support efficient and reliable payroll operations.</td>
    </tr>
  </tbody>
</table>

---
""".strip()


def build_cross_module_summary(cross_counts: Dict[str, int]) -> str:
    if not any(cross_counts.values()):
        return "No material cross-module integrity findings were identified in the current dataset.\n\n---"

    return f"""Where a Cross-Module Integrity review was performed, the table below summarises the number of cross-module inconsistencies identified by severity. Counts reflect **integrity risk indicators only** and do not represent confirmed non-compliance or quantified financial exposure.

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>{cross_counts["HIGH"]}</td>
      <td>Cross-dataset inconsistencies that may materially affect confidence in employee lifecycle, payroll sequencing, or linked record integrity.</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>{cross_counts["MEDIUM"]}</td>
      <td>Cross-module mismatches or data linkage issues that warrant review but may be explainable through timing, process, or source-system differences.</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>{cross_counts["LOW"]}</td>
      <td>Lower-impact cross-module inconsistencies that should be monitored and improved over time.</td>
    </tr>
  </tbody>
</table>

---
""".strip()


def build_key_findings_overview(findings: List[Finding]) -> str:
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

<table class="summary-table">
  <thead>
    <tr>
      <th>Severity</th>
      <th>Count</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge-high">High</span></td>
      <td>{high}</td>
      <td>{high_desc}</td>
    </tr>
    <tr>
      <td><span class="badge-medium">Medium</span></td>
      <td>{med}</td>
      <td>{med_desc}</td>
    </tr>
    <tr>
      <td><span class="badge-low">Low</span></td>
      <td>{low}</td>
      <td>{low_desc}</td>
    </tr>
  </tbody>
</table>

---
""".strip()


def build_limitations() -> str:
    return """This review is subject to the following limitations:

- Calculations assume the underlying pay rates, loadings and multipliers are correct in the source systems.
- Award and enterprise agreement interpretation is not performed by this tool.
- Holiday calendars, leave rules and accrual settings are assumed to reflect the organisation’s intended configuration.
- Data quality issues (missing records, duplicates, inconsistent identifiers) may affect the completeness and accuracy of the results.

---
""".strip()


def build_next_steps(base_output_dir: Path) -> str:
    summary = load_executive_summary_json(base_output_dir)

    if not summary:
        return """1. Validate the highest-severity findings first.
2. Review the most affected modules and confirm whether findings reflect genuine control issues or data limitations.
3. Address structural data gaps that weaken evidentiary confidence.
4. Confirm root causes before remediation.
5. Re-run the review after corrective action to confirm that risk indicators have reduced.

---
""".strip()

    top_modules = summary.get("top_high_modules", [])
    class_summary = summary.get("class_summary", {})
    structural_count = class_summary.get("STRUCTURAL", 0)
    total_findings = summary.get("total_findings", 0)

    action_labels = {
        "TERM": "termination handling",
        "RKEG": "record-keeping controls",
        "LEAVE": "leave calculation and balance integrity",
        "LSL": "long service leave eligibility and accrual",
        "CROSS_MODULE": "cross-module lifecycle consistency",
    }

    friendly = [action_labels.get(m, m) for m in top_modules[:2]]

    if len(friendly) >= 2:
        first_line = (
            f"1. Prioritise detailed review of {friendly[0]} and {friendly[1]} first, "
            "as these areas show the strongest concentration of high-severity findings."
        )
    elif len(friendly) == 1:
        first_line = (
            f"1. Prioritise detailed review of {friendly[0]} first, "
            "as this area shows the strongest concentration of high-severity findings."
        )
    else:
        first_line = "1. Prioritise validation of the highest-severity findings first."

    if total_findings and structural_count / total_findings >= 0.3:
        structural_line = (
            "3. Address structural data gaps that may weaken evidentiary confidence and make findings harder to validate."
        )
    else:
        structural_line = (
            "3. Address any structural data gaps identified, particularly where they reduce confidence in validation or audit defensibility."
        )

    return f"""{first_line}
2. Confirm whether the identified findings reflect configuration weaknesses, process breakdowns, incomplete records, or isolated data anomalies.
{structural_line}
4. Validate substantive logical integrity findings before remediation decisions are made.
5. Re-run the review after corrective action to confirm that risk indicators have reduced and no new integrity issues have emerged.

---
""".strip()


def build_appendices(included_modules: set[str], base_output_dir: Path) -> str:
    mods = {m.strip().upper() for m in (included_modules or set())}
    modules_dir = base_output_dir

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

    if MODULE_CROSS in mods:
        lines.append("#### Cross-Module Integrity (CROSS_MODULE)")
        lines.append("")
        lines.append("- Employee lifecycle mismatches across datasets")
        lines.append("- Leave activity inconsistent with employment or termination status")
        lines.append("- Payroll events inconsistent with linked employee or termination records")
        lines.append("- Cross-dataset linkage or sequencing anomalies")
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
        lines.extend([
            "- `employee_id`",
            "- `leave_type`",
            "- `as_of_date`",
            "- `rule_code`",
            "- `severity`",
            "- `classification`",
            "- `message`",
            "- `diff_units`",
            "- `finding_id`",
            "- `next_action`",
            "",
        ])

    if MODULE_LSL in mods:
        lines.append("**LSL Exposure**")
        lines.append("")
        lines.extend([
            "- `employee_id`",
            "- `leave_type`",
            "- `as_of_date`",
            "- `rule_code`",
            "- `severity`",
            "- `classification`",
            "- `message`",
            "- `diff_units`",
            "- `finding_id`",
            "- `next_action`",
            "",
        ])

    if MODULE_TERM in mods:
        lines.append("**Termination Exposure (TERM)**")
        lines.append("")
        lines.extend([
            "- `employee_id`",
            "- `termination_date`",
            "- `final_pay_date`",
            "- `rule_code`",
            "- `severity`",
            "- `classification`",
            "- `message`",
            "- `days_gap`",
            "- `evidence`",
            "- `finding_id`",
            "- `next_action`",
            "",
        ])

    if MODULE_RKEG in mods:
        lines.append("**Record-Keeping & Evidence Gaps (RKEG)**")
        lines.append("")
        lines.extend([
            "- `employee_id`",
            "- `leave_type`",
            "- `as_of_date`",
            "- `rule_code`",
            "- `severity`",
            "- `classification`",
            "- `message`",
            "- `diff_units`",
            "- `evidence`",
            "- `finding_id`",
            "- `next_action`",
            "",
        ])

    if MODULE_CROSS in mods:
        lines.append("**Cross Module Integrity (CROSS_MODULE)**")
        lines.append("")
        lines.extend([
            "- `employee_id`",
            "- `leave_type`",
            "- `as_of_date`",
            "- `rule_code`",
            "- `severity`",
            "- `classification`",
            "- `message`",
            "- `diff_units`",
            "- `evidence`",
            "- `finding_id`",
            "- `next_action`",
            "",
        ])

    lines.append("---")
    lines.append("")
    lines.append("### Appendix C – Machine-readable outputs")
    lines.append("")
    lines.append("Complete machine-readable outputs are available in the following files:")
    lines.append("")

    if MODULE_LEAVE in mods:
        leave_findings = modules_dir / "leave_leakage_findings.csv"
        leakage_report = base_output_dir / "leakage_report.csv"
        if leave_findings.exists():
            lines.append(f"- `{leave_findings.relative_to(base_output_dir)}`")
        if leakage_report.exists():
            lines.append(f"- `{leakage_report.relative_to(base_output_dir)}`")

    if MODULE_LSL in mods:
        lsl_findings = modules_dir / "lsl_findings.csv"
        lsl_summary = modules_dir / "lsl_summary_by_severity.csv"
        if lsl_findings.exists():
            lines.append(f"- `{lsl_findings.relative_to(base_output_dir)}`")
        if lsl_summary.exists():
            lines.append(f"- `{lsl_summary.relative_to(base_output_dir)}`")

    if MODULE_TERM in mods:
        term_findings = modules_dir / "term_findings.csv"
        term_summary = modules_dir / "term_summary_by_severity.csv"
        term_summary_extra = modules_dir / "term_summary.csv"
        if term_findings.exists():
            lines.append(f"- `{term_findings.relative_to(base_output_dir)}`")
        if term_summary.exists():
            lines.append(f"- `{term_summary.relative_to(base_output_dir)}`")
        if term_summary_extra.exists():
            lines.append(f"- `{term_summary_extra.relative_to(base_output_dir)}`")

    if MODULE_RKEG in mods:
        rkeg_findings = modules_dir / "rkeg_findings.csv"
        rkeg_summary = modules_dir / "rkeg_summary_by_severity.csv"
        if rkeg_findings.exists():
            lines.append(f"- `{rkeg_findings.relative_to(base_output_dir)}`")
        if rkeg_summary.exists():
            lines.append(f"- `{rkeg_summary.relative_to(base_output_dir)}`")

    if MODULE_CROSS in mods:
        cross_findings = modules_dir / "cross_module_findings.csv"
        cross_summary = modules_dir / "cross_module_summary_by_severity.csv"
        if cross_findings.exists():
            rel_path = str(cross_findings.relative_to(base_output_dir)).replace("\\", "/")
            lines.append(f"- `{rel_path}`")
        if cross_summary.exists():
            rel_path = str(cross_summary.relative_to(base_output_dir)).replace("\\", "/")
            lines.append(f"- `{rel_path}`")

    exec_summary_md = base_output_dir / "executive" / "executive_summary.md"
    exec_summary_json = base_output_dir / "executive" / "executive_summary.json"
    if exec_summary_md.exists():
        lines.append(f"- `{exec_summary_md.relative_to(base_output_dir)}`")
    if exec_summary_json.exists():
        lines.append(f"- `{exec_summary_json.relative_to(base_output_dir)}`")

    lines.append("")
    lines.append(
        "These files provide row-level detail suitable for operational review, sampling, remediation planning, or incorporation into a broader audit work program."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


# ---------- Orchestrator ----------

def generate_exec_pack(
    organisation_name: str = "Organisation not specified",
    review_period: str | None = None,
    modules: Optional[Iterable[str]] = None,
    output_dir: Path | None = None,
) -> Path:
    """
    Generate crc_executive_pack.md for the supplied output directory.
    """

    target_dir = output_dir or OUTPUTS_DIR

    requested: set[str] = {m.strip().upper() for m in (modules or DEFAULT_MODULES)}
    included: set[str] = {m for m in requested if _module_ran(m, target_dir)}

    report_title: str = _build_report_title(included or requested)

    print("Requested modules:", requested)
    print("Included modules:", included)
    print("Module CSV detection:")
    for m in requested:
        print(" -", m, "=>", _module_ran(m, target_dir))
    print_exec_pack_preflight(target_dir, included)

    if MODULE_LEAVE in included:
        leave_findings_path = target_dir / "leave_leakage_findings.csv"
        leave_findings = [Finding.from_row(r) for r in load_csv(leave_findings_path)]

    sorted_findings = sort_findings(leave_findings) if leave_findings else []
    rkeg_counts = load_rkeg_severity_counts(target_dir) if MODULE_RKEG in included else {}
    term_counts = load_term_severity_counts(target_dir) if MODULE_TERM in included else {}
    lsl_counts = load_lsl_severity_counts(target_dir) if MODULE_LSL in included else {}
    cross_counts = load_cross_module_severity_counts(target_dir) if MODULE_CROSS in included else {}

    if review_period is None:
        review_period = derive_exec_review_period_from_data(included, target_dir)

    parts: List[str] = [build_header(report_title, organisation_name, review_period)]

    structure = ReportStructure()

    structure.add("Executive Summary", 1, lambda: build_executive_summary(target_dir))
    structure.add("Highlight Insights", 1, lambda: build_highlight_insights(target_dir))
    structure.add("Risk Profile Overview", 1, lambda: build_risk_profile_overview(target_dir))
    structure.add("Data Sources", 1, lambda: build_data_sources_section(included, target_dir))
    structure.add("Scope & Methodology", 1, lambda: build_scope_and_methodology(included))

    summary_modules = {MODULE_LEAVE, MODULE_LSL, MODULE_TERM, MODULE_RKEG, MODULE_CROSS}
    if any(m in included for m in summary_modules):
        structure.add("Module Summary Overview", 1, lambda: "")

        if MODULE_LEAVE in included:
            structure.add(
                "Leave & Entitlement Leakage (LEAVE) – Summary Overview",
                2,
                lambda: (
                    build_key_findings_overview(sorted_findings)
                    if sorted_findings
                    else build_leave_no_findings_message("leave and entitlement")
                ),
            )

        if MODULE_LSL in included:
            lsl_findings_path = target_dir / "lsl_findings.csv"
            lsl_has_data = lsl_findings_path.exists() and bool(load_csv(lsl_findings_path))

            if any(lsl_counts.values()):
                structure.add(
                    "Long Service Leave (LSL) Exposure – Severity Overview",
                    2,
                    lambda: build_lsl_severity_summary(lsl_counts),
                )
            else:
                structure.add(
                    "Long Service Leave (LSL) – Coverage Note",
                    2,
                    lambda: (
                        build_lsl_no_findings_message("long service leave")
                        if lsl_has_data
                        else build_lsl_coverage_note()
                    ),
                )

        if MODULE_TERM in included:
            structure.add(
                "Termination Exposure – Severity Overview",
                2,
                lambda: (
                    build_term_severity_summary(term_counts)
                    if any(term_counts.values())
                    else build_term_no_findings_message("termination-related")
                ),
            )

        if MODULE_RKEG in included:
            structure.add(
                "Record-Keeping & Evidence Gaps (RKEG) – Severity Overview",
                2,
                lambda: (
                    build_rkeg_summary(rkeg_counts)
                    if any(rkeg_counts.values())
                    else build_rkeg_no_findings_message("record-keeping and evidence gap")
                ),
            )

        if MODULE_CROSS in included:
            structure.add(
                "Cross-Module Integrity – Summary Overview",
                2,
                lambda: (
                    build_cross_module_summary(cross_counts)
                    if any(cross_counts.values())
                    else build_rkeg_no_findings_message("cross-module integrity")
                ),
            )

        structure.add(
            "How to interpret findings",
            2,
            lambda: build_interpretation_block_exec(included),
        )

    structure.add("Limitations & Assumptions", 1, build_limitations)
    structure.add("Recommended Next Steps", 1, lambda: build_next_steps(target_dir))
    structure.add("Appendices", 1, lambda: build_appendices(included, target_dir))

    parts.append(structure.render_markdown())
    final_md = "\n".join(parts)

    scan_result = scan_report_text(final_md)

    if scan_result["hard"]:
        print("⚠ HARD forbidden terms detected in report:")
        print(sorted(set(scan_result["hard"])))

    if scan_result["soft"]:
        print("ℹ Soft-flag terms detected in report:")
        print(sorted(set(scan_result["soft"])))

    md_path = target_dir / "crc_executive_pack.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(final_md, encoding="utf-8")

    print(f"Executive pack generated at: {md_path}")
    return md_path


def generate_leave_leakage_report(
    organisation_name: str = "Organisation not specified",
    review_period: str | None = None,
    modules: Optional[Iterable[str]] = None,
    output_dir: Path | None = None,
) -> Path:
    """
    Backward-compatible wrapper.
    """
    return generate_exec_pack(
        organisation_name=organisation_name,
        review_period=review_period,
        modules=modules,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--organisation-name", default="Organisation not specified")

    args = parser.parse_args()

    path = generate_exec_pack(
        organisation_name=args.organisation_name,
        output_dir=Path(args.output_dir),
        modules=DEFAULT_MODULES,
    )

    print(f"Generated at: {path}")