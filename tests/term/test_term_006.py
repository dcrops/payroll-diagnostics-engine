import pandas as pd

from termination_exposure.detectors.registry import run_rule


def test_term_006():
    rule = {
        "id": "TERM-006",
        "severity": "MEDIUM",
        "config": {
            "window_before_days": 14,
            "window_after_days": 30,
        },
        "text": {
            "finding": "Termination records were identified with nearby pay events but no clearly flagged final pay event.",
            "remediation": "Ensure final pay events are clearly flagged in payroll outputs and reconcile pay events around termination dates to confirm which event represents finalisation.",
        },
    }

    datasets = {
        "terminations": pd.DataFrame(
            [
                {
                    "employee_id": "E006",
                    "termination_date": "2024-03-20",
                }
            ]
        ),
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E006", "pay_date": "2024-03-18", "is_final_pay": ""},
                {"employee_id": "E006", "pay_date": "2024-03-27", "is_final_pay": ""},
            ]
        ),
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={})

    assert len(findings) == 1
    assert findings[0].employee_id == "E006"
    assert findings[0].rule_code == "TERM-006"