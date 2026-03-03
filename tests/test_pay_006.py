from pathlib import Path

from rkeg.datasets import load_all_datasets
from rkeg.engine import run_rkeg_engine


def _load_sample():
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data" / "sample"
    return load_all_datasets(data_dir)


def test_pay_006_missing_base_rate_produces_findings():
    datasets = _load_sample()
    findings = list(run_rkeg_engine(datasets, enabled_tiers={1, 2}))
    pay_006 = [f for f in findings if f.rule_code == "RKEG-PAY-006"]

    assert len(pay_006) > 0, "Expected RKEG-PAY-006 to produce findings for sample data"