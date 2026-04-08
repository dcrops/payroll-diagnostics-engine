from __future__ import annotations

from typing import List

from src.founder_copilot.retrieval import retrieve, clear_index_cache


def rule_ids(results) -> List[str]:
    return [r.chunk.metadata.get("rule_id", "") for r in results]


def modules(results) -> List[str]:
    return [r.chunk.metadata.get("module", "") for r in results]


def domains(results) -> List[str]:
    return [r.chunk.metadata.get("domain", "") for r in results]


def datasets_primary(results) -> List[str]:
    return [r.chunk.metadata.get("datasets_primary", "") for r in results]


def setup_module():
    """
    Clear cache before tests in case the index was recently rebuilt.
    """
    clear_index_cache()


def test_exact_rule_lookup_returns_single_exact_match():
    results = retrieve("RKEG-SUP-001")

    assert len(results) == 1
    assert results[0].chunk.metadata["rule_id"] == "RKEG-SUP-001"
    assert results[0].score == 1.0


def test_list_intent_returns_all_term_rules():
    results = retrieve("show me termination rules")

    assert len(results) >= 10
    assert all(m == "TERM" for m in modules(results))


def test_list_intent_returns_all_lsl_rules():
    results = retrieve("show me LSL rules")

    assert len(results) >= 10
    assert all(m == "LSL" for m in modules(results))


def test_superannuation_query_returns_sup_domain_rules():
    results = retrieve("show me superannuation rules")

    assert len(results) >= 1
    assert all(d == "SUP" for d in domains(results))


def test_dataset_query_returns_pay_events_rules():
    results = retrieve("show me rules using pay_events")

    assert len(results) >= 1
    assert all(ds == "pay_events" for ds in datasets_primary(results))


def test_explicit_module_filter_is_respected():
    results = retrieve(
        "show me termination rules",
        filters={"module": "TERM"},
    )

    assert len(results) >= 1
    assert all(m == "TERM" for m in modules(results))


def test_explicit_module_filter_overrides_inference():
    results = retrieve(
        "show me leave rules",
        filters={"module": "TERM"},
    )

    assert len(results) >= 1
    assert all(m == "TERM" for m in modules(results))


def test_semantic_query_returns_some_results():
    results = retrieve("rules about missing termination evidence", k=5)

    assert len(results) >= 1
    assert any("TERM" == m for m in modules(results))


def test_list_intent_with_cross_module_returns_cross_module_rules():
    results = retrieve("show all cross module rules")

    assert len(results) >= 1
    assert all(m == "CROSS_MODULE" for m in modules(results))