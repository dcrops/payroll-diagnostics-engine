import pandas as pd

from rkeg.detectors.employee import run_rule


def test_emp_002_flags_missing_or_invalid_start_date():
    rule = {
        "id": "RKEG-EMP-002",
        "severity": "HIGH",
        "text": {
            "finding": "Employee records were identified without a recorded employment start date.",
            "remediation": "Record and retain employment commencement dates for all employees and enforce this as a mandatory field in onboarding processes.",
        },
    }

    datasets = {
        "employee_master": pd.DataFrame(
            [
                {"employee_id": "E001", "start_date": ""},
                {"employee_id": "E002", "start_date": "not_a_date"},
                {"employee_id": "E003", "start_date": "2024-01-15"},
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E001" in flagged_ids
    assert "E002" in flagged_ids
    assert "E003" not in flagged_ids
    assert len(findings) == 2