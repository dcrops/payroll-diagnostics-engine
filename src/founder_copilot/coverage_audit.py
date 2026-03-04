# src/founder_copilot/coverage_audit.py

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

import yaml

from .config import RKEG_RULES_YAML

# Detects rule IDs like:
# RKEG-LEAVE-002, RKEG-PAY-008, LEAVE-ACC-004 etc.
RULE_ID_RE = re.compile(r"\b[A-Z]{2,10}(?:-[A-Z]{2,10})?-\d{3}\b")


@dataclass(frozen=True)
class CoverageReport:
    yaml_rule_ids: Set[str]
    code_rule_ids: Set[str]
    missing_in_code: List[str]
    orphan_in_code: List[str]
    occurrences: Dict[str, List[str]]  # rule_id -> list of files where it appears


def load_yaml_rule_ids(yaml_path: Path) -> Set[str]:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    rules = data["rules"] if isinstance(data, dict) and "rules" in data else data
    if not isinstance(rules, list):
        raise ValueError("Unexpected YAML structure; expected list or {rules: [...]}")

    ids: Set[str] = set()
    for r in rules:
        if isinstance(r, dict) and r.get("id"):
            ids.add(str(r["id"]).strip().upper())
    return ids


def scan_code_for_rule_ids(code_root: Path) -> Tuple[Set[str], Dict[str, List[str]]]:
    """
    Static scan: searches *.py files for tokens that look like rule IDs.
    """
    found: Set[str] = set()
    occurrences: Dict[str, List[str]] = {}

    for py_file in code_root.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        matches = set(m.group(0).upper() for m in RULE_ID_RE.finditer(text))
        if not matches:
            continue

        for rid in matches:
            found.add(rid)
            occurrences.setdefault(rid, []).append(str(py_file))

    return found, occurrences


def build_coverage_report(
    *,
    yaml_path: Path = RKEG_RULES_YAML,
    code_root: Path = Path("src"),
    restrict_to_prefix: str = "RKEG-",
) -> CoverageReport:
    """
    Compare YAML rule IDs to code references.
    'restrict_to_prefix' keeps the scan focused (avoids matching unrelated IDs).
    """
    yaml_ids = load_yaml_rule_ids(yaml_path)

    # Restrict YAML IDs (just in case the YAML contains other modules later)
    yaml_ids = {rid for rid in yaml_ids if rid.startswith(restrict_to_prefix)}

    code_ids, occ = scan_code_for_rule_ids(code_root)
    code_ids = {rid for rid in code_ids if rid.startswith(restrict_to_prefix)}

    missing_in_code = sorted(yaml_ids - code_ids)
    orphan_in_code = sorted(code_ids - yaml_ids)

    return CoverageReport(
        yaml_rule_ids=yaml_ids,
        code_rule_ids=code_ids,
        missing_in_code=missing_in_code,
        orphan_in_code=orphan_in_code,
        occurrences=occ,
    )


def print_report(report: CoverageReport, *, show_occurrences: bool = True) -> None:
    print(f"YAML rules (RKEG): {len(report.yaml_rule_ids)}")
    print(f"Rule IDs referenced in code: {len(report.code_rule_ids)}")
    print()

    if report.missing_in_code:
        print("❌ Rules present in YAML but NOT found in code (likely missing implementation/wiring):")
        for rid in report.missing_in_code:
            print(f"  - {rid}")
        print()
    else:
        print("✅ All YAML rules were found referenced somewhere in code.")
        print()

    if report.orphan_in_code:
        print("⚠️ Rule IDs found in code but NOT present in YAML (possible dead code / old rules):")
        for rid in report.orphan_in_code:
            print(f"  - {rid}")
        print()
    else:
        print("✅ No orphan rule IDs detected in code.")
        print()

    if show_occurrences and report.missing_in_code:
        print("📌 Tip: If a rule is missing in code, you’d normally expect it to appear in:")
        print("   - src/rkeg/detectors/*.py or")
        print("   - src/rkeg/engine.py routing / registry")
        print()

    # Optional: show where a few found IDs occur (useful sanity)
    if show_occurrences and report.code_rule_ids:
        sample = sorted(list(report.code_rule_ids))[:5]
        print("🔎 Sample occurrences (first 5 rule IDs found in code):")
        for rid in sample:
            files = report.occurrences.get(rid, [])
            print(f"  - {rid}")
            for f in files[:3]:
                print(f"      {f}")
        print()


def main() -> None:
    report = build_coverage_report()
    print_report(report)


if __name__ == "__main__":
    main()