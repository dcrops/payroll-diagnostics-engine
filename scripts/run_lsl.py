import argparse
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

# Import your LEAVE module
from src.lsl_exposure.run import main as run_lsl


def parse_args():
    parser = argparse.ArgumentParser(description="Run LSL module")
    parser.add_argument("--client", required=True)
    parser.add_argument("--pilot", required=True)
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"Running LSL module for:")
    print(f"Client: {args.client}")
    print(f"Pilot: {args.pilot}")

    run_lsl(client=args.client, pilot=args.pilot)


if __name__ == "__main__":
    main()