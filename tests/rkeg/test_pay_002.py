import pandas as pd

from rkeg.detectors.pay import run_rule


def test_pay_002_flags_missing_or_invalid_gross_amount():
    rule = {
        "id": "RKEG-PAY-002",
        "severity": "HIGH",
        "text": {
            "finding": "Pay events were identified without a valid gross amount recorded.",
            "remediation": "Ensure all pay events include a valid gross amount and enforce validation in payroll exports and downstream reporting so incomplete records cannot be used for decision-making.",
        },
    }

    datasets = {
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E001", "pay_date": "2024-03-15", "gross_amount": ""},
                {"employee_id": "E002", "pay_date": "2024-03-15", "gross_amount": "abc"},
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