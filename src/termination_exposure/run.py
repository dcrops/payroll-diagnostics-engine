from __future__ import annotations

import csv
import json
import yaml
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any

from termination_exposure.rules import run_rule
from common.data_window import write_data_window

# ---------- Paths ----------

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "sample"
OUTPUTS_DIR = BASE_DIR / "outputs"
MODULES_DIR = OUTPUTS_DIR / "modules"

TERMINATIONS_CSV = DATA_DIR / "terminations.csv"
PAY_EVENTS_CSV = DATA_DIR / "pay_events.csv"
EMPLOYEES_CSV = DATA_DIR / "employees.csv"

TERM_FINDINGS_CSV = MODULES_DIR / "term_findings.csv"
TERM_SUMMARY_BY_SEVERITY_CSV = MODULES_DIR / "term_summary_by_severity.csv"
TERM_SUMMARY_CSV = MODULES_DIR / "term_summary.csv"

TERM_RULES_YML = BASE_DIR / "src" / "termination_exposure" / "config" / "term_rules.yml"


# ---------- CSV helpers ----------

def _extract_term_dates(rows: List[Dict[str, str]]) -> List[date]:
    """
    Collect valid dates from termination / pay event rows.

    We look at termination and final-pay date columns, try common
    formats, and ignore anything that won't parse cleanly.
    """
    if not rows:
        return []

    candidate_cols = [
        "termination_date",
        "term_date",
        "final_pay_date",
        "pay_date",
    ]

    dates: List[date] = []

    for row in rows:
        for col in candidate_cols:
            raw = (row.get(col) or "").strip()
            if not raw:
                continue

            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    d = datetime.strptime(raw, fmt).date()
                    dates.append(d)
                    break
                except ValueError:
                    continue

    return dates

def load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)

def load_rules(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("rules", [])


def write_term_findings(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "employee_id",
        "termination_date",
        "final_pay_date",
        "rule_code",
        "severity",
        "message",
        "days_gap",
        "evidence",
        "finding_id",
        "next_action",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            out_row: Dict[str, Any] = {}

            for field in fieldnames:
                value = row.get(field)

                if field == "evidence":
                    # Serialise evidence dict to JSON for audit/debug use
                    if isinstance(value, (dict, list)):
                        out_row[field] = json.dumps(value, ensure_ascii=False)
                    elif value is None:
                        out_row[field] = ""
                    else:
                        out_row[field] = str(value)
                else:
                    out_row[field] = "" if value is None else value

            writer.writerow(out_row)


def build_summary_by_severity(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build simple HIGH / MEDIUM / LOW counts for TERM.

    Shape:
        [{"severity": "HIGH", "finding_count": 2}, ...]
    """
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for f in findings:
        sev = str(f.get("severity", "")).strip().upper()
        if sev in counts:
            counts[sev] += 1

    rows: List[Dict[str, Any]] = []
    for sev in ["HIGH", "MEDIUM", "LOW"]:
        rows.append(
            {
                "severity": sev,
                "finding_count": counts[sev],
            }
        )
    return rows


def write_term_summary_by_severity(
    path: Path, rows: List[Dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["severity", "finding_count"]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "severity": row.get("severity", ""),
                    "finding_count": row.get("finding_count", 0),
                }
            )


def build_term_rule_summary(
    findings: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Build rule-level summary for TERM, matching rkeg_summary.csv shape.

    Shape:
        rule_code,severity,finding_count
    """
    counts: Dict[tuple[str, str], int] = {}

    for f in findings:
        rule_code = str(f.get("rule_code", "")).strip()
        severity = str(f.get("severity", "")).strip().upper()
        if not rule_code or not severity:
            continue
        key = (rule_code, severity)
        counts[key] = counts.get(key, 0) + 1

    rows: List[Dict[str, Any]] = []
    # Keep ordering deterministic: sort by rule_code then severity
    for (rule_code, severity), n in sorted(counts.items()):
        rows.append(
            {
                "rule_code": rule_code,
                "severity": severity,
                "finding_count": n,
            }
        )

    return rows


def write_term_rule_summary(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["rule_code", "severity", "finding_count"]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "rule_code": row.get("rule_code", ""),
                    "severity": row.get("severity", ""),
                    "finding_count": row.get("finding_count", 0),
                }
            )


# ---------- Main orchestration ----------


def run_termination_exposure_review() -> None:
    """
    Run all TERM v1 rules and write:
      - outputs/modules/term_findings.csv
      - outputs/modules/term_summary_by_severity.csv
      - outputs/modules/term_summary.csv

    This function does not handle reporting; it only produces CSV outputs
    for downstream use by the reporting layer.
    """
    print(f"[TERM] Loading terminations from: {TERMINATIONS_CSV}")
    print(f"[TERM] Loading pay events from:  {PAY_EVENTS_CSV}")
    print(f"[TERM] Loading employees from:   {EMPLOYEES_CSV}")

    terminations = load_csv(TERMINATIONS_CSV)
    pay_events = load_csv(PAY_EVENTS_CSV)
    employees = load_csv(EMPLOYEES_CSV)

    print(f"[TERM] Loaded {len(terminations)} termination rows, "
          f"{len(pay_events)} pay events, {len(employees)} employees")

    # Derive TERM data window from client source data
    term_dates = _extract_term_dates(terminations) + _extract_term_dates(pay_events)
    if term_dates:
        MODULES_DIR.mkdir(parents=True, exist_ok=True)
        term_window_path = MODULES_DIR / "term_data_window.csv"
        write_data_window(term_window_path, term_dates)
        print(
            f"[TERM] Wrote data window to {term_window_path} "
            f"({min(term_dates)} → {max(term_dates)})"
        )
    else:
        print("[TERM] No usable dates found for data window – term_data_window.csv not written")

    rules = load_rules(TERM_RULES_YML)

    datasets = {
        "terminations": terminations,
        "pay_events": pay_events,
        "employee_master": employees,
    }

    findings = []
    for rule in rules:
        findings.extend([f.__dict__ for f in run_rule(rule, datasets)])

    print(f"[TERM] Generated {len(findings)} findings")

    write_term_findings(TERM_FINDINGS_CSV, findings)

    summary_by_sev = build_summary_by_severity(findings)
    write_term_summary_by_severity(TERM_SUMMARY_BY_SEVERITY_CSV, summary_by_sev)

    rule_summary = build_term_rule_summary(findings)
    write_term_rule_summary(TERM_SUMMARY_CSV, rule_summary)


if __name__ == "__main__":
    run_termination_exposure_review()