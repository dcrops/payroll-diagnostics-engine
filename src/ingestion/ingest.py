from pathlib import Path
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "clients"

CLIENT = "CLT_KAGGLE_TEST"
PILOT = "PILOT_001_2026_03_26"

PILOT_ROOT = DATA_ROOT / CLIENT / PILOT

RAW = PILOT_ROOT / "raw"
CONFIG = PILOT_ROOT / "config"
PROCESSED = PILOT_ROOT / "processed"
LOGS = PILOT_ROOT / "logs"
OUTPUTS = PILOT_ROOT / "outputs"


def load_mapping(config_path):
    with open(config_path / "column_mapping.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _normalise_leave_type(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.upper()
        .str.replace(" ", "_", regex=False)
    )


def create_leave_balances(employees_df, raw_dir, leave_cfg):
    df = pd.read_csv(raw_dir / leave_cfg["source_file"])
    df = df.rename(columns=leave_cfg["rename"])

    master_ids = employees_df["employee_id"].tolist()

    df = df.copy()
    df["employee_id"] = [master_ids[i % len(master_ids)] for i in range(len(df))]

    # Standardise leave type consistently across all generated files
    df["leave_type"] = _normalise_leave_type(df["leave_type"])

    # Snapshot date should be aligned to the leave record end date for this pilot
    df["as_of_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["balance_units"] = pd.to_numeric(df["balance_units"], errors="coerce")

    return df[
        [
            "employee_id",
            "leave_type",
            "as_of_date",
            "balance_units",
        ]
    ]


def create_payroll(employees_df):
    payroll = employees_df.copy()

    payroll["pay_date"] = "2026-03-15"
    payroll["pay_period_start"] = "2026-03-02"
    payroll["pay_period_end"] = "2026-03-15"

    payroll["earning_code"] = "BASE"
    payroll["earning_description"] = "Base Pay"

    payroll["units"] = 76

    payroll["gross_earnings"] = (payroll["annual_salary"] / 26).round(2)
    payroll["rate"] = (payroll["gross_earnings"] / payroll["units"]).round(2)
    payroll["amount"] = payroll["gross_earnings"].round(2)

    return payroll[
        [
            "employee_id",
            "pay_date",
            "pay_period_start",
            "pay_period_end",
            "earning_code",
            "earning_description",
            "units",
            "rate",
            "amount",
            "gross_earnings",
        ]
    ]


def create_leave_requests(employees_df, raw_dir, leave_cfg):
    df = pd.read_csv(raw_dir / leave_cfg["source_file"])
    df = df.rename(columns=leave_cfg["rename"])

    master_ids = employees_df["employee_id"].tolist()

    df = df.copy()
    df["employee_id"] = [master_ids[i % len(master_ids)] for i in range(len(df))]

    # Match leave type format with ledger + snapshot
    df["leave_type"] = _normalise_leave_type(df["leave_type"])

    # Keep request dates aligned with source records
    df["request_start_date"] = pd.to_datetime(
        df["start_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    df["request_end_date"] = pd.to_datetime(
        df["end_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    df["units_requested"] = pd.to_numeric(df["days_taken"], errors="coerce")
    df["request_id"] = [f"R{str(i + 1).zfill(3)}" for i in range(len(df))]
    df["approval_status"] = "APPROVED"

    # For pilot purposes, treat all requests as approved on request start date
    df["approval_date"] = df["request_start_date"]
    df["approved_by"] = "MGR01"

    return df[
        [
            "request_id",
            "employee_id",
            "leave_type",
            "request_start_date",
            "request_end_date",
            "units_requested",
            "approval_status",
            "approval_date",
            "approved_by",
        ]
    ]


def create_timesheets(employees_df):
    records = []

    for emp_id in employees_df["employee_id"]:
        for day in pd.date_range("2024-03-01", "2024-03-10"):
            records.append(
                {
                    "employee_id": emp_id,
                    "work_date": day.strftime("%Y-%m-%d"),
                    "hours_worked": 7.6,
                    "timesheet_status": "submitted",
                }
            )

    return pd.DataFrame(records)


def create_leave_ledger(employees_df, raw_dir, leave_cfg):
    df = pd.read_csv(raw_dir / leave_cfg["source_file"])
    df = df.rename(columns=leave_cfg["rename"])

    master_ids = employees_df["employee_id"].tolist()

    df = df.copy()
    df["employee_id"] = [master_ids[i % len(master_ids)] for i in range(len(df))]

    # Match leave type format with requests + snapshot
    df["leave_type"] = _normalise_leave_type(df["leave_type"])

    # Align ledger event date to request_end_date logic
    df["event_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["units"] = pd.to_numeric(df["days_taken"], errors="coerce")
    df["event_type"] = "taken"

    return df[
        [
            "employee_id",
            "leave_type",
            "event_date",
            "units",
            "event_type",
        ]
    ]

def create_terminations(employees_df):
    terminated = employees_df.loc[
        employees_df["employment_status"].astype(str).str.strip().str.upper() == "TERMINATED",
        ["employee_id"]
    ].copy()

    base_date = pd.Timestamp("2026-02-01")
    terminated["termination_date"] = [
        (base_date + pd.Timedelta(days=i % 60)).strftime("%Y-%m-%d")
        for i in range(len(terminated))
    ]

    termination_types = ["RESIGNATION", "REDUNDANCY", "DISMISSAL"]
    termination_reasons = ["VOLUNTARY", "ROLE_CEASED", "PERFORMANCE"]

    terminated["termination_type"] = [
        termination_types[i % len(termination_types)]
        for i in range(len(terminated))
    ]

    terminated["termination_reason"] = [
        termination_reasons[i % len(termination_reasons)]
        for i in range(len(terminated))
    ]

    terminated["evidence_ref"] = [
        f"TERM-{str(i + 1).zfill(4)}"
        for i in range(len(terminated))
    ]

    return terminated

def create_pay_events_for_term(employees_df, terminations_df):
    terminated_ids = set(terminations_df["employee_id"].astype(str))
    term_lookup = dict(
        zip(
            terminations_df["employee_id"].astype(str),
            pd.to_datetime(terminations_df["termination_date"])
        )
    )

    records = []

    for i, row in employees_df.iterrows():
        emp_id = str(row["employee_id"])
        annual_salary = float(row["annual_salary"])
        gross = round(annual_salary / 26, 2)
        rate = round(gross / 76, 2)

        # Active employees
        if emp_id not in terminated_ids:
            records.append({
                "employee_id": emp_id,
                "pay_date": "2026-03-15",
                "pay_period_start": "2026-03-02",
                "pay_period_end": "2026-03-15",
                "earning_code": "BASE",
                "earning_description": "Base Pay",
                "is_final_pay": "N",
                "units": 76.0,
                "rate": rate,
                "amount": gross,
                "gross_earnings": gross,
            })
            continue

        term_date = term_lookup[emp_id]
        scenario = i % 4

        # 0 = final pay after termination
        if scenario == 0:
            pay_date = term_date + pd.Timedelta(days=3)
            earning_code = "FINAL"
            earning_description = "Final Pay"
            is_final_pay = "Y"

        # 1 = pay before termination only
        elif scenario == 1:
            pay_date = term_date - pd.Timedelta(days=3)
            earning_code = "BASE"
            earning_description = "Base Pay"
            is_final_pay = "N"

        # 2 = pay after termination but not flagged final
        elif scenario == 2:
            pay_date = term_date + pd.Timedelta(days=5)
            earning_code = "BASE"
            earning_description = "Base Pay"
            is_final_pay = "N"

        # 3 = older pay only
        else:
            pay_date = term_date - pd.Timedelta(days=10)
            earning_code = "BASE"
            earning_description = "Base Pay"
            is_final_pay = "N"

        records.append({
            "employee_id": emp_id,
            "pay_date": pay_date.strftime("%Y-%m-%d"),
            "pay_period_start": (pay_date - pd.Timedelta(days=13)).strftime("%Y-%m-%d"),
            "pay_period_end": pay_date.strftime("%Y-%m-%d"),
            "earning_code": earning_code,
            "earning_description": earning_description,
            "is_final_pay": is_final_pay,
            "units": 76.0,
            "rate": rate,
            "amount": gross,
            "gross_earnings": gross,
        })

    return pd.DataFrame(records)


def append_lsl_ledger_rows(leave_ledger_df, employees_df):
    eligible = employees_df.copy()

    eligible["years_at_company"] = pd.to_numeric(
        eligible["years_at_company"], errors="coerce"
    ).fillna(0)

    eligible = eligible[eligible["years_at_company"] >= 7].copy()

    if eligible.empty:
        return leave_ledger_df

    records = []

    for i, row in eligible.iterrows():
        emp_id = str(row["employee_id"]).strip()
        years = float(row["years_at_company"])
        start_date = pd.to_datetime(row["start_date"], errors="coerce")
        termination_date = pd.to_datetime(row["termination_date"], errors="coerce")

        if pd.isna(start_date):
            continue

        # Simple synthetic LSL accrual history:
        # one opening-style accrual after eligibility, then one later adjustment/accrual
        first_lsl_date = start_date + pd.Timedelta(days=int(7 * 365))
        second_lsl_date = first_lsl_date + pd.Timedelta(days=365)

        opening_units = round(max(10.0, (years - 7) * 4 + 10), 2)
        later_units = round(max(2.0, (years - 7) * 2), 2)

        records.append({
            "employee_id": emp_id,
            "leave_type": "LSL",
            "event_date": first_lsl_date.strftime("%Y-%m-%d"),
            "units": opening_units,
            "event_type": "ACCRUAL",
        })

        records.append({
            "employee_id": emp_id,
            "leave_type": "LSL",
            "event_date": second_lsl_date.strftime("%Y-%m-%d"),
            "units": later_units,
            "event_type": "ADJUSTMENT",
        })

        # If terminated, add a payout event for some employees so not all terminated staff retain LSL
        if not pd.isna(termination_date):
            if i % 2 == 0:
                payout_date = termination_date + pd.Timedelta(days=7)
                payout_units = round(opening_units + later_units, 2)

                records.append({
                    "employee_id": emp_id,
                    "leave_type": "LSL",
                    "event_date": payout_date.strftime("%Y-%m-%d"),
                    "units": -payout_units,
                    "event_type": "PAYOUT",
                })

    lsl_rows = pd.DataFrame(records)

    combined = pd.concat([leave_ledger_df, lsl_rows], ignore_index=True)
    return combined

def append_lsl_snapshot_from_ledger(leave_balances_df, leave_ledger_df):
    lsl_ledger = leave_ledger_df[
        leave_ledger_df["leave_type"].astype(str).str.upper() == "LSL"
    ].copy()

    if lsl_ledger.empty:
        return leave_balances_df

    lsl_ledger["units"] = pd.to_numeric(lsl_ledger["units"], errors="coerce").fillna(0)

    lsl_snapshot = (
        lsl_ledger.groupby("employee_id", as_index=False)["units"]
        .sum()
        .rename(columns={"units": "balance_units"})
    )

    lsl_snapshot["leave_type"] = "LSL"
    lsl_snapshot["as_of_date"] = "2024-12-31"
    lsl_snapshot["balance_units"] = lsl_snapshot["balance_units"].round(2)

    base_snapshot = leave_balances_df[
        leave_balances_df["leave_type"].astype(str).str.upper() != "LSL"
    ].copy()

    combined = pd.concat(
        [
            base_snapshot,
            lsl_snapshot[["employee_id", "leave_type", "as_of_date", "balance_units"]],
        ],
        ignore_index=True,
    )

    return combined

def add_employment_status(employees_df):
    df = employees_df.copy()

    df["termination_date"] = pd.to_datetime(
        df["termination_date"], errors="coerce"
    )

    df["employment_status"] = df["termination_date"].apply(
        lambda x: "TERMINATED" if pd.notna(x) else "ACTIVE"
    )

    return df

def main(client: str, pilot: str):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    DATA_ROOT = PROJECT_ROOT / "data" / "clients"

    PILOT_ROOT = DATA_ROOT / client / pilot

    RAW = PILOT_ROOT / "raw"
    CONFIG = PILOT_ROOT / "config"
    PROCESSED = PILOT_ROOT / "processed"
    LOGS = PILOT_ROOT / "logs"
    OUTPUTS = PILOT_ROOT / "outputs"

    # make sure folders exist
    PROCESSED.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    mapping = load_mapping(CONFIG)
   # mapping = load_mapping()
    emp_cfg = mapping["employees"]

    df = pd.read_csv(RAW / emp_cfg["source_file"])
    df = df.rename(columns=emp_cfg["rename"])

    # --- Derived fields ---
    df["annual_salary"] = (df["monthly_income"] * 12).round(2)

    # Temporary source-driven status used only to derive termination_date
    df["attrition_status"] = df["attrition_flag"].map(
        {
            "Yes": "TERMINATED",
            "No": "ACTIVE",
        }
    ).fillna("ACTIVE")

    # More realistic start dates for 2024 leave data
    reference_date = pd.Timestamp("2024-01-01")

    df["start_date"] = reference_date - pd.to_timedelta(
        df["years_at_company"] * 365, unit="D"
    )
    df["start_date"] = df["start_date"].dt.strftime("%Y-%m-%d")

    df["termination_date"] = ""
    df.loc[df["attrition_status"] == "TERMINATED", "termination_date"] = "2025-12-31"

    df["employment_type"] = "FULL_TIME"
    df["fte"] = 1.0
    df["base_rate"] = ((df["monthly_income"] * 12) / 52 / 38).round(2)

    # Final employment status derived from termination_date
    df["employment_status"] = pd.to_datetime(
        df["termination_date"], errors="coerce"
    ).apply(lambda x: "TERMINATED" if pd.notna(x) else "ACTIVE")

    # --- Final schema ---
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

    PROCESSED.mkdir(parents=True, exist_ok=True)
    employees.to_csv(PROCESSED / "employees.csv", index=False)

    print("✅ employees.csv created")
    print(employees.head())

    # --- TERM supporting data first ---
    terminations = create_terminations(employees)
    terminations.to_csv(PROCESSED / "terminations.csv", index=False)

    print("✅ terminations.csv created")
    print(terminations.head())

    # --- Payroll / pay events ---
    payroll = create_pay_events_for_term(employees, terminations)
    payroll.to_csv(PROCESSED / "payroll_transactions.csv", index=False)
    payroll.to_csv(PROCESSED / "pay_events.csv", index=False)

    print("✅ payroll_transactions.csv created")
    print("✅ pay_events.csv created")
    print(payroll.head())

    # --- Leave datasets ---
    leave_cfg = mapping["leave_balances"]

    leave_balances = create_leave_balances(employees, RAW, leave_cfg)

    leave_requests = create_leave_requests(employees, RAW, leave_cfg)
    leave_requests.to_csv(PROCESSED / "leave_requests.csv", index=False)

    timesheets = create_timesheets(employees)
    timesheets.to_csv(PROCESSED / "timesheets.csv", index=False)

    leave_ledger = create_leave_ledger(employees, RAW, leave_cfg)
    leave_ledger = append_lsl_ledger_rows(leave_ledger, employees)
    leave_ledger.to_csv(PROCESSED / "leave_ledger.csv", index=False)

    leave_balances = append_lsl_snapshot_from_ledger(leave_balances, leave_ledger)
    leave_balances.to_csv(PROCESSED / "balances_snapshot.csv", index=False)

    print("✅ leave_requests.csv created")
    print("✅ timesheets.csv created")
    print("✅ leave_ledger.csv created")
    print("✅ balances_snapshot.csv created")


if __name__ == "__main__":
    main()