from __future__ import annotations

from pathlib import Path
from datetime import date
import pandas as pd
import yaml

from src.common.paths import get_processed_dir, get_outputs_dir
from src.common.data_window import write_data_window

from src.lsl_exposure.models import Finding
from src.lsl_exposure.detectors.registry import run_rule
from src.lsl_exposure.rules import prepare_lsl_state, compute_exposure_band


REQUIRED_EMP = {"employee_id", "employment_type", "fte", "start_date"}
REQUIRED_SNAP = {"employee_id", "leave_type", "as_of_date", "balance_units"}
REQUIRED_LEDGER = {"employee_id", "leave_type", "event_date", "units", "event_type"}


def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _load_rules(rules_path: Path) -> list[dict]:
    with rules_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("rules", [])


def main(client: str, pilot: str) -> int:
    processed_dir = get_processed_dir(client, pilot)
    output_dir = get_outputs_dir(client, pilot)

    rules_path = Path(__file__).resolve().parent / "config" / "lsl_rules.yml"

    employees = pd.read_csv(
        processed_dir / "employees.csv",
        dtype={"employee_id": "string"},
    )

    snapshot = pd.read_csv(
        processed_dir / "balances_snapshot.csv",
        dtype={"employee_id": "string", "leave_type": "string"},
    )

    ledger = pd.read_csv(
        processed_dir / "leave_ledger.csv",
        dtype={"employee_id": "string", "leave_type": "string", "event_type": "string"},
    )

    pay_rates_path = processed_dir / "pay_rates.csv"
    pay_rates = None
    if pay_rates_path.exists():
        pay_rates = pd.read_csv(
            pay_rates_path,
            dtype={"employee_id": "string"},
        )

    for df in (employees, snapshot, ledger):
        df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    _require_cols(snapshot, REQUIRED_SNAP, "balances_snapshot.csv")
    _require_cols(ledger, REQUIRED_LEDGER, "leave_ledger.csv")

    employees["start_date"] = pd.to_datetime(employees["start_date"], errors="coerce")
    snapshot["as_of_date"] = pd.to_datetime(snapshot["as_of_date"], errors="coerce")
    ledger["event_date"] = pd.to_datetime(ledger["event_date"], errors="coerce")

    bad_emp_dates = employees["start_date"].isna().sum()
    bad_snapshot_dates = snapshot["as_of_date"].isna().sum()
    bad_ledger_dates = ledger["event_date"].isna().sum()

    print(f"[input] Using processed directory: {processed_dir}")
    print(f"[input] Unparseable employee start_date rows: {bad_emp_dates}")
    print(f"[input] Unparseable snapshot as_of_date rows: {bad_snapshot_dates}")
    print(f"[input] Unparseable ledger event_date rows: {bad_ledger_dates}")

    window_dates: list[date] = []

    emp_dates = employees["start_date"].dropna()
    snap_dates = snapshot["as_of_date"].dropna()
    ledger_dates = ledger["event_date"].dropna()

    if not emp_dates.empty:
        window_dates.extend(emp_dates.dt.date.tolist())
    if not snap_dates.empty:
        window_dates.extend(snap_dates.dt.date.tolist())
    if not ledger_dates.empty:
        window_dates.extend(ledger_dates.dt.date.tolist())

    write_data_window(output_dir / "lsl_data_window.csv", window_dates)

    snapshot_date = snapshot["as_of_date"].max()

    state = prepare_lsl_state(
        employees=employees,
        snapshot=snapshot,
        pay_rates=pay_rates,
        snapshot_date=snapshot_date,
    )

    rules = _load_rules(rules_path)
    print([r["id"] for r in rules][-5:])

    findings: list[Finding] = []
    datasets = {
        "employee_master": employees,
        "leave_snapshot": snapshot,
        "leave_ledger": ledger,
    }

    context = {"state": state}

    for rule in rules:
        findings.extend(run_rule(rule, datasets, context=context))

    eligibility_years = 7.0
    full_years = 10.0
    hours_per_day = 7.6

    total_low, total_high = compute_exposure_band(
        state=state,
        eligibility_years=eligibility_years,
        full_years=full_years,
        hours_per_day=hours_per_day,
    )

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
                "classification",
                "message",
                "diff_units",
                "evidence",
                "finding_id",
                "next_action",
            ]
        )

    findings_path = output_dir / "lsl_findings.csv"
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

    summary_path = output_dir / "lsl_summary.csv"
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

    severity_summary_path = output_dir / "lsl_summary_by_severity.csv"
    severity_summary_df.to_csv(severity_summary_path, index=False)

    exposure_path = output_dir / "lsl_exposure_summary.csv"
    pd.DataFrame(
        [
            {"metric": "estimated_exposure_low", "value": round(total_low, 2), "currency": "AUD"},
            {"metric": "estimated_exposure_high", "value": round(total_high, 2), "currency": "AUD"},
            {
                "metric": "note",
                "value": "Indicative-only estimate based on heuristics, not statutory entitlement calculations.",
                "currency": "",
            },
        ]
    ).to_csv(exposure_path, index=False)

    print(f"Wrote: {findings_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {severity_summary_path}")
    print(f"Wrote: {exposure_path}")

    return 0