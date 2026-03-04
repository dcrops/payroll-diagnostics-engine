from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .config import RKEG_RULES_YAML


def _load_yaml_rules(yaml_path: Path) -> tuple[Any, List[Dict[str, Any]], str]:
    """
    Returns: (raw_doc, rules_list, mode)
      mode is either "dict_rules" if doc is {rules: [...]}, or "list_rules" if doc is a list.
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML not found: {yaml_path}")

    raw = yaml_path.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)

    if isinstance(doc, dict) and isinstance(doc.get("rules"), list):
        return doc, doc["rules"], "dict_rules"
    if isinstance(doc, list):
        return doc, doc, "list_rules"

    raise ValueError("Unexpected YAML structure; expected list or dict with 'rules' key")


def _normalize_dims(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val.strip()] if val.strip() else []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return [str(val).strip()] if str(val).strip() else []


def _has_existing_dims(rule: Dict[str, Any]) -> bool:
    rd = rule.get("risk_dimension") or rule.get("risk_dimensions")
    return len(_normalize_dims(rd)) > 0


def _load_suggestions(json_path: Path) -> List[Dict[str, Any]]:
    if not json_path.exists():
        raise FileNotFoundError(f"Suggestions JSON not found: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    suggestions = data.get("suggestions")
    if not isinstance(suggestions, list):
        raise ValueError("Suggestions JSON must contain a 'suggestions' list")

    # Keep only approved suggestions
    approved = [s for s in suggestions if isinstance(s, dict) and s.get("approved") is True]
    return approved


def apply_approved_tags(
    *,
    suggestions_json: Path,
    yaml_path: Path = RKEG_RULES_YAML,
    dry_run: bool = True,
    overwrite_existing: bool = False,
    write_key: str = "risk_dimension",
) -> Dict[str, Any]:
    """
    Apply approved risk_dimension tags from suggestions JSON into YAML rules.

    - dry_run=True: prints what would change, does not write YAML
    - overwrite_existing=False: will NOT touch rules that already have risk_dimension(s)
    - write_key: "risk_dimension" (recommended) or "risk_dimensions"
    """
    doc, rules, mode = _load_yaml_rules(yaml_path)
    approved = _load_suggestions(suggestions_json)

    # Build lookup rule_id -> suggested list
    sug_map: Dict[str, List[str]] = {}
    for s in approved:
        rid = str(s.get("rule_id", "")).strip()
        dims = s.get("suggested_risk_dimension")
        dims_norm = _normalize_dims(dims)
        if rid and dims_norm:
            sug_map[rid] = dims_norm

    changes: List[Dict[str, Any]] = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rid = str(rule.get("id", "")).strip()
        if not rid:
            continue

        if rid not in sug_map:
            continue

        if (not overwrite_existing) and _has_existing_dims(rule):
            continue

        new_dims = sug_map[rid]
        old_dims = _normalize_dims(rule.get("risk_dimension") or rule.get("risk_dimensions"))

        # Apply
        rule[write_key] = new_dims

        changes.append(
            {
                "rule_id": rid,
                "old": old_dims,
                "new": new_dims,
                "title": rule.get("title"),
            }
        )

    result = {
        "yaml_path": str(yaml_path),
        "suggestions_json": str(suggestions_json),
        "approved_in_json": len(approved),
        "applied_changes": len(changes),
        "dry_run": dry_run,
        "overwrite_existing": overwrite_existing,
        "write_key": write_key,
        "changes": changes,
    }

    # Print summary
    print(f"YAML: {yaml_path}")
    print(f"Suggestions JSON: {suggestions_json}")
    print(f"Approved suggestions in JSON: {len(approved)}")
    print(f"Changes to apply: {len(changes)}")
    print(f"dry_run={dry_run}, overwrite_existing={overwrite_existing}, write_key={write_key}")
    print()

    for c in changes:
        print(f"- {c['rule_id']}: {c.get('title')}")
        print(f"  old: {c['old']}")
        print(f"  new: {c['new']}")
    if not changes:
        print("No changes matched (check approved=true and rule_id values).")

    if dry_run:
        print("\nDRY RUN: no YAML written.")
        return result

    # Write YAML back (note: formatting/comments may change)
    yaml_path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print("\n✅ YAML updated.")
    from .format_yaml import format_rules_yaml
    format_rules_yaml(yaml_path)
    return result


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Apply approved risk_dimension tags to YAML rules")
    p.add_argument("suggestions_json", type=str, help="Path to tag_suggestions JSON")
    p.add_argument("--yaml-path", type=str, default=str(RKEG_RULES_YAML))
    p.add_argument("--apply", action="store_true", help="Actually write YAML (otherwise dry-run)")
    p.add_argument("--overwrite-existing", action="store_true", help="Overwrite existing risk_dimension tags")
    p.add_argument("--write-key", type=str, default="risk_dimension", choices=["risk_dimension", "risk_dimensions"])
    args = p.parse_args()

    apply_approved_tags(
        suggestions_json=Path(args.suggestions_json),
        yaml_path=Path(args.yaml_path),
        dry_run=not args.apply,
        overwrite_existing=args.overwrite_existing,
        write_key=args.write_key,
    )


if __name__ == "__main__":
    main()