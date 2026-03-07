import pandas as pd

from rkeg.detectors.super_ import run_rule


def test_sup_006_flags_multiple_default_super_funds():
    rule = {
        "id": "RKEG-SUP-006",
        "severity": "MEDIUM",
        "text": {
            "finding": "Employees were identified with multiple default superannuation fund records.",
            "remediation": "Ensure each employee has a single valid default super fund and reconcile conflicting records.",
        },
    }

    datasets = {
        "employee_super": pd.DataFrame(
            [
                {"employee_id": "E301", "fund_name": "AustralianSuper", "fund_type": "DEFAULT", "status": "ACTIVE"},
                {"employee_id": "E301", "fund_name": "Hostplus", "fund_type": "DEFAULT", "status": "ACTIVE"},
                {"employee_id": "E302", "fund_name": "REST", "fund_type": "DEFAULT", "status": "ACTIVE"},
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E301" in flagged_ids
    assert "E302" not in flagged_ids
    assert len(findings) == 1