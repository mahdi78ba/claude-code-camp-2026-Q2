"""Boukensha — a MUD-playing agent, built from scratch.

Top-level package. Mirrors the Ruby reference's lib/boukensha.rb, which
requires the config loader, the player task, the tool/message/context
structs, the tool registry and its error class, the prompt builder and its
provider backends, the HTTP client, the agent loop, and (as of this
iteration) the session logger — plus the module-level config/debug
singleton the logger reads.
"""

import os
from pathlib import Path

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
from . import tools
from . import models

# ---------- module-level config/debug singleton -----------------------
#
# Python equivalent of Ruby's `Boukensha` module gaining `config` and
# `debug!`/`debug?` as module-level state. The accessor is named
# `get_config`, not `config`: defining a module-level function literally
# named `config` here would silently shadow the `boukensha.config`
# *submodule* (the file defining the `Config` class above), which
# Python's import system already exposes as an attribute of this package
# the moment it's imported — a collision Ruby doesn't have, since
# `Config` (the class) and `config` (the method) are distinct identifiers
# there.
#
# `quiet!`/`loud!`/`quiet?` (and this module's own former
# `enable_quiet`/`enable_loud`/`is_quiet`) are gone as of this iteration —
# removed in Ruby's own ruby/11_tui Repl refactor, since nothing ever read
# the quiet flag in either language even before that removal.

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


from .version import VERSION
from .logger import Logger
from .client import Client
from .agent import Agent
from .run_dsl import RunDSL
from .repl import Repl

# ---------- Boukensha.run() -------------------------------------------
#
# Python port of Boukensha.run. Every prior step required the caller to
# build and wire Context, Registry, a Backend, PromptBuilder, Client, and
# Logger by hand before constructing an Agent. This collapses all of that
# behind one call: describe *what* to do (a task, and the tools the agent
# may use), not *how* to plumb it.
#
# Ruby's version takes a block and `instance_eval`s it against a RunDSL
# instance, so a bare `tool` call inside the block resolves as
# `self.tool`. Python has no equivalent to `instance_eval` — there's no
# way to make a bare `tool(...)` call inside a function silently resolve
# against an arbitrary receiver. The Pythonic equivalent is an explicit
# `configure` callable, invoked as `configure(dsl)`, where the caller
# writes `dsl.tool(...)` instead of a bare `tool`. This preserves the
# actual design intent — a single, narrow method surface for registering
# tools, no access to internals — only the syntax for reaching that
# surface changes.


