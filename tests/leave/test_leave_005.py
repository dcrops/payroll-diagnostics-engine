import pandas as pd

from leave_leakage.rules import run_rule


def test_leave_005():
    rule = {
        "id": "LEAVE-005",
        "severity": "HIGH",
        "config": {
            "tolerance_units": 0.01,
        },
        "text": {
            "finding": "Leave ledger-derived balances do not reconcile to leave snapshot balances within the configured tolerance.",
            "remediation": "Reconcile the ledger period and snapshot as-of date for this leave type. Check for missing or duplicate ledger events, timing cut-offs, or manual adjustments, then confirm which source is authoritative for reporting.",
        },
    }

    datasets = {
        "employee_master": pd.DataFrame(),
        "leave_ledger": pd.DataFrame(),
        "leave_snapshot": pd.DataFrame(
            [
                {
                    "employee_id": "E001",
                    "leave_type": "ANNUAL",
                    "as_of_date": pd.Timestamp("2024-03-31"),
                    "balance_units": 100.0,
                }
            ]
        ),
    }

    ledger_recon = pd.DataFrame(
        [
            {
                "employee_id": "E001",
                "leave_type": "ANNUAL",
                "as_of_date": pd.Timestamp("2024-03-31"),
                "balance_units": 100.0,
                "ledger_balance_units": 80.0,
                "diff_units": 20.0,
            }
        ]
    )

    findings = run_rule(rule, datasets, ledger_recon=ledger_recon)

    assert len(findings) == 1
    assert findings[0].employee_id == "E001"
    assert findings[0].rule_code == "LEAVE-005"