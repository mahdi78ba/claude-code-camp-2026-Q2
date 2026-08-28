"""The interactive REPL session loop.

Python port of Boukensha::Repl. Wraps the same primitives as a single
boukensha.run() call, but instead of running once it stays alive: it reads
a line from the user, runs the agent, prints the reply, and loops back to
the prompt. The Context is shared across every turn, so conversation
history accumulates naturally.

Built-in commands (not sent to the agent):
  /help    print the command list
  /clear   wipe conversation history (tools stay registered)
  /exit    leave the REPL
  /quit    alias for /exit

Ctrl-D leaves the REPL (Python raises EOFError from input(), where Ruby's
$stdin.gets returns nil). Ctrl-C is deliberately not caught here — it
propagates out of start() and is handled one level up, by repl()
(boukensha/__init__.py), mirroring where Ruby's Boukensha.repl (not
Repl#start) catches Interrupt.

This class no longer hard-codes print()/input(): on_output() lets a
front-end (Tui) capture everything this Repl would otherwise print, and
handle_command()/run_turn()/banner() are public so a front-end can drive
turns and slash commands directly instead of only through start()'s own
loop. Mirrors Ruby's ruby/11_tui Repl refactor. /quiet and /loud (and the
module-level enable_quiet/enable_loud/is_quiet they toggled) are removed
here for the same reason Ruby dropped them in that same refactor: nothing
ever read the quiet flag, in either language, even before this change.
"""

from __future__ import annotations

from pathlib import Path

from .agent import Agent
from .errors import ApiError, LoopError

PROMPT = "boukensha> "

HELP = """Commands:
  /clear    wipe conversation history (tools stay)
  /compact  drop oldest 40% of messages to free context
  /exit     leave the REPL
  /help     show this message
"""


class Repl:
    def __init__(self, *, context, registry, builder, client, logger,
                 config_dir=None, provider=None, model=None, version=None,
                 api_key=None, mcp_servers=None, task_settings=None,
                 max_iterations=None, max_turn_tokens=None, max_output_tokens=None):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.task_settings = task_settings
        self.max_iterations = max_iterations
        self.max_turn_tokens = max_turn_tokens
        self.max_output_tokens = max_output_tokens
        self.config_dir = config_dir
        self.provider = provider
        self.model = model
        self.version = version
        self.api_key = api_key
        self.mcp_servers = mcp_servers or []
        self.turn = 0
        self._output_cb = None

    def on_output(self, callback):
        """Register a callback that receives every string this Repl would
        otherwise print to stdout. When set, print() is bypassed entirely
        and all output is routed through the callback instead. Used by
        Tui."""
        self._output_cb = callback

    def banner(self):
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
        mcp_status = self.mcp_status_string()

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){pad}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:      {config_line}\n"
            f"  provider:    {provider_line}\n"
            f"  mcp servers: {mcp_status}\n"
            "\n"
            "  /clear           reset conversation history\n"
            "  /compact         free context (drop oldest messages)\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def mcp_status_string(self):
        """Build the mcp-servers status string shown in the banner. A
        server only appears in self.mcp_servers once its MCP handshake
        already succeeded (tools.mcp.register drops anything that failed
        to start), so this just reports what's already known — no
        re-probing, and therefore no risk of a double-login the way a
        fresh probe would risk for a server backed by a single stateful
        session.
        """
        if not self.mcp_servers:
            return "(not configured)"
        return ", ".join(f"{s['name']} (connected)" for s in self.mcp_servers)

    def handle_command(self, line):
        """Handle a slash command. Returns "quit", "command", or None (not
        a command). Output is routed through the registered on_output
        callback if present."""
        if line in ("/exit", "/quit"):
            self._output("Goodbye.")
            return "quit"
        elif line == "/help":
            self._output(HELP)
            return "command"
        elif line == "/clear":
            self.context.clear_messages()
            self.turn = 0
            self._output("(conversation history cleared)")
            return "command"
        elif line == "/compact":
            dropped = self.context.compact_messages()
            self._output(f"(compacted context — {dropped} messages dropped)")
            return "command"
        return None

    def run_turn(self, line):
        self.turn += 1
        self.logger.turn(n=self.turn)
        self.context.add_message("user", line)

        agent = Agent(
            context=self.context, registry=self.registry, builder=self.builder,
            client=self.client, logger=self.logger, task_settings=self.task_settings,
            max_iterations=self.max_iterations, max_turn_tokens=self.max_turn_tokens,
            max_output_tokens=self.max_output_tokens,
        )
        try:
            result = agent.run()
        except LoopError as e:
            self._output(f"\n[error] {e}")
            return
        except ApiError as e:
            self._output(f"\n[error] API call failed: {e}")
            return

        self._output("")
        self._output(result)

    def start(self):
        self._output(self.banner())

        while True:
            try:
                line = input(PROMPT)
            except EOFError:  # Ctrl-D
                break

            line = line.strip()
            if not line:
                continue

            result = self.handle_command(line)
            if result == "quit":
                break
            if result == "command":
                continue

            self.run_turn(line)

    # ---------- private -----------------------------------------------

    def _output(self, text=""):
        if self._output_cb:
            self._output_cb(str(text))
        else:
            print(text)
