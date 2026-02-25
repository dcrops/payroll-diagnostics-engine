from __future__ import annotations

from pathlib import Path
import pandas as pd

from lsl_exposure.rules import (
    Finding,
    prepare_lsl_state,
    rule_lsl_missing_for_eligible,
    rule_lsl_negative_balance,
    rule_lsl_zero_balance_for_long_tenure,
    rule_lsl_balance_suspiciously_low,
    compute_exposure_band,
)

from common.data_window import write_data_window

REQUIRED_EMP = {"employee_id", "employment_type", "fte", "start_date"}
REQUIRED_SNAP = {"employee_id", "leave_type", "as_of_date", "balance_units"}
# Optional pay_rates columns: employee_id, hourly_rate and/or annual_salary, optional as_of_date


def _require_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "outputs"
    modules_dir = out_dir / "modules"

    out_dir.mkdir(parents=True, exist_ok=True)
    modules_dir.mkdir(parents=True, exist_ok=True)

    employees = pd.read_csv(
        "data/sample/employees.csv",
        dtype={"employee_id": "string"},
    )

    snapshot = pd.read_csv(
        "data/sample/balances_snapshot.csv",
        dtype={"employee_id": "string", "leave_type": "string"},
    )

    # Optional pay rates file (you create it if you want $ exposure)
    pay_rates_path = repo_root / "data" / "sample" / "pay_rates.csv"
    pay_rates = None
    if pay_rates_path.exists():
        pay_rates = pd.read_csv(
            pay_rates_path,
            dtype={"employee_id": "string"},
        )

    for df in (employees, snapshot):
        df["employee_id"] = df["employee_id"].astype(str).str.strip()

    _require_cols(employees, REQUIRED_EMP, "employees.csv")
    _require_cols(snapshot, REQUIRED_SNAP, "balances_snapshot.csv")

    # Parse dates
    employees["start_date"] = pd.to_datetime(
        employees["start_date"], errors="coerce", dayfirst=True
    )
    snapshot["as_of_date"] = pd.to_datetime(
        snapshot["as_of_date"], errors="coerce", dayfirst=True
    )

    bad_emp_dates = employees["start_date"].isna().sum()
    bad_snapshot_dates = snapshot["as_of_date"].isna().sum()
    print(f"[input] Unparseable employee start_date rows: {bad_emp_dates}")
    print(f"[input] Unparseable snapshot as_of_date rows: {bad_snapshot_dates}")

    # ----------------------------
    # LSL data window (for reporting)
    # ----------------------------
    window_dates: list[date] = []

    emp_dates = employees["start_date"].dropna()
    snap_dates = snapshot["as_of_date"].dropna()

    if not emp_dates.empty:
        window_dates.extend(emp_dates.dt.date.tolist())
    if not snap_dates.empty:
        window_dates.extend(snap_dates.dt.date.tolist())

    write_data_window(modules_dir / "lsl_data_window.csv", window_dates)

    # Latest snapshot date is still useful for state prep
    snapshot_date = snapshot["as_of_date"].max()

    # Build LSL state view
    state = prepare_lsl_state(
        employees=employees,
        snapshot=snapshot,
        pay_rates=pay_rates,
        snapshot_date=snapshot_date,
    )

    # ----------------------------
    # Run rules
    # ----------------------------
    eligibility_years = 7.0
    full_years = 10.0
    hours_per_day = 7.6

    findings: list[Finding] = []
    findings.extend(rule_lsl_missing_for_eligible(state, eligibility_years=eligibility_years))
    findings.extend(rule_lsl_negative_balance(state))
    findings.extend(rule_lsl_zero_balance_for_long_tenure(state, eligibility_years=eligibility_years))
    findings.extend(rule_lsl_balance_suspiciously_low(state, full_years=full_years, low_floor_units=20.0))

    # Exposure sizing (optional; only counts rows with hourly_rate)
    total_low, total_high = compute_exposure_band(
        state=state,
        eligibility_years=eligibility_years,
        full_years=full_years,
        hours_per_day=hours_per_day,
    )

    # ----------------------------
    # Write findings output
    # ----------------------------
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

    findings_path = modules_dir / "lsl_findings.csv"
    findings_df.to_csv(findings_path, index=False)

    # ----------------------------
    # Summary output (counts by rule and severity)
    # ----------------------------
    if len(findings_df) == 0:
        summary_df = pd.DataFrame(columns=["rule_code", "severity", "finding_count"])
    else:
        summary_df = (
            findings_df.groupby(["rule_code", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values(["severity", "finding_count"], ascending=[True, False])
        )

    summary_path = modules_dir / "lsl_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    # ----------------------------
    # Summary output (totals by severity)
    # ----------------------------
    if len(findings_df) == 0:
        severity_summary_df = pd.DataFrame(columns=["severity", "finding_count"])
    else:
        severity_summary_df = (
            findings_df.groupby("severity", as_index=False)
            .size()
            .rename(columns={"size": "finding_count"})
            .sort_values("finding_count", ascending=False)
        )

    severity_summary_path = modules_dir / "lsl_summary_by_severity.csv"
    severity_summary_df.to_csv(severity_summary_path, index=False)

    # ----------------------------
    # Exposure summary
    # ----------------------------
    exposure_path = modules_dir / "lsl_exposure_summary.csv"
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


if __name__ == "__main__":
    raise SystemExit(main())
