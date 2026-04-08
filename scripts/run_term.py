import argparse
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

# Import your TERM module
from src.termination_exposure.run import main as run_term


def parse_args():
    parser = argparse.ArgumentParser(description="Run TERM module")
    parser.add_argument("--client", required=True)
    parser.add_argument("--pilot", required=True)
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"Running TERM module for:")
    print(f"Client: {args.client}")
    print(f"Pilot: {args.pilot}")

    run_term(client=args.client, pilot=args.pilot)


if __name__ == "__main__":
    main()