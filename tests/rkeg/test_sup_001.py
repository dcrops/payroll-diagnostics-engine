import pandas as pd

from rkeg.detectors.super_ import run_rule


def test_sup_001_flags_super_rate_outside_expected_tolerance_band():
    rule = {
        "id": "RKEG-SUP-001",
        "severity": "HIGH",
        "config": {
            "target_rate": 0.11,
            "tolerance": 0.01,
        },
        "text": {
            "finding": "Superannuation amounts were identified that fall outside the expected percentage tolerance range of ordinary earnings.",
            "remediation": "Validate super configuration rates and ensure correct super calculations are applied to ordinary time earnings.",
        },
    }

    datasets = {
        "pay_events": pd.DataFrame(
            [
                # 5% -> should flag
                {"employee_id": "E001", "pay_date": "2024-03-15", "gross_amount": 1000, "super_amount": 50},
                # 11% -> should not flag
                {"employee_id": "E002", "pay_date": "2024-03-15", "gross_amount": 1000, "super_amount": 110},
                # 12% within tolerance band 10%-12% -> should not flag
                {"employee_id": "E003", "pay_date": "2024-03-15", "gross_amount": 1000, "super_amount": 120},
                # zero super should not be flagged by this rule
                {"employee_id": "E004", "pay_date": "2024-03-15", "gross_amount": 1000, "super_amount": 0},
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E001" in flagged_ids
    assert "E002" not in flagged_ids
    assert "E003" not in flagged_ids
    assert "E004" not in flagged_ids
    assert len(findings) == 1