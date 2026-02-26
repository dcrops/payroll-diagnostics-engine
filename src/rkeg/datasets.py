# src/rkeg/datasets.py
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

# Logical dataset name (used in YAML) -> filename on disk
DATASET_FILE_MAP: dict[str, str] = {
    "employee_master": "employees.csv",
    "pay_events": "pay_events.csv",
    "leave_ledger": "leave_ledger.csv",
    "leave_snapshot": "balances_snapshot.csv",
    "terminations": "terminations.csv",
    # new ones:
    "super_payments": "super_payments.csv",
    "rate_history": "rate_history.csv",
    "pay_overrides": "pay_overrides.csv",
}


def load_dataset(dataset_name: str, base_path: Path) -> pd.DataFrame | None:
    """
    Load a single logical dataset by name.

    Returns None if the underlying file does not exist, so the engine
    can treat missing datasets as 'visibility gaps' instead of crashing.
    """
    filename = DATASET_FILE_MAP.get(dataset_name)
    if filename is None:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    file_path = base_path / filename
    if not file_path.exists():
        return None

    return pd.read_csv(file_path)


def load_all_datasets(base_path: Path) -> Dict[str, pd.DataFrame]:
    """
    Load all known datasets into the dict structure expected by run_rkeg_engine.
    Only includes datasets whose files actually exist.
    """
    datasets: Dict[str, pd.DataFrame] = {}

    for logical_name, filename in DATASET_FILE_MAP.items():
        file_path = base_path / filename
        if not file_path.exists():
            # Optional dataset – skip for now; your rules can check for presence
            continue

        datasets[logical_name] = pd.read_csv(file_path)

    return datasets