import pandas as pd

from termination_exposure.detectors.registry import run_rule


def test_term_007():
    rule = {
        "id": "TERM-007",
        "severity": "HIGH",
        "config": {
            "material_balance_units": 10,
            "snapshot_grace_days": 14,
        },
        "text": {
            "finding": "A terminated employee retains a material LSL balance in the snapshot extract.",
            "remediation": "Confirm whether the employee’s LSL was paid or intentionally remains open, and ensure the snapshot reflects the correct post-termination position.",
        },
    }

    datasets = {
        "terminations": pd.DataFrame(
            [
                {
                    "employee_id": "T007",
                    "termination_date": "2024-03-01",
                }
            ]
        ),
        "leave_snapshot": pd.DataFrame(
            [
                {
                    "employee_id": "T007",
                    "leave_type": "LSL",
                    "as_of_date": "2024-03-31",
                    "balance_units": 25,
                }
            ]
        ),
        "leave_ledger": pd.DataFrame(),
        "pay_events": pd.DataFrame(),
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={})

    assert len(findings) == 1
    assert findings[0].employee_id == "T007"
    assert findings[0].leave_type == "LSL"
    assert findings[0].rule_code == "TERM-007"