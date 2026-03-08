import pandas as pd

from leave_leakage.rules import run_rule


def test_leave_003():
    rule = {
        "id": "LEAVE-003",
        "severity": "HIGH",
        "text": {
            "finding": "Leave taken events were identified with event dates before the employee's recorded start date.",
            "remediation": "Verify the employee start date in HR/payroll and the leave event date in the ledger. If either is incorrect due to migration or backdating, correct the source record and re-run. If intentional, document the reason and approval.",
        },
    }

    datasets = {
        "employee_master": pd.DataFrame(
            [
                {
                    "employee_id": "E001",
                    "employment_type": "FULL_TIME",
                    "start_date": "2024-04-01",
                }
            ]
        ),
        "leave_ledger": pd.DataFrame(
            [
                {
                    "employee_id": "E001",
                    "leave_type": "ANNUAL",
                    "event_date": pd.Timestamp("2024-03-15"),
                    "units": -8.0,
                    "event_type": "TAKEN",
                }
            ]
        ),
        "leave_snapshot": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LEAVE-003"