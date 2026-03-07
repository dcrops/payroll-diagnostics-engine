import pandas as pd

from rkeg.detectors.leave import run_rule


def test_leave_004_flags_leave_ledger_rows_with_missing_event_date():
    rule = {
        "id": "RKEG-LEAVE-004",
        "severity": "HIGH",
        "text": {
            "finding": "Leave ledger records were identified without a valid event date.",
            "remediation": "Ensure all leave ledger transactions include valid event dates and enforce validation in payroll exports.",
        },
    }

    datasets = {
        "leave_ledger": pd.DataFrame(
            [
                {
                    "employee_id": "E401",
                    "event_date": "",
                    "leave_type": "ANNUAL",
                    "event_type": "TAKEN",
                    "units": -7.6,
                },
                {
                    "employee_id": "E402",
                    "event_date": "2024-03-15",
                    "leave_type": "SICK",
                    "event_type": "TAKEN",
                    "units": -7.6,
                },
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E401" in flagged_ids
    assert "E402" not in flagged_ids
    assert len(findings) == 1