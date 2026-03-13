import pandas as pd

from termination_exposure.detectors.registry import run_rule


def test_term_009():
    rule = {
        "id": "TERM-009",
        "severity": "HIGH",
        "config": {
            "material_balance_units": 10,
            "snapshot_grace_days": 14,
            "closure_event_types": ["TAKEN", "ADJUSTMENT", "PAYOUT"],
        },
        "text": {
            "finding": "A terminated employee retains a material LSL balance without an apparent post-termination closure trail.",
            "remediation": "Review final pay processing, LSL ledger activity and balance treatment to confirm whether the employee’s LSL position was properly closed.",
        },
    }

    datasets = {
        "terminations": pd.DataFrame(
            [
                {
                    "employee_id": "T009",
                    "termination_date": "2024-03-01",
                }
            ]
        ),
        "leave_snapshot": pd.DataFrame(
            [
                {
                    "employee_id": "T009",
                    "leave_type": "LSL",
                    "as_of_date": "2024-03-31",
                    "balance_units": 30,
                }
            ]
        ),
        "leave_ledger": pd.DataFrame(
            [
                {
                    "employee_id": "T009",
                    "leave_type": "LSL",
                    "event_date": "2024-02-15",
                    "units": 8,
                    "event_type": "ACCRUAL",
                }
            ]
        ),
        "pay_events": pd.DataFrame(),
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={})

    assert len(findings) == 1
    assert findings[0].employee_id == "T009"
    assert findings[0].leave_type == "LSL"
    assert findings[0].rule_code == "TERM-009"