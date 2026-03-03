# src/founder_copilot/store.py

from dataclasses import dataclass
from typing import Any, Dict, List
from pathlib import Path
import json


@dataclass
class Chunk:
    """
    Atomic knowledge unit for CRC Founder Copilot.

    One rule OR one design section = one Chunk.
    """
    id: str
    text: str
    metadata: Dict[str, Any]
    embedding: List[float]


# ------------------------
# Persistence (JSONL)
# ------------------------

def save_chunks_jsonl(chunks: List[Chunk], path: Path) -> None:
    """
    Save chunks to JSONL (one chunk per line).
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            record = {
                "id": chunk.id,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "embedding": chunk.embedding,
            }
            f.write(json.dumps(record) + "\n")


def load_chunks_jsonl(path: Path) -> List[Chunk]:
    """
    Load chunks from JSONL file.
    """
    chunks: List[Chunk] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)

            chunks.append(
                Chunk(
                    id=record["id"],
                    text=record["text"],
                    metadata=record["metadata"],
                    embedding=record["embedding"],
                )
            )

    return chunks