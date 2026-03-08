import pandas as pd

from leave_leakage.rules import run_rule


def test_leave_001():
    rule = {
        "id": "LEAVE-001",
        "severity": "HIGH",
        "text": {
            "finding": "Leave snapshot balances were identified with negative balance values.",
            "remediation": "Review the employee’s leave ledger and recent payroll adjustments to confirm whether the negative balance reflects a data error, timing difference, or an approved leave arrangement.",
        },
    }

    datasets = {
        "leave_snapshot": pd.DataFrame(
            [
                {
                    "employee_id": "E001",
                    "leave_type": "ANNUAL",
                    "as_of_date": pd.Timestamp("2024-03-31"),
                    "balance_units": -4.0,
                },
                {
                    "employee_id": "E002",
                    "leave_type": "ANNUAL",
                    "as_of_date": pd.Timestamp("2024-03-31"),
                    "balance_units": 10.0,
                },
            ]
        ),
        "leave_ledger": pd.DataFrame(),
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LEAVE-001"