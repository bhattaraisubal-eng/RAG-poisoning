"""
run_all_studies.py — Run both studies sequentially.

Usage:
    python run_all_studies.py             # Full run (~1440 rounds)
    python run_all_studies.py --dry-run   # Smoke test both studies
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv


def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    dry_run = "--dry-run" in sys.argv
    mode = "DRY RUN" if dry_run else "FULL"

    print(f"\n{'#'*70}")
    print(f"  RUNNING ALL STUDIES ({mode})")
    print(f"{'#'*70}\n")

    start = time.time()

    # Study 1: Framing Strategy (across all models)
    print("\n>>> STUDY 1: Framing Strategy (all models) <<<")
    from run_study1 import main as study1_main
    study1_main()

    # Study 2: Format Comparison (across all models)
    print("\n>>> STUDY 2: Format Comparison (all models) <<<")
    from run_study2 import main as study2_main
    study2_main()

    elapsed = time.time() - start
    print(f"\n{'#'*70}")
    print(f"  ALL STUDIES COMPLETE — {elapsed:.0f}s total")
    print(f"{'#'*70}\n")


if __name__ == "__main__":
    main()
