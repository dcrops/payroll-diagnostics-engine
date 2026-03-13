import pandas as pd

from termination_exposure.detectors.registry import run_rule


def test_term_008():
    rule = {
        "id": "TERM-008",
        "severity": "HIGH",
        "text": {
            "finding": "LSL ledger movement was recorded after the employee termination date.",
            "remediation": "Review termination timing and LSL processing history to confirm whether the movement is valid and properly evidenced.",
        },
    }

    datasets = {
        "terminations": pd.DataFrame(
            [
                {
                    "employee_id": "T008",
                    "termination_date": "2024-03-01",
                }
            ]
        ),
        "leave_ledger": pd.DataFrame(
            [
                {
                    "employee_id": "T008",
                    "leave_type": "LSL",
                    "event_date": "2024-03-15",
                    "units": 8,
                    "event_type": "ACCRUAL",
                }
            ]
        ),
        "leave_snapshot": pd.DataFrame(),
        "pay_events": pd.DataFrame(),
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={})

    assert len(findings) == 1
    assert findings[0].employee_id == "T008"
    assert findings[0].leave_type == "LSL"
    assert findings[0].rule_code == "TERM-008"