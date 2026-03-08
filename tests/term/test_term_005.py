from termination_exposure.rules import run_rule


def test_term_005():
    rule = {
        "id": "TERM-005",
        "severity": "HIGH",
        "text": {
            "finding": "Termination records were identified without a supporting evidence reference.",
            "remediation": "Record and retain a supporting evidence reference for each termination, such as a resignation notice, termination letter or document identifier.",
        },
    }

    datasets = {
        "terminations": [
            {"employee_id": "E005", "termination_date": "2024-03-31", "evidence_ref": ""},
        ],
        "pay_events": [],
        "employee_master": [],
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].employee_id == "E005"
    assert findings[0].rule_code == "TERM-005"