# src/founder_copilot/retrieval.py

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openai import OpenAI

from .config import EMBEDDING_MODEL, RAG_INDEX_JSONL
from .store import Chunk, load_chunks_jsonl

client = OpenAI()

# Matches:
# - RKEG-001
# - TERM-004
# - RKEG-SUP-001
# - LEAVE-ACC-004
# - CROSS-MODULE-002
RULE_ID_PATTERN = re.compile(r"\b[A-Z]{2,20}(?:-[A-Z]{2,20})*-\d{3}\b")


@dataclass(frozen=True)
class RetrievalResult:
    chunk: Chunk
    score: float


# -------------------------
# Loading / caching
# -------------------------

@lru_cache(maxsize=1)
def load_index_cached() -> Tuple[Chunk, ...]:
    """
    Load the JSONL index from disk once and cache it in memory.
    """
    chunks = load_chunks_jsonl(RAG_INDEX_JSONL)
    return tuple(chunks)


def clear_index_cache() -> None:
    """
    Clear cached index after rebuilding the JSONL file.
    """
    load_index_cached.cache_clear()


# -------------------------
# Helpers
# -------------------------

def _normalize_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        return [str(x) for x in val]
    return [str(val)]


def _normalize_upper(val: Any) -> Optional[str]:
    if val is None:
        return None
    text = str(val).strip()
    return text.upper() if text else None


def _contains_any(haystack: Sequence[str], needles: Sequence[str]) -> bool:
    hay = {str(x).upper() for x in haystack}
    ned = {str(x).upper() for x in needles}
    return any(x in hay for x in ned)


# -------------------------
# Filtering helpers
# -------------------------

def apply_filters(
    chunks: Sequence[Chunk],
    filters: Optional[Dict[str, Any]] = None,
) -> List[Chunk]:
    """
    Filter chunks by metadata.

    Supported filter keys:
      - module: str
      - tier: int
      - severity: str
      - source_type: str
      - rule_id: str
      - domain: str
      - risk_dimension: str | list[str]
      - risk_dimensions: str | list[str]
      - datasets_primary: str
      - datasets_references: str | list[str]
    """
    if not filters:
        return list(chunks)

    out: List[Chunk] = []

    f_module = _normalize_upper(filters.get("module"))
    f_tier = filters.get("tier")
    f_severity = _normalize_upper(filters.get("severity"))
    f_source_type = filters.get("source_type")
    f_rule_id = _normalize_upper(filters.get("rule_id"))
    f_domain = _normalize_upper(filters.get("domain"))

    f_risk_dims = _normalize_list(
        filters.get("risk_dimensions", filters.get("risk_dimension"))
    )
    f_risk_dims = [x.upper() for x in f_risk_dims if str(x).strip()]

    f_datasets_primary = _normalize_upper(filters.get("datasets_primary"))
    f_datasets_refs = _normalize_list(filters.get("datasets_references"))
    f_datasets_refs = [x.upper() for x in f_datasets_refs if str(x).strip()]

    for c in chunks:
        md = c.metadata or {}

        md_module = _normalize_upper(md.get("module"))
        md_tier = md.get("tier")
        md_severity = _normalize_upper(md.get("severity"))
        md_source_type = md.get("source_type")
        md_rule_id = _normalize_upper(md.get("rule_id"))
        md_domain = _normalize_upper(md.get("domain"))

        md_risk_dims = _normalize_list(
            md.get("risk_dimensions", md.get("risk_dimension"))
        )
        md_risk_dims = [x.upper() for x in md_risk_dims]

        md_dataset_primary = _normalize_upper(md.get("datasets_primary"))
        md_dataset_refs = _normalize_list(md.get("datasets_references"))
        md_dataset_refs = [x.upper() for x in md_dataset_refs]

        if f_module and md_module != f_module:
            continue

        if f_tier is not None and md_tier != f_tier:
            continue

        if f_severity and md_severity != f_severity:
            continue

        if f_source_type and md_source_type != f_source_type:
            continue

        if f_rule_id and md_rule_id != f_rule_id:
            continue

        if f_domain and md_domain != f_domain:
            continue

        if f_risk_dims and not _contains_any(md_risk_dims, f_risk_dims):
            continue

        if f_datasets_primary and md_dataset_primary != f_datasets_primary:
            continue

        if f_datasets_refs and not _contains_any(md_dataset_refs, f_datasets_refs):
            continue

        out.append(c)

    return out


# -------------------------
# Exact rule-id detection
# -------------------------

def extract_rule_ids(query: str) -> List[str]:
    """
    Return any rule-like tokens found in the query.
    """
    return RULE_ID_PATTERN.findall(query.upper())


def exact_rule_lookup(
    chunks: Sequence[Chunk],
    rule_id: str,
) -> Optional[Chunk]:
    """
    Find a chunk by exact metadata rule_id match.
    """
    rid = rule_id.upper()
    for c in chunks:
        if _normalize_upper((c.metadata or {}).get("rule_id")) == rid:
            return c
    return None


# -------------------------
# Query hint inference
# -------------------------

