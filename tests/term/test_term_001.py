import pandas as pd

from termination_exposure.detectors.registry import run_rule


def test_term_001():
    rule = {
        "id": "TERM-001",
        "severity": "HIGH",
        "text": {
            "finding": "Termination records were identified with no pay event on or after the recorded termination date.",
            "remediation": "Review termination processing records and confirm whether final pay was processed. If it was, ensure the relevant pay event is clearly identifiable in payroll data.",
        },
    }

    datasets = {
        "terminations": pd.DataFrame(
            [
                {"employee_id": "E001", "termination_date": "2024-03-31"},
            ]
        ),
        "pay_events": pd.DataFrame(
            [
                {"employee_id": "E001", "pay_date": "2024-03-15", "is_final_pay": ""},
            ]
        ),
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={})

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "TERM-001"