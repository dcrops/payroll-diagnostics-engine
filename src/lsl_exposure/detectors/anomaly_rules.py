from __future__ import annotations

import pandas as pd
from lsl_exposure.models import Finding


def detect_extreme_lsl_balance(
    rule: dict,
    datasets: dict[str, pd.DataFrame],
    context: dict,
) -> list[Finding]:
    return []