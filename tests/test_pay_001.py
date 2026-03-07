import pandas as pd

from rkeg.detectors.pay import run_rule


def test_pay_001_flags_missing_or_invalid_pay_date():
    rule = {
        "id": "RKEG-PAY-001",
        "severity": "HIGH",
        "text": {
            "finding": "Pay events were identified without a valid pay date.",
            "remediation": "Ensure all pay events include a valid pay date and enforce validation in payroll processes so events cannot be processed or exported without this field populated.",
        },
    }

    datasets = {
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E001", "pay_date": "", "gross_amount": 1500},
                {"employee_id": "E002", "pay_date": "not_a_date", "gross_amount": 1200},
                {"employee_id": "E003", "pay_date": "2024-03-15", "gross_amount": 1800},
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E001" in flagged_ids
    assert "E002" in flagged_ids
    assert "E003" not in flagged_ids
    assert len(findings) == 2