# src/rkeg/rules.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml


@dataclass
class Finding:
    """
    Canonical RKEG finding.

    Fields are designed to align with the CRC module reporting schema
    used across Executive and standalone module reports:

    employee_id, leave_type, as_of_date, rule_code, severity, message,
    diff_units, evidence, finding_id, next_action.

    The schema is intentionally consistent across modules to support
    clean aggregation, severity summaries, and defensible reporting.
    """

    employee_id: str | None
    leave_type: str | None
    as_of_date: str | None

    rule_code: str        # e.g. "RKEG-EMP-001"
    severity: str         # "HIGH" / "MEDIUM" / "LOW"
    message: str          # short finding statement

    diff_units: float | None  # mostly unused for RKEG, but kept for schema compatibility
    evidence: str        # JSON-ish string describing context
    finding_id: str      # unique per finding (e.g. uuid hex)
    next_action: str     # remediation text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def findings_to_dataframe(findings: Iterable[Finding]) -> pd.DataFrame:
    rows = [f.to_dict() for f in findings]
    return pd.DataFrame(rows)


def write_findings_csv(findings: Iterable[Finding], path: Path) -> None:
    df = findings_to_dataframe(findings)

    if df.empty:
        # Maintain canonical CRC finding column order for consistent
        # module-level reporting and downstream severity summaries.
        df = pd.DataFrame(
            columns=[
                "employee_id",
                "leave_type",
                "as_of_date",
                "rule_code",
                "severity",
                "message",
                "diff_units",
                "evidence",
                "finding_id",
                "next_action",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# --------------------------
# Rule config loader (YAML)
# --------------------------

CONFIG_PATH = Path(__file__).parent / "config" / "rkeg_rules.yml"


def load_rule_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
