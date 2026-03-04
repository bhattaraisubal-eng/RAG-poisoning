"""
run_study2.py — Study 2: Format (Prose vs Structured)

IV: Payload format
  - prose: Natural paragraph
  - routing_table: Distribution list format
  - bullet_list: Bulleted list
  - json_like: JSON-like structure

Controls: Same authoritative framing, same email, same keywords
Design: 3 models x 4 conditions x 2 reps x 10 rounds = 240 rounds

Usage:
    python run_study2.py             # Full run
    python run_study2.py --dry-run   # Smoke test (2 rounds, 1 rep per model)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from openai import OpenAI
from experiment.payload_templates import STUDY2_TEMPLATES, TARGET_MODELS
from experiment.runner import StudyConfig, run_study
from experiment.analysis import analyze_study


def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    dry_run = "--dry-run" in sys.argv

    client = OpenAI()

    if dry_run:
        print("\n  *** DRY RUN MODE — 2 rounds, 1 rep per model ***\n")

    all_results = []

    for model in TARGET_MODELS:
        print(f"\n  === Model: {model} ===")

        model_tag = model.replace("-", "_")
        config = StudyConfig(
            study_name=f"study_2_format_{model_tag}",
            conditions=STUDY2_TEMPLATES,
            rounds_per_rep=2 if dry_run else 10,
            reps=1 if dry_run else 2,
            target_model=model,
        )

        result = run_study(client, config)
        analysis = analyze_study(
            result,
            output_prefix=f"study_2_format_{model_tag}" if not dry_run else None,
        )
        all_results.append({"model": model, "result": result, "analysis": analysis})

    # Cross-model comparison table
    _print_cross_model_table(all_results, list(STUDY2_TEMPLATES.keys()))

    if dry_run:
        print("\n  Dry run complete. Pipeline works.")


def _print_cross_model_table(all_results, conditions):
    """Print a cross-model comparison table showing compromise rates per condition."""
    print(f"\n{'='*70}")
    print(f"  CROSS-MODEL COMPARISON — Study 2: Format Comparison")
    print(f"{'='*70}")

    header = f"  {'Model':<18s}"
    for cond in conditions:
        header += f" {cond:>14s}"
    print(header)
    print(f"  {'-'*18}" + f" {'-'*14}" * len(conditions))

    for entry in all_results:
        model = entry["model"]
        summaries = entry["result"]["condition_summaries"]
        row = f"  {model:<18s}"
        for cond in conditions:
            rate = summaries.get(cond, {}).get("compromise_rate", 0)
            row += f" {rate:>13.1%}"
        print(row)

    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
