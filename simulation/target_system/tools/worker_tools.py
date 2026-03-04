"""tools/worker_tools.py — OpenAI function definitions for the Worker."""

WORKER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"}
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_result",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {"type": "string"}
                },
                "required": ["result"],
            },
        },
    },
]
