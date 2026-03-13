import pandas as pd

from termination_exposure.detectors.registry import run_rule
from termination_exposure.rules import prepare_term_state


def test_term_003():
    rule = {
        "id": "TERM-003",
        "severity": "MEDIUM",
        "config": {
            "max_gap_days": 35,
        },
        "text": {
            "finding": "Termination records were identified where the gap between the last pay event and termination date exceeded the configured threshold.",
            "remediation": "Review the final pay timeline and confirm whether the employee ceased work, remained unpaid for a period, or whether payroll records are incomplete.",
        },
    }

    terminations = pd.DataFrame(
        [
            {"employee_id": "E003", "termination_date": "2024-03-20"},
        ]
    )

    pay_events = pd.DataFrame(
        [
            {"employee_id": "E003", "pay_date": "2024-01-10", "is_final_pay": ""},
        ]
    )

    state = prepare_term_state(
        terminations=terminations,
        pay_events=pay_events,
        employees=pd.DataFrame(),
    )

    datasets = {
        "terminations": terminations,
        "pay_events": pay_events,
        "employee_master": pd.DataFrame(),
    }

    findings = run_rule(rule, datasets, context={"state": state})

    assert len(findings) == 1
    assert findings[0].employee_id == "E003"
    assert findings[0].rule_code == "TERM-003"