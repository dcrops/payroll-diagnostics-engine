from __future__ import annotations

from subprocess import run
import sys
from pathlib import Path


PYTHON = sys.executable
ROOT = Path(__file__).resolve().parent

COMMANDS = [
    ([PYTHON, "-m", "rkeg.run"], ROOT),
    ([PYTHON, "-m", "leave_leakage.run"], ROOT),
    ([PYTHON, "-m", "termination_exposure.run"], ROOT),
    ([PYTHON, "-m", "lsl_exposure.run"], ROOT),
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

    print("\n✅ All CRC diagnostic modules completed successfully.")


if __name__ == "__main__":
    main()