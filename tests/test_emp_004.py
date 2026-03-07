import pandas as pd

from rkeg.detectors.employee import run_rule


def test_emp_004_flags_terminated_employees_still_marked_active():
    rule = {
        "id": "RKEG-EMP-004",
        "severity": "HIGH",
        "text": {
            "finding": "Employees were identified with recorded terminations while still appearing as active in the employee master data.",
            "remediation": "Ensure employee master records are promptly updated following termination and reconcile termination events against employee status as part of offboarding controls.",
        },
    }

    datasets = {
        "employee_master": pd.DataFrame(
            [
                {"employee_id": "E001", "employment_type": "FULL_TIME"},
                {"employee_id": "E002", "employment_type": "CASUAL"},
                {"employee_id": "E003", "employment_type": "TERMINATED"},
            ]
        ),
        "terminations": pd.DataFrame(
            [
                {"employee_id": "E001"},
                {"employee_id": "E003"},
            ]
        ),
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E001" in flagged_ids
    assert "E003" not in flagged_ids
    assert "E002" not in flagged_ids
    assert len(findings) == 1