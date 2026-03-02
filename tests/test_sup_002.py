import pandas as pd
from rkeg.detectors.super_ import run_rule


def test_sup_002_flags_material_difference():
    rule = {
        "id": "RKEG-SUP-002",
        "severity": "HIGH",
        "text": {"finding": "Reconciliation mismatch."}
    }

    pay_events = pd.DataFrame({
        "employee_id": ["E001"],
        "pay_date": ["2024-01-15"],
        "super_amount": [1000.00]
    })

    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "super_amount": [800.00]
    })

    datasets = {
        "pay_events": pay_events,
        "super_payments": super_payments
    }

    findings = list(run_rule(rule, datasets))
    assert len(findings) == 1

def test_sup_002_does_not_flag_within_tolerance():
    rule = {
        "id": "RKEG-SUP-002",
        "severity": "HIGH",
        "text": {"finding": "Reconciliation mismatch."}
    }

    pay_events = pd.DataFrame({
        "employee_id": ["E001"],
        "pay_date": ["2024-01-15"],
        "super_amount": [1000.00]
    })

    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "super_amount": [998.00]  # small diff
    })

    datasets = {
        "pay_events": pay_events,
        "super_payments": super_payments
    }

    findings = list(run_rule(rule, datasets))
    assert len(findings) == 0