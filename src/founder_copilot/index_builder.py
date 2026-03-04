# src/founder_copilot/index_builder.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import textwrap
import yaml
from openai import OpenAI

from .config import RKEG_RULES_YAML, RAG_INDEX_JSONL, EMBEDDING_MODEL
from .store import Chunk, save_chunks_jsonl

client = OpenAI()


@dataclass
class RuleRecord:
    """
    In-memory representation of a single YAML rule
    before it becomes a Chunk.
    """
    module: str
    rule_id: str
    title: str
    tier: int
    severity: str
    risk_dimensions: List[str]
    source_type: str
    file_path: Path
    raw_rule: Dict[str, Any]


# --------------------------------------------------------------------
# 1) Load rules from rkeg_rules.yml → RuleRecord list
# --------------------------------------------------------------------

def load_rkeg_rules(yaml_path: Path) -> List[RuleRecord]:
    """
    Load RKEG rules from rkeg_rules.yml and normalise them
    into RuleRecord objects.
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"RKEG YAML not found at {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Handle both:
    # - top-level: { rules: [...] }
    # - or: [ {...}, {...} ]
    if isinstance(data, dict) and "rules" in data:
        rules = data["rules"]
    elif isinstance(data, list):
        rules = data
    else:
        raise ValueError("Unexpected RKEG YAML structure; expected list or dict with 'rules' key")

    if not isinstance(rules, list):
        raise ValueError("RKEG rules must be a list")

    records: List[RuleRecord] = []

    for r in rules:
        if not isinstance(r, dict):
            continue  # skip weird entries

        rule_id = str(r.get("id", "")).strip()
        if not rule_id:
            # Optional: could log a warning here
            continue

        title = str(r.get("title", "")).strip()

        # Tier – default to 2 if missing
        tier_raw = r.get("tier", 2)
        try:
            tier = int(tier_raw)
        except (TypeError, ValueError):
            tier = 2

        # Severity – normalise to uppercase string
        severity = str(r.get("severity", "MEDIUM")).upper()

        # Risk dimensions – allow for different key names and shapes
        rd = r.get("risk_dimensions") or r.get("risk_dimension") or []
        if isinstance(rd, str):
            risk_dimensions = [rd]
        elif isinstance(rd, list):
            risk_dimensions = [str(x) for x in rd]
        else:
            risk_dimensions = []

        records.append(
            RuleRecord(
                module="RKEG",
                rule_id=rule_id,
                title=title,
                tier=tier,
                severity=severity,
                risk_dimensions=risk_dimensions,
                source_type="yaml_rule",
                file_path=yaml_path,
                raw_rule=r,
            )
        )

    return records


# --------------------------------------------------------------------
# 2) RuleRecord → Chunk (no embeddings yet)
# --------------------------------------------------------------------

def rule_record_to_chunk(record: RuleRecord) -> Chunk:
    """
    Flatten a RuleRecord into a Chunk (embedding left empty for now).
    """
    r = record.raw_rule

    text_fields: List[str] = []

    text_fields.append(f"Rule ID: {record.rule_id}")
    if record.title:
        text_fields.append(f"Title: {record.title}")
    text_fields.append(f"Module: {record.module}")
    text_fields.append(f"Tier: {record.tier}")
    text_fields.append(f"Severity: {record.severity}")
    if record.risk_dimensions:
        text_fields.append("Risk Dimensions: " + ", ".join(record.risk_dimensions))

    # Config block (e.g. tolerance_units)
    config_section = r.get("config") or {}
    if isinstance(config_section, dict) and config_section:
        cfg_pairs = [f"{key}={value}" for key, value in config_section.items()]
        text_fields.append("Config: " + ", ".join(cfg_pairs))

    # Text section – finding, why_it_matters, remediation, rationale
    text_section = r.get("text") or {}
    if isinstance(text_section, dict):
        finding = text_section.get("finding")
        why_it_matters = text_section.get("why_it_matters")
        remediation = text_section.get("remediation")
        rationale = text_section.get("rationale")  # some rules might use this

        if finding:
            text_fields.append(f"Finding: {finding}")
        if why_it_matters:
            text_fields.append(f"Why it matters: {why_it_matters}")
        if remediation:
            text_fields.append(f"Remediation: {remediation}")
        if rationale:
            text_fields.append(f"Rationale: {rationale}")

    # Optional: description or other free-text fields
    description = r.get("description")
    if description:
        text_fields.append(f"Description: {description}")

    flat_text = "\n".join(text_fields)

    metadata: Dict[str, Any] = {
        "module": record.module,
        "rule_id": record.rule_id,
        "title": record.title,    
        "tier": record.tier,
        "severity": record.severity,
        "risk_dimension": record.risk_dimensions,
        "source_type": record.source_type,
        "file_path": str(record.file_path),
        "section": record.title or record.rule_id,
        "config": config_section,
    }

    # Embedding is empty for now; we’ll fill it after we call OpenAI.
    return Chunk(
        id=f"{record.module}:{record.rule_id}",
        text=flat_text,
        metadata=metadata,
        embedding=[],
    )


def build_rkeg_chunks_dry_run() -> List[Chunk]:
    """
    Load RKEG rules and convert them into Chunk objects (no embeddings).
    Used for inspection / sanity checking.
    """
    rule_records = load_rkeg_rules(RKEG_RULES_YAML)
    chunks = [rule_record_to_chunk(rec) for rec in rule_records]
    return chunks


# --------------------------------------------------------------------
# 3) Embedding step – turn Chunk.text into vectors
# --------------------------------------------------------------------

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Call OpenAI embeddings API for a list of texts and return vectors.
    """
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    # response.data[i].embedding is the vector
    return [item.embedding for item in response.data]


