"""agents/worker.py — Worker Agent with OpenAI tool-calling loop."""

import json
import time
from openai import OpenAI, RateLimitError
from target_system.config import (
    TARGET_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
    WORKER_BASE_PROMPT, WORKER_SECURITY_PATCHES,
)
from target_system.tools.worker_tools import WORKER_TOOLS
from target_system.logger import logger as _global_logger

_MAX_RETRIES = 5


class WorkerAgent:
    def __init__(self, client: OpenAI, database, email_outbox,
                 logger=None, model=None):
        self.client = client
        self.database = database
        self.email_outbox = email_outbox
        self.logger = logger or _global_logger
        self.model = model or TARGET_MODEL
        self.max_iterations = 10

    def execute(self, instruction: str) -> str:
        """Execute a delegated task. Returns the result string."""
        system_prompt = WORKER_BASE_PROMPT
        for patch in WORKER_SECURITY_PATCHES:
            system_prompt += f"\n\n{patch}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": instruction},
        ]

        for _ in range(self.max_iterations):
            response = self._call_with_retry(self._trimmed(messages))
            choice = response.choices[0]

            # No tool calls — agent is done
            if choice.finish_reason == "stop":
                return choice.message.content or "(no response)"

            # Process tool calls
            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": "error: malformed arguments",
                    })
                    continue
                result = self._dispatch(name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)[:1000],
                })

        return "(worker reached max iterations)"

    @staticmethod
    def _trimmed(messages, keep_pairs=2):
        """Keep system + user + last N assistant/tool pairs to limit context.

        Groups messages into pairs: each assistant message with tool_calls
        is grouped with its subsequent tool response messages. We keep only
        the last `keep_pairs` groups to avoid breaking the tool call chain.
        """
        fixed = []
        groups = []
        current_group = []

        for m in messages:
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
            if role in ("system", "user"):
                fixed.append(m)
            elif role == "assistant":
                if current_group:
                    groups.append(current_group)
                current_group = [m]
            elif role == "tool":
                current_group.append(m)

        if current_group:
            groups.append(current_group)

        kept = []
        for group in groups[-keep_pairs:]:
            kept.extend(group)

        return fixed + kept

    def _call_with_retry(self, messages):
        for attempt in range(_MAX_RETRIES):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                    messages=messages,
                    tools=WORKER_TOOLS,
                )
            except RateLimitError:
                wait = 2 ** attempt
                time.sleep(wait)
        # Final attempt — let it raise
        return self.client.chat.completions.create(
            model=self.model,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            messages=messages,
            tools=WORKER_TOOLS,
        )

    def _dispatch(self, name: str, args: dict) -> str:
        if name == "query_database":
            rows = self.database.query(args["sql"])
            return json.dumps(rows, default=str)

        if name == "send_email":
            return self.email_outbox.send(
                to=args["to"],
                subject=args["subject"],
                body=args["body"],
            )

        if name == "report_result":
            self.logger.log_tool_call(
                agent="worker",
                tool_name="report_result",
                inputs={"result": args["result"][:200]},
                output="reported",
            )
            return args["result"]

        return f"unknown tool: {name}"
