import pandas as pd
from pathlib import Path
import json
import argparse


def load_summary(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing summary file: {path}")
    return pd.read_csv(path)

def derive_signals(df: pd.DataFrame) -> dict:
    total_findings = df["finding_count"].sum()

    # Aggregate by classification
    class_summary = (
        df.groupby("classification")["finding_count"]
        .sum()
        .to_dict()
    )

    # Aggregate by severity
    severity_summary = (
        df.groupby("severity")["finding_count"]
        .sum()
        .to_dict()
    )

    # High severity by module
    high_df = df[df["severity"] == "HIGH"]

    high_by_module = (
        high_df.groupby("module")["finding_count"]
        .sum()
        .sort_values(ascending=False)
    )

    top_high_modules = high_by_module.head(2).index.tolist()

    # Classification shares
    class_shares = {
        k: v / total_findings for k, v in class_summary.items()
    }

    dominant_classification = max(class_summary, key=class_summary.get)
    dominant_severity = max(severity_summary, key=severity_summary.get)

    return {
        "total_findings": int(total_findings),
        "class_summary": class_summary,
        "severity_summary": severity_summary,
        "class_shares": class_shares,
        "dominant_classification": dominant_classification,
        "dominant_severity": dominant_severity,
        "top_high_modules": top_high_modules,
    }

def interpret_signals(signals: dict) -> dict:
    total = signals["total_findings"]
    dom_class = signals["dominant_classification"]
    dom_sev = signals["dominant_severity"]
    shares = signals["class_shares"]
    top_modules = signals["top_high_modules"]
    class_summary = signals.get("class_summary", {})
    severity_summary = signals.get("severity_summary", {})

    lines = []
    lines.append(f"CRC identified {total} findings across the reviewed modules.")

    structural_count = class_summary.get("STRUCTURAL", 0)
    structural_share = shares.get("STRUCTURAL", 0)
    high_count = severity_summary.get("HIGH", 0)
    high_share = high_count / total if total else 0

    # Classification interpretation
    if shares.get(dom_class, 0) >= 0.5:
        if dom_class == "LOGICAL":
            lines.append(
                "The overall profile is primarily driven by logical integrity failures rather than structural data limitations."
            )
            meaning = (
                "The results suggest the main concern is substantive payroll processing "
                "and control integrity rather than simple evidentiary or data quality limitations."
            )
        elif dom_class == "STRUCTURAL":
            lines.append(
                "The overall profile is primarily driven by structural data limitations and evidence gaps."
            )
            meaning = (
                "The results suggest data completeness and record-keeping limitations are "
                "reducing confidence in payroll integrity and may be obscuring underlying issues."
            )
        elif dom_class == "CONTEXTUAL":
            lines.append(
                "The overall profile is primarily driven by contextual findings requiring business interpretation."
            )
            meaning = (
                "The results suggest the main effort now is review of policy application, "
                "business context, and case-by-case judgement rather than purely technical correction."
            )
        else:
            lines.append(
                "The findings are concentrated within a single classification category."
            )
            meaning = (
                "The risk profile is highly concentrated and should be reviewed directly."
            )
    else:
        lines.append(
            "The overall profile is mixed across logical, structural, and contextual findings."
        )
        meaning = (
            "The results indicate a combination of substantive control issues, structural data limitations, "
            "and items requiring business judgement."
        )

    # Module focus
    if len(top_modules) >= 2:
        lines.append(
            f"High-severity findings are concentrated in {top_modules[0]} and {top_modules[1]}, "
            "indicating the strongest exposure sits in termination handling and record-keeping integrity."
        )
    elif len(top_modules) == 1:
        lines.append(
            f"High-severity findings are concentrated in {top_modules[0]}, indicating this is the strongest area of exposure."
        )

    # Structural insight
    if structural_count > 0 and structural_share < 0.5:
        lines.append(
            "Structural findings are present, but they are not the primary driver of risk in this review."
        )
    elif structural_share >= 0.5:
        lines.append(
            "Structural findings are a major feature of the current profile and are materially affecting confidence in the results."
        )

    # Severity insight
    if dom_sev == "HIGH":
        lines.append(
            "A substantial proportion of findings are high severity, indicating meaningful control exposure."
        )
    else:
        lines.append(
            f"The most common severity level is {dom_sev}."
        )

    # Recommended focus
    if len(top_modules) >= 2:
        recommendation = (
            f"Prioritise detailed review of {top_modules[0]} and {top_modules[1]} first, "
            "then address structural data gaps that may weaken evidentiary confidence."
        )
    elif len(top_modules) == 1:
        recommendation = (
            f"Prioritise detailed review of {top_modules[0]} first, "
            "then address structural data gaps that may weaken evidentiary confidence."
        )
    else:
        recommendation = (
            "Prioritise review of the highest-severity findings first, "
            "then address structural data gaps that may weaken evidentiary confidence."
        )

    return {
        "summary_lines": lines,
        "what_this_means": meaning,
        "recommended_focus": recommendation,
    }

def write_outputs(summary: dict, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "executive_summary.json"
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

def write_markdown(summary: dict, output_dir: Path):
    md_path = output_dir / "executive_summary.md"

    lines = ["## Executive Summary\n"]

    for line in summary["summary_lines"]:
        lines.append(f"- {line}")

    lines.append("\n### What this means\n")
    lines.append(summary["what_this_means"])

    lines.append("\n### Recommended focus\n")
    lines.append(summary["recommended_focus"])

    md_path.write_text("\n".join(lines))

def run(summary_file: Path, output_dir: Path):
    df = load_summary(summary_file)

    signals = derive_signals(df)
    interpretation = interpret_signals(signals)

    final = {**signals, **interpretation}

    write_outputs(final, output_dir)
    write_markdown(final, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)

    args = parser.parse_args()

    run(
        summary_file=Path(args.input),
        output_dir=Path(args.output_dir),
    )