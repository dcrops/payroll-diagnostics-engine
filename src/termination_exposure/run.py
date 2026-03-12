from __future__ import annotations

from pathlib import Path
from datetime import date
import pandas as pd
import yaml

from termination_exposure.models import Finding
from termination_exposure.detectors.registry import run_rule
from termination_exposure.rules import prepare_term_state

from common.data_window import write_data_window


REQUIRED_TERM = {"employee_id", "termination_date"}
REQUIRED_PAY = {"employee_id", "pay_date"}
REQUIRED_EMP = {"employee_id"}


def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _load_rules(rules_path: Path) -> list[dict]:
    with rules_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("rules", [])


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "outputs"
    modules_dir = out_dir / "modules"
    rules_path = Path(__file__).resolve().parent / "config" / "term_rules.yml"

    out_dir.mkdir(parents=True, exist_ok=True)
    modules_dir.mkdir(parents=True, exist_ok=True)

    terminations = pd.read_csv(
        repo_root / "data" / "sample" / "terminations.csv",
        dtype={"employee_id": "string"},
    )

    pay_events = pd.read_csv(
        repo_root / "data" / "sample" / "pay_events.csv",
        dtype={"employee_id": "string"},
    )

    employees = pd.read_csv(
        repo_root / "data" / "sample" / "employees.csv",
        dtype={"employee_id": "string"},
    )

    for df in (terminations, pay_events, employees):
        df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(terminations, REQUIRED_TERM, "terminations.csv")
    _require_cols(pay_events, REQUIRED_PAY, "pay_events.csv")
    _require_cols(employees, REQUIRED_EMP, "employees.csv")

    terminations["termination_date"] = pd.to_datetime(terminations["termination_date"], errors="coerce")
    pay_events["pay_date"] = pd.to_datetime(pay_events["pay_date"], errors="coerce")

    bad_term_dates = terminations["termination_date"].isna().sum()
    bad_pay_dates = pay_events["pay_date"].isna().sum()

    print(f"[input] Unparseable termination_date rows: {bad_term_dates}")
    print(f"[input] Unparseable pay_date rows: {bad_pay_dates}")

    window_dates: list[date] = []

    term_dates = terminations["termination_date"].dropna()
    pay_dates = pay_events["pay_date"].dropna()

    if not term_dates.empty:
        window_dates.extend(term_dates.dt.date.tolist())
    if not pay_dates.empty:
        window_dates.extend(pay_dates.dt.date.tolist())

    write_data_window(modules_dir / "term_data_window.csv", window_dates)

    state = prepare_term_state(
        terminations=terminations,
        pay_events=pay_events,
        employees=employees,
    )

    rules = _load_rules(rules_path)

    findings: list[Finding] = []
    datasets = {
        "terminations": terminations,
        "pay_events": pay_events,
        "employee_master": employees,
    }
    context = {"state": state}

    for rule in rules:
        findings.extend(run_rule(rule, datasets, context=context))

    if findings:
        findings_df = pd.DataFrame([f.__dict__ for f in findings])
    else:
        findings_df = pd.DataFrame(
            columns=[
                "employee_id",
                "leave_type",
                "as_of_date",
                "rule_code",
                "severity",
                "message",
                "diff_units",
                "evidence",
                "finding_id",
                "next_action",
            ]
        )

    findings_path = modules_dir / "term_findings.csv"
    findings_df.to_csv(findings_path, index=False)

    if len(findings_df) == 0:
        summary_df = pd.DataFrame(columns=["rule_code", "severity", "finding_count"])
    else:
        summary_df = (
            findings_df.groupby(["rule_code", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["severity", "finding_count"], ascending=[True, False])
        )

    summary_path = modules_dir / "term_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    if len(findings_df) == 0:
        severity_summary_df = pd.DataFrame(columns=["severity", "finding_count"])
    else:
        severity_summary_df = (
            findings_df.groupby("severity", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

    severity_summary_path = modules_dir / "term_summary_by_severity.csv"
    severity_summary_df.to_csv(severity_summary_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {severity_summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())