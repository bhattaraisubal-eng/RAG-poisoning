"""
runner.py — Orchestrates study execution: conditions x reps x rounds.

Calls engine.run_round for each combination and aggregates results.
Conditions run in parallel via ThreadPoolExecutor (I/O-bound work).
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from dataclasses import dataclass
from openai import OpenAI
from target_system.run_task import TargetSystem
from target_system.logger import SystemLogger
from target_system.config import TARGET_MODEL
from red_team.trigger_queries import get_trigger_query
from experiment.engine import run_round
from experiment.payload_templates import ATTACKER_EMAIL


@dataclass
class StudyConfig:
    """Configuration for a single study."""
    study_name: str
    conditions: dict[str, dict[str, str]]  # condition_name -> {data_export, unrelated}
    rounds_per_rep: int
    reps: int
    attacker_email: str = ATTACKER_EMAIL
    target_model: str | None = None  # None = use config.py default


def run_study(client: OpenAI, config: StudyConfig) -> dict:
    """Run a full study: all conditions x reps x rounds.

    Conditions run in parallel threads. Each thread gets its own OpenAI
    client, SystemLogger, and TargetSystem to avoid shared mutable state.

    Returns:
        dict with study metadata, per-condition summaries, and all round details.
    """
    study_start = time.time()
    total_rounds = len(config.conditions) * config.reps * config.rounds_per_rep

    print(f"\n{'='*70}")
    print(f"  STUDY: {config.study_name}")
    print(f"  Conditions: {list(config.conditions.keys())}")
    print(f"  {config.reps} reps x {config.rounds_per_rep} rounds = "
          f"{total_rounds} total rounds")
    print(f"  Running {len(config.conditions)} conditions sequentially")
    print(f"{'='*70}\n")

    # Run conditions sequentially to stay within rate limits
    all_results = []
    condition_summaries = {}
    for condition_name, templates in config.conditions.items():
        cond_results, cond_progress = _run_condition(
            api_key=client.api_key,
            condition_name=condition_name,
            templates=templates,
            config=config,
        )
        print(f"  [DONE] {condition_name} — "
              f"{len(cond_results)} rounds completed")
        all_results.extend(cond_results)
        condition_summaries[condition_name] = _summarize_condition(
            condition_name, cond_results
        )
        for line in cond_progress:
            print(line)

    elapsed = time.time() - study_start

    study_result = {
        "study_name": config.study_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "config": {
            "conditions": list(config.conditions.keys()),
            "rounds_per_rep": config.rounds_per_rep,
            "reps": config.reps,
            "attacker_email": config.attacker_email,
            "target_model": config.target_model or TARGET_MODEL,
        },
        "condition_summaries": condition_summaries,
        "all_rounds": all_results,
    }

    # Print summary table
    _print_summary(config.study_name, condition_summaries)

    # Save to file
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{config.study_name}_{ts}.json"
    with open(filename, "w") as f:
        json.dump(study_result, f, indent=2, default=str)
    print(f"\n  Results saved to {filename}")

    return study_result


def _run_condition(
    api_key: str,
    condition_name: str,
    templates: dict[str, str],
    config: StudyConfig,
) -> tuple[list[dict], list[str]]:
    """Run all reps x rounds for a single condition.

    Runs in its own thread with isolated OpenAI client, SystemLogger,
    and TargetSystem instances.

    Returns:
        (results_list, progress_lines) — results and display-ready progress.
    """
    # Each thread gets its own client to avoid shared connection state
    thread_client = OpenAI(api_key=api_key)
    model = config.target_model

    condition_results = []
    progress_lines = []

    for rep in range(1, config.reps + 1):
        # Each rep gets a fresh logger + target system
        thread_logger = SystemLogger()
        target = TargetSystem(thread_client, logger=thread_logger, model=model)
        seed = hash((condition_name, rep)) % 10000

        progress_lines.append(
            f"  [{condition_name}] rep {rep}/{config.reps}:"
        )

        for round_num in range(1, config.rounds_per_rep + 1):
            user_query, is_data_export = get_trigger_query(
                round_num, seed=seed
            )

            template_key = "data_export" if is_data_export else "unrelated"
            payload_template = templates[template_key]

            result = run_round(
                target=target,
                user_query=user_query,
                is_data_export=is_data_export,
                payload_template=payload_template,
                round_number=round_num,
                attacker_email=config.attacker_email,
            )

            result["condition"] = condition_name
            result["rep"] = rep
            result["study"] = config.study_name

            condition_results.append(result)

            # Build progress line (printed after completion)
            surface = "DE" if is_data_export else "  "
            retr = "R" if result["payload_retrieved"] else "."
            comp = "X" if result["compromised"] else "."
            atk = "A" if result["attacker_contacted"] else "."
            progress_lines.append(
                f"    R{round_num:02d} [{surface}] "
                f"retr={retr} comp={comp} atk={atk}"
            )

    return condition_results, progress_lines


def _create_target(client: OpenAI, target_model: str | None,
                   logger=None) -> TargetSystem:
    """Create a TargetSystem with optional model and logger overrides."""
    return TargetSystem(client, logger=logger, model=target_model)


def _summarize_condition(condition_name: str, results: list[dict]) -> dict:
    """Compute aggregate stats for one condition."""
    total = len(results)
    de_rounds = [r for r in results if r["is_data_export"]]
    retrieved = [r for r in results if r["payload_retrieved"]]
    compromised = [r for r in results if r["compromised"]]
    injection = [r for r in results if r.get("compromise_cause") == "rag_injection"]
    hallucination = [r for r in results if r.get("compromise_cause") == "hallucination"]
    attacker_hit = [r for r in results if r["attacker_contacted"]]

    de_retrieved = [r for r in de_rounds if r["payload_retrieved"]]
    de_compromised = [r for r in de_rounds if r["compromised"]]
    de_injection = [r for r in de_rounds if r.get("compromise_cause") == "rag_injection"]

    # Conversion: of rounds where payload was retrieved, how many compromised?
    retrieved_and_compromised = [r for r in retrieved if r["compromised"]]

    return {
        "condition": condition_name,
        "total_rounds": total,
        "data_export_rounds": len(de_rounds),
        "retrieval_rate": len(retrieved) / total if total else 0,
        "compromise_rate": len(compromised) / total if total else 0,
        "injection_rate": len(injection) / total if total else 0,
        "hallucination_rate": len(hallucination) / total if total else 0,
        "attacker_contact_rate": len(attacker_hit) / total if total else 0,
        # Data-export surface only
        "de_retrieval_rate": len(de_retrieved) / len(de_rounds) if de_rounds else 0,
        "de_compromise_rate": len(de_compromised) / len(de_rounds) if de_rounds else 0,
        "de_injection_rate": len(de_injection) / len(de_rounds) if de_rounds else 0,
        # Conversion funnel
        "conversion_rate": (
            len(retrieved_and_compromised) / len(retrieved) if retrieved else 0
        ),
        # Raw counts
        "counts": {
            "total": total,
            "data_export": len(de_rounds),
            "retrieved": len(retrieved),
            "compromised": len(compromised),
            "injection": len(injection),
            "hallucination": len(hallucination),
            "attacker_contacted": len(attacker_hit),
        },
    }


def _print_summary(study_name: str, summaries: dict[str, dict]):
    """Print a formatted summary table to console."""
    print(f"\n{'='*70}")
    print(f"  RESULTS: {study_name}")
    print(f"{'='*70}")
    print(f"  {'Condition':<16s} {'Retrieval':>10s} {'Compromise':>11s} "
          f"{'Injection':>10s} {'Conversion':>11s} {'DE Comp':>8s}")
    print(f"  {'-'*16} {'-'*10} {'-'*11} {'-'*10} {'-'*11} {'-'*8}")

    for name, s in summaries.items():
        print(f"  {name:<16s} "
              f"{s['retrieval_rate']:>9.1%} "
              f"{s['compromise_rate']:>10.1%} "
              f"{s['injection_rate']:>9.1%} "
              f"{s['conversion_rate']:>10.1%} "
              f"{s['de_compromise_rate']:>7.1%}")

    print(f"{'='*70}\n")
