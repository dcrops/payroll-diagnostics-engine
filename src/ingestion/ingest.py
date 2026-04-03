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

def _log_header(title: str):
    print(f"\n{'=' * 12} {title} {'=' * 12}")


def _diagnose_mapping(dataset_name: str, raw_df: pd.DataFrame, rename_map: dict):
    _log_header(f"MAPPING DIAGNOSTICS: {dataset_name}")

    raw_cols = list(raw_df.columns)
    expected_source_cols = list(rename_map.keys())
    canonical_cols = list(rename_map.values())

    missing_source_cols = [col for col in expected_source_cols if col not in raw_df.columns]
    matched_source_cols = [col for col in expected_source_cols if col in raw_df.columns]
    unused_raw_cols = [col for col in raw_cols if col not in expected_source_cols]

    print(f"Raw columns ({len(raw_cols)}): {raw_cols}")
    print(f"Expected source columns ({len(expected_source_cols)}): {expected_source_cols}")

    if matched_source_cols:
        print(f"Matched source columns ({len(matched_source_cols)}): {matched_source_cols}")

    if missing_source_cols:
        print(f"WARNING - Missing source columns ({len(missing_source_cols)}): {missing_source_cols}")
    else:
        print("No missing source columns.")

    if unused_raw_cols:
        print(f"Unused raw columns ({len(unused_raw_cols)}): {unused_raw_cols}")
    else:
        print("No unused raw columns.")

    print(f"Canonical target columns ({len(canonical_cols)}): {canonical_cols}")


def _diagnose_post_rename(dataset_name: str, df: pd.DataFrame, canonical_cols: list[str]):
    present_canonical = [col for col in canonical_cols if col in df.columns]
    missing_canonical = [col for col in canonical_cols if col not in df.columns]
    all_null_canonical = [col for col in present_canonical if df[col].isna().all()]

    print(f"Present canonical columns ({len(present_canonical)}): {present_canonical}")

    if missing_canonical:
        print(
            f"WARNING - Missing canonical columns after rename "
            f"({len(missing_canonical)}): {missing_canonical}"
        )
    else:
        print("No missing canonical columns after rename.")

    if all_null_canonical:
        print(
            f"WARNING - Canonical columns fully null after rename "
            f"({len(all_null_canonical)}): {all_null_canonical}"
        )
    else:
        print("No canonical columns fully null after rename.")

def _validate_critical_fields(
    dataset_name: str,
    df: pd.DataFrame,
    required_columns: list[str],
):
    missing_columns = [col for col in required_columns if col not in df.columns]

    all_null_columns = []
    for col in required_columns:
        if col in df.columns:
            cleaned = _normalise_blank_strings(df[col])
            if cleaned.isna().all():
                all_null_columns.append(col)

    if missing_columns:
        raise ValueError(
            f"{dataset_name}: missing critical columns after mapping: {missing_columns}"
        )

    if all_null_columns:
        raise ValueError(
            f"{dataset_name}: critical columns fully null/blank after mapping/parsing: {all_null_columns}"
        )

    print(f"VALIDATION OK - {dataset_name}: critical fields present and not fully null: {required_columns}")


def _warn_if_all_null(
    dataset_name: str,
    df: pd.DataFrame,
    warning_columns: list[str],
):
    all_null_columns = []
    for col in warning_columns:
        if col in df.columns:
            cleaned = _normalise_blank_strings(df[col])
            if cleaned.isna().all():
                all_null_columns.append(col)

    if all_null_columns:
        print(
            f"WARNING - {dataset_name}: optional but important columns fully null/blank: {all_null_columns}"
        )


def _normalise_leave_type(series: pd.Series) -> pd.Series:
    series = _normalise_blank_strings(series)

    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .str.replace(" ", "_", regex=False)
    )

def _normalise_blank_strings(series: pd.Series) -> pd.Series:
    return series.replace(r"^\s*$", pd.NA, regex=True)


