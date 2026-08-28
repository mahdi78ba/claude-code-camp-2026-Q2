"""Tasks — each a role in the agentic loop bound to its own LLM.

week1_baseline only drives a single `player` task (the main loop); later
steps assign different LLMs to different tasks.
"""

from .base import Base
from .player import Player

__all__ = ["Base", "Player"]
