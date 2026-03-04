"""tools/orchestrator_tools.py — OpenAI function definitions for the Orchestrator."""

ORCHESTRATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {"type": "string"}
                },
                "required": ["instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
            },
        },
    },
]
