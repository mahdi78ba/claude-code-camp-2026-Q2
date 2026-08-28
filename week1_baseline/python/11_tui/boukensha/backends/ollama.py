"""Serializes a Context into the local Ollama /api/chat format.

Python port of Boukensha::Backends::Ollama.
"""

from __future__ import annotations

from .base import Base


class Ollama(Base):
    MODELS = {
        "gemma4": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:e2b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:e4b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:12b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:26b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:31b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3:30b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3:8b": {
            "context_window": 40_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "deepseek-r1:8b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
    }

    def __init__(self, *, model, host="http://localhost:11434") -> None:
        self.host = host
        self._configure_model(model)

    def to_messages(self, system, messages):
        system_message = [{"role": "system", "content": system}]
        conversation = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append({
                    "role": "tool",
                    "tool_name": msg.tool_use_id,
                    "content": msg.content,
                })
            elif msg.role == "assistant":
                conversation.append(self._assistant_message(msg.content))
            else:
                conversation.append({"role": str(msg.role), "content": msg.content})
        return system_message + conversation

    def to_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, *, max_output_tokens=1024, tools=None):
        return {
            "model": self.model,
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
        }

    @property
    def headers(self):
        return {"Content-Type": "application/json"}

    @property
    def url(self):
        return f"{self.host}/api/chat"

    def parse_response(self, response):
        """Normalizes an Ollama /api/chat response into the common shape:
        {stop_reason: "tool_use" | "end_turn",
         content: [{"type": "text", "text": ...} |
                   {"type": "tool_use", "id": ..., "name": ..., "input": ...}]}

        Ollama doesn't assign call ids, so the function name is reused as
        the id (Ollama also matches tool results back to a call by name).
        """
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        content = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            fn = tc.get("function") or {}
            content.append({
                "type": "tool_use",
                "id": fn.get("name"),
                "name": fn.get("name"),
                "input": fn.get("arguments") or {},
            })

        return {
            "stop_reason": "tool_use" if tool_calls else "end_turn",
            "content": content,
        }

    def _assistant_message(self, content):
        """Rebuilds an Ollama assistant message from normalized content
        blocks (the inverse of parse_response)."""
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        text = "".join(b["text"] for b in blocks if b["type"] == "text")
        tool_blocks = [b for b in blocks if b["type"] == "tool_use"]

        message = {"role": "assistant", "content": text}
        if tool_blocks:
            message["tool_calls"] = [
                {"function": {"name": b["name"], "arguments": b["input"]}}
                for b in tool_blocks
            ]
        return message
