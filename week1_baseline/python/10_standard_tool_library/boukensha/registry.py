"""How Boukensha manages and dispatches tool calls.

Python port of Boukensha::Registry. Two jobs: storing tools (delegated to
the Context it wraps) and dispatching calls to them by name.
"""

from __future__ import annotations

from typing import Any, Callable

from .errors import UnknownToolError
from .tool import Tool


class Registry:
    def __init__(self, context) -> None:
        self.context = context

    def tool(self, name, *, description: str, parameters: dict | None = None,
             block: Callable[..., Any]) -> Tool:
        tool = Tool(str(name), description, parameters or {}, block)
        self.context.register_tool(tool)
        return tool

    def dispatch(self, name, args: dict | None = None) -> Any:
        tool = self.context.tools.get(str(name))
        if tool is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**(args or {}))

    def registered(self, name) -> bool:
        return str(name) in self.context.tools
