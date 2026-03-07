import pandas as pd

from rkeg.detectors.leave import run_rule


def _base_rule():
    return {
        "id": "RKEG-LEAVE-001",
        "severity": "HIGH",
        "text": {
            "finding": "Leave ledger movements were detected without corresponding payroll transactions.",
            "remediation": "Reconcile leave taken entries to payroll transactions.",
        },
    }


def test_leave_001_flags_taken_without_same_day_pay_event():
    rule = _base_rule()

    leave_ledger = pd.DataFrame({
        "employee_id": ["E004"],
        "leave_type": ["ANNUAL"],
        "event_date": ["2024-03-20"],
        "units": [-8.0],
        "event_type": ["TAKEN"],
    })

    # Pay event exists for E004, but on a different date (03-15), not 03-20
    pay_events = pd.DataFrame({
        "employee_id": ["E004"],
        "pay_date": ["2024-03-15"],
        "gross_amount": [2000],
    })

    datasets = {"leave_ledger": leave_ledger, "pay_events": pay_events}

    findings = list(run_rule(rule, datasets))

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_code == "RKEG-LEAVE-001"
    assert f.employee_id == "E004"
    assert "matched_pay_event_on_same_date=False" in f.evidence


def test_leave_001_does_not_flag_when_same_day_pay_event_exists():
    rule = _base_rule()

    leave_ledger = pd.DataFrame({
        "employee_id": ["E001"],
        "leave_type": ["ANNUAL"],
        "event_date": ["2024-03-15"],
        "units": [-8.0],
        "event_type": ["TAKEN"],
    })

    pay_events = pd.DataFrame({
        "employee_id": ["E001"],
        "pay_date": ["2024-03-15"],
        "gross_amount": [6000],
    })

    datasets = {"leave_ledger": leave_ledger, "pay_events": pay_events}

    findings = list(run_rule(rule, datasets))
    assert findings == []


def test_leave_001_ignores_non_taken_events():
    rule = _base_rule()

    # ACCRUAL with no matching pay should NOT trigger LEAVE-001
    leave_ledger = pd.DataFrame({
        "employee_id": ["E001"],
        "leave_type": ["ANNUAL"],
        "event_date": ["2024-03-15"],
        "units": [10.0],
        "event_type": ["ACCRUAL"],
    })

    pay_events = pd.DataFrame({
        "employee_id": ["E001"],
        "pay_date": ["2024-03-15"],
        "gross_amount": [6000],
    })

    datasets = {"leave_ledger": leave_ledger, "pay_events": pay_events}

    findings = list(run_rule(rule, datasets))
    assert findings == []