def run(*, task, system=None, model=None, backend=None, api_key=None,
        ollama_host="http://localhost:11434", log=None,
        context_window=None, max_output_tokens=None, working_dir=None,
        allowed_commands=None, shell_timeout=30, mcp=None, configure=None):
    """One-shot run: send a single task, get a response, return.

    working_dir:      roots all tool calls to this directory (default:
                       Path.cwd()). Registers boukensha.tools.file_system
                       (pwd, list_directory, read_file, write_file,
                       delete_file, search_files) and boukensha.tools.shell
                       (run_command) automatically. Pass working_dir=False
                       to opt out entirely.

    allowed_commands:  list of shell-executable names the agent is allowed
                        to run via run_command (e.g. ["python", "git"]).
                        None (default) permits everything — useful for demos.
                        Pass an empty list [] to disable run_command entirely.

    shell_timeout:     seconds before a run_command is killed (default 30).

    mcp:                list of MCP server configs ({name, command, env}) —
                        registers every tool each configured server exposes,
                        keeping one client (and one subprocess) alive per
                        server across every tool call. When None (default),
                        config.mcp_servers() (settings.yaml's mcp_servers:
                        list) is used. Pass mcp=False to disable entirely,
                        or mcp=[] for the same effect.
    """
    cfg = get_config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())

    if system is None:
        system = task_class.system_prompt(
            task_settings, user_prompts_dir=cfg.user_prompts_dir,
            default_prompts_dir=Config.PROMPTS_DIR,
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)
    if api_key is None:
        api_key = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY"),
            "gemini": os.environ.get("GEMINI_API_KEY"),
            "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
        }.get(backend)

    if working_dir is None:
        working_dir = Path.cwd()

    if context_window is None:
        context_window = models.context_window(model)

    ctx = Context(task=task_class, system=system, working_dir=working_dir,
                  context_window=context_window,
                  compaction_threshold=cfg.agent_compaction_threshold())
    registry = Registry(ctx)

    if working_dir:
        tools.file_system.register(registry, working_dir=working_dir)
        tools.shell.register(registry, working_dir=working_dir,
                              timeout=shell_timeout, allowed_commands=allowed_commands)

    resolved_mcp = [] if mcp is False else (mcp or cfg.mcp_servers())
    if resolved_mcp:
        tools.mcp.register(registry, servers=resolved_mcp)

    if configure is not None:
        configure(RunDSL(registry))

    if backend == "anthropic":
        be = backends.Anthropic(api_key=api_key, model=model)
    elif backend == "openai":
        be = backends.OpenAI(api_key=api_key, model=model)
    elif backend == "gemini":
        be = backends.Gemini(api_key=api_key, model=model)
    elif backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=model)
    elif backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=api_key, model=model)
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. Use 'anthropic', 'openai', "
            f"'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = (
        task_class.max_output_tokens(task_settings)
        if max_output_tokens is None else max_output_tokens
    )
    logger = Logger(log=log, snapshot={
        "task": task_class.task_name(),
        "max_iterations": effective_max_iterations,
        "max_turn_tokens": cfg.agent_max_turn_tokens(),
        "max_output_tokens": effective_max_output_tokens,
        "context_window": context_window,
        "model": model,
        "provider": backend,
    })
    agent = Agent(
        context=ctx, registry=registry, builder=builder, client=client,
        logger=logger, task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_turn_tokens=cfg.agent_max_turn_tokens(),
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()


# ---------- Boukensha.repl() ------------------------------------------
#
# Interactive REPL: register tools once, then loop — reading tasks from
# stdin, running the agent, and printing replies — until the user types
# /exit or sends EOF. Conversation history accumulates across every turn
# so the agent always sees the full transcript.
#
# Same setup as run() (config, system/model/backend/api_key resolution,
# Context/Registry/RunDSL, backend/builder/client/logger construction),
# minus the `task` parameter — the user supplies tasks interactively —
# and it hands off to a Repl object instead of building and running one
# Agent immediately.


def repl(*, system=None, model=None, backend=None, api_key=None,
          ollama_host="http://localhost:11434", log=None,
          context_window=None, max_output_tokens=None, working_dir=None,
          allowed_commands=None, shell_timeout=30, mcp=None, configure=None,
          tui=True):
    """Interactive REPL — see boukensha.run() for full option documentation.

    tui: True (default) wraps the REPL in a Textual TUI (boukensha.tui.Tui).
    Pass tui=False to fall back to the plain print()/input() REPL instead.
    """
    cfg = get_config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())

    if system is None:
        system = task_class.system_prompt(
            task_settings, user_prompts_dir=cfg.user_prompts_dir,
            default_prompts_dir=Config.PROMPTS_DIR,
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)
    if api_key is None:
        api_key = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY"),
            "gemini": os.environ.get("GEMINI_API_KEY"),
            "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
        }.get(backend)

    if working_dir is None:
        working_dir = Path.cwd()

    if context_window is None:
        context_window = models.context_window(model)

    ctx = Context(task=task_class, system=system, working_dir=working_dir,
                  context_window=context_window,
                  compaction_threshold=cfg.agent_compaction_threshold())
    registry = Registry(ctx)

    if working_dir:
        tools.file_system.register(registry, working_dir=working_dir)
        tools.shell.register(registry, working_dir=working_dir,
                              timeout=shell_timeout, allowed_commands=allowed_commands)

    resolved_mcp = [] if mcp is False else (mcp or cfg.mcp_servers())
    mcp_clients = tools.mcp.register(registry, servers=resolved_mcp) if resolved_mcp else []

    if configure is not None:
        configure(RunDSL(registry))

    if backend == "anthropic":
        be = backends.Anthropic(api_key=api_key, model=model)
    elif backend == "openai":
        be = backends.OpenAI(api_key=api_key, model=model)
    elif backend == "gemini":
        be = backends.Gemini(api_key=api_key, model=model)
    elif backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=model)
    elif backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=api_key, model=model)
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. Use 'anthropic', 'openai', "
            f"'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = (
        task_class.max_output_tokens(task_settings)
        if max_output_tokens is None else max_output_tokens
    )
    logger = Logger(log=log, snapshot={
        "task": task_class.task_name(),
        "max_iterations": effective_max_iterations,
        "max_turn_tokens": cfg.agent_max_turn_tokens(),
        "max_output_tokens": effective_max_output_tokens,
        "context_window": context_window,
        "model": model,
        "provider": backend,
    })

    repl_obj = Repl(
        context=ctx, registry=registry, builder=builder, client=client,
        logger=logger, task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_turn_tokens=cfg.agent_max_turn_tokens(),
        max_output_tokens=effective_max_output_tokens,
        config_dir=cfg.dir, provider=backend, model=model,
        version=VERSION, api_key=api_key, mcp_servers=mcp_clients,
    )
    try:
        if tui:
            from .tui import Tui  # local import: don't require textual unless tui=True
            Tui(repl_obj).run()
        else:
            repl_obj.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()


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
    "tools",
    "models",
    "get_config",
    "enable_debug",
    "is_debug",
    "Logger",
    "Client",
    "Agent",
    "RunDSL",
    "run",
    "VERSION",
    "Repl",
    "repl",
]
