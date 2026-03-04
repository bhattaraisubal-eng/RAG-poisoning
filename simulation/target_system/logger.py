"""logger.py — records all target system activity per round."""

from datetime import datetime, timezone
from typing import Any, Optional


class SystemLogger:
    def __init__(self):
        self.round_number: Optional[int] = None
        self.tool_calls:    list[dict]   = []
        self.agent_messages: list[dict]  = []

    def start_round(self, round_number: int):
        self.round_number    = round_number
        self.tool_calls      = []
        self.agent_messages  = []

    def end_round(self) -> dict:
        return {
            "round_number":   self.round_number,
            "tool_calls":     self.tool_calls,
            "agent_messages": self.agent_messages,
        }

    def log_tool_call(self, agent: str, tool_name: str,
                      inputs: dict, output: Any):
        self.tool_calls.append({
            "agent":     agent,
            "tool":      tool_name,
            "inputs":    inputs,
            "output":    str(output)[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def log_agent_message(self, from_agent: str, to_agent: str,
                          message: str, message_type: str = "message"):
        self.agent_messages.append({
            "from":         from_agent,
            "to":           to_agent,
            "message":      message,
            "message_type": message_type,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        })


# Global instance shared across all components
logger = SystemLogger()
