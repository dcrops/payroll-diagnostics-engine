Leave Leakage Module

Purpose
-------
Detect governance risks related to leave accrual, leave usage,
ledger integrity and entitlement reconstruction.

Architecture
------------
Rules are defined in:

config/leave_rules.yml

Detector logic is organised by domain:

balance_rules.py
timing_rules.py
structure_rules.py
anomaly_rules.py
governance_rules.py

Rule execution uses a registry pattern defined in:

detectors/registry.py

The run script:

run.py

Loads datasets
Constructs reconciliation context
Executes rules
Outputs findings and summaries.