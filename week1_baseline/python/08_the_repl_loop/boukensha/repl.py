"""The interactive REPL session loop.

Python port of Boukensha::Repl. Wraps the same primitives as a single
boukensha.run() call, but instead of running once it stays alive: it reads
a line from the user, runs the agent, prints the reply, and loops back to
the prompt. The Context is shared across every turn, so conversation
history accumulates naturally.

Built-in commands (not sent to the agent):
  /help    print the command list
  /quiet   suppress detailed logging
  /loud    re-enable logging
  /clear   wipe conversation history (tools stay registered)
  /exit    leave the REPL
  /quit    alias for /exit

Ctrl-D leaves the REPL (Python raises EOFError from input(), where Ruby's
$stdin.gets returns nil). Ctrl-C is deliberately not caught here — it
propagates out of start() and is handled one level up, by repl()
(boukensha/__init__.py), mirroring where Ruby's Boukensha.repl (not
Repl#start) catches Interrupt.
"""

from __future__ import annotations

from pathlib import Path

from . import enable_loud, enable_quiet
from .agent import Agent
from .errors import ApiError, LoopError

PROMPT = "boukensha> "

HELP = """Commands:
  /quiet   suppress logging output
  /loud    re-enable logging output
  /clear   wipe conversation history (tools stay)
  /exit    leave the REPL
  /help    show this message
"""


class Repl:
    def __init__(self, *, context, registry, builder, client, logger,
                 config_dir=None, provider=None, model=None, version=None,
                 api_key=None, task_settings=None, max_iterations=None,
                 max_output_tokens=None):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.task_settings = task_settings
        self.max_iterations = max_iterations
        self.max_output_tokens = max_output_tokens
        self.config_dir = config_dir
        self.provider = provider
        self.model = model
        self.version = version
        self.api_key = api_key
        self.turn = 0

    def start(self):
        print(self._banner())

        while True:
            try:
                line = input(PROMPT)
            except EOFError:  # Ctrl-D
                break

            line = line.strip()
            if not line:
                continue

            if line in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif line == "/help":
                print(HELP)
                continue
            elif line == "/quiet":
                enable_quiet()
                print("(logging suppressed — type /loud to re-enable)")
                continue
            elif line == "/loud":
                enable_loud()
                print("(logging enabled)")
                continue
            elif line == "/clear":
                self.context.clear_messages()
                self.turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(line)

    # ---------- private -----------------------------------------------

    def _banner(self):
        key_status = (
            "✓ API key set" if (self.api_key and self.api_key.strip()) else "✗ API key not set"
        )
        provider_line = f"{self.provider or 'default'} ({self.model or 'default'})  {key_status}"
        config_exists = bool(self.config_dir) and Path(self.config_dir).is_dir()
        config_line = (
            self.config_dir if config_exists
            else f"{self.config_dir or '(default)'}  ✗ directory not found"
        )
        ver = self.version or "?.?.?"
        pad = " " * (9 - len(ver))

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){pad}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            "\n"
            "  /quiet or /loud   toggle logging\n"
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def _run_turn(self, line):
        self.turn += 1
        self.logger.turn(n=self.turn)
        self.context.add_message("user", line)

        agent = Agent(
            context=self.context, registry=self.registry, builder=self.builder,
            client=self.client, logger=self.logger, task_settings=self.task_settings,
            max_iterations=self.max_iterations, max_output_tokens=self.max_output_tokens,
        )
        try:
            result = agent.run()
        except LoopError as e:
            print(f"\n[error] {e}")
            return
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
            return

        print()
        print(result)