def build_rkeg_index_with_embeddings() -> List[Chunk]:
    """
    Build the full RKEG index:
    - Rule YAML → Chunk (metadata + text)
    - Chunk.text → OpenAI embeddings
    - Chunk.embedding populated
    """
    chunks = build_rkeg_chunks_dry_run()

    if not chunks:
        return []

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb

    return chunks


# --------------------------------------------------------------------
# 4) Persist index + print sample
# --------------------------------------------------------------------

def _truncate(text: str, max_chars: int = 300) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def rebuild_founder_index() -> None:
    """
    Main entrypoint for building the CRC Founder Copilot index
    from RKEG YAML rules.

    - Builds chunks with embeddings
    - Saves to JSONL
    - Prints a small sample for inspection
    """
    print(f"Loading RKEG rules from: {RKEG_RULES_YAML}")
    chunks = build_rkeg_index_with_embeddings()

    if not chunks:
        print("⚠️ No chunks created. Check your rkeg_rules.yml structure.")
        return

    # Save full index
    save_chunks_jsonl(chunks, RAG_INDEX_JSONL)

    print()
    print(f"✅ CRC Founder Copilot index rebuilt.")
    print(f"   Chunks: {len(chunks)}")
    print(f"   Output: {RAG_INDEX_JSONL}")
    print()

    # Show a small sample for sanity
    sample = chunks[:3]
    chunks_with_config = [c for c in chunks if c.metadata.get("config")]
    config_sample = chunks_with_config[0] if chunks_with_config else None

    for idx, chunk in enumerate(sample, start=1):
        print("=" * 80)
        print(f"Sample Chunk #{idx}")
        print("- id:", chunk.id)
        print("- metadata:")
        for k, v in chunk.metadata.items():
            print(f"    {k}: {v}")
        print("- text (truncated):")
        print(textwrap.indent(_truncate(chunk.text), prefix="    "))
        print()

    if config_sample is not None:
        print("=" * 80)
        print("Sample Chunk with non-empty config")
        print("- id:", config_sample.id)
        print("- metadata.config:", config_sample.metadata.get("config"))
        print("- text (truncated):")
        print(textwrap.indent(_truncate(config_sample.text), prefix="    "))
        print()
    else:
        print("ℹ️ No rules with a non-empty config section were found.")


def main() -> None:
    """
    Script entrypoint.
    """
    rebuild_founder_index()


if __name__ == "__main__":
    main()