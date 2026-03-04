"""agents/orchestrator.py — Orchestrator Agent with OpenAI tool-calling loop."""

import json
import time
from openai import OpenAI, RateLimitError
from target_system.config import (
    TARGET_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
    ORCHESTRATOR_BASE_PROMPT, ORCHESTRATOR_SECURITY_PATCHES,
)
from target_system.tools.orchestrator_tools import ORCHESTRATOR_TOOLS
from target_system.logger import logger as _global_logger

_MAX_RETRIES = 5


class OrchestratorAgent:
    def __init__(self, client: OpenAI, rag_store, worker_agent,
                 logger=None, model=None):
        self.client = client
        self.rag_store = rag_store
        self.worker = worker_agent
        self.logger = logger or _global_logger
        self.model = model or TARGET_MODEL
        self.max_iterations = 10

    def handle_task(self, user_request: str) -> str:
        """Process a user request. Returns the final response string."""
        system_prompt = ORCHESTRATOR_BASE_PROMPT
        for patch in ORCHESTRATOR_SECURITY_PATCHES:
            system_prompt += f"\n\n{patch}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request},
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

        return "(orchestrator reached max iterations)"

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
                    tools=ORCHESTRATOR_TOOLS,
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
            tools=ORCHESTRATOR_TOOLS,
        )

    def _dispatch(self, name: str, args: dict) -> str:
        if name == "read_memory":
            results = self.rag_store.read(args["query"])
            entry_ids = [r["id"] for r in results]
            # Log with entry IDs so engine can detect payload retrieval
            self.logger.log_tool_call(
                agent="orchestrator",
                tool_name="read_memory",
                inputs=args,
                output=f"{len(results)} entries returned (ids: {entry_ids})",
            )
            # Strip IDs before sending to LLM (it only needs content + source)
            llm_results = [{"content": r["content"], "source": r["source"]}
                           for r in results]
            return json.dumps(llm_results, default=str)

        if name == "delegate_task":
            instruction = args["instruction"]
            self.logger.log_agent_message(
                from_agent="orchestrator",
                to_agent="worker",
                message=instruction,
                message_type="delegation",
            )
            worker_result = self.worker.execute(instruction)
            self.logger.log_agent_message(
                from_agent="worker",
                to_agent="orchestrator",
                message=worker_result[:500],
                message_type="result",
            )
            return worker_result

        if name == "write_memory":
            entry_id = self.rag_store.write(
                content=f"{args['key']}: {args['value']}",
                metadata={"category": "agent_written"},
                source="agent",
            )
            self.logger.log_tool_call(
                agent="orchestrator",
                tool_name="write_memory",
                inputs=args,
                output=f"entry_id={entry_id}",
            )
            return f"Saved (id={entry_id})"

        return f"unknown tool: {name}"
