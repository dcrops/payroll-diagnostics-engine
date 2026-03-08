import pandas as pd

from lsl_exposure.rules import run_rule


def test_lsl_001():
    rule = {
        "id": "LSL-001",
        "severity": "HIGH",
        "config": {
            "eligibility_years": 7.0,
        },
        "text": {
            "finding": "Employees were identified as meeting the configured LSL eligibility threshold without a corresponding LSL balance record.",
            "remediation": "Confirm whether LSL is being tracked outside the payroll system. If not, review historical service records and determine appropriate LSL accruals or provisions.",
        },
    }

    state = pd.DataFrame(
        [
            {
                "employee_id": "E001",
                "service_years": 10.0,
                "lsl_balance_units": pd.NA,
                "lsl_as_of_date": pd.NaT,
                "snapshot_date": pd.Timestamp("2024-03-31"),
            },
            {
                "employee_id": "E002",
                "service_years": 5.0,
                "lsl_balance_units": pd.NA,
                "lsl_as_of_date": pd.NaT,
                "snapshot_date": pd.Timestamp("2024-03-31"),
            },
        ]
    )

    findings = run_rule(rule, datasets={}, state=state)

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LSL-001"