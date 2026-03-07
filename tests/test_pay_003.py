import pandas as pd

from rkeg.detectors.pay import run_rule


def test_pay_003_flags_missing_run_reference():
    rule = {
        "id": "RKEG-PAY-003",
        "severity": "MEDIUM",
        "text": {
            "finding": "Pay events were identified without a pay run or batch reference.",
            "remediation": "Ensure all pay events include a pay run or batch reference and align exported payroll data structures with the underlying run identifiers used in the payroll system.",
        },
    }

    datasets = {
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E001", "pay_date": "2024-03-15", "gross_amount": 1500, "run_id": ""},
                {"employee_id": "E002", "pay_date": "2024-03-15", "gross_amount": 1200, "run_id": "   "},
                {"employee_id": "E003", "pay_date": "2024-03-15", "gross_amount": 1800, "run_id": "RUN003"},
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E001" in flagged_ids
    assert "E002" in flagged_ids
    assert "E003" not in flagged_ids
    assert len(findings) == 2