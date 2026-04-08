# reporting/leave_common.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from reporting.executive.exec_pack_md import (
    LEAVE_FINDINGS_CSV,
    LEAKAGE_REPORT_CSV,
)


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
        """Construct a Finding from a CSV row.

        Handles a couple of common header variants so the engine is a bit resilient.
        """
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
        """Try a few common column names for exposure amounts.

        If none are present or parseable, return None and the exposure section
        will fall back to a 'not available' style narrative.
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

def _load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_leave_findings() -> List[Finding]:
    rows = _load_csv(LEAVE_FINDINGS_CSV)
    return [Finding.from_row(r) for r in rows]


def load_leave_exposure_rows() -> List[ExposureRow]:
    rows = _load_csv(LEAKAGE_REPORT_CSV)
    exposure_rows: List[ExposureRow] = []
    for r in rows:
        er = ExposureRow.from_row(r)
        if er is not None:
            exposure_rows.append(er)
    return exposure_rows


# ---------- Review period helper (leave-specific) ----------

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


def derive_leave_review_period(findings: List[Finding]) -> str:
    """Derive a human-readable review period from leave findings.

    Uses the earliest and latest valid as_of_date values.
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