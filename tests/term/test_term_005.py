import pandas as pd

from termination_exposure.detectors.registry import run_rule


def test_term_005():
    rule = {
        "id": "TERM-005",
        "severity": "HIGH",
        "text": {
            "finding": "Termination records were identified without a supporting evidence reference.",
            "remediation": "Record and retain a supporting evidence reference for each termination, such as a resignation notice, termination letter or document identifier.",
        },
    }

    datasets = {
        "terminations": pd.DataFrame(
            [
                {
                    "employee_id": "E005",
                    "termination_date": "2024-03-20",
                    "termination_type": "RESIGNATION",
                    "termination_reason": "Personal",
                    "evidence_ref": "",
                }
            ]
        ),
        "employee_master": pd.DataFrame(),
        "pay_events": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={})

    assert len(findings) == 1
    assert findings[0].employee_id == "E005"
    assert findings[0].rule_code == "TERM-005"