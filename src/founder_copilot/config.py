# src/founder_copilot/config.py

from pathlib import Path

# -----------------------
# Project / path settings
# -----------------------

# config.py lives at: <repo>/src/founder_copilot/config.py
# parents[0] = src/founder_copilot
# parents[1] = src
# parents[2] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# We'll keep RAG artefacts out of src/, next to outputs/
DATA_DIR = PROJECT_ROOT / "data"
FOUNDER_RAG_DIR = DATA_DIR / "founder_copilot"
FOUNDER_RAG_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------
# Rule YAML paths
# -----------------------

RKEG_RULES_YAML = PROJECT_ROOT / "src" / "rkeg" / "config" / "rkeg_rules.yml"
TERM_RULES_YAML = PROJECT_ROOT / "src" / "termination_exposure" / "config" / "term_rules.yml"
LSL_RULES_YAML = PROJECT_ROOT / "src" / "lsl_exposure" / "config" / "lsl_rules.yml"
LEAVE_RULES_YAML = PROJECT_ROOT / "src" / "leave_leakage" / "config" / "leave_rules.yml"
CROSS_MODULE_RULES_YAML = PROJECT_ROOT / "src" / "cross_module_integrity" / "config" / "cross_module_rules.yml"

# Optional: where we expect Markdown/docs to live
# You can expand these later if the copilot starts indexing docs too
RKEG_DESIGN_MD = PROJECT_ROOT / "src" / "reporting" / "rkeg_text.py"   # placeholder
RISK_FRAMEWORK_MD = PROJECT_ROOT / "src" / "reporting" / "context.py"  # placeholder

# Where we'll persist our built index (simple JSONL for now)
RAG_INDEX_JSONL = FOUNDER_RAG_DIR / "crc_founder_index.jsonl"

# -----------------------
# OpenAI / model settings
# -----------------------

# Embedding model
EMBEDDING_MODEL = "text-embedding-3-large"

# Chat model for answering questions
CHAT_MODEL = "gpt-4.1"

# -----------------------
# Retrieval defaults
# -----------------------

# How many chunks to pull back per query by default
DEFAULT_TOP_K = 3

# Soft limit used when we design chunking
MAX_CHUNK_TOKENS = 800