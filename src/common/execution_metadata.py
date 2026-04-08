from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def write_execution_metadata(
    output_dir: Path,
    module_name: str,
    mode: str,
    include_supporting: bool,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        [
            {
                "module": module_name,
                "mode": mode,
                "include_supporting": include_supporting,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )

    path = output_dir / f"{module_name.lower()}_execution_metadata.csv"
    df.to_csv(path, index=False)
    return path