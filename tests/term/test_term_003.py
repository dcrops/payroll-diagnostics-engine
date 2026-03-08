from termination_exposure.rules import run_rule


def test_term_003():
    rule = {
        "id": "TERM-003",
        "severity": "MEDIUM",
        "config": {"max_gap_days": 35},
        "text": {
            "finding": "Termination records were identified where the gap between the last pay event and termination date exceeded the configured threshold.",
            "remediation": "Review the final pay timeline and confirm whether the employee ceased work, remained unpaid for a period, or whether payroll records are incomplete.",
        },
    }

    datasets = {
        "terminations": [
            {"employee_id": "E003", "termination_date": "2024-03-31"},
        ],
        "pay_events": [
            {"employee_id": "E003", "pay_date": "2024-01-15", "is_final_pay": ""},
        ],
        "employee_master": [],
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E003"
    assert findings[0].rule_code == "TERM-003"