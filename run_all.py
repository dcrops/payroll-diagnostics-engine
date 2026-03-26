from __future__ import annotations

from subprocess import run
import sys
import argparse
from pathlib import Path

PYTHON = sys.executable
ROOT = Path(__file__).resolve().parent


def build_commands(data_dir: str):
    return [
        ([PYTHON, "-m", "src.rkeg.run", "--data-dir", data_dir], ROOT),
        ([PYTHON, "-m", "src.leave_leakage.run", "--data-dir", data_dir], ROOT),
        ([PYTHON, "-m", "src.termination_exposure.run", "--data-dir", data_dir], ROOT),
        ([PYTHON, "-m", "src.lsl_exposure.run", "--data-dir", data_dir], ROOT),
        ([PYTHON, "-m", "src.cross_module_integrity.run", "--data-dir", data_dir], ROOT),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all CRC diagnostic modules")
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Path to processed input data directory",
    )
    args = parser.parse_args()

    commands = build_commands(args.data_dir)

    print(f"Using Python interpreter: {PYTHON}")
    print(f"Using data directory: {args.data_dir}")

    for cmd, cwd in commands:
        print(f"\n▶ Running: {' '.join(str(c) for c in cmd)}")
        print(f"  in cwd: {cwd}")

        result = run(cmd, cwd=str(cwd))
        if result.returncode != 0:
            print("❌ Command failed, stopping pipeline.")
            sys.exit(result.returncode)

    print("\n✅ All CRC diagnostic modules completed successfully.")


if __name__ == "__main__":
    main()