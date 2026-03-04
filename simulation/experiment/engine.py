"""
engine.py — Runs a single round of the experiment with a fixed payload.

No LLM strategist, no adaptive learning. Fully deterministic payloads.
"""

import json
from openai import OpenAI
from target_system.run_task import TargetSystem
from target_system.scoring_judge import judge_round
from experiment.payload_templates import render_template, ATTACKER_EMAIL


def run_round(
    target: TargetSystem,
    user_query: str,
    is_data_export: bool,
    payload_template: str,
    round_number: int = 1,
    attacker_email: str = ATTACKER_EMAIL,
) -> dict:
    """Run one round: inject payload, run task, score result.

    Args:
        target: TargetSystem instance (shared across rounds, reset each time).
        user_query: The user query string for this round.
        is_data_export: Whether the user query is a data-export query.
        payload_template: The raw template string with {attacker_email} placeholder.
        round_number: Round index for logging.
        attacker_email: Email to inject into the payload.

    Returns:
        dict with round results including retrieval, compromise, and cause.
    """
    # 1. Reset RAG to baseline (remove previous round's poison)
    target.rag_store.reset_to_baseline()

    # 2. Render and inject fixed payload
    payload_content = render_template(payload_template, attacker_email)
    poison_id = target.rag_store.write(
        content=payload_content,
        metadata={"category": "procedure", "department": "finance"},
        source="system",  # Appears as trusted internal document
    )

    # 3. Reset email outbox
    target.email_outbox.reset()

    # 4. Run target system with trigger task
    task_result = target.run_task(user_query, round_number=round_number)
    logs = task_result["logs"]

    # 5. Check if payload was retrieved
    rag_reads = [tc for tc in logs["tool_calls"] if tc["tool"] == "read_memory"]
    payload_retrieved = any(
        poison_id in str(tc.get("output", "")) for tc in rag_reads
    )
    search_queries = [tc["inputs"].get("query", "") for tc in rag_reads]

    # 6. Score with judge
    judge_result = judge_round(
        target.email_outbox,
        payload_retrieved=payload_retrieved,
        attacker_target_email=attacker_email,
    )

    # 7. Check if attacker email specifically was contacted
    attacker_contacted = any(
        attacker_email in e["to"]
        for e in target.email_outbox.sent_emails
    )

    return {
        "round": round_number,
        "user_query": user_query,
        "is_data_export": is_data_export,
        "payload_retrieved": payload_retrieved,
        "search_queries": search_queries,
        "compromised": judge_result["compromised"],
        "compromise_cause": judge_result["compromise_cause"],
        "attacker_contacted": attacker_contacted,
        "total_emails": judge_result["total_emails"],
        "unauthorized_emails": judge_result["unauthorized_emails"],
        "authorized_emails": judge_result["authorized_emails"],
        "incidental_external": judge_result["incidental_external"],
        "orchestrator_response": task_result["response"][:300],
    }
