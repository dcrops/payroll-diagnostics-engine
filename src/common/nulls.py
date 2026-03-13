from __future__ import annotations

import pandas as pd


def is_missing(value) -> bool:
    """
    Standardised null / blank detection for CRC rules.
    Treats None, NaN, empty strings, and whitespace as missing.
    """
    if value is None:
        return True

    if pd.isna(value):
        return True

    if isinstance(value, str) and value.strip() == "":
        return True

    return False