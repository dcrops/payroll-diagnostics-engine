from termination_exposure.rules import run_rule


def test_term_004():
    rule = {
        "id": "TERM-004",
        "severity": "MEDIUM",
        "text": {
            "finding": "Termination records were identified with missing or inconsistent termination type or reason information.",
            "remediation": "Ensure termination type and reason are captured consistently across HR and payroll data and reconcile conflicting values.",
        },
    }

    datasets = {
        "terminations": [
            {"employee_id": "E004", "termination_date": "2024-03-31", "termination_reason": ""},
        ],
        "pay_events": [],
        "employee_master": [],
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E004"
    assert findings[0].rule_code == "TERM-004"