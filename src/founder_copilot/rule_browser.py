from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from .retrieval import load_index_cached, apply_filters


def list_rules_by_risk_dimension(
    risk_dimension: str,
    *,
    module: Optional[str] = None,
    tier: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Returns a list of {rule_id, title/section, tier, severity, dims}.
    Deterministic: uses metadata only (no LLM).
    """
    risk_dimension = (risk_dimension or "").strip()
    if not risk_dimension:
        return []

    chunks = load_index_cached()
    filters = {"risk_dimension": [risk_dimension]}
    if module:
        filters["module"] = module
    if tier is not None:
        filters["tier"] = tier

    filtered = apply_filters(chunks, filters)

    out: List[Dict[str, Any]] = []
    for c in filtered:
        md = c.metadata or {}
        out.append(
            {
                "rule_id": md.get("rule_id"),
                "title": md.get("title") or md.get("section"),
                "module": md.get("module"),
                "tier": md.get("tier"),
                "severity": md.get("severity"),
                "risk_dimension": md.get("risk_dimension") or [],
            }
        )

    # sort for readability
    out.sort(key=lambda x: (str(x.get("module")), str(x.get("rule_id"))))
    return out


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="List rules by risk dimension")
    p.add_argument("risk_dimension", type=str)
    p.add_argument("--module", type=str, default=None)
    p.add_argument("--tier", type=int, default=None)
    args = p.parse_args()

    rows = list_rules_by_risk_dimension(args.risk_dimension, module=args.module, tier=args.tier)
    if not rows:
        print("No rules found.")
        return

    for r in rows:
        print(f"- {r['rule_id']} (Tier {r['tier']}, {r['severity']}): {r['title']}")

if __name__ == "__main__":
    main()