from subprocess import run
import sys
from pathlib import Path

# Use the same interpreter that is running this script
PYTHON = sys.executable

# Paths
ROOT = Path(__file__).resolve().parent
PH_APP_DIR = ROOT.parent / "address-holidays-app"

# Each command is (argv_list, cwd)
# Each command is (argv_list, cwd)
COMMANDS = [
    # Core payroll modules
    ([PYTHON, "-m", "leave_leakage.run"], ROOT),
    ([PYTHON, "-m", "lsl_exposure.run"], ROOT),

    # Termination Exposure module
    ([PYTHON, "-m", "termination_exposure.run"], ROOT),

    # Combined reporting (uses outputs from the modules above)
    ([PYTHON, "-m", "reporting.run"], ROOT),

    # Public holiday batch - run from the address-holidays-app repo
    ([PYTHON, "-m", "src.address_holidays.run"], PH_APP_DIR),
]


def main() -> None:
    print(f"Using Python interpreter: {PYTHON}")
    for cmd, cwd in COMMANDS:
        print(f"\n▶ Running: {' '.join(str(c) for c in cmd)}")
        print(f"   in cwd: {cwd}")
        result = run(cmd, cwd=str(cwd))
        if result.returncode != 0:
            print("✗ Command failed, stopping pipeline.")
            sys.exit(result.returncode)

    print("\n✅ All compliance checks and reports completed successfully.")


if __name__ == "__main__":
    main()
