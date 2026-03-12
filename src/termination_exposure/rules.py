from __future__ import annotations

import pandas as pd


def prepare_term_state(
    terminations: pd.DataFrame,
    pay_events: pd.DataFrame,
    employees: pd.DataFrame,
) -> pd.DataFrame:
    emp = employees.copy()
    emp["employee_id"] = emp["employee_id"].astype(str).str.strip()
    term = terminations.copy()
    term["employee_id"] = term["employee_id"].astype(str).str.strip()
    term["termination_date"] = pd.to_datetime(term["termination_date"], errors="coerce")

    pay = pay_events.copy()
    if not pay.empty:
        pay["employee_id"] = pay["employee_id"].astype(str).str.strip()
        pay["pay_date"] = pd.to_datetime(pay["pay_date"], errors="coerce")

        if "is_final_pay" not in pay.columns:
            pay["is_final_pay"] = ""

        pay["is_final_pay_norm"] = (
            pay["is_final_pay"].astype(str).str.strip().str.lower().isin({"y", "yes", "true", "t", "1"})
        )

        pay = pay.sort_values(["employee_id", "pay_date"])

        last_pay = (
            pay.groupby("employee_id", as_index=False)
            .tail(1)[["employee_id", "pay_date"]]
            .rename(columns={"pay_date": "last_pay_date"})
        )

        first_final_pay = (
            pay[pay["is_final_pay_norm"]]
            .sort_values(["employee_id", "pay_date"])
            .groupby("employee_id", as_index=False)
            .head(1)[["employee_id", "pay_date"]]
            .rename(columns={"pay_date": "first_final_pay_date"})
        )
    else:
        last_pay = pd.DataFrame(columns=["employee_id", "last_pay_date"])
        first_final_pay = pd.DataFrame(columns=["employee_id", "first_final_pay_date"])

    state = term.merge(last_pay, on="employee_id", how="left")
    state = state.merge(first_final_pay, on="employee_id", how="left")
    state = state.merge(
        emp[["employee_id", "employment_type"]],
        on="employee_id",
        how="left"
)
    return state