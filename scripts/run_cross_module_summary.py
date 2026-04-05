from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "clients"


MODULE_FINDINGS = {
    "TERM": "term_findings.csv",
    "RKEG": "rkeg_findings.csv",
    "LEAVE": "leave_leakage_findings.csv",
    "LSL": "lsl_findings.csv",
    "CROSS_MODULE": "cross_module_findings.csv",
}


def _empty_findings_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "employee_id",
            "leave_type",
            "as_of_date",
            "rule_code",
            "severity",
            "classification",
            "message",
            "diff_units",
            "evidence",
            "finding_id",
            "next_action",
            "module",
        ]
    )


def _load_module_findings(outputs_dir: Path, module_name: str, filename: str) -> pd.DataFrame:
    path = outputs_dir / filename

    if not path.exists():
        print(f"[WARN] {module_name}: findings file not found: {path.name}")
        return _empty_findings_df()

    df = pd.read_csv(path)

    if df.empty:
        print(f"[INFO] {module_name}: findings file exists but is empty: {path.name}")
        df = _empty_findings_df()
    else:
        df = df.copy()

    if "classification" not in df.columns:
        df["classification"] = "UNCLASSIFIED"
    else:
        df["classification"] = df["classification"].fillna("UNCLASSIFIED")

    if "severity" not in df.columns:
        df["severity"] = pd.NA

    if "rule_code" not in df.columns:
        df["rule_code"] = pd.NA

    df["module"] = module_name

    expected_cols = [
        "employee_id",
        "leave_type",
        "as_of_date",
        "rule_code",
        "severity",
        "classification",
        "message",
        "diff_units",
        "evidence",
        "finding_id",
        "next_action",
        "module",
    ]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA

    return df[expected_cols]


def build_cross_module_summary(client: str, pilot: str) -> None:
    pilot_root = DATA_ROOT / client / pilot
    outputs_dir = pilot_root / "outputs"

    if not outputs_dir.exists():
        raise FileNotFoundError(f"Outputs directory not found: {outputs_dir}")

    module_dfs: list[pd.DataFrame] = []

    for module_name, filename in MODULE_FINDINGS.items():
        df = _load_module_findings(outputs_dir, module_name, filename)
        module_dfs.append(df)

    all_findings = pd.concat(module_dfs, ignore_index=True)

    all_findings_path = outputs_dir / "crc_all_module_findings.csv"
    all_findings.to_csv(all_findings_path, index=False)

    if all_findings.empty:
        by_module_df = pd.DataFrame(columns=["module", "finding_count"])
        by_classification_df = pd.DataFrame(columns=["classification", "finding_count"])
        by_classification_x_severity_df = pd.DataFrame(
            columns=["classification", "severity", "finding_count"]
        )
        by_module_x_classification_df = pd.DataFrame(
            columns=["module", "classification", "finding_count"]
        )
        by_module_x_classification_x_severity_df = pd.DataFrame(
            columns=["module", "classification", "severity", "finding_count"]
        )
    else:
        by_module_df = (
            all_findings.groupby("module", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

        by_classification_df = (
            all_findings.groupby("classification", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

        by_classification_x_severity_df = (
            all_findings.groupby(["classification", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["classification", "severity"])
        )

        by_module_x_classification_df = (
            all_findings.groupby(["module", "classification"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["module", "finding_count"], ascending=[True, False])
        )

        by_module_x_classification_x_severity_df = (
            all_findings.groupby(["module", "classification", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["module", "classification", "severity"])
        )

    by_module_path = outputs_dir / "crc_summary_by_module.csv"
    by_classification_path = outputs_dir / "crc_summary_by_classification.csv"
    by_classification_x_severity_path = outputs_dir / "crc_summary_classification_x_severity.csv"
    by_module_x_classification_path = outputs_dir / "crc_summary_module_x_classification.csv"
    by_module_x_classification_x_severity_path = (
        outputs_dir / "crc_summary_module_x_classification_x_severity.csv"
    )

    by_module_df.to_csv(by_module_path, index=False)
    by_classification_df.to_csv(by_classification_path, index=False)
    by_classification_x_severity_df.to_csv(by_classification_x_severity_path, index=False)
    by_module_x_classification_df.to_csv(by_module_x_classification_path, index=False)
    by_module_x_classification_x_severity_df.to_csv(
        by_module_x_classification_x_severity_path, index=False
    )

    print(f"Wrote: {all_findings_path}")
    print(f"Wrote: {by_module_path}")
    print(f"Wrote: {by_classification_path}")
    print(f"Wrote: {by_classification_x_severity_path}")
    print(f"Wrote: {by_module_x_classification_path}")
    print(f"Wrote: {by_module_x_classification_x_severity_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate CRC findings across modules into cross-module summary outputs."
    )
    parser.add_argument("--client", required=True, help="Client code, e.g. CLT_KAGGLE_TEST")
    parser.add_argument("--pilot", required=True, help="Pilot code, e.g. PILOT_003_2026_04_02")
    args = parser.parse_args()

    build_cross_module_summary(client=args.client, pilot=args.pilot)


if __name__ == "__main__":
    main()