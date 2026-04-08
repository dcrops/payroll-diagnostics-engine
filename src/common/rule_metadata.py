from __future__ import annotations

from pathlib import Path
import yaml


def load_rule_metadata_map(rules_path: Path) -> dict[str, dict]:
    with rules_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    rules = payload.get("rules", [])
    result: dict[str, dict] = {}

    for rule in rules:
        rule_code = str(rule.get("id", "")).strip()
        if not rule_code:
            continue

        viability = rule.get("viability", {}) or {}
        data_strength = rule.get("data_strength", {}) or {}

        result[rule_code] = {
            "payroll_only_viable": viability.get("payroll_only"),
            "viability_level": viability.get("level"),
            "payroll_signal_strength": data_strength.get("payroll_signal"),
        }

    return result