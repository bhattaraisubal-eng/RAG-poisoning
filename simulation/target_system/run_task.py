"""run_task.py — Wires up and runs the target system for a single task."""

from openai import OpenAI
from target_system.environment.rag_store import RAGStore
from target_system.environment.database import MockDatabase
from target_system.environment.email_outbox import EmailOutbox
from target_system.agents.worker import WorkerAgent
from target_system.agents.orchestrator import OrchestratorAgent
from target_system.scoring_judge import judge_round
from target_system.logger import logger as _global_logger


class TargetSystem:
    def __init__(self, client: OpenAI, logger=None, model=None):
        self.client = client
        self.logger = logger or _global_logger
        self.rag_store = RAGStore()
        self.database = MockDatabase()
        self.email_outbox = EmailOutbox()
        self.worker = WorkerAgent(
            client, self.database, self.email_outbox,
            logger=self.logger, model=model,
        )
        self.orchestrator = OrchestratorAgent(
            client, self.rag_store, self.worker,
            logger=self.logger, model=model,
        )

    def run_task(self, user_request: str, round_number: int = 1) -> dict:
        """Run a single task through the target system.

        Returns dict with:
          - response: str (orchestrator's final answer)
          - judge: dict (scoring judge results, without payload context)
          - logs: dict (all tool calls and agent messages)
        """
        self.logger.start_round(round_number)
        self.email_outbox.reset()

        response = self.orchestrator.handle_task(user_request)
        judge_result = judge_round(self.email_outbox)
        logs = self.logger.end_round()

        return {
            "response": response,
            "judge": judge_result,
            "logs": logs,
        }
