# src/founder_copilot/explain_finding.py

from __future__ import annotations

import json
from typing import Any, Dict, Optional
import csv
from pathlib import Path

from .copilot import answer_query


def _truncate(s: str, max_chars: int = 800) -> str:
    s = s or ""
    return s if len(s) <= max_chars else s[: max_chars - 3] + "..."


def _safe_json_pretty(value: Any) -> str:
    """
    Tries to pretty-print evidence JSON if it looks like JSON.
    Falls back to string.
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)

    text = str(value).strip()
    if not text:
        return ""

    # Try parse JSON-string evidence like: "{""sources"": ... }"
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except Exception:
        return text


def explain_finding(
    finding: Dict[str, Any],
    *,
    k: int = 1,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.1,
) -> str:
    """
    Explain a single CRC finding row using Founder Copilot RAG.

    finding should look like a row from your findings CSV, e.g. keys:
      - rule_code (or rule_id)
      - severity
      - message
      - evidence
      - employee_id
      - leave_type
      - as_of_date
      - diff_units
      - finding_id
      - next_action

    We force retrieval to the specific rule_id (k=1) to keep it deterministic.
    """
    rule_code = (finding.get("rule_code") or finding.get("rule_id") or "").strip()
    if not rule_code:
        # Keep consistent with our guardrail phrasing
        return "Insufficient CRC knowledge base context."

    severity = finding.get("severity", "")
    message = finding.get("message", "")
    employee_id = finding.get("employee_id", "")
    leave_type = finding.get("leave_type", "")
    as_of_date = finding.get("as_of_date", "")
    diff_units = finding.get("diff_units", "")
    finding_id = finding.get("finding_id", "")
    next_action = finding.get("next_action", "")

    evidence_pretty = _truncate(_safe_json_pretty(finding.get("evidence")), max_chars=1200)

    # We provide the finding row as "external context" (client data),
    # and the CRC rule explanation comes from RAG context.
    prompt = f"""Explain this CRC finding in plain English for internal use.

Finding details:
- finding_id: {finding_id}
- rule_code: {rule_code}
- severity: {severity}
- employee_id: {employee_id}
- leave_type: {leave_type}
- as_of_date: {as_of_date}
- diff_units: {diff_units}
- message: {_truncate(str(message), 600)}
- evidence: {_truncate(evidence_pretty, 1200)}
- next_action: {_truncate(str(next_action), 600)}

Instructions:
- Use ONLY the retrieved CRC rule context to explain what the rule means.
- Use ONLY the finding details above to describe why it triggered (do not invent details).
- Do NOT mention regulators, legislation, Fair Work, ATO, awards, or legal requirements unless those are explicitly present in the retrieved CRC context.
- Provide a short "What to do next" section referencing remediation and/or next_action.
- Do NOT use general payroll knowledge.
- If the retrieved CRC context does not contain enough information, respond exactly:
  Insufficient CRC knowledge base context.
"""

    # Force retrieval to the exact rule
    return answer_query(
        prompt,
        k=k,
        filters={"rule_id": rule_code},
        model=model,
        temperature=temperature,
    )

def load_findings_csv(csv_path: str | Path) -> list[dict[str, Any]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Findings CSV not found: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def find_finding_by_id(rows: list[dict[str, Any]], finding_id: str) -> Optional[dict[str, Any]]:
    fid = (finding_id or "").strip()
    if not fid:
        return None

    for r in rows:
        if (r.get("finding_id") or "").strip() == fid:
            return r
    return None


def explain_finding_id(
    csv_path: str | Path,
    finding_id: str,
    *,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.1,
) -> str:
    rows = load_findings_csv(csv_path)
    row = find_finding_by_id(rows, finding_id)
    if not row:
        return f"Finding ID not found in CSV: {finding_id}"

    return explain_finding(row, k=1, model=model, temperature=temperature)