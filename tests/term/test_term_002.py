from termination_exposure.rules import run_rule


def test_term_002():
    rule = {
        "id": "TERM-002",
        "severity": "HIGH",
        "text": {
            "finding": "Final pay events were identified with pay dates before the recorded termination date.",
            "remediation": "Confirm the termination date and final pay date, and ensure finalisation events are dated and flagged consistently.",
        },
    }

    datasets = {
        "terminations": [
            {"employee_id": "E002", "termination_date": "2024-03-31"},
        ],
        "pay_events": [
            {"employee_id": "E002", "pay_date": "2024-03-20", "is_final_pay": "yes"},
        ],
        "employee_master": [],
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E002"
    assert findings[0].rule_code == "TERM-002"