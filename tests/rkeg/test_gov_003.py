import pandas as pd

from rkeg.detectors.governance import run_rule


def test_gov_003_flags_high_override_volume_relative_to_pay_events():
    rule = {
        "id": "RKEG-GOV-003",
        "severity": "MEDIUM",
        "config": {"threshold_ratio": 0.10},
        "text": {
            "finding": "A high volume of manual overrides was identified relative to the total number of pay events processed.",
            "remediation": "Review the drivers of manual overrides, address underlying configuration or process issues, and reduce reliance on manual adjustments where possible.",
        },
    }

    datasets = {
        "pay_events": pd.DataFrame([{"employee_id": f"E{i}", "pay_date": "2024-03-01"} for i in range(20)]),
        "pay_overrides": pd.DataFrame(
            [
                {"employee_id": "E1"},
                {"employee_id": "E2"},
                {"employee_id": "E3"},
            ]
        ),
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].rule_code == "RKEG-GOV-003"