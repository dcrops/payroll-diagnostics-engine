import pandas as pd
from rkeg.detectors.leave import run_rule


def _base_rule():
    return {
        "id": "RKEG-LEAVE-003",
        "severity": "HIGH",
        "config": {"min_balance_units": 10.0},
        "text": {
            "finding": "No ledger history.",
            "remediation": "Investigate history coverage."
        }
    }


def test_leave_003_flags_when_no_ledger_history_and_balance_large():
    rule = _base_rule()

    leave_snapshot = pd.DataFrame({
        "employee_id": ["ORPHAN001"],
        "leave_type": ["ANNUAL"],
        "as_of_date": ["2024-03-31"],
        "balance_units": [200.0],
    })

    leave_ledger = pd.DataFrame({
        # No matching ORPHAN001 rows
        "employee_id": ["E001"],
        "leave_type": ["ANNUAL"],
        "event_date": ["2023-01-01"],
        "units": [100.0],
        "event_type": ["ACCRUAL"],
    })

    datasets = {
        "leave_snapshot": leave_snapshot,
        "leave_ledger": leave_ledger,
    }

    findings = list(run_rule(rule, datasets))
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_code == "RKEG-LEAVE-003"
    assert f.employee_id == "ORPHAN001"


def test_leave_003_does_not_flag_when_ledger_history_exists():
    rule = _base_rule()

    leave_snapshot = pd.DataFrame({
        "employee_id": ["E001"],
        "leave_type": ["ANNUAL"],
        "as_of_date": ["2024-03-31"],
        "balance_units": [200.0],
    })

    leave_ledger = pd.DataFrame({
        "employee_id": ["E001"],
        "leave_type": ["ANNUAL"],
        "event_date": ["2023-01-01"],
        "units": [100.0],
        "event_type": ["ACCRUAL"],
    })

    datasets = {
        "leave_snapshot": leave_snapshot,
        "leave_ledger": leave_ledger,
    }

    findings = list(run_rule(rule, datasets))
    assert findings == []


def test_leave_003_respects_min_balance_threshold():
    rule = _base_rule()

    leave_snapshot = pd.DataFrame({
        "employee_id": ["ORPHAN002"],
        "leave_type": ["ANNUAL"],
        "as_of_date": ["2024-03-31"],
        "balance_units": [5.0],  # below threshold
    })

    datasets = {
        "leave_snapshot": leave_snapshot,
        "leave_ledger": pd.DataFrame(),  # no ledger at all
    }

    findings = list(run_rule(rule, datasets))
    assert findings == []