"""Boukensha — a MUD-playing agent, built from scratch.

Top-level package. Mirrors the Ruby reference's lib/boukensha.rb, which
requires the config loader, the player task, the tool/message/context
structs, the tool registry and its error class, the prompt builder and its
provider backends, the HTTP client, the agent loop, and (as of this
iteration) the session logger — plus the module-level config/debug
singleton the logger reads.
"""

from .config import Config
from . import tasks
from .tasks import Player
from .tool import Tool
from .message import Message
from .context import Context
from .errors import UnknownToolError, UnsupportedModelError, ApiError
from .registry import Registry
from .prompt_builder import PromptBuilder
from . import backends

# ---------- module-level config/debug singleton -----------------------
#
# Python equivalent of Ruby's `Boukensha` module gaining `config`, `debug!`/
# `debug?`, and `quiet!`/`loud!`/`quiet?` as module-level state. The
# accessor is named `get_config`, not `config`: defining a module-level
# function literally named `config` here would silently shadow the
# `boukensha.config` *submodule* (the file defining the `Config` class
# above), which Python's import system already exposes as an attribute of
# this package the moment it's imported — a collision Ruby doesn't have,
# since `Config` (the class) and `config` (the method) are distinct
# identifiers there. Only `get_config()` and `is_debug()` are actually
# consumed (by `Logger`); `enable_quiet`/`enable_loud`/`is_quiet` are
# unused in this iteration in either language, shipped for parity.

_quiet = False
_debug = False
_config = None


def get_config():
    global _config
    if _config is None:
        _config = Config()
    return _config


def enable_debug():
    global _debug
    _debug = True


def is_debug():
    return _debug


def enable_quiet():
    global _quiet
    _quiet = True


def enable_loud():
    global _quiet
    _quiet = False


def is_quiet():
    return _quiet


from .logger import Logger
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
    "Registry",
    "PromptBuilder",
    "backends",
    "get_config",
    "enable_debug",
    "is_debug",
    "enable_quiet",
    "enable_loud",
    "is_quiet",
    "Logger",
    "Client",
    "Agent",
]
