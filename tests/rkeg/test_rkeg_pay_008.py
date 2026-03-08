import pandas as pd
from rkeg.detectors.pay import run_rule


def _rule():
    return {
        "id": "RKEG-PAY-008",
        "severity": "HIGH",
        "text": {
            "finding": "Pay events could not be matched to a valid rate history record.",
            "remediation": "Reconcile pay events to rate history.",
        },
    }


def test_pay_008_flags_outside_window():
    pay_events = pd.DataFrame({
        "employee_id": ["E001"],
        "pay_date": ["2024-03-15"],
    })

    rate_history = pd.DataFrame({
        "employee_id": ["E001"],
        "effective_from": ["2020-01-01"],
        "effective_to": ["2023-12-31"],
    })

    datasets = {"pay_events": pay_events, "rate_history": rate_history}

    findings = list(run_rule(_rule(), datasets))

    assert len(findings) == 1
    assert findings[0].rule_code == "RKEG-PAY-008"


def test_pay_008_does_not_flag_inside_window():
    pay_events = pd.DataFrame({
        "employee_id": ["E001"],
        "pay_date": ["2024-03-15"],
    })

    rate_history = pd.DataFrame({
        "employee_id": ["E001"],
        "effective_from": ["2020-01-01"],
        "effective_to": [None],
    })

    datasets = {"pay_events": pay_events, "rate_history": rate_history}

    findings = list(run_rule(_rule(), datasets))

    assert findings == []