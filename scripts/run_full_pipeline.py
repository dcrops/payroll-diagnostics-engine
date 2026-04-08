from __future__ import annotations

from subprocess import run
import sys
import argparse
from pathlib import Path

PYTHON = sys.executable
ROOT = Path(__file__).resolve().parent


def build_commands(
    client: str,
    pilot: str,
    mode: str,
    include_supporting: bool,
):
    extra_args = ["--mode", mode]
    if include_supporting:
        extra_args.append("--include-supporting")

    return [
        ([PYTHON, "run_ingestion.py", "--client", client, "--pilot", pilot], ROOT),
        ([PYTHON, "run_leave.py", "--client", client, "--pilot", pilot, *extra_args], ROOT),
        ([PYTHON, "run_lsl.py", "--client", client, "--pilot", pilot, *extra_args], ROOT),
        ([PYTHON, "run_term.py", "--client", client, "--pilot", pilot, *extra_args], ROOT),
        ([PYTHON, "run_rkeg.py", "--client", client, "--pilot", pilot, *extra_args], ROOT),
        ([PYTHON, "run_cross_module.py", "--client", client, "--pilot", pilot, *extra_args], ROOT),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full CRC pipeline")
    parser.add_argument("--client", required=True, help="Client name, e.g. CLT_KAGGLE_TEST")
    parser.add_argument("--pilot", required=True, help="Pilot name, e.g. PILOT_001_2026_03_26")
    parser.add_argument(
        "--mode",
        choices=["full", "payroll_only"],
        default="full",
        help="Rule execution mode.",
    )
    parser.add_argument(
        "--include-supporting",
        action="store_true",
        help="Include partially viable supporting rules in payroll_only mode.",
    )
    args = parser.parse_args()

    commands = build_commands(
        client=args.client,
        pilot=args.pilot,
        mode=args.mode,
        include_supporting=args.include_supporting,
    )

    print(f"Using Python interpreter: {PYTHON}")
    print(f"Using client: {args.client}")
    print(f"Using pilot: {args.pilot}")
    print(f"Using mode: {args.mode}")
    print(f"Include supporting: {args.include_supporting}")

    for cmd, cwd in commands:
        print(f"\n▶ Running: {' '.join(str(c) for c in cmd)}")
        print(f"  in cwd: {cwd}")

        result = run(cmd, cwd=str(cwd))
        if result.returncode != 0:
            print("❌ Command failed, stopping pipeline.")
            sys.exit(result.returncode)

    print("\n✅ Full CRC pipeline completed successfully.")


if __name__ == "__main__":
    main()