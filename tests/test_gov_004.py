import pandas as pd

from rkeg.detectors.governance import run_rule


def test_gov_004_flags_override_rows_with_missing_timestamp():
    rule = {
        "id": "RKEG-GOV-004",
        "severity": "MEDIUM",
        "text": {
            "finding": "Payroll override records were identified without a valid timestamp.",
            "remediation": "Ensure override records include timestamps and enforce system controls to prevent incomplete override records.",
        },
    }

    datasets = {
        "pay_overrides": pd.DataFrame(
            [
                {
                    "employee_id": "E501",
                    "pay_date": "2024-02-20",
                    "override_type": "RATE",
                    "field_overridden": "base_rate",
                    "original_value": 30,
                    "new_value": 35,
                    "reason_code": "ADJUSTMENT",
                    "approval_status": "APPROVED",
                    "approved_by": "HR_MANAGER",
                    "created_by": "PAYROLL_ADMIN",
                    "created_at": "",
                },
                {
                    "employee_id": "E502",
                    "pay_date": "2024-02-20",
                    "override_type": "HOURS",
                    "field_overridden": "hours_worked",
                    "original_value": 38,
                    "new_value": 42,
                    "reason_code": "CORRECTION",
                    "approval_status": "APPROVED",
                    "approved_by": "PAYROLL_MANAGER",
                    "created_by": "PAYROLL_ADMIN",
                    "created_at": "2024-02-14T09:20:00",
                },
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E501" in flagged_ids
    assert "E502" not in flagged_ids
    assert len(findings) == 1
    