from pathlib import Path
import pandas as pd
import yaml

BASE = Path("data/clients/kaggle_demo/pilot_001")
RAW = BASE / "raw"
CONFIG = BASE / "config"
PROCESSED = BASE / "processed"

def load_mapping():
    with open(CONFIG / "column_mapping.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def create_leave_balances(employees_df, raw_dir, leave_cfg):
    df = pd.read_csv(raw_dir / leave_cfg["source_file"])
    df = df.rename(columns=leave_cfg["rename"])

    # --- Clean names ---
    df["employee_name"] = df["employee_name"].str.strip().str.lower()

    # Create a lookup from employees
    emp_lookup = employees_df.copy()
    emp_lookup["employee_name"] = (
        emp_lookup["job_title"]  # TEMP fallback (we’ll fix this properly below)
    )

    # 🚨 Instead of trying to match names (which we don't have in IBM HR),
    # we will assign IDs directly

    master_ids = employees_df["employee_id"].tolist()

    df["employee_id"] = [
        master_ids[i % len(master_ids)]
        for i in range(len(df))
    ]

    # Standardise leave type
    df["leave_type"] = df["leave_type"].str.lower().str.replace(" ", "_")

    # Standardise date
    df["as_of_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    df["as_of_date"] = df["as_of_date"].dt.strftime("%Y-%m-%d")

    return df[
        [
            "employee_id",
            "leave_type",
            "as_of_date",
            "balance_units",
        ]
    ]

def main():
    mapping = load_mapping()
    emp_cfg = mapping["employees"]

    df = pd.read_csv(RAW / emp_cfg["source_file"])
    df = df.rename(columns=emp_cfg["rename"])

    # --- Derived fields ---
    df["annual_salary"] = df["monthly_income"] * 12

    df["employment_status"] = df["attrition_flag"].map({
        "Yes": "Terminated",
        "No": "Active"
    }).fillna("Active")

    reference_date = pd.Timestamp("2026-03-01")

    df["start_date"] = reference_date - pd.to_timedelta(
        df["years_at_company"] * 365, unit="D"
    )
    df["start_date"] = df["start_date"].dt.strftime("%Y-%m-%d")

    df["termination_date"] = ""
    df.loc[df["employment_status"] == "Terminated", "termination_date"] = "2025-12-31"

    # --- Final schema ---
    employees = df[
        [
            "employee_id",
            "department",
            "job_title",
            "annual_salary",
            "overtime_flag",
            "employment_status",
            "start_date",
            "termination_date",
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

    payroll = create_payroll(employees)
    payroll.to_csv(PROCESSED / "payroll_transactions.csv", index=False)

    print("✅ payroll_transactions.csv created")
    print(payroll.head())

    leave_cfg = mapping["leave_balances"]

    leave_balances = create_leave_balances(employees, RAW, leave_cfg)
    leave_balances.to_csv(PROCESSED / "leave_balances.csv", index=False)

    print("✅ leave_balances.csv created")
    print(leave_balances.head())

def create_payroll(employees_df):
    payroll = employees_df.copy()

    payroll["pay_date"] = "2026-03-15"
    payroll["pay_period_start"] = "2026-03-02"
    payroll["pay_period_end"] = "2026-03-15"

    payroll["earning_code"] = "BASE"
    payroll["earning_description"] = "Base Pay"

    payroll["units"] = 76

    payroll["gross_earnings"] = payroll["annual_salary"] / 26
    payroll["rate"] = payroll["gross_earnings"] / payroll["units"]
    payroll["amount"] = payroll["gross_earnings"]

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

if __name__ == "__main__":
    main()