"""Serializes a Context into the Gemini generateContent API format.

Python port of Boukensha::Backends::Gemini.
"""

from __future__ import annotations

from .base import Base


class Gemini(Base):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS = {
        "gemini-3.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.5, "output": 9.0},
            "usage_unit": "tokens",
        },
        "gemini-3.1-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.25, "output": 1.5},
            "usage_unit": "tokens",
        },
        "gemini-2.5-pro": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.25, "output": 10.0},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.30, "output": 2.50},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.10, "output": 0.40},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key, model) -> None:
        self.api_key = api_key
        self._configure_model(model)

    def to_messages(self, messages):
        result = []
        for msg in messages:
            if msg.role == "assistant":
                result.append({"role": "model", "parts": self._assistant_parts(msg.content)})
            elif msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.tool_use_id,
                            "response": {"content": msg.content},
                        }
                    }],
                })
            else:
                result.append({"role": str(msg.role), "parts": [{"text": msg.content}]})
        return result

    def to_tools(self, tools):
        if not tools:
            return []
        return [{
            "functionDeclarations": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                }
                for tool in tools.values()
            ]
        }]

    def to_payload(self, context, *, max_output_tokens=1024, tools=None):
        return {
            "systemInstruction": {"parts": [{"text": context.system}]},
            "contents": self.to_messages(context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    @property
    def url(self):
        return f"{self.BASE_URL}/{self.model}:generateContent"

    def parse_response(self, response):
        """Normalizes a Gemini generateContent response into the common
        shape: {stop_reason: "tool_use" | "end_turn",
                content: [{"type": "text", "text": ...} |
                          {"type": "tool_use", "id": ..., "name": ..., "input": ...}]}

        Gemini doesn't assign call ids, so the function name is reused as
        the id (Gemini also matches functionResponse back to a call by name).
        """
        candidates = response.get("candidates") or [{}]
        parts = (candidates[0].get("content") or {}).get("parts") or []

        content = []
        tool_used = False

        for part in parts:
            if part.get("functionCall") is not None:
                fc = part["functionCall"]
                content.append({
                    "type": "tool_use",
                    "id": fc.get("name"),
                    "name": fc.get("name"),
                    "input": fc.get("args") or {},
                })
                tool_used = True
            elif part.get("text") is not None:
                content.append({"type": "text", "text": part["text"]})

        return {"stop_reason": "tool_use" if tool_used else "end_turn", "content": content}

    def _assistant_parts(self, content):
        """Rebuilds Gemini "model" parts from normalized content blocks
        (the inverse of parse_response)."""
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        parts = []
        for b in blocks:
            if b["type"] == "tool_use":
                parts.append({"functionCall": {"name": b["name"], "args": b["input"]}})
            else:
                parts.append({"text": b["text"]})
        return parts
