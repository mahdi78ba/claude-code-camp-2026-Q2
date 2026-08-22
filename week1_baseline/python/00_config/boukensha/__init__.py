"""Boukensha — a MUD-playing agent, built from scratch.

Top-level package. Mirrors the Ruby reference's lib/boukensha.rb, which
requires the config loader and the player task.
"""

from .config import Config
from . import tasks
from .tasks import Player

__all__ = ["Config", "tasks", "Player"]
