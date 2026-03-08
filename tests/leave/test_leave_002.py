import pandas as pd

from leave_leakage.rules import run_rule


def test_leave_002():
    rule = {
        "id": "LEAVE-002",
        "severity": "MEDIUM",
        "text": {
            "finding": "Leave ledger events were identified with unit signs that are inconsistent with the event type.",
            "remediation": "Review the leave ledger configuration and data ingestion rules to confirm expected sign conventions for TAKEN and ACCRUAL events. Check whether the entry reflects a system configuration issue, import mapping error, or manual adjustment.",
        },
    }

    datasets = {
        "leave_snapshot": pd.DataFrame(),
        "leave_ledger": pd.DataFrame(
            [
                {
                    "employee_id": "E001",
                    "leave_type": "ANNUAL",
                    "event_date": pd.Timestamp("2024-03-10"),
                    "units": 8.0,
                    "event_type": "TAKEN",
                },
                {
                    "employee_id": "E002",
                    "leave_type": "ANNUAL",
                    "event_date": pd.Timestamp("2024-03-10"),
                    "units": 8.0,
                    "event_type": "ACCRUAL",
                },
            ]
        ),
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LEAVE-002"