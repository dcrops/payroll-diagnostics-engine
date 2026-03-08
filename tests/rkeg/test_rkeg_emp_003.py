import pandas as pd

from rkeg.detectors.employee import run_rule


def test_emp_003_flags_missing_or_invalid_employment_status():
    rule = {
        "id": "RKEG-EMP-003",
        "severity": "HIGH",
        "text": {
            "finding": "Employee records were identified without a valid employment status.",
            "remediation": "Ensure all employee records include a valid employment status and enforce controlled status values across HR and payroll systems.",
        },
    }

    datasets = {
        "employee_master": pd.DataFrame(
            [
                {"employee_id": "E001", "employment_type": ""},
                {"employee_id": "E002", "employment_type": "UNKNOWN"},
                {"employee_id": "E003", "employment_type": "FULL_TIME"},
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E001" in flagged_ids
    assert "E002" in flagged_ids
    assert "E003" not in flagged_ids
    assert len(findings) == 2