"""Everything needed to make one agent API call.

Python port of Boukensha::Context.
"""

from __future__ import annotations

import math
from pathlib import Path

from .message import Message
from .tool import Tool


class Context:
    def __init__(self, *, task, system=None, working_dir=None,
                 context_window=200_000, compaction_threshold=0.85) -> None:
        self.task = task
        self.system = system
        self.working_dir = str(Path(working_dir).resolve()) if working_dir else None
        self.context_window = context_window
        self.compaction_threshold = compaction_threshold
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.current_tokens = 0
        self.turn_tokens = 0

    def register_tool(self, tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role, content, *, tool_use_id=None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    def update_tokens(self, n) -> None:
        """Update the known context size from the last API response's input_tokens."""
        self.current_tokens = int(n or 0)

    def reset_turn_tokens(self) -> None:
        """Reset the cumulative per-turn spend counter. Called at the top of a turn."""
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens, output_tokens) -> None:
        """Add one API call's input+output tokens to the cumulative per-turn
        total. This is the spend budget -- distinct from current_tokens
        (window pressure)."""
        self.turn_tokens += int(input_tokens or 0) + int(output_tokens or 0)

    @property
    def usage_fraction(self) -> float:
        """Fraction of the context window currently in use (0.0-1.0)."""
        if self.context_window <= 0:
            return 0.0
        return self.current_tokens / self.context_window

    @property
    def usage_pct(self) -> int:
        """Integer percentage (0-100)."""
        return round(self.usage_fraction * 100)

    def needs_compaction(self, *, threshold=None) -> bool:
        """True when we should compact before the next API call. Defaults
        to the configured compaction_threshold (a fraction of
        context_window)."""
        threshold = self.compaction_threshold if threshold is None else threshold
        return self.usage_fraction >= threshold

    def compact_messages(self, *, target_fraction=0.60) -> int:
        """Drop the oldest 40% of messages, keeping at least 2. Resets
        current_tokens to 0 (will be updated by the next API response).
        Returns the number of messages dropped."""
        drop_count = min(math.ceil(len(self.messages) * 0.40), len(self.messages) - 2)
        drop_count = max(drop_count, 0)
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    def clear_messages(self) -> None:
        """Drop all conversation history, keeping tools and system prompt intact.

        Used by the REPL's `/clear` command.
        """
        self.messages = []
        self.current_tokens = 0

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        task_name = None if self.task is None else self.task.task_name()
        return (
            f"#<Context task={task_name} turns={self.turn_count} tools={self.tool_count} "
            f"window={self.context_window} current={self.current_tokens}>"
        )

    __repr__ = __str__
