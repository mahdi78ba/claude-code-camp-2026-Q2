"""Boukensha — a MUD-playing agent, built from scratch.

Top-level package. Mirrors the Ruby reference's lib/boukensha.rb, which
requires the config loader, the player task, the tool/message/context
structs, the tool registry and its error class, and (as of this iteration)
the prompt builder and its provider backends.
"""

from .config import Config
from . import tasks
from .tasks import Player
from .tool import Tool
from .message import Message
from .context import Context
from .errors import UnknownToolError, UnsupportedModelError
from .registry import Registry
from .prompt_builder import PromptBuilder
from . import backends

__all__ = [
    "Config",
    "tasks",
    "Player",
    "Tool",
    "Message",
    "Context",
    "UnknownToolError",
    "UnsupportedModelError",
    "Registry",
    "PromptBuilder",
    "backends",
]
