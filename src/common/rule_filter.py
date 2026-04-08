def should_run_rule(rule: dict, mode: str = "full", include_supporting: bool = False) -> bool:
    viability = rule.get("viability", {})

    payroll_only = viability.get("payroll_only")

    # Default behaviour if metadata missing (backward compatible)
    if payroll_only is None:
        return True

    if mode == "full":
        return True

    if mode == "payroll_only":
        if payroll_only is True:
            return True
        if include_supporting and payroll_only == "partial":
            return True
        return False

    return True