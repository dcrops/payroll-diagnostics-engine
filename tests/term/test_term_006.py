from termination_exposure.rules import run_rule


def test_term_006():
    rule = {
        "id": "TERM-006",
        "severity": "MEDIUM",
        "config": {
            "window_before_days": 14,
            "window_after_days": 30,
        },
        "text": {
            "finding": "Termination records were identified with nearby pay events but no clearly flagged final pay event.",
            "remediation": "Ensure final pay events are clearly flagged in payroll outputs and reconcile pay events around termination dates to confirm which event represents finalisation.",
        },
    }

    datasets = {
        "terminations": [
            {"employee_id": "E006", "termination_date": "2024-03-31"},
        ],
        "pay_events": [
            {"employee_id": "E006", "pay_date": "2024-03-25", "gross_amount": "1500", "is_final_pay": ""},
            {"employee_id": "E006", "pay_date": "2024-04-10", "gross_amount": "500", "is_final_pay": ""},
        ],
        "employee_master": [],
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E006"
    assert findings[0].rule_code == "TERM-006"