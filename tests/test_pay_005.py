from pathlib import Path
from rkeg.datasets import load_all_datasets
from rkeg.engine import run_rkeg_engine


def _load_sample():
    repo_root = Path(__file__).resolve().parents[1]
    return load_all_datasets(repo_root / "data" / "sample")


def test_pay_005_adjustment_without_super():
    datasets = _load_sample()
    findings = list(run_rkeg_engine(datasets, enabled_tiers={1, 2}))

    pay_005 = [f for f in findings if f.rule_code == "RKEG-PAY-005"]

    assert len(pay_005) > 0