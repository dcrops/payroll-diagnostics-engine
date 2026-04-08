from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class ValidationIssue:
    module_name: str
    level: str          # ERROR | WARNING
    dataset: str
    column: Optional[str]
    issue_code: str
    message: str


@dataclass
class ValidationResult:
    module_name: str
    status: str         # READY | READY_WITH_WARNINGS | BLOCKED
    can_run: bool
    issues: list[ValidationIssue]

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "WARNING")


def _normalise_blank_strings(series: pd.Series) -> pd.Series:
    return series.replace(r"^\s*$", pd.NA, regex=True)


def _series_all_missing(series: pd.Series) -> bool:
    cleaned = _normalise_blank_strings(series)
    return cleaned.isna().all()


def make_result(module_name: str, issues: list[ValidationIssue]) -> ValidationResult:
    has_errors = any(i.level == "ERROR" for i in issues)
    has_warnings = any(i.level == "WARNING" for i in issues)

    if has_errors:
        status = "BLOCKED"
        can_run = False
    elif has_warnings:
        status = "READY_WITH_WARNINGS"
        can_run = True
    else:
        status = "READY"
        can_run = True

    return ValidationResult(
        module_name=module_name,
        status=status,
        can_run=can_run,
        issues=issues,
    )


def add_issue(
    issues: list[ValidationIssue],
    module_name: str,
    level: str,
    dataset: str,
    column: Optional[str],
    issue_code: str,
    message: str,
) -> None:
    issues.append(
        ValidationIssue(
            module_name=module_name,
            level=level,
            dataset=dataset,
            column=column,
            issue_code=issue_code,
            message=message,
        )
    )


def check_dataset_present(
    issues: list[ValidationIssue],
    module_name: str,
    dataset_name: str,
    df: pd.DataFrame,
    required: bool = True,
) -> None:
    if df is None or df.empty:
        level = "ERROR" if required else "WARNING"
        code = "MISSING_DATASET" if required else "OPTIONAL_DATASET_EMPTY"
        msg = (
            f"Required dataset '{dataset_name}' is missing or empty."
            if required
            else f"Optional dataset '{dataset_name}' is missing or empty."
        )
        add_issue(issues, module_name, level, dataset_name, None, code, msg)


def check_required_columns(
    issues: list[ValidationIssue],
    module_name: str,
    dataset_name: str,
    df: pd.DataFrame,
    required_columns: list[str],
    level: str = "ERROR",
) -> None:
    if df is None or df.empty:
        return

    for col in required_columns:
        if col not in df.columns:
            add_issue(
                issues,
                module_name,
                level,
                dataset_name,
                col,
                "MISSING_COLUMN",
                f"Column '{col}' is required in dataset '{dataset_name}' but was not found.",
            )


def check_critical_columns_not_all_missing(
    issues: list[ValidationIssue],
    module_name: str,
    dataset_name: str,
    df: pd.DataFrame,
    critical_columns: list[str],
    level: str = "ERROR",
) -> None:
    if df is None or df.empty:
        return

    for col in critical_columns:
        if col in df.columns and _series_all_missing(df[col]):
            add_issue(
                issues,
                module_name,
                level,
                dataset_name,
                col,
                "ALL_VALUES_MISSING",
                f"Critical column '{col}' in dataset '{dataset_name}' is fully null/blank.",
            )


def check_column_has_any_matching_values(
    issues: list[ValidationIssue],
    module_name: str,
    dataset_name: str,
    df: pd.DataFrame,
    column: str,
    allowed_values: list[str],
    level: str = "WARNING",
) -> None:
    if df is None or df.empty or column not in df.columns:
        return

    series = (
        df[column]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    allowed = {str(v).strip().upper() for v in allowed_values}
    has_match = series.isin(allowed).any()

    if not has_match:
        add_issue(
            issues,
            module_name,
            level,
            dataset_name,
            column,
            "NO_MATCHING_VALUES",
            f"Column '{column}' in dataset '{dataset_name}' does not contain any of the expected values: {sorted(allowed)}.",
        )


def print_validation_result(result: ValidationResult) -> None:
    print(f"\n=== {result.module_name} validation status: {result.status} ===")

    if not result.issues:
        print("No validation issues.")
        return

    for issue in result.issues:
        loc = f"{issue.dataset}.{issue.column}" if issue.column else issue.dataset
        print(f"[{issue.level}] {issue.issue_code} - {loc}: {issue.message}")


def write_validation_outputs(
    result: ValidationResult,
    output_dir: Path,
    filename_prefix: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_df = pd.DataFrame(
        [
            {
                "module_name": result.module_name,
                "status": result.status,
                "can_run": result.can_run,
                "error_count": result.error_count,
                "warning_count": result.warning_count,
            }
        ]
    )

    issues_df = pd.DataFrame([asdict(issue) for issue in result.issues])

    summary_df.to_csv(output_dir / f"{filename_prefix}_validation_summary.csv", index=False)

    if issues_df.empty:
        issues_df = pd.DataFrame(
            columns=["module_name", "level", "dataset", "column", "issue_code", "message"]
        )

    issues_df.to_csv(output_dir / f"{filename_prefix}_validation_issues.csv", index=False)