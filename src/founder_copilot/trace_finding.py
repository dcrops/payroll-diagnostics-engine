from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .explain_finding import load_findings_csv, find_finding_by_id


@dataclass(frozen=True)
class EvidenceTrace:
    finding_id: str
    rule_code: str
    employee_id: str
    sources: List[str]
    primary_keys: Dict[str, Any]
    explanation: str


def _try_parse_json(text: str) -> Optional[Any]:
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None

    # Common case: valid JSON
    try:
        return json.loads(s)
    except Exception:
        pass

    # Sometimes evidence is CSV-escaped JSON like {""sources"": ...}
    try:
        s2 = s.replace('""', '"')
        return json.loads(s2)
    except Exception:
        return None


def extract_evidence(row: Dict[str, Any]) -> EvidenceTrace:
    finding_id = (row.get("finding_id") or "").strip()
    rule_code = (row.get("rule_code") or row.get("rule_id") or "").strip()
    employee_id = (row.get("employee_id") or "").strip()

    evidence_raw = row.get("evidence")
    parsed = _try_parse_json(evidence_raw)

    sources: List[str] = []
    primary_keys: Dict[str, Any] = {}
    explanation = ""

    if isinstance(parsed, dict):
        sources = parsed.get("sources") or []
        primary_keys = parsed.get("primary_keys") or {}
        explanation = parsed.get("explanation") or ""
        # normalize
        if isinstance(sources, str):
            sources = [sources]
        sources = [str(x) for x in sources]
        primary_keys = {str(k): v for k, v in primary_keys.items()}

    return EvidenceTrace(
        finding_id=finding_id,
        rule_code=rule_code,
        employee_id=employee_id,
        sources=sources,
        primary_keys=primary_keys,
        explanation=str(explanation),
    )


def trace_finding_id(findings_csv: str | Path, finding_id: str) -> str:
    rows = load_findings_csv(findings_csv)
    row = find_finding_by_id(rows, finding_id)
    if not row:
        return f"Finding ID not found in CSV: {finding_id}"

    trace = extract_evidence(row)

    lines: List[str] = []
    lines.append("CRC Evidence Trace")
    lines.append("")
    lines.append(f"finding_id: {trace.finding_id}")
    lines.append(f"rule_code:  {trace.rule_code}")
    if trace.employee_id:
        lines.append(f"employee_id:{trace.employee_id}")
    lines.append("")

    if trace.sources:
        lines.append("Sources referenced in evidence:")
        for s in trace.sources:
            lines.append(f"- {s}")
        lines.append("")
    else:
        lines.append("Sources referenced in evidence: (none found in evidence JSON)")
        lines.append("")

    if trace.primary_keys:
        lines.append("Primary keys:")
        for k, v in trace.primary_keys.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    else:
        lines.append("Primary keys: (none found in evidence JSON)")
        lines.append("")

    if trace.explanation:
        lines.append("Evidence explanation:")
        lines.append(trace.explanation)
        lines.append("")

    # Useful extra context from the row itself
    msg = (row.get("message") or "").strip()
    if msg:
        lines.append("Finding message:")
        lines.append(msg)
        lines.append("")

    nxt = (row.get("next_action") or "").strip()
    if nxt:
        lines.append("Next action:")
        lines.append(nxt)
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Trace evidence for a finding_id from a findings CSV")
    p.add_argument("csv_path", type=str)
    p.add_argument("finding_id", type=str)
    args = p.parse_args()

    print(trace_finding_id(args.csv_path, args.finding_id))


if __name__ == "__main__":
    main()