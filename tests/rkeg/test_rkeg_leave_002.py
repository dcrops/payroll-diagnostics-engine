import pandas as pd
from rkeg.detectors.leave import run_rule


def _base_rule():
    return {
        "id": "RKEG-LEAVE-002",
        "severity": "HIGH",
        "config": {"tolerance_units": 0.5},
        "text": {
            "finding": "Leave snapshot drift detected.",
            "remediation": "Investigate discrepancies."
        }
    }


def test_leave_002_flags_mismatch_above_tolerance():
    # Snapshot says 143, ledger reconstructs 136 → diff 7 > 0.5 → flag
    rule = _base_rule()

    leave_snapshot = pd.DataFrame({
        "employee_id": ["E001"],
        "leave_type": ["ANNUAL"],
        "as_of_date": ["2024-03-31"],
        "balance_units": [143.0],
    })

    leave_ledger = pd.DataFrame({
        "employee_id": ["E001", "E001", "E001"],
        "leave_type": ["ANNUAL", "ANNUAL", "ANNUAL"],
        "event_date": ["2023-01-01", "2023-06-15", "2024-02-15"],
        "units": [152.0, -8.0, -8.0],
        "event_type": ["ACCRUAL", "TAKEN", "TAKEN"],
    })

    datasets = {
        "leave_snapshot": leave_snapshot,
        "leave_ledger": leave_ledger,
    }

    findings = list(run_rule(rule, datasets))

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_code == "RKEG-LEAVE-002"
    assert f.employee_id == "E001"
    assert f.leave_type == "ANNUAL"
    assert "143.00" in f.message
    assert "136.00" in f.message


def test_leave_002_does_not_flag_within_tolerance():
    # Snapshot says 136.2, ledger 136 → diff 0.2 <= 0.5 → no finding
    rule = _base_rule()

    leave_snapshot = pd.DataFrame({
        "employee_id": ["E001"],
        "leave_type": ["ANNUAL"],
        "as_of_date": ["2024-03-31"],
        "balance_units": [136.2],
    })

    leave_ledger = pd.DataFrame({
        "employee_id": ["E001", "E001", "E001"],
        "leave_type": ["ANNUAL", "ANNUAL", "ANNUAL"],
        "event_date": ["2023-01-01", "2023-06-15", "2024-02-15"],
        "units": [152.0, -8.0, -8.0],
        "event_type": ["ACCRUAL", "TAKEN", "TAKEN"],
    })

    datasets = {
        "leave_snapshot": leave_snapshot,
        "leave_ledger": leave_ledger,
    }

    findings = list(run_rule(rule, datasets))

    assert findings == []


def test_leave_002_handles_multiple_employees():
    rule = _base_rule()

    leave_snapshot = pd.DataFrame({
        "employee_id": ["E001", "E002"],
        "leave_type": ["ANNUAL", "ANNUAL"],
        "as_of_date": ["2024-03-31", "2024-03-31"],
        "balance_units": [143.0, 100.0],
    })

    leave_ledger = pd.DataFrame({
        "employee_id": ["E001", "E001", "E001", "E002"],
        "leave_type": ["ANNUAL", "ANNUAL", "ANNUAL", "ANNUAL"],
        "event_date": ["2023-01-01", "2023-06-15", "2024-02-15", "2023-01-01"],
        "units": [152.0, -8.0, -8.0, 100.0],
        "event_type": ["ACCRUAL", "TAKEN", "TAKEN", "ACCRUAL"],
    })

    datasets = {
        "leave_snapshot": leave_snapshot,
        "leave_ledger": leave_ledger,
    }

    findings = list(run_rule(rule, datasets))

    # E001 should be flagged (143 vs 136), E002 should be fine (100 vs 100)
    assert len(findings) == 1
    assert findings[0].employee_id == "E001"