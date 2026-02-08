from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable
import pandas as pd
from pathlib import Path


@dataclass
class RkegFinding:
    """Canonical RKEG finding representation.

    This is module-local; combine_findings will just see the CSV.
    """
    rule_id: str
    domain: str          # "EMP", "PAY", "LEAVE", "TERM"
    severity: str        # "HIGH", "MEDIUM", "LOW"
    employee_id: str | None
    affected_record_ids: str | None  # free-text: ids, dates, etc
    finding: str
    why_it_matters: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def findings_to_dataframe(findings: Iterable[RkegFinding]) -> pd.DataFrame:
    rows = [f.to_dict() for f in findings]
    return pd.DataFrame(rows)


def write_findings_csv(findings: Iterable[RkegFinding], out_path: Path) -> None:
    df = findings_to_dataframe(findings)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
