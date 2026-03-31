# src/founder_copilot/index_builder.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import textwrap
import yaml
from openai import OpenAI

from .config import (
    RAG_INDEX_JSONL,
    EMBEDDING_MODEL,
    RKEG_RULES_YAML,
    TERM_RULES_YAML,
    LSL_RULES_YAML,
    LEAVE_RULES_YAML,
    CROSS_MODULE_RULES_YAML,
)
from .store import Chunk, save_chunks_jsonl

client = OpenAI()


# --------------------------------------------------------------------
# Ruleset registry
# --------------------------------------------------------------------

RULESET_PATHS: Dict[str, Path] = {
    "RKEG": RKEG_RULES_YAML,
    "TERM": TERM_RULES_YAML,
    "LSL": LSL_RULES_YAML,
    "LEAVE": LEAVE_RULES_YAML,
    "CROSS_MODULE": CROSS_MODULE_RULES_YAML,
}


# --------------------------------------------------------------------
# In-memory rule representation
# --------------------------------------------------------------------

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
    domain: str
    risk_dimensions: List[str]
    datasets_primary: Optional[str]
    datasets_references: List[str]
    source_type: str
    file_path: Path
    raw_rule: Dict[str, Any]


# --------------------------------------------------------------------
# Helper normalisers
# --------------------------------------------------------------------

def _extract_rules_list(data: Any, yaml_path: Path) -> List[Dict[str, Any]]:
    """
    Accept either:
    - top-level: { rules: [...] }
    - or: [ {...}, {...} ]
    """
    if isinstance(data, dict) and "rules" in data:
        rules = data["rules"]
    elif isinstance(data, list):
        rules = data
    else:
        raise ValueError(
            f"Unexpected YAML structure in {yaml_path}; "
            f"expected a list or dict with 'rules' key"
        )

    if not isinstance(rules, list):
        raise ValueError(f"Rules in {yaml_path} must be a list")

    cleaned_rules: List[Dict[str, Any]] = []
    for r in rules:
        if isinstance(r, dict):
            cleaned_rules.append(r)

    return cleaned_rules


def _normalise_tier(raw_value: Any, default: int = 2) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def _normalise_risk_dimensions(rule: Dict[str, Any]) -> List[str]:
    """
    Support both:
    - risk_dimensions: [...]
    - risk_dimension: [...]
    """
    raw_value = rule.get("risk_dimensions")
    if raw_value is None:
        raw_value = rule.get("risk_dimension")

    if raw_value is None:
        return []

    if isinstance(raw_value, str):
        return [raw_value.strip()] if raw_value.strip() else []

    if isinstance(raw_value, list):
        result = []
        for item in raw_value:
            value = str(item).strip()
            if value:
                result.append(value)
        return result

    return []


def _normalise_domain(rule: Dict[str, Any]) -> str:
    return str(rule.get("domain", "")).strip().upper()


