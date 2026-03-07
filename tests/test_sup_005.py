import pandas as pd

from rkeg.detectors.super_ import run_rule


def test_sup_005_flags_super_payment_rows_with_missing_payment_date():
    rule = {
        "id": "RKEG-SUP-005",
        "severity": "HIGH",
        "text": {
            "finding": "Superannuation payment records were identified without a valid payment date.",
            "remediation": "Ensure all super payment records include valid payment dates and enforce validation before exporting super contribution data.",
        },
    }

    datasets = {
        "super_payments": pd.DataFrame(
            [
                {
                    "employee_id": "E201",
                    "payment_date": "",
                    "period_end_date": "2024-03-31",
                    "super_amount": 550.00,
                },
                {
                    "employee_id": "E202",
                    "payment_date": "2024-04-15",
                    "period_end_date": "2024-03-31",
                    "super_amount": 396.00,
                },
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E201" in flagged_ids
    assert "E202" not in flagged_ids
    assert len(findings) == 1