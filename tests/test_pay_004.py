import pandas as pd

from rkeg.detectors.pay import run_rule


def test_pay_004_flags_pay_events_without_employee_master_record():
    rule = {
        "id": "RKEG-PAY-004",
        "severity": "HIGH",
        "text": {
            "finding": "Pay events were identified for individuals not present in the employee master records.",
            "remediation": "Reconcile pay events to employee master records and ensure all individuals paid through payroll are properly recorded and retained in employee data.",
        },
    }

    datasets = {
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E001", "pay_date": "2024-03-15", "gross_amount": 1500},
                {"employee_id": "ORPHAN001", "pay_date": "2024-03-15", "gross_amount": 1200},
            ]
        ),
        "employee_master": pd.DataFrame(
            [
                {"employee_id": "E001"},
                {"employee_id": "E002"},
            ]
        ),
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "ORPHAN001"