def _normalise_datasets(rule: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
    """
    Support:
    datasets:
      primary: pay_events
      references:
        - employee_master
        - leave_ledger
    """
    datasets = rule.get("datasets") or {}

    if not isinstance(datasets, dict):
        return None, []

    primary_raw = datasets.get("primary")
    primary = str(primary_raw).strip() if primary_raw is not None else None
    if primary == "":
        primary = None

    references_raw = datasets.get("references") or []
    references: List[str] = []

    if isinstance(references_raw, str):
        value = references_raw.strip()
        if value:
            references.append(value)
    elif isinstance(references_raw, list):
        for item in references_raw:
            value = str(item).strip()
            if value:
                references.append(value)

    return primary, references


# --------------------------------------------------------------------
# 1) Generic loader
# --------------------------------------------------------------------

def load_rules(yaml_path: Path, module_name: str) -> List[RuleRecord]:
    """
    Load rules for a given module from YAML and normalise them
    into RuleRecord objects.
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"{module_name} YAML not found at {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rules = _extract_rules_list(data, yaml_path)

    records: List[RuleRecord] = []

    for r in rules:
        rule_id = str(r.get("id", "")).strip()
        if not rule_id:
            continue

        title = str(r.get("title", "")).strip()
        tier = _normalise_tier(r.get("tier", 2), default=2)
        severity = str(r.get("severity", "MEDIUM")).strip().upper()
        domain = _normalise_domain(r)
        risk_dimensions = _normalise_risk_dimensions(r)
        datasets_primary, datasets_references = _normalise_datasets(r)

        records.append(
            RuleRecord(
                module=module_name,
                rule_id=rule_id,
                title=title,
                tier=tier,
                severity=severity,
                domain=domain,
                risk_dimensions=risk_dimensions,
                datasets_primary=datasets_primary,
                datasets_references=datasets_references,
                source_type="yaml_rule",
                file_path=yaml_path,
                raw_rule=r,
            )
        )

    return records


# --------------------------------------------------------------------
# 2) RuleRecord -> Chunk (no embeddings yet)
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

    if record.domain:
        text_fields.append(f"Domain: {record.domain}")

    text_fields.append(f"Tier: {record.tier}")
    text_fields.append(f"Severity: {record.severity}")

    if record.risk_dimensions:
        text_fields.append("Risk Dimensions: " + ", ".join(record.risk_dimensions))

    if record.datasets_primary:
        text_fields.append(f"Primary Dataset: {record.datasets_primary}")

    if record.datasets_references:
        text_fields.append(
            "Reference Datasets: " + ", ".join(record.datasets_references)
        )

    # Optional config section
    config_section = r.get("config") or {}
    if isinstance(config_section, dict) and config_section:
        cfg_pairs = [f"{key}={value}" for key, value in config_section.items()]
        text_fields.append("Config: " + ", ".join(cfg_pairs))
    else:
        config_section = {}

    # Optional text section
    text_section = r.get("text") or {}
    if isinstance(text_section, dict):
        finding = text_section.get("finding")
        why_it_matters = text_section.get("why_it_matters")
        remediation = text_section.get("remediation")
        rationale = text_section.get("rationale")

        if finding:
            text_fields.append(f"Finding: {finding}")
        if why_it_matters:
            text_fields.append(f"Why it matters: {why_it_matters}")
        if remediation:
            text_fields.append(f"Remediation: {remediation}")
        if rationale:
            text_fields.append(f"Rationale: {rationale}")

    # Optional free text
    description = r.get("description")
    if description:
        text_fields.append(f"Description: {description}")

    flat_text = "\n".join(text_fields)

    metadata: Dict[str, Any] = {
        "module": record.module,
        "rule_id": record.rule_id,
        "title": record.title,
        "domain": record.domain,
        "tier": record.tier,
        "severity": record.severity,
        "risk_dimensions": record.risk_dimensions,
        "datasets_primary": record.datasets_primary,
        "datasets_references": record.datasets_references,
        "source_type": record.source_type,
        "file_path": str(record.file_path),
        "section": record.title or record.rule_id,
        "config": config_section,
    }

    return Chunk(
        id=f"{record.module}:{record.rule_id}",
        text=flat_text,
        metadata=metadata,
        embedding=[],
    )


# --------------------------------------------------------------------
# 3) Build chunks
# --------------------------------------------------------------------

def build_module_chunks(module_name: str, yaml_path: Path) -> List[Chunk]:
    """
    Build chunk objects for a single module, without embeddings.
    """
    rule_records = load_rules(yaml_path, module_name)
    return [rule_record_to_chunk(rec) for rec in rule_records]


def build_all_chunks_dry_run() -> List[Chunk]:
    """
    Build chunk objects for all configured modules, without embeddings.
    Useful for inspection / sanity checking.
    """
    all_chunks: List[Chunk] = []

    for module_name, yaml_path in RULESET_PATHS.items():
        module_chunks = build_module_chunks(module_name, yaml_path)
        all_chunks.extend(module_chunks)

    return all_chunks


# --------------------------------------------------------------------
# 4) Embeddings
# --------------------------------------------------------------------

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Call OpenAI embeddings API for a list of texts and return vectors.
    """
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def build_index_with_embeddings() -> List[Chunk]:
    """
    Build the full CRC Founder Copilot index:
    - YAML rules across all configured modules -> Chunk
    - Chunk.text -> OpenAI embeddings
    - Chunk.embedding populated
    """
    chunks = build_all_chunks_dry_run()

    if not chunks:
        return []

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb

    return chunks


# --------------------------------------------------------------------
# 5) Persist + inspect
# --------------------------------------------------------------------

def _truncate(text: str, max_chars: int = 300) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _print_sample_chunks(chunks: List[Chunk], sample_size: int = 3) -> None:
    sample = chunks[:sample_size]
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


def _print_module_counts(chunks: List[Chunk]) -> None:
    module_counts: Dict[str, int] = {}

    for chunk in chunks:
        module = str(chunk.metadata.get("module", "UNKNOWN"))
        module_counts[module] = module_counts.get(module, 0) + 1

    print("Chunks by module:")
    for module_name, count in sorted(module_counts.items()):
        print(f"  - {module_name}: {count}")


def rebuild_founder_index() -> None:
    """
    Main entrypoint for building the CRC Founder Copilot index
    from all configured module YAML rules.

    - Builds chunks with embeddings
    - Saves to JSONL
    - Prints summary + sample chunks
    """
    print("Rebuilding CRC Founder Copilot index from configured rulesets...")
    print()

    for module_name, yaml_path in RULESET_PATHS.items():
        print(f" - {module_name}: {yaml_path}")

    print()
    chunks = build_index_with_embeddings()

    if not chunks:
        print("⚠️ No chunks created. Check your YAML files and schema structure.")
        return

    save_chunks_jsonl(chunks, RAG_INDEX_JSONL)

    print()
    print("✅ CRC Founder Copilot index rebuilt.")
    print(f"   Total chunks: {len(chunks)}")
    print(f"   Output: {RAG_INDEX_JSONL}")
    print()

    _print_module_counts(chunks)
    print()
    _print_sample_chunks(chunks)


def main() -> None:
    rebuild_founder_index()


if __name__ == "__main__":
    main()