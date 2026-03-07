import pandas as pd

from rkeg.detectors.pay import run_rule


def test_pay_011_flags_rate_history_rows_with_missing_effective_dates():
    rule = {
        "id": "RKEG-PAY-011",
        "severity": "HIGH",
        "text": {
            "finding": "Rate history records were identified without valid effective date fields.",
            "remediation": "Ensure all rate history records include valid effective from and effective to dates and enforce validation in payroll configuration processes.",
        },
    }

    datasets = {
        "rate_history": pd.DataFrame(
            [
                {
                    "employee_id": "E101",
                    "effective_from": "",
                    "effective_to": "2024-12-31",
                    "base_rate": 38.50,
                    "employment_type": "FULL_TIME",
                    "classification": "L3",
                    "pay_cycle": "FORTNIGHTLY",
                    "change_reason": "Annual review",
                },
                {
                    "employee_id": "E102",
                    "effective_from": "2024-01-01",
                    "effective_to": "",
                    "base_rate": 41.20,
                    "employment_type": "PART_TIME",
                    "classification": "L2",
                    "pay_cycle": "FORTNIGHTLY",
                    "change_reason": "Promotion",
                },
                {
                    "employee_id": "E103",
                    "effective_from": "2024-01-01",
                    "effective_to": "2024-12-31",
                    "base_rate": 42.00,
                    "employment_type": "FULL_TIME",
                    "classification": "L4",
                    "pay_cycle": "FORTNIGHTLY",
                    "change_reason": "Control",
                },
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E101" in flagged_ids
    assert "E102" in flagged_ids
    assert "E103" not in flagged_ids
    assert len(findings) == 2