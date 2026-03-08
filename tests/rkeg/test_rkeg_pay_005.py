import pandas as pd

from rkeg.detectors.pay import run_rule


def test_pay_005_adjustment_without_super():
    rule = {
        "id": "RKEG-PAY-005",
        "severity": "HIGH",
        "text": {
            "finding": "Earnings adjustment was identified without a corresponding proportional adjustment to superannuation.",
            "remediation": "Review payroll adjustment processes and ensure superannuation is recalculated on earnings corrections.",
        },
    }

    datasets = {
        "pay_events": pd.DataFrame(
            [
                # Should trigger: negative gross, zero super adjustment
                {
                    "employee_id": "E001",
                    "pay_date": "2024-03-15",
                    "gross_amount": -800,
                    "super_amount": 0,
                    "run_id": "RUN010",
                },
                # Should not trigger: negative gross with non-zero super adjustment
                {
                    "employee_id": "E002",
                    "pay_date": "2024-03-15",
                    "gross_amount": -800,
                    "super_amount": -88,
                    "run_id": "RUN010",
                },
                # Should not trigger: positive gross
                {
                    "employee_id": "E003",
                    "pay_date": "2024-03-15",
                    "gross_amount": 1500,
                    "super_amount": 165,
                    "run_id": "RUN011",
                },
            ]
        )
    }

    findings = run_rule(rule, datasets)

    flagged_ids = {f.employee_id for f in findings}

    assert "E001" in flagged_ids
    assert "E002" not in flagged_ids
    assert "E003" not in flagged_ids
    assert len(findings) == 1