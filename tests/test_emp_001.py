import pandas as pd

from rkeg.detectors.employee import run_rule


def test_emp_001_flags_records_without_employee_master():
    rule = {
        "id": "RKEG-EMP-001",
        "severity": "HIGH",
        "text": {
            "finding": "Payroll and/or leave records were identified for individuals who do not have a corresponding employee master record.",
            "remediation": "Ensure all individuals referenced in payroll and leave systems have a corresponding employee master record and enforce validation before processing.",
        },
    }

    datasets = {
        "employee_master": pd.DataFrame(
            [
                {"employee_id": "E001"},
                {"employee_id": "E002"},
            ]
        ),
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E001"},
                {"employee_id": "ORPHAN001"},
            ]
        ),
        "leave_ledger": pd.DataFrame(
            [
                {"employee_id": "E002"},
                {"employee_id": "ORPHAN002"},
            ]
        ),
        "leave_snapshot": pd.DataFrame(),
        "terminations": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "ORPHAN001" in flagged_ids
    assert "ORPHAN002" in flagged_ids
    assert "E001" not in flagged_ids
    assert "E002" not in flagged_ids
    assert len(findings) == 2