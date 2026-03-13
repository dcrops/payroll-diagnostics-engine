import pandas as pd

from termination_exposure.detectors.registry import run_rule


def test_term_002():
    rule = {
        "id": "TERM-002",
        "severity": "HIGH",
        "text": {
            "finding": "Final pay events were identified with pay dates before the recorded termination date.",
            "remediation": "Confirm the termination date and final pay date, and ensure finalisation events are dated and flagged consistently.",
        },
    }

    datasets = {
        "terminations": pd.DataFrame(
            [
                {"employee_id": "E002", "termination_date": "2024-03-20"},
            ]
        ),
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E002", "pay_date": "2024-03-15", "is_final_pay": "yes"},
            ]
        ),
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={})

    assert len(findings) == 1
    assert findings[0].employee_id == "E002"
    assert findings[0].rule_code == "TERM-002"