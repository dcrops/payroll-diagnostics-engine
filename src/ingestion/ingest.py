from pathlib import Path
import argparse
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "clients"


def load_mapping(pilot_root: Path):
    config_candidate = pilot_root / "config" / "column_mapping.yaml"
    root_candidate = pilot_root / "column_mapping.yaml"

    if config_candidate.exists():
        mapping_path = config_candidate
    elif root_candidate.exists():
        mapping_path = root_candidate
    else:
        raise FileNotFoundError(
            f"Could not find column_mapping.yaml in either "
            f"{config_candidate} or {root_candidate}"
        )

    with open(mapping_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _normalise_leave_type(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.upper()
        .str.replace(" ", "_", regex=False)
    )


def _read_and_rename(raw_dir: Path, cfg: dict) -> pd.DataFrame:
    df = pd.read_csv(raw_dir / cfg["source_file"])
    rename_map = cfg.get("rename", {})
    return df.rename(columns=rename_map)


def _ensure_columns(df: pd.DataFrame, required: list[str], fill_value=pd.NA) -> pd.DataFrame:
    df = df.copy()
    for col in required:
        if col not in df.columns:
            df[col] = fill_value
    return df


def create_employees(raw_dir: Path, mapping: dict) -> pd.DataFrame:
    emp_cfg = mapping["employees"]
    df = _read_and_rename(raw_dir, emp_cfg)

    df = _ensure_columns(
        df,
        [
            "employee_id",
            "start_date",
            "employment_status",
            "employment_type",
            "standard_hours",
            "fte",
            "base_rate",
            "department",
        ],
    )

    # Normalise employee_id
    df["employee_id"] = df["employee_id"].astype(str).str.strip()

    # Dates
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Numeric fields
    for col in ["standard_hours", "fte", "base_rate"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Derive annual_salary only when possible
    if "annual_salary" not in df.columns:
        df["annual_salary"] = pd.NA

        if "monthly_income" in df.columns:
            monthly_income = pd.to_numeric(df["monthly_income"], errors="coerce")
            df["annual_salary"] = (monthly_income * 12).round(2)
        elif "base_rate" in df.columns and "standard_hours" in df.columns:
            annual_salary = df["base_rate"] * df["standard_hours"].fillna(38) * 52
            df["annual_salary"] = annual_salary.round(2)

    # Optional fields often present in older/synthetic datasets
    optional_cols = [
        "job_title",
        "overtime_flag",
        "age",
        "gender",
        "marital_status",
        "total_working_years",
        "years_at_company",
    ]
    df = _ensure_columns(df, optional_cols)

    # Defaults
    if df["employment_type"].isna().all():
        df["employment_type"] = "UNKNOWN"

    if df["fte"].isna().all():
        df["fte"] = 1.0

    # Placeholder termination_date until merged from terminations
    df["termination_date"] = pd.NA

    # If source status exists, keep it for now
    df["employment_status"] = (
        df["employment_status"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"NAN": pd.NA})
    )

    employees = df[
        [
            "employee_id",
            "department",
            "job_title",
            "annual_salary",
            "overtime_flag",
            "employment_status",
            "employment_type",
            "fte",
            "start_date",
            "termination_date",
            "base_rate",
            "age",
            "gender",
            "marital_status",
            "total_working_years",
            "years_at_company",
        ]
    ].copy()

    return employees


def create_terminations(raw_dir: Path, mapping: dict) -> pd.DataFrame:
    term_cfg = mapping["terminations"]
    df = _read_and_rename(raw_dir, term_cfg)

    df = _ensure_columns(
        df,
        [
            "employee_id",
            "termination_date",
            "termination_type",
            "termination_reason",
            "evidence_reference",
        ],
    )

    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["termination_date"] = pd.to_datetime(df["termination_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    terminations = df[
        [
            "employee_id",
            "termination_date",
            "termination_type",
            "termination_reason",
            "evidence_reference",
        ]
    ].copy()

    terminations = terminations.dropna(subset=["employee_id", "termination_date"]).drop_duplicates()

    return terminations


def merge_termination_status(employees: pd.DataFrame, terminations: pd.DataFrame) -> pd.DataFrame:
    df = employees.copy()

    term_dates = (
        terminations[["employee_id", "termination_date"]]
        .dropna(subset=["employee_id"])
        .drop_duplicates(subset=["employee_id"], keep="first")
    )

    df = df.drop(columns=["termination_date"], errors="ignore")
    df = df.merge(term_dates, on="employee_id", how="left")

    df["employment_status"] = pd.to_datetime(
        df["termination_date"], errors="coerce"
    ).apply(lambda x: "TERMINATED" if pd.notna(x) else "ACTIVE")

    return df


def create_pay_events(raw_dir: Path, mapping: dict) -> pd.DataFrame:
    pay_cfg = mapping["pay_events"]
    df = _read_and_rename(raw_dir, pay_cfg)

    df = _ensure_columns(
        df,
        [
            "employee_id",
            "pay_date",
            "pay_run_id",
            "gross_amount",
            "ote_amount",
            "super_amount",
            "is_final_pay",
            "pay_code",
        ],
    )

    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["pay_date"] = pd.to_datetime(df["pay_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    for col in ["gross_amount", "ote_amount", "super_amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    pay_events = df[
        [
            "employee_id",
            "pay_date",
            "pay_run_id",
            "gross_amount",
            "ote_amount",
            "super_amount",
            "is_final_pay",
            "pay_code",
        ]
    ].copy()

    return pay_events


def create_leave_ledger(raw_dir: Path, mapping: dict) -> pd.DataFrame:
    ledger_cfg = mapping["leave_ledger"]
    df = _read_and_rename(raw_dir, ledger_cfg)

    df = _ensure_columns(
        df,
        [
            "transaction_id",
            "employee_id",
            "event_date",
            "leave_type",
            "transaction_type",
            "units",
        ],
    )

    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["leave_type"] = _normalise_leave_type(df["leave_type"])
    df["units"] = pd.to_numeric(df["units"], errors="coerce")

    # CRC-friendly alias
    df["event_type"] = df["transaction_type"].astype(str).str.strip().str.upper()

    leave_ledger = df[
        [
            "transaction_id",
            "employee_id",
            "leave_type",
            "event_date",
            "units",
            "transaction_type",
            "event_type",
        ]
    ].copy()

    return leave_ledger


def create_leave_snapshot(raw_dir: Path, mapping: dict) -> pd.DataFrame:
    snapshot_cfg = mapping["leave_snapshot"]
    df = _read_and_rename(raw_dir, snapshot_cfg)

    df = _ensure_columns(
        df,
        [
            "employee_id",
            "as_of_date",
            "leave_type",
            "balance",
        ],
    )

    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["as_of_date"] = pd.to_datetime(df["as_of_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["leave_type"] = _normalise_leave_type(df["leave_type"])
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")

    snapshot = df[
        [
            "employee_id",
            "leave_type",
            "as_of_date",
            "balance",
        ]
    ].copy()

    # Preserve CRC's existing preferred output name
    snapshot = snapshot.rename(columns={"balance": "balance_units"})

    return snapshot


def main(client: str, pilot: str):
    pilot_root = DATA_ROOT / client / pilot
    raw_dir = pilot_root / "raw"
    processed_dir = pilot_root / "processed"
    logs_dir = pilot_root / "logs"
    outputs_dir = pilot_root / "outputs"

    processed_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    mapping = load_mapping(pilot_root)

    # Employees
    employees = create_employees(raw_dir, mapping)

    # Terminations
    terminations = create_terminations(raw_dir, mapping)
    employees = merge_termination_status(employees, terminations)

    # Pay events
    pay_events = create_pay_events(raw_dir, mapping)

    # Leave
    leave_ledger = create_leave_ledger(raw_dir, mapping)
    leave_snapshot = create_leave_snapshot(raw_dir, mapping)

    # Write outputs
    employees.to_csv(processed_dir / "employees.csv", index=False)
    terminations.to_csv(processed_dir / "terminations.csv", index=False)
    pay_events.to_csv(processed_dir / "pay_events.csv", index=False)

    # Optional alias to preserve older downstream expectations
    pay_events.to_csv(processed_dir / "payroll_transactions.csv", index=False)

    leave_ledger.to_csv(processed_dir / "leave_ledger.csv", index=False)
    leave_snapshot.to_csv(processed_dir / "balances_snapshot.csv", index=False)

    print("✅ employees.csv created")
    print(employees.head())

    print("✅ terminations.csv created")
    print(terminations.head())

    print("✅ pay_events.csv created")
    print("✅ payroll_transactions.csv created")
    print(pay_events.head())

    print("✅ leave_ledger.csv created")
    print(leave_ledger.head())

    print("✅ balances_snapshot.csv created")
    print(leave_snapshot.head())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CRC ingestion for a client pilot")
    parser.add_argument("--client", required=True, help="Client code, e.g. CLT_KAGGLE_TEST")
    parser.add_argument("--pilot", required=True, help="Pilot code, e.g. PILOT_002_2026_04_02")
    args = parser.parse_args()

    main(client=args.client, pilot=args.pilot)