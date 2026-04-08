from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "clients"


def _pct_change(base: int, new: int) -> str:
    if base == 0:
        return "n/a"
    change = ((new - base) / base) * 100
    return f"{int(round(change))}%"


def build_insight(client: str, full_pilot: str) -> None:
    outputs_dir = DATA_ROOT / client / full_pilot / "outputs"
    comparison_path = outputs_dir / "crc_coverage_comparison.csv"

    if not comparison_path.exists():
        raise FileNotFoundError(f"Missing comparison file: {comparison_path}")

    df = pd.read_csv(comparison_path)

    lines: list[str] = []
    lines.append("# CRC Coverage Insight")
    lines.append("")

    total_payroll = int(df["payroll_total"].sum())
    total_full = int(df["full_total"].sum())
    total_delta = int(total_full - total_payroll)
    total_delta_pct = _pct_change(total_payroll, total_full)

    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Payroll-only findings: **{total_payroll}**")
    lines.append(f"- Full analysis findings: **{total_full}**")
    lines.append(f"- Additional findings identified with broader data coverage: **{total_delta} ({total_delta_pct})**")
    lines.append("")

    max_row = df.sort_values("delta_total", ascending=False).iloc[0]
    if int(max_row["delta_total"]) > 0:
        module = str(max_row["module"])
        uplift = _pct_change(int(max_row["payroll_total"]), int(max_row["full_total"]))
        lines.append(
            f"**{module}** shows the largest increase in findings when additional datasets are available, "
            f"with **{int(max_row['delta_total'])} additional findings** ({uplift} increase)."
        )
        lines.append("")

    lines.append("## Module Breakdown")
    lines.append("")

    for _, row in df.iterrows():
        module = str(row["module"])

        payroll_total = int(row["payroll_total"])
        full_total = int(row["full_total"])
        delta = int(row["delta_total"])

        payroll_core = int(row["payroll_core"])
        payroll_supporting = int(row["payroll_supporting"])
        payroll_extended = int(row["payroll_extended"])

        full_core = int(row["full_core"])
        full_supporting = int(row["full_supporting"])
        full_extended = int(row["full_extended"])

        lines.append(f"### {module}")
        lines.append("")
        lines.append(
            f"- Payroll-only: {payroll_total} findings "
            f"(core={payroll_core}, supporting={payroll_supporting}, extended={payroll_extended})"
        )
        lines.append(
            f"- Full: {full_total} findings "
            f"(core={full_core}, supporting={full_supporting}, extended={full_extended})"
        )

        if delta == 0:
            if module == "CROSS_MODULE":
                lines.append(
                    "- No additional findings were identified with broader datasets. "
                    "This module is fully assessable using payroll-only data and provides strong visibility into "
                    "cross-dataset inconsistencies."
                )
            else:
                lines.append(
                    "- No additional findings were identified with broader datasets. "
                    "This module is largely assessable using payroll-only data."
                )
        else:
            pct = _pct_change(payroll_total, full_total)
            lines.append(f"- Additional findings identified: {delta} ({pct} increase)")

            if module == "TERM":
                lines.append("")
                lines.append(
                    "Termination-related risks show the strongest dependency on additional datasets. "
                    "These areas are not fully assessable using payroll-only data and may only be identified when "
                    "broader system context is available."
                )
            elif module == "RKEG":
                lines.append("")
                lines.append(
                    "Governance and evidence-related risks are partially observable in payroll data, "
                    "with additional datasets improving both coverage and confidence of assessment."
                )

        lines.append("")

    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "Payroll-only analysis provides strong visibility into balance integrity, lifecycle sequencing, "
        "and cross-dataset consistency."
    )
    lines.append("")
    lines.append(
        "However, certain risk categories—particularly termination handling and governance controls—are not fully "
        "assessable without broader system context."
    )
    lines.append("")
    lines.append(
        "This reflects a coverage-based diagnostic model, where different datasets enable different levels of risk visibility."
    )
    lines.append("")
    lines.append("This supports a tiered diagnostic approach:")
    lines.append("")
    lines.append("- Payroll-only → fast, low-friction, high-confidence baseline")
    lines.append("- Full analysis → expanded coverage and deeper risk visibility")
    lines.append("")

    out_path = outputs_dir / "crc_coverage_insight.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote: {out_path}")
    print("\n--- Preview ---\n")
    print("\n".join(lines[:30]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CRC coverage insight markdown.")
    parser.add_argument("--client", required=True)
    parser.add_argument("--full-pilot", required=True)
    args = parser.parse_args()

    build_insight(client=args.client, full_pilot=args.full_pilot)


if __name__ == "__main__":
    main()