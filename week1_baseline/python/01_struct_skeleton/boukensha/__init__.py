"""Boukensha — a MUD-playing agent, built from scratch.

Top-level package. Mirrors the Ruby reference's lib/boukensha.rb, which
requires the config loader, the player task, and the tool/message/context
structs.
"""

from .config import Config
from . import tasks
from .tasks import Player
from .tool import Tool
from .message import Message
from .context import Context

__all__ = ["Config", "tasks", "Player", "Tool", "Message", "Context"]
