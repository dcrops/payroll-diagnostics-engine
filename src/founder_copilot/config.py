# src/founder_copilot/config.py

from pathlib import Path

# -----------------------
# Project / path settings
# -----------------------

# config.py lives at: <repo>/src/founder_copilot/config.py
# parents[0] = src/founder_copilot
# parents[1] = src
# parents[2] = repo root  👈 this is what we want
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# We'll keep RAG artefacts out of src/, next to outputs/
DATA_DIR = PROJECT_ROOT / "data"
FOUNDER_RAG_DIR = DATA_DIR / "founder_copilot"
FOUNDER_RAG_DIR.mkdir(parents=True, exist_ok=True)

# Path to your RKEG YAML (from your screenshot)
RKEG_RULES_YAML = PROJECT_ROOT / "src" / "rkeg" / "config" / "rkeg_rules.yml"

# Optional: where we expect Markdown docs to live.
# You can adjust these as you create them.
RKEG_DESIGN_MD = PROJECT_ROOT / "src" / "reporting" / "rkeg_text.py"  # placeholder
RISK_FRAMEWORK_MD = PROJECT_ROOT / "src" / "reporting" / "context.py"  # or a dedicated md later

# Where we'll persist our built index (simple JSONL for now)
RAG_INDEX_JSONL = FOUNDER_RAG_DIR / "crc_founder_index.jsonl"


# -----------------------
# OpenAI / model settings
# -----------------------

# Embedding model – we’ll actually use this later in the index builder
EMBEDDING_MODEL = "text-embedding-3-large"  # adjust if needed

# Chat model for answering questions
CHAT_MODEL = "gpt-4.1"  # or whatever you end up standardising on

# -----------------------
# Retrieval defaults
# -----------------------

# How many chunks to pull back per query by default
DEFAULT_TOP_K = 3

# Soft limit used when we design chunking – we won’t hard-enforce tokens yet,
# but this gives us a target size when splitting large markdown sections.
MAX_CHUNK_TOKENS = 800