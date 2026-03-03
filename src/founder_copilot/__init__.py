# src/founder_copilot/__init__.py
"""
Founder Copilot – internal RAG layer for CRC.

This package provides:
- Ingestion of CRC artefacts (YAML rules, Markdown specs, risk framework docs)
- Chunking with metadata (module, rule_id, tier, severity, risk_dimension, etc.)
- Embedding + retrieval for founder-facing questions

It is:
- Internal-only
- Read-only (no modification of rule logic)
- Built on top of stable rule engines and reporting
"""