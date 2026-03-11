from __future__ import annotations

import pandas as pd
from lsl_exposure.models import Finding


def detect_lsl_before_employment_start(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    return []


def detect_lsl_after_termination(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    return []