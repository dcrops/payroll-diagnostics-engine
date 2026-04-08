from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "clients"

MODULE_VIABILITY_FILES = {
    "TERM": "term_summary_by_viability.csv",
    "LEAVE": "leave_leakage_summary_by_viability.csv",
    "LSL": "lsl_summary_by_viability.csv",
    "RKEG": "rkeg_summary_by_viability.csv",
    "CROSS_MODULE": "cross_module_summary_by_viability.csv",
}


def _empty_module_df(module_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"module": module_name, "viability_level": "core", "finding_count": 0},
            {"module": module_name, "viability_level": "supporting", "finding_count": 0},
            {"module": module_name, "viability_level": "extended", "finding_count": 0},
        ]
    )


def _load_viability_summary(outputs_dir: Path, module_name: str, filename: str) -> pd.DataFrame:
    path = outputs_dir / filename

    if not path.exists():
        print(f"[WARN] {module_name}: viability summary not found: {path.name}")
        return _empty_module_df(module_name)

    df = pd.read_csv(path)

    if df.empty:
        print(f"[INFO] {module_name}: viability summary exists but is empty: {path.name}")
        return _empty_module_df(module_name)

    df = df.copy()
    df["module"] = module_name

    if "viability_level" not in df.columns:
        df["viability_level"] = pd.NA
    if "finding_count" not in df.columns:
        df["finding_count"] = 0

    df = df[["module", "viability_level", "finding_count"]]

    expected_levels = {"core", "supporting", "extended"}
    existing_levels = set(df["viability_level"].dropna().astype(str).str.lower())

    missing_rows = []
    for level in sorted(expected_levels - existing_levels):
        missing_rows.append(
            {"module": module_name, "viability_level": level, "finding_count": 0}
        )

    if missing_rows:
        df = pd.concat([df, pd.DataFrame(missing_rows)], ignore_index=True)

    df["viability_level"] = df["viability_level"].astype(str).str.lower()
    df["finding_count"] = pd.to_numeric(df["finding_count"], errors="coerce").fillna(0).astype(int)

    return df


def build_coverage_summary(client: str, pilot: str) -> None:
    outputs_dir = DATA_ROOT / client / pilot / "outputs"

    if not outputs_dir.exists():
        raise FileNotFoundError(f"Outputs directory not found: {outputs_dir}")

    module_dfs: list[pd.DataFrame] = []

    for module_name, filename in MODULE_VIABILITY_FILES.items():
        df = _load_viability_summary(outputs_dir, module_name, filename)
        module_dfs.append(df)

    combined_df = pd.concat(module_dfs, ignore_index=True)

    combined_long_path = outputs_dir / "crc_coverage_summary.csv"
    combined_df.to_csv(combined_long_path, index=False)

    pivot_df = (
        combined_df.pivot(index="module", columns="viability_level", values="finding_count")
        .fillna(0)
        .astype(int)
        .reset_index()
    )

    for col in ["core", "supporting", "extended"]:
        if col not in pivot_df.columns:
            pivot_df[col] = 0

    pivot_df = pivot_df[["module", "core", "supporting", "extended"]]
    pivot_df["total_findings"] = pivot_df["core"] + pivot_df["supporting"] + pivot_df["extended"]

    module_order = ["LEAVE", "TERM", "LSL", "RKEG", "CROSS_MODULE"]
    pivot_df["module"] = pd.Categorical(pivot_df["module"], categories=module_order, ordered=True)
    pivot_df = pivot_df.sort_values("module").reset_index(drop=True)
    pivot_df["module"] = pivot_df["module"].astype(str)

    pivot_path = outputs_dir / "crc_coverage_summary_pivot.csv"
    pivot_df.to_csv(pivot_path, index=False)

    print(f"Wrote: {combined_long_path}")
    print(f"Wrote: {pivot_path}")
    print("\nCRC Coverage Summary")
    print(pivot_df.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build CRC coverage summary from module viability outputs."
    )
    parser.add_argument("--client", required=True, help="Client code, e.g. CLT_KAGGLE_TEST")
    parser.add_argument("--pilot", required=True, help="Pilot code, e.g. PILOT_004_CONTROLLED_CLEAN")
    args = parser.parse_args()

    build_coverage_summary(client=args.client, pilot=args.pilot)


if __name__ == "__main__":
    main()