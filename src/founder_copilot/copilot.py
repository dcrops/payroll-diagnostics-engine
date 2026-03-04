# src/founder_copilot/copilot.py

from __future__ import annotations

from typing import Any, Dict, Optional

from openai import OpenAI

from .retrieval import retrieve

client = OpenAI()

SYSTEM_PROMPT = """You are CRC Founder Copilot (internal use only).

Rules:
- Answer ONLY using the provided CRC context.
- If the answer is not contained in the provided context, respond exactly:
  Insufficient CRC knowledge base context.
- Do NOT use general payroll knowledge.
- Do NOT speculate.
- Do NOT provide legal advice.
- Prefer referencing rule IDs when applicable.
- Keep responses structured and concise.
"""


def _format_context(results) -> str:
    """
    Convert retrieved chunks into a compact context block for the LLM.
    """
    blocks = []
    for r in results:
        rule_id = r.chunk.metadata.get("rule_id")
        title = r.chunk.metadata.get("section")  # or metadata["title"] if we add it later
        blocks.append(
            f"[{rule_id}] {title}\n"
            f"{r.chunk.text}\n"
        )
    return "\n---\n".join(blocks)


def answer_query(
    query: str,
    *,
    k: int = 3,
    filters: Optional[Dict[str, Any]] = None,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.1,
) -> str:
    """
    Retrieve top-k CRC chunks and generate a grounded answer.

    If retrieval returns nothing, return the guardrail message.
    """
    results = retrieve(query, k=k, filters=filters)

    if not results:
        return "Insufficient CRC knowledge base context."

    context = _format_context(results)

    user_prompt = f"""CRC Context:
{context}

User Question:
{query}

Answer using ONLY the CRC Context above.
"""

    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    return resp.choices[0].message.content.strip()