def infer_filters_from_query(query: str) -> Dict[str, Any]:
    """
    Infer lightweight metadata filters from the query text.
    These are intentionally conservative.
    """
    q = query.lower()
    inferred: Dict[str, Any] = {}

    # Module hints
    if "cross module" in q or "cross-module" in q:
        inferred["module"] = "CROSS_MODULE"
    elif "termination" in q or re.search(r"\bterm\b", q):
        inferred["module"] = "TERM"
    elif "long service leave" in q or re.search(r"\blsl\b", q):
        inferred["module"] = "LSL"
    elif re.search(r"\bleave\b", q):
        inferred["module"] = "LEAVE"
    elif "rkeg" in q or "record keeping" in q or "evidence gap" in q:
        inferred["module"] = "RKEG"

    # Domain hints
    if "superannuation" in q or re.search(r"\bsuper\b", q):
        inferred["domain"] = "SUP"
    elif "termination" in q:
        inferred["domain"] = "TERM"
    elif "leave" in q:
        inferred["domain"] = "LEAVE"
    elif "employee" in q:
        inferred["domain"] = "EMP"
    elif "pay" in q or "payroll" in q:
        inferred["domain"] = "PAY"
    elif "governance" in q:
        inferred["domain"] = "GOVERNANCE"

    # Dataset hints
    if "pay events" in q or "pay_events" in q:
        inferred["datasets_primary"] = "pay_events"
    elif "employee master" in q or "employee_master" in q:
        inferred["datasets_primary"] = "employee_master"
    elif "leave ledger" in q or "leave_ledger" in q:
        inferred["datasets_primary"] = "leave_ledger"
    elif "terminations" in q:
        inferred["datasets_primary"] = "terminations"

    return inferred


def merge_filters(
    explicit_filters: Optional[Dict[str, Any]],
    inferred_filters: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Explicit filters win over inferred filters.

    Also suppress related inferred filters when an explicit higher-priority
    structural filter is present, to avoid contradictory combinations like:
      explicit module=TERM + inferred domain=LEAVE
    """
    merged: Dict[str, Any] = {}

    inferred = dict(inferred_filters or {})
    explicit = dict(explicit_filters or {})

    # If module is explicitly set, drop inferred domain/dataset hints.
    # Module is a stronger routing constraint than free-text inference.
    if "module" in explicit:
        inferred.pop("domain", None)
        inferred.pop("datasets_primary", None)
        inferred.pop("datasets_references", None)

    # If domain is explicitly set, drop inferred dataset hints.
    if "domain" in explicit:
        inferred.pop("datasets_primary", None)
        inferred.pop("datasets_references", None)

    merged.update(inferred)
    merged.update(explicit)
    return merged


# -------------------------
# Intent detection
# -------------------------

def is_list_intent(query: str) -> bool:
    """
    Detect queries that are asking to list/browse a full category of rules
    rather than retrieve only the top semantic matches.
    """
    q = query.lower().strip()

    list_phrases = [
        "show me",
        "list",
        "show all",
        "all ",
        "what are the",
        "what rules",
        "which rules",
        "available rules",
    ]

    has_list_phrase = any(phrase in q for phrase in list_phrases)

    has_rule_word = any(
        token in q for token in ["rule", "rules", "checks", "findings"]
    )

    inferred = infer_filters_from_query(query)
    has_category = any(
        key in inferred
        for key in ["module", "domain", "datasets_primary"]
    )

    return has_list_phrase and has_rule_word and has_category


def list_results_from_chunks(chunks: Sequence[Chunk]) -> List[RetrievalResult]:
    """
    Convert chunks to RetrievalResult for browse/list mode.
    Uses a constant score because ranking is not the point here.
    """
    sorted_chunks = sorted(
        chunks,
        key=lambda c: (
            str((c.metadata or {}).get("module", "")),
            str((c.metadata or {}).get("rule_id", "")),
        ),
    )
    return [RetrievalResult(chunk=c, score=1.0) for c in sorted_chunks]


# -------------------------
# Vector similarity
# -------------------------

def embed_query(text: str) -> List[float]:
    """
    Embed a query string using OpenAI embeddings.
    """
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text],
    )
    return resp.data[0].embedding


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """
    Cosine similarity in pure Python.
    """
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def top_k_by_similarity(
    query_embedding: Sequence[float],
    chunks: Sequence[Chunk],
    k: int = 3,
    min_score: float = 0.25,
) -> List[RetrievalResult]:
    """
    Score each chunk by cosine similarity and return top-k above min_score.
    """
    scored: List[RetrievalResult] = []

    for c in chunks:
        score = cosine_similarity(query_embedding, c.embedding)
        if score >= min_score:
            scored.append(RetrievalResult(chunk=c, score=score))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:k]


# -------------------------
# Main retrieval entrypoint
# -------------------------

def retrieve(
    query: str,
    *,
    k: int = 3,
    filters: Optional[Dict[str, Any]] = None,
    prefer_exact_rule_id: bool = True,
    infer_filters: bool = True,
    min_score: float = 0.25,
) -> List[RetrievalResult]:
    """
    Retrieve relevant chunks for a query.

    Strategy:
      1) Load cached index.
      2) If query contains a rule_id and prefer_exact_rule_id=True:
         try exact match.
      3) Merge inferred filters + explicit filters.
      4) If list intent is detected, return all filtered chunks.
      5) Otherwise embed query + vector search top-k.
    """
    all_chunks = load_index_cached()

    # 1) Exact match path
    if prefer_exact_rule_id:
        rule_ids = extract_rule_ids(query)
        if rule_ids:
            rid = rule_ids[0]
            candidate_chunks = apply_filters(all_chunks, filters) if filters else list(all_chunks)
            found = exact_rule_lookup(candidate_chunks, rid)
            if found:
                return [RetrievalResult(chunk=found, score=1.0)]

    # 2) Inferred + explicit filters
    inferred = infer_filters_from_query(query) if infer_filters else {}
    merged_filters = merge_filters(filters, inferred)

    candidate_chunks = apply_filters(all_chunks, merged_filters)

    if not candidate_chunks:
        return []

    # 3) Browse/list mode
    if is_list_intent(query):
        return list_results_from_chunks(candidate_chunks)

    # 4) Normal semantic retrieval
    q_emb = embed_query(query)
    return top_k_by_similarity(q_emb, candidate_chunks, k=k, min_score=min_score)