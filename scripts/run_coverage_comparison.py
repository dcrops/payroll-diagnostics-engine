from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "clients"


def _load_pivot(client: str, pilot: str) -> pd.DataFrame:
    path = DATA_ROOT / client / pilot / "outputs" / "crc_coverage_summary_pivot.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Coverage summary pivot not found for pilot '{pilot}': {path}"
        )

    df = pd.read_csv(path)

    expected_cols = ["module", "core", "supporting", "extended", "total_findings"]
    for col in expected_cols:
        if col not in df.columns:
            if col == "module":
                raise ValueError(f"Missing required column '{col}' in {path}")
            df[col] = 0

    df = df[expected_cols].copy()

    for col in ["core", "supporting", "extended", "total_findings"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df


def build_coverage_comparison(client: str, payroll_pilot: str, full_pilot: str) -> None:
    payroll_df = _load_pivot(client, payroll_pilot).rename(
        columns={
            "core": "payroll_core",
            "supporting": "payroll_supporting",
            "extended": "payroll_extended",
            "total_findings": "payroll_total",
        }
    )

    full_df = _load_pivot(client, full_pilot).rename(
        columns={
            "core": "full_core",
            "supporting": "full_supporting",
            "extended": "full_extended",
            "total_findings": "full_total",
        }
    )

    comparison_df = payroll_df.merge(full_df, on="module", how="outer").fillna(0)

    numeric_cols = [
        "payroll_core",
        "payroll_supporting",
        "payroll_extended",
        "payroll_total",
        "full_core",
        "full_supporting",
        "full_extended",
        "full_total",
    ]
    for col in numeric_cols:
        comparison_df[col] = pd.to_numeric(comparison_df[col], errors="coerce").fillna(0).astype(int)

    comparison_df["delta_core"] = comparison_df["full_core"] - comparison_df["payroll_core"]
    comparison_df["delta_supporting"] = comparison_df["full_supporting"] - comparison_df["payroll_supporting"]
    comparison_df["delta_extended"] = comparison_df["full_extended"] - comparison_df["payroll_extended"]
    comparison_df["delta_total"] = comparison_df["full_total"] - comparison_df["payroll_total"]

    module_order = ["LEAVE", "TERM", "LSL", "RKEG", "CROSS_MODULE"]
    comparison_df["module"] = pd.Categorical(
        comparison_df["module"], categories=module_order, ordered=True
    )
    comparison_df = comparison_df.sort_values("module").reset_index(drop=True)
    comparison_df["module"] = comparison_df["module"].astype(str)

    out_dir = DATA_ROOT / client / full_pilot / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "crc_coverage_comparison.csv"
    comparison_df.to_csv(out_path, index=False)

    print(f"Wrote: {out_path}")
    print("\nCRC Coverage Comparison")
    print(comparison_df.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare CRC coverage summaries between payroll-only and full runs."
    )
    parser.add_argument("--client", required=True, help="Client code, e.g. CLT_KAGGLE_TEST")
    parser.add_argument(
        "--payroll-pilot",
        required=True,
        help="Pilot used for payroll-only run, e.g. PILOT_004_CONTROLLED_CLEAN",
    )
    parser.add_argument(
        "--full-pilot",
        required=True,
        help="Pilot used for full run, e.g. PILOT_004_CONTROLLED_CLEAN_FULL",
    )
    args = parser.parse_args()

    build_coverage_comparison(
        client=args.client,
        payroll_pilot=args.payroll_pilot,
        full_pilot=args.full_pilot,
    )


if __name__ == "__main__":
    main()