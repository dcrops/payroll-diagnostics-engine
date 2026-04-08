from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.lsl_exposure.run import main as run_lsl


def parse_args():
    parser = argparse.ArgumentParser(description="Run LSL module")
    parser.add_argument("--client", required=True)
    parser.add_argument("--pilot", required=True)
    parser.add_argument(
        "--mode",
        choices=["full", "payroll_only"],
        default="full",
    )
    parser.add_argument(
        "--include-supporting",
        action="store_true",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("Running LSL module for:")
    print(f"Client: {args.client}")
    print(f"Pilot: {args.pilot}")
    print(f"Mode: {args.mode}")
    print(f"Include supporting: {args.include_supporting}")

    return run_lsl(
        client=args.client,
        pilot=args.pilot,
        mode=args.mode,
        include_supporting=args.include_supporting,
    )


if __name__ == "__main__":
    raise SystemExit(main())