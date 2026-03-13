import pandas as pd

from termination_exposure.detectors.registry import run_rule


def test_term_004():
    rule = {
        "id": "TERM-004",
        "severity": "MEDIUM",
        "text": {
            "finding": "Termination records were identified with missing or inconsistent termination type or reason information.",
            "remediation": "Ensure termination type and reason are captured consistently across HR and payroll data and reconcile conflicting values.",
        },
    }

    datasets = {
        "terminations": pd.DataFrame(
            [
                {
                    "employee_id": "E004",
                    "termination_date": "2024-03-20",
                    "termination_type": "",
                    "termination_reason": "",
                }
            ]
        ),
        "employee_master": pd.DataFrame(),
        "pay_events": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={})

    assert len(findings) == 1
    assert findings[0].employee_id == "E004"
    assert findings[0].rule_code == "TERM-004"