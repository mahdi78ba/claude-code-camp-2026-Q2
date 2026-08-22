"""Everything needed to make one agent API call.

Python port of Boukensha::Context.
"""

from __future__ import annotations

from .message import Message
from .tool import Tool


class Context:
    def __init__(self, *, task, system=None) -> None:
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role, content, *, tool_use_id=None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        task_name = None if self.task is None else self.task.task_name()
        return f"#<Context task={task_name} turns={self.turn_count} tools={self.tool_count}>"

    __repr__ = __str__
