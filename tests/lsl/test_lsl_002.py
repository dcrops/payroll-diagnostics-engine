import pandas as pd

from lsl_exposure.detectors.registry import run_rule


def test_lsl_002():
    rule = {
        "id": "LSL-002",
        "severity": "HIGH",
        "text": {
            "finding": "Negative LSL balances were identified in the leave snapshot.",
            "remediation": "Review LSL configuration and any manual adjustments. Correct posting or mapping issues and re-run.",
        },
    }

    state = pd.DataFrame(
        [
            {
                "employee_id": "E001",
                "service_years": 8.0,
                "lsl_balance_units": -5.0,
                "lsl_as_of_date": pd.Timestamp("2024-03-31"),
                "snapshot_date": pd.Timestamp("2024-03-31"),
            },
            {
                "employee_id": "E002",
                "service_years": 8.0,
                "lsl_balance_units": 10.0,
                "lsl_as_of_date": pd.Timestamp("2024-03-31"),
                "snapshot_date": pd.Timestamp("2024-03-31"),
            },
        ]
    )

    findings = run_rule(rule, datasets={}, context={"state": state})

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LSL-002"