def _parse_dates(
    series: pd.Series,
    dataset_name: str,
    column_name: str,
    fail_if_all_non_null_unparsed: bool = False,
) -> pd.Series:
    original = _normalise_blank_strings(series)

    # First pass (no dayfirst assumption)
    parsed = pd.to_datetime(
        original,
        errors="coerce",
    )

    # Second pass (for remaining unparsed values, try dayfirst)
    mask_unparsed = original.notna() & parsed.isna()
    if mask_unparsed.any():
        parsed_dayfirst = pd.to_datetime(
            original[mask_unparsed],
            errors="coerce",
            dayfirst=True,
        )
        parsed.loc[mask_unparsed] = parsed_dayfirst

    original_non_null_count = original.notna().sum()
    parsed_non_null_count = parsed.notna().sum()

    if fail_if_all_non_null_unparsed and original_non_null_count > 0 and parsed_non_null_count == 0:
        raise ValueError(
            f"{dataset_name}: all non-null values in '{column_name}' failed date parsing"
        )

    if original_non_null_count > 0 and parsed_non_null_count < original_non_null_count:
        failed_count = original_non_null_count - parsed_non_null_count
        print(
            f"WARNING - {dataset_name}: {failed_count} value(s) in '{column_name}' failed date parsing"
        )

    return parsed.dt.strftime("%Y-%m-%d")


def _read_and_rename(raw_dir: Path, dataset_name: str, cfg: dict) -> pd.DataFrame:
    source_file = cfg["source_file"]
    rename_map = cfg.get("rename", {})

    df = pd.read_csv(raw_dir / source_file)

    _diagnose_mapping(dataset_name, df, rename_map)

    renamed_df = df.rename(columns=rename_map)

    _diagnose_post_rename(dataset_name, renamed_df, list(rename_map.values()))

    return renamed_df


def _ensure_columns(df: pd.DataFrame, required: list[str], fill_value=pd.NA) -> pd.DataFrame:
    df = df.copy()
    for col in required:
        if col not in df.columns:
            df[col] = fill_value
    return df


def create_employees(raw_dir: Path, mapping: dict) -> pd.DataFrame:
    emp_cfg = mapping["employees"]
    df = _read_and_rename(raw_dir, "employees", emp_cfg)

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
    df["employee_id"] = _normalise_blank_strings(
        df["employee_id"].astype("string").str.strip()
    )

    # Dates
    df["start_date"] = _parse_dates(
        df["start_date"],
        dataset_name="employees",
        column_name="start_date",
        fail_if_all_non_null_unparsed=False,
    )

    # Numeric fields
    for col in ["standard_hours", "fte", "base_rate"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    _validate_critical_fields(
        "employees",
        df,
        ["employee_id"],
    )

    _warn_if_all_null(
        "employees",
        df,
        ["start_date", "employment_type"],
    )

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

    df["employment_type"] = _normalise_blank_strings(
        df["employment_type"].astype("string").str.strip().str.upper()
    )

    # Defaults
    if df["employment_type"].isna().all():
        df["employment_type"] = "UNKNOWN"

    if df["fte"].isna().all():
        df["fte"] = 1.0

    # Placeholder termination_date until merged from terminations
    df["termination_date"] = pd.NA

    # If source status exists, keep it for now
    df["employment_status"] = _normalise_blank_strings(
        df["employment_status"].astype("string").str.strip().str.upper()
    )

        # Normalise employee_id
    df["employee_id"] = df["employee_id"].astype(str).str.strip()

    # Dates
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Numeric fields
    for col in ["standard_hours", "fte", "base_rate"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    _validate_critical_fields(
        "employees",
        df,
        ["employee_id"],
    )

    _warn_if_all_null(
        "employees",
        df,
        ["start_date", "employment_type"],
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
    df = _read_and_rename(raw_dir, "terminations", term_cfg)

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

    df["employee_id"] = _normalise_blank_strings(
        df["employee_id"].astype("string").str.strip()
    )

    df["termination_date"] = _parse_dates(
        df["termination_date"],
        dataset_name="terminations",
        column_name="termination_date",
        fail_if_all_non_null_unparsed=True,
    )

    _validate_critical_fields(
        "terminations",
        df,
        ["employee_id", "termination_date"],
    )

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
    df = _read_and_rename(raw_dir, "pay_events", pay_cfg)

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

    df["employee_id"] = _normalise_blank_strings(
        df["employee_id"].astype("string").str.strip()
    )

    df["pay_date"] = _parse_dates(
        df["pay_date"],
        dataset_name="pay_events",
        column_name="pay_date",
        fail_if_all_non_null_unparsed=True,
    )

    for col in ["gross_amount", "ote_amount", "super_amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    _validate_critical_fields(
        "pay_events",
        df,
        ["employee_id", "pay_date"],
    )

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
    df = _read_and_rename(raw_dir, "leave_ledger", ledger_cfg)

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

    df["employee_id"] = _normalise_blank_strings(
        df["employee_id"].astype("string").str.strip()
    )

    df["event_date"] = _parse_dates(
        df["event_date"],
        dataset_name="leave_ledger",
        column_name="event_date",
        fail_if_all_non_null_unparsed=True,
    )

    df["leave_type"] = _normalise_leave_type(
        _normalise_blank_strings(df["leave_type"])
    )

    df["units"] = pd.to_numeric(df["units"], errors="coerce")

    df["transaction_type"] = _normalise_blank_strings(
        df["transaction_type"].astype("string").str.strip().str.upper()
    )

    # CRC-friendly alias
    df["event_type"] = _normalise_blank_strings(
        df["transaction_type"].astype("string").str.strip().str.upper()
    )

    _validate_critical_fields(
        "leave_ledger",
        df,
        ["employee_id", "event_date", "leave_type", "units"],
    )

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


def create_leave_snapshot(
    raw_dir: Path,
    mapping: dict,
    snapshot_date_fallback: str | None = None,
) -> pd.DataFrame:
    snapshot_cfg = mapping["leave_snapshot"]
    df = _read_and_rename(raw_dir, "leave_snapshot", snapshot_cfg)

    df = _ensure_columns(
        df,
        [
            "employee_id",
            "as_of_date",
            "leave_type",
            "balance",
        ],
    )

    df["employee_id"] = _normalise_blank_strings(
        df["employee_id"].astype("string").str.strip()
    )

    df["as_of_date"] = _parse_dates(
        df["as_of_date"],
        dataset_name="leave_snapshot",
        column_name="as_of_date",
        fail_if_all_non_null_unparsed=False,
    )

    df["leave_type"] = _normalise_leave_type(
        _normalise_blank_strings(df["leave_type"])
    )

    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")

    # Derive snapshot date if not supplied in source
    if df["as_of_date"].isna().all() and snapshot_date_fallback:
        print(
            f"INFO - leave_snapshot: deriving as_of_date from fallback date "
            f"{snapshot_date_fallback}"
        )
        df["as_of_date"] = snapshot_date_fallback

    _validate_critical_fields(
        "leave_snapshot",
        df,
        ["employee_id", "leave_type", "balance"],
    )

    _warn_if_all_null(
        "leave_snapshot",
        df,
        ["as_of_date"],
    )

    snapshot = df[
        [
            "employee_id",
            "leave_type",
            "as_of_date",
            "balance",
        ]
    ].copy()

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

    snapshot_date_fallback = None
    if "pay_date" in pay_events.columns:
        non_null_pay_dates = pay_events["pay_date"].dropna()
        if not non_null_pay_dates.empty:
            snapshot_date_fallback = non_null_pay_dates.max()
            print(
                f"INFO - derived leave snapshot fallback date from pay_events: "
                f"{snapshot_date_fallback}"
            )

    # Leave
    leave_ledger = create_leave_ledger(raw_dir, mapping)
    leave_snapshot = create_leave_snapshot(
        raw_dir,
        mapping,
        snapshot_date_fallback=snapshot_date_fallback,
    )

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