from __future__ import annotations

from typing import Any, Dict, List, Optional

from .copilot import answer_query

DISCOVERY_SYSTEM_HINT = """
You are CRC Discovery/Scoping Assistant (internal use only).

Task:
- Map client concerns to CRC risk framework dimensions.
- Retrieve relevant CRC rules where possible (via context).
- Recommend an engagement scope (Exec Pack Tier 1 vs add Tier 2) WITHOUT claiming findings.

Rules:
- Do NOT claim the client has any issue (no diagnosis without data).
- Do NOT provide legal advice.
- Only use retrieved CRC context.
- If context is insufficient, say: Insufficient CRC knowledge base context.
Output format:
1) Concerns (bulleted)
2) Mapped risk dimensions (bulleted)
3) Relevant CRC rules (bulleted with rule IDs)
4) Suggested scope (short paragraph)
"""


def suggest_crc_scope(
    concerns: List[str],
    *,
    module: Optional[str] = None,
    k: int = 5,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.1,
) -> str:
    concerns_clean = [c.strip() for c in concerns if c and c.strip()]
    if not concerns_clean:
        return "Insufficient CRC knowledge base context."

    filters: Dict[str, Any] = {}
    if module:
        filters["module"] = module

    prompt = f"""{DISCOVERY_SYSTEM_HINT}

Client-stated concerns:
- """ + "\n- ".join(concerns_clean) + """

Use CRC context to:
- map concerns to risk dimensions
- list relevant rules
- suggest Tier 1 vs Tier 2 scope rationale
"""
    return answer_query(prompt, k=k, filters=filters or None, model=model, temperature=temperature)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="CRC Discovery / Scoping Assistant")
    p.add_argument("--module", type=str, default="RKEG")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--model", type=str, default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("concerns", nargs="+", help="Concerns as separate arguments or quoted strings")
    args = p.parse_args()

    print(suggest_crc_scope(args.concerns, module=args.module, k=args.k, model=args.model, temperature=args.temperature))

if __name__ == "__main__":
    main()