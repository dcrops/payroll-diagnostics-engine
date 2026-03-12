import pandas as pd

from lsl_exposure.detectors.registry import run_rule


def test_lsl_004():
    rule = {
        "id": "LSL-004",
        "severity": "MEDIUM",
        "config": {
            "full_years": 10.0,
            "low_floor_units": 20.0,
        },
        "text": {
            "finding": "Long-tenured employees were identified with LSL balances below the configured low-balance floor.",
            "remediation": "Review LSL accrual rules and historical balances to confirm whether the low LSL balance is expected for this employee.",
        },
    }

    state = pd.DataFrame(
        [
            {
                "employee_id": "E001",
                "service_years": 12.0,
                "lsl_balance_units": 5.0,
                "lsl_as_of_date": pd.Timestamp("2024-03-31"),
                "snapshot_date": pd.Timestamp("2024-03-31"),
            },
            {
                "employee_id": "E002",
                "service_years": 12.0,
                "lsl_balance_units": 50.0,
                "lsl_as_of_date": pd.Timestamp("2024-03-31"),
                "snapshot_date": pd.Timestamp("2024-03-31"),
            },
        ]
    )

    findings = run_rule(rule, datasets={}, context={"state": state})

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LSL-004"