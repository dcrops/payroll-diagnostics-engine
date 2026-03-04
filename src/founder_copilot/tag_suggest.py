from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from .config import RKEG_RULES_YAML

client = OpenAI()

# Keep this list as the single source of truth for allowed tags
ALLOWED_RISK_DIMENSIONS = [
    "structural_completeness",
    "calculation_integrity",
    "timing_integrity",
    "evidence_traceability",
    "exception_handling",
    "data_anomaly_sanity",
    "governance_exposure",
    "cross_module_linkage_risk",
]


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _build_rule_text(rule: Dict[str, Any]) -> str:
    """
    Create a compact, informative text representation for tag suggestion.
    """
    rid = _safe_str(rule.get("id"))
    title = _safe_str(rule.get("title"))
    domain = _safe_str(rule.get("domain"))
    tier = _safe_str(rule.get("tier"))
    severity = _safe_str(rule.get("severity"))

    txt = rule.get("text") or {}
    finding = _safe_str(txt.get("finding")) if isinstance(txt, dict) else ""
    why = _safe_str(txt.get("why_it_matters")) if isinstance(txt, dict) else ""
    remediation = _safe_str(txt.get("remediation")) if isinstance(txt, dict) else ""

    parts = [
        f"Rule ID: {rid}",
        f"Title: {title}" if title else "",
        f"Domain: {domain}" if domain else "",
        f"Tier: {tier}" if tier else "",
        f"Severity: {severity}" if severity else "",
        f"Finding: {finding}" if finding else "",
        f"Why it matters: {why}" if why else "",
        f"Remediation: {remediation}" if remediation else "",
    ]
    return "\n".join([p for p in parts if p])


def _has_risk_dims(rule: Dict[str, Any]) -> bool:
    rd = rule.get("risk_dimension") or rule.get("risk_dimensions")
    if rd is None:
        return False
    if isinstance(rd, str):
        return bool(rd.strip())
    if isinstance(rd, list):
        return len([x for x in rd if str(x).strip()]) > 0
    return False


def _normalize_tags(tags: Any) -> List[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        return []
    cleaned = []
    for t in tags:
        s = str(t).strip()
        if s:
            cleaned.append(s)
    return cleaned


def suggest_tags_for_rule(
    rule_text: str,
    *,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.0,
) -> List[str]:
    """
    Suggest 1–3 risk_dimension tags from ALLOWED_RISK_DIMENSIONS.
    Returns a list of tags (subset of allowed list).
    """
    system = (
        "You are CRC Founder Copilot (internal).\n"
        "Your task is to classify a CRC rule into 1–3 risk dimensions.\n"
        "You MUST choose ONLY from the allowed list.\n"
        "Return ONLY valid JSON like: {\"risk_dimension\": [\"...\"]}\n"
        "No commentary, no markdown."
    )
    user = (
        "Allowed risk dimensions:\n"
        + "\n".join(f"- {d}" for d in ALLOWED_RISK_DIMENSIONS)
        + "\n\nRule:\n"
        + rule_text
        + "\n\nSelect 1–3 risk dimensions that best match the rule."
    )

    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    content = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(content)
    except Exception:
        return []

    tags = _normalize_tags(data.get("risk_dimension"))
    # enforce allowed list + uniqueness
    allowed = set(ALLOWED_RISK_DIMENSIONS)
    out = []
    for t in tags:
        if t in allowed and t not in out:
            out.append(t)
    return out[:3]

def _tier(rule: Dict[str, Any]) -> int:
    try:
        return int(rule.get("tier", 2))
    except Exception:
        return 2

def _severity_rank(rule: Dict[str, Any]) -> int:
    sev = str(rule.get("severity", "")).strip().upper()
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(sev, 0)


def load_rules_yaml(yaml_path: Path) -> List[Dict[str, Any]]:
    import yaml

    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML not found: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if isinstance(data, dict) and "rules" in data:
        rules = data["rules"]
    elif isinstance(data, list):
        rules = data
    else:
        raise ValueError("Unexpected YAML structure; expected list or dict with 'rules' key")

    if not isinstance(rules, list):
        raise ValueError("YAML 'rules' must be a list")

    return [r for r in rules if isinstance(r, dict)]


def suggest_tags(
    *,
    yaml_path: Path = RKEG_RULES_YAML,
    limit: Optional[int] = 10,
    output_json: Optional[Path] = None,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    """
    Suggest tags for rules missing risk_dimension.
    Writes a reviewable JSON file if output_json is provided.
    """
    rules = load_rules_yaml(yaml_path)

    missing = [r for r in rules if not _has_risk_dims(r)]

    # Sort: Tier 1 first, then HIGH severity first, then domain, then id
    missing.sort(
        key=lambda r: (
            _tier(r),
            -_severity_rank(r),
            str(r.get("domain", "")).upper(),
            str(r.get("id", "")).upper(),
        )
    )

    if limit is not None:
        missing = missing[: max(0, int(limit))]

    suggestions = []
    for r in missing:
        rid = _safe_str(r.get("id"))
        rule_text = _build_rule_text(r)
        tags = suggest_tags_for_rule(rule_text, model=model)
        suggestions.append(
            {
                "rule_id": rid,
                "suggested_risk_dimension": tags,
                "approved": False,   # <-- human-in-the-loop gate
                "title": _safe_str(r.get("title")),
                "domain": _safe_str(r.get("domain")),
                "tier": r.get("tier"),
                "severity": _safe_str(r.get("severity")),
            }
        )

    result = {
        "yaml_path": str(yaml_path),
        "allowed_risk_dimensions": ALLOWED_RISK_DIMENSIONS,
        "suggestions": suggestions,
        "count_missing_in_yaml": len([r for r in rules if not _has_risk_dims(r)]),
        "count_suggested": len(suggestions),
    }

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Suggest CRC risk_dimension tags for YAML rules")
    p.add_argument("--yaml-path", type=str, default=str(RKEG_RULES_YAML))
    p.add_argument("--limit", type=int, default=10, help="How many missing-tag rules to process")
    p.add_argument("--out", type=str, default="outputs/tag_suggestions_rkeg.json")
    p.add_argument("--model", type=str, default="gpt-4.1-mini")
    args = p.parse_args()

    result = suggest_tags(
        yaml_path=Path(args.yaml_path),
        limit=args.limit,
        output_json=Path(args.out) if args.out else None,
        model=args.model,
    )

    print(f"YAML: {result['yaml_path']}")
    print(f"Missing-tag rules in YAML: {result['count_missing_in_yaml']}")
    print(f"Suggested (this run): {result['count_suggested']}")
    print()
    for s in result["suggestions"]:
        print(f"- {s['rule_id']} ({s['domain']}, Tier {s['tier']}, {s['severity']}): {s['title']}")
        print(f"  suggested risk_dimension: {s['suggested_risk_dimension']}")
    if args.out:
        print()
        print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()