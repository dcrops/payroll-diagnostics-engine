# tests/test_emp_005.py

import pandas as pd

from rkeg.detectors.employee import run_rule


def _base_rule():
    return {
        "id": "RKEG-EMP-005",
        "severity": "HIGH",
        "text": {
            "finding": "Employees were identified without a corresponding rate history record.",
            "remediation": "Ensure all employees have rate history records."
        },
    }


def test_emp_005_flags_employee_without_rate_history():
    rule = _base_rule()

    employee_master = pd.DataFrame({
        "employee_id": ["E001", "E002"],
        "name": ["Alice", "Bob"],
    })

    rate_history = pd.DataFrame({
        "employee_id": ["E001"],
        "effective_from": ["2023-01-01"],
        "base_rate": [30.0],
    })

    datasets = {
        "employee_master": employee_master,
        "rate_history": rate_history,
    }

    findings = list(run_rule(rule, datasets))

    # Only E002 should be flagged
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_code == "RKEG-EMP-005"
    assert f.employee_id == "E002"
    assert "E002" in f.evidence


def test_emp_005_no_findings_when_all_have_history():
    rule = _base_rule()

    employee_master = pd.DataFrame({
        "employee_id": ["E001", "E002"],
    })

    rate_history = pd.DataFrame({
        "employee_id": ["E001", "E002"],
        "effective_from": ["2023-01-01", "2023-02-01"],
        "base_rate": [30.0, 32.0],
    })

    datasets = {
        "employee_master": employee_master,
        "rate_history": rate_history,
    }

    findings = list(run_rule(rule, datasets))
    assert findings == []


def test_emp_005_returns_empty_if_rate_history_missing():
    rule = _base_rule()

    employee_master = pd.DataFrame({
        "employee_id": ["E001"],
    })

    datasets = {
        "employee_master": employee_master,
        "rate_history": pd.DataFrame(),  # no history at all
    }

    findings = list(run_rule(rule, datasets))
    assert findings == []