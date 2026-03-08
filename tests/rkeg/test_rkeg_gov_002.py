import pandas as pd

from rkeg.detectors.governance import run_rule


def test_gov_002_flags_missing_reason_or_approval():
    rule = {
        "id": "RKEG-GOV-002",
        "severity": "MEDIUM",
        "text": {
            "finding": "Payroll overrides were identified with missing or incomplete reason or approval information.",
            "remediation": "Enforce mandatory reason and approval fields for payroll overrides and ensure incomplete records cannot be finalised.",
        },
    }

    datasets = {
        "pay_overrides": pd.DataFrame(
            [
                {
                    "employee_id": "E601",
                    "pay_date": "2024-02-25",
                    "override_type": "RATE",
                    "field_overridden": "base_rate",
                    "original_value": 28,
                    "new_value": 30,
                    "reason_code": "",
                    "approval_status": "APPROVED",
                    "approved_by": "HR_MANAGER",
                    "created_by": "PAYROLL_ADMIN",
                    "created_at": "2024-02-20T10:15:00",
                },
                {
                    "employee_id": "E602",
                    "pay_date": "2024-02-25",
                    "override_type": "HOURS",
                    "field_overridden": "hours_worked",
                    "original_value": 38,
                    "new_value": 42,
                    "reason_code": "CORRECTION",
                    "approval_status": "APPROVED",
                    "approved_by": "PAYROLL_MANAGER",
                    "created_by": "PAYROLL_ADMIN",
                    "created_at": "2024-02-20T09:20:00",
                },
            ]
        )
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E601"