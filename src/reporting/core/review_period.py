from __future__ import annotations

from pathlib import Path
from datetime import date
from typing import Iterable, List, Optional
import csv


def _parse_iso_date(value: str | None) -> Optional[date]:
    """
    Parse a simple YYYY-MM-DD string into a date, or return None.

    Data window files are under our control, so we expect ISO format.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def derive_review_period_from_windows(
    window_files: Iterable[Path],
    fallback: Optional[str] = "Period not specified",
) -> Optional[str]:
    """
    Read one or more 'data window' CSVs of the form:

        first_date,last_date
        2023-01-01,2024-12-31

    and return a human-readable "dd Mon YYYY to dd Mon YYYY" string
    spanning ALL windows.

    If no valid dates are found:
      - if fallback is None, return None
      - otherwise, return the fallback string.
    """
    all_dates: List[date] = []

    for path in window_files:
        if not path.exists():
            continue

        try:
            with path.open("r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # We accept a couple of reasonable column names
                    for key in ("first_date", "last_date", "start_date", "end_date"):
                        d = _parse_iso_date(row.get(key))
                        if d is not None:
                            all_dates.append(d)
        except OSError:
            # Non-fatal – missing/locked file shouldn't crash reporting
            continue

    if not all_dates:
        return fallback

    start = min(all_dates)
    end = max(all_dates)

    if start == end:
        return start.strftime("%d %b %Y")

    return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"