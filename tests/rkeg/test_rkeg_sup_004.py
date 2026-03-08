# tests/test_sup_004.py
from pathlib import Path

from rkeg.datasets import load_all_datasets
from rkeg.engine import run_rkeg_engine


def _load_sample_datasets():
    """
    Helper to load the sample CSVs using the same loader as rkeg.run.
    """
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data" / "sample"
    return load_all_datasets(data_dir)


def test_sup_004_missing_default_fund_produces_findings():
    """
    RKEG-SUP-004:
    Employees without a recorded default superannuation fund.

    This test just asserts that, given our sample data, the rule
    actually fires and produces at least one finding.
    """
    datasets = _load_sample_datasets()

    # Enable both tiers so Tier 2 SUP rules run.
    findings = list(run_rkeg_engine(datasets, enabled_tiers={1, 2}))

    sup_004_findings = [f for f in findings if f.rule_code == "RKEG-SUP-004"]

    # We don't care about the exact count here – just that the rule is live.
    assert (
        len(sup_004_findings) > 0
    ), "Expected RKEG-SUP-004 to produce at least one finding in sample data"