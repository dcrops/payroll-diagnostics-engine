from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import pandas as pd


@dataclass
class Finding:
    """
    Canonical RKEG finding aligned to CRC reporting schema.
    """

    employee_id: str | None
    leave_type: str | None
    as_of_date: str | None

    rule_code: str
    severity: str
    classification: str
    message: str

    diff_units: float | None
    evidence: str
    finding_id: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Backwards-compatible alias for minimal detector churn
RkegFinding = Finding


def findings_to_dataframe(findings: Iterable[Finding]) -> pd.DataFrame:
    rows = [f.to_dict() for f in findings]
    return pd.DataFrame(rows)


def write_findings_csv(findings: Iterable[Finding], out_path: Path) -> None:
    df = findings_to_dataframe(findings)

    if df.empty:
        df = pd.DataFrame(
            columns=[
                "employee_id",
                "leave_type",
                "as_of_date",
                "rule_code",
                "severity",
                "classification",
                "message",
                "diff_units",
                "evidence",
                "finding_id",
                "next_action",
            ]
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)