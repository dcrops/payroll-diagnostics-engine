import pandas as pd

from rkeg.detectors.pay import run_rule


def test_pay_010_flags_pay_events_outside_employment_period():
    rule = {
        "id": "RKEG-PAY-010",
        "severity": "HIGH",
        "text": {
            "finding": "Pay events were identified that fall outside the employee's recorded employment period.",
            "remediation": "Reconcile pay events against employment start and termination dates and investigate any payments recorded outside valid employment periods.",
        },
    }

    datasets = {
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E001", "pay_date": "2024-06-15", "gross_amount": 1500},
                {"employee_id": "E002", "pay_date": "2024-09-15", "gross_amount": 1200},
                {"employee_id": "E003", "pay_date": "2024-07-15", "gross_amount": 1800},
            ]
        ),
        "employee_master": pd.DataFrame(
            [
                {"employee_id": "E001", "start_date": "2024-07-01", "termination_date": None},
                {"employee_id": "E002", "start_date": "2023-02-01", "termination_date": "2024-08-31"},
                {"employee_id": "E003", "start_date": "2024-07-01", "termination_date": None},
            ]
        ),
        "terminations": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E001" in flagged_ids
    assert "E002" in flagged_ids
    assert "E003" not in flagged_ids
    assert len(findings) == 2