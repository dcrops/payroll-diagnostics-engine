from __future__ import annotations

from pathlib import Path
from datetime import date
from typing import Iterable, List
import csv


def write_data_window(path: Path, dates: Iterable[date]) -> None:
    """
    Write a simple data window CSV of the form:

        first_date,last_date
        2023-01-03,2024-04-30

    If no valid dates are supplied, nothing is written.

    This is engine-side (analysis). Reporting just reads the file.
    """
    cleaned: List[date] = [d for d in dates if isinstance(d, date)]
    if not cleaned:
        return

    first = min(cleaned)
    last = max(cleaned)

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["first_date", "last_date"])
        writer.writeheader()
        writer.writerow(
            {
                "first_date": first.isoformat(),
                "last_date": last.isoformat(),
            }
        )