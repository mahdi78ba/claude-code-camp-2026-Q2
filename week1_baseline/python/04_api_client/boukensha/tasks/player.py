"""The player task — the main agentic loop.

Python port of Boukensha::Tasks::Player.
"""

from __future__ import annotations

from .base import Base


class Player(Base):
    @classmethod
    def task_name(cls) -> str:
        return "player"
