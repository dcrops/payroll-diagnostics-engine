import pandas as pd
from rkeg.engine import run_rkeg_engine


def test_tier_2_rule_not_run_when_only_tier_1_enabled():
    # Minimal dataset with clearly late super
    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "payment_date": ["2024-03-15"],
        "super_amount": [1000.00]
    })

    datasets = {
        "super_payments": super_payments,
        "pay_events": pd.DataFrame(),
        "employee_master": pd.DataFrame(),
    }

    # Only Tier 1 enabled
    findings = list(run_rkeg_engine(datasets, enabled_tiers={1}))

    # SUP-003 is Tier 2, so should not run
    rule_codes = [f.rule_code for f in findings]
    assert "RKEG-SUP-003" not in rule_codes

def test_tier_2_rule_runs_when_tier_2_enabled():
    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "payment_date": ["2024-03-15"],
        "super_amount": [1000.00]
    })

    datasets = {
        "super_payments": super_payments,
        "pay_events": pd.DataFrame(),
        "employee_master": pd.DataFrame(),
    }

    findings = list(run_rkeg_engine(datasets, enabled_tiers={2}))

    rule_codes = [f.rule_code for f in findings]
    assert "RKEG-SUP-003" in rule_codes