import pandas as pd
from rkeg.detectors.super_ import run_rule


def test_sup_003_flags_late_payment():
    # Arrange
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
        "config": {
            "days_after_period_end": 30
        },
        "text": {
            "finding": "Late super payment detected.",
            "remediation": "Fix payment timing."
        }
    }

    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "payment_date": ["2024-03-15"],  # 43 days after Jan 31
        "super_amount": [1000.00]
    })

    datasets = {
        "super_payments": super_payments
    }

    # Act
    findings = list(run_rule(rule, datasets))

    # Assert
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_code == "RKEG-SUP-003"
    assert "Late super payment detected." in finding.message
    assert "days_late" in finding.evidence

def test_sup_003_does_not_flag_on_time_payment():
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
        "config": {
            "days_after_period_end": 30
        },
        "text": {
            "finding": "Late super payment detected.",
            "remediation": "Fix payment timing."
        }
    }

    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "payment_date": ["2024-02-15"],  # Within 30 days
        "super_amount": [1000.00]
    })

    datasets = {
        "super_payments": super_payments
    }

    findings = list(run_rule(rule, datasets))

    assert len(findings) == 0

def test_sup_003_respects_config_window():
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
        "config": {
            "days_after_period_end": 60
        },
        "text": {
            "finding": "Late super payment detected.",
            "remediation": "Fix payment timing."
        }
    }

    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "payment_date": ["2024-03-15"],  # ~43 days after Jan 31
        "super_amount": [1000.00]
    })

    datasets = {
        "super_payments": super_payments
    }

    findings = list(run_rule(rule, datasets))

    # Should NOT flag because 60-day window
    assert len(findings) == 0

def test_sup_003_uses_default_window_when_config_missing():
    # No config block at all
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
        "text": {
            "finding": "Late super payment detected.",
            "remediation": "Fix payment timing."
        }
    }

    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "payment_date": ["2024-03-15"],  # ~43 days after
        "super_amount": [1000.00]
    })

    datasets = {"super_payments": super_payments}

    findings = list(run_rule(rule, datasets))

    # Default should be 30 days, so this *should* be flagged as late
    assert len(findings) == 1

def test_sup_003_returns_empty_if_dataset_missing():
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
    }

    datasets = {
        # "super_payments" intentionally omitted
    }

    findings = list(run_rule(rule, datasets))

    assert findings == []


def test_sup_003_returns_empty_if_dataset_empty():
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
    }

    super_payments = pd.DataFrame(columns=["employee_id", "period_end_date", "payment_date"])
    datasets = {"super_payments": super_payments}

    findings = list(run_rule(rule, datasets))

    assert findings == []

def test_sup_003_handles_missing_employee_id_column():
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
        "config": {"days_after_period_end": 30},
        "text": {
            "finding": "Late super payment detected.",
            "remediation": "Fix payment timing."
        }
    }

    # Note: no employee_id column here
    super_payments = pd.DataFrame({
        "period_end_date": ["2024-01-31"],
        "payment_date": ["2024-03-15"],
        "super_amount": [1000.00]
    })

    datasets = {"super_payments": super_payments}

    findings = list(run_rule(rule, datasets))

    assert len(findings) == 1
    f = findings[0]
    # We expect employee_id to be empty string when column is missing
    assert f.employee_id == ""
    assert "Employee [not supplied]" in f.message

def test_sup_003_ignores_rows_with_unparseable_dates():
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
        "config": {"days_after_period_end": 30},
        "text": {
            "finding": "Late super payment detected.",
            "remediation": "Fix payment timing."
        }
    }

    super_payments = pd.DataFrame({
        "employee_id": ["E001", "E002"],
        "period_end_date": ["2024-01-31", "not-a-date"],
        "payment_date": ["2024-03-15", "also-bad"],
        "super_amount": [1000.00, 500.00]
    })

    datasets = {"super_payments": super_payments}

    findings = list(run_rule(rule, datasets))

    # Only the valid row for E001 should be considered and flagged
    assert len(findings) == 1
    assert findings[0].employee_id == "E001"

def test_sup_003_evidence_contains_days_late_and_config():
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
        "config": {"days_after_period_end": 30},
        "text": {
            "finding": "Late super payment detected.",
            "remediation": "Fix payment timing."
        }
    }

    super_payments = pd.DataFrame({
        "employee_id": ["E001"],
        "period_end_date": ["2024-01-31"],
        "payment_date": ["2024-03-15"],
        "super_amount": [1000.00]
    })

    datasets = {"super_payments": super_payments}

    findings = list(run_rule(rule, datasets))

    assert len(findings) == 1
    f = findings[0]

    assert f.diff_units == "days_late"
    assert "days_after_period_end=30" in f.evidence
    assert "days_late=" in f.evidence

def test_sup_003_only_flags_late_rows_when_mixed():
    rule = {
        "id": "RKEG-SUP-003",
        "severity": "HIGH",
        "config": {"days_after_period_end": 30},
        "text": {
            "finding": "Late super payment detected.",
            "remediation": "Fix payment timing."
        }
    }

    super_payments = pd.DataFrame({
        "employee_id": ["E001", "E002"],
        "period_end_date": ["2024-01-31", "2024-01-31"],
        "payment_date": ["2024-02-15", "2024-03-15"],  # E001 on time, E002 late
        "super_amount": [1000.00, 800.00]
    })

    datasets = {"super_payments": super_payments}

    findings = list(run_rule(rule, datasets))

    assert len(findings) == 1
    assert findings[0].employee_id == "E002"