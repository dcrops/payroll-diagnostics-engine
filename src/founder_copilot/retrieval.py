# src/founder_copilot/retrieval.py

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from openai import OpenAI

from .config import EMBEDDING_MODEL, RAG_INDEX_JSONL
from .store import Chunk, load_chunks_jsonl

client = OpenAI()

# Matches things like: RKEG-PAY-008, LEAVE-ACC-004, TERM-XXX-001, RKEG-LEAVE-002, etc.
RULE_ID_PATTERN = re.compile(r"\b[A-Z]{2,10}(?:-[A-Z]{2,10})?-\d{3}\b")


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
    Load the JSONL index from disk ONCE and cache it in memory.
    Returns a tuple to keep it hashable-ish and discourage mutation.
    """
    chunks = load_chunks_jsonl(RAG_INDEX_JSONL)
    return tuple(chunks)


def clear_index_cache() -> None:
    """
    Clear cached index (useful if you rebuild the JSONL index and want a refresh
    without restarting Python).
    """
    load_index_cached.cache_clear()


# -------------------------
# Filtering helpers
# -------------------------

def _normalize_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        return [str(x) for x in val]
    return [str(val)]


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
      - risk_dimension: str | list[str]  (matches ANY)
      - source_type: str
      - rule_id: str (exact match against metadata["rule_id"])
    """
    if not filters:
        return list(chunks)

    out: List[Chunk] = []

    f_module = filters.get("module")
    f_tier = filters.get("tier")
    f_severity = filters.get("severity")
    f_source_type = filters.get("source_type")
    f_rule_id = filters.get("rule_id")
    f_risk_dims = _normalize_list(filters.get("risk_dimension"))

    for c in chunks:
        md = c.metadata or {}

        if f_module and md.get("module") != f_module:
            continue

        if f_tier is not None and md.get("tier") != f_tier:
            continue

        if f_severity and str(md.get("severity", "")).upper() != str(f_severity).upper():
            continue

        if f_source_type and md.get("source_type") != f_source_type:
            continue

        if f_rule_id and md.get("rule_id") != f_rule_id:
            continue

        if f_risk_dims:
            chunk_dims = md.get("risk_dimension") or []
            if isinstance(chunk_dims, str):
                chunk_dims = [chunk_dims]
            chunk_dims = [str(x) for x in chunk_dims]

            # Match ANY (OR) — if any requested dim appears in the chunk dims.
            if not any(dim in chunk_dims for dim in f_risk_dims):
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
        if (c.metadata or {}).get("rule_id", "").upper() == rid:
            return c
    return None


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
    Returns value in [-1, 1], higher is more similar.
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
    min_score: float = 0.25,
) -> List[RetrievalResult]:
    """
    Retrieve relevant chunks for a query.

    Strategy:
      1) Load cached index.
      2) If query contains a rule_id and prefer_exact_rule_id=True:
           - try exact match (optionally also apply filters)
           - return that single chunk as score=1.0
      3) Apply metadata filters to narrow search space.
      4) Embed query + vector search top-k.
    """
    all_chunks = load_index_cached()

    # 1) Exact match path (fast + deterministic)
    if prefer_exact_rule_id:
        rule_ids = extract_rule_ids(query)
        if rule_ids:
            # Use the first detected rule id
            rid = rule_ids[0]

            # If filters include module/tier/etc, apply them before exact lookup
            filtered_for_exact = apply_filters(all_chunks, filters) if filters else list(all_chunks)
            found = exact_rule_lookup(filtered_for_exact, rid)
            if found:
                return [RetrievalResult(chunk=found, score=1.0)]

    # 2) Filter then semantic retrieval
    candidate_chunks = apply_filters(all_chunks, filters)

    # Edge case: filters eliminate everything
    if not candidate_chunks:
        return []

    q_emb = embed_query(query)
    return top_k_by_similarity(q_emb, candidate_chunks, k=k, min_score=min_score)