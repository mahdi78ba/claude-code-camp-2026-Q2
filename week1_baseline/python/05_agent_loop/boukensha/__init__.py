"""Boukensha — a MUD-playing agent, built from scratch.

Top-level package. Mirrors the Ruby reference's lib/boukensha.rb, which
requires the config loader, the player task, the tool/message/context
structs, the tool registry and its error class, the prompt builder and its
provider backends, the HTTP client, and (as of this iteration) the agent
loop itself.
"""

from .config import Config
from . import tasks
from .tasks import Player
from .tool import Tool
from .message import Message
from .context import Context
from .errors import UnknownToolError, UnsupportedModelError, ApiError, LoopError
from .registry import Registry
from .prompt_builder import PromptBuilder
from . import backends
from .client import Client
from .agent import Agent

__all__ = [
    "Config",
    "tasks",
    "Player",
    "Tool",
    "Message",
    "Context",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "Registry",
    "PromptBuilder",
    "backends",
    "Client",
    "Agent",
]
