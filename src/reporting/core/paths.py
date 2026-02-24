# reporting/core/paths.py
from pathlib import Path


def get_repo_root() -> Path:
    """
    Return the root of the CRC repository.

    Assumes this file lives at repo_root/src/reporting/core/paths.py.
    """
    return Path(__file__).resolve().parents[3]


def get_default_outputs_dir() -> Path:
    """
    Default directory where CRC CSVs and Markdown outputs live.
    """
    return get_repo_root() / "outputs"