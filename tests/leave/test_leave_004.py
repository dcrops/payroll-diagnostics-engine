import pandas as pd

from leave_leakage.rules import run_rule


def test_leave_004():
    rule = {
        "id": "LEAVE-004",
        "severity": "HIGH",
        "text": {
            "finding": "Leave accrual events were identified for employees recorded as casual.",
            "remediation": "Confirm the employee’s employment type in HR/payroll and review leave accrual configuration. If the employee is incorrectly classified as casual, correct the classification. If the accrual is unintended, disable or reverse the accrual and document the remediation.",
        },
    }

    datasets = {
        "employee_master": pd.DataFrame(
            [
                {
                    "employee_id": "E001",
                    "employment_type": "CASUAL",
                }
            ]
        ),
        "leave_ledger": pd.DataFrame(
            [
                {
                    "employee_id": "E001",
                    "leave_type": "ANNUAL",
                    "event_date": pd.Timestamp("2024-03-01"),
                    "units": 8.0,
                    "event_type": "ACCRUAL",
                }
            ]
        ),
        "leave_snapshot": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LEAVE-004"