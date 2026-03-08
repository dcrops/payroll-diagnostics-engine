import pandas as pd

from lsl_exposure.rules import run_rule


def test_lsl_003():
    rule = {
        "id": "LSL-003",
        "severity": "HIGH",
        "config": {
            "eligibility_years": 7.0,
        },
        "text": {
            "finding": "Employees meeting the configured LSL eligibility threshold were identified with an LSL balance of zero.",
            "remediation": "Confirm whether LSL has been intentionally excluded or whether accruals have not been configured correctly for this employee.",
        },
    }

    state = pd.DataFrame(
        [
            {
                "employee_id": "E001",
                "service_years": 9.0,
                "lsl_balance_units": 0.0,
                "lsl_as_of_date": pd.Timestamp("2024-03-31"),
                "snapshot_date": pd.Timestamp("2024-03-31"),
            },
            {
                "employee_id": "E002",
                "service_years": 9.0,
                "lsl_balance_units": 15.0,
                "lsl_as_of_date": pd.Timestamp("2024-03-31"),
                "snapshot_date": pd.Timestamp("2024-03-31"),
            },
        ]
    )

    findings = run_rule(rule, datasets={}, state=state)

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LSL-003"