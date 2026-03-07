from rkeg.detectors.governance import run_rule


def test_gov_001_flags_missing_override_log():
    rule = {
        "id": "RKEG-GOV-001",
        "severity": "MEDIUM",
        "text": {
            "finding": "No structured override or exception log was provided for manual payroll adjustments.",
            "remediation": "Introduce a basic override register or system-based workflow to record all manual payroll changes, including who made the change, when, and for what reason.",
        },
    }

    datasets = {
        "pay_events": None,
        "pay_overrides": None,
    }

    findings = run_rule(rule, datasets)

    assert len(findings) == 1
    assert findings[0].rule_code == "RKEG-GOV-001"