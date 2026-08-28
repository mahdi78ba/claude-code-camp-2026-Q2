"""Tui wraps a Repl instance in a Textual terminal UI.

Python analog of Ruby's ruby/11_tui Boukensha::Tui — there is no Python
library that wraps Bubble Tea's own Go code, so this is new code built on
Textual (https://textual.textualize.io/) rather than a line-for-line port.
See docs/plans/python_port/11_tui.md for why Textual was chosen and which
parts of Ruby's design are preserved deliberately (thread-safety) versus
reimplemented Textual's own way (rendering).

Layout (top -> bottom), same four zones as Ruby's tui.rb:

    conversation viewport (scrollable)   <- RichLog
    live progress line                   <- Static, updated on a tick
    boukensha> input box                 <- Input
    status line (always-on)              <- Static, docked to the bottom

Tui owns no session logic of its own. It only drives Repl's public
on_output()/handle_command()/run_turn() surface, and Logger.subscribe()
for the live progress line — exactly the same seam Ruby's Tui uses, so
none of Agent/Client/Registry ever needed to change for either language's
TUI to exist.

Known, deliberate gap versus Ruby: Ruby's TUI can interrupt a running turn
with Esc (Thread#raise into the turn thread). Python has no safe
equivalent to injecting an exception into a running thread, so that
keybinding is not implemented here — Ctrl+C/Ctrl+Q still quits the whole
app (Textual's own default), just not a single in-flight turn.
"""

from __future__ import annotations

import queue

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog, Static

TICK_SECONDS = 0.1


class Tui(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #conversation {
        height: 1fr;
        border: round $primary;
    }

    #progress {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }

    #input {
        height: 3;
    }

    #status {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        dock: bottom;
    }
    """

    BINDINGS = [
        ("ctrl+l", "clear_conversation", "Clear"),
    ]

    def __init__(self, repl):
        super().__init__()
        self.repl = repl
        self._events: queue.Queue = queue.Queue()
        self._live_active = False
        self._live_action = "idle"
        self._live_iteration = 0
        self._live_tool_calls = 0
        self._session_input_tokens = 0
        self._turn_count = 0
        # Guards against a second turn starting (or /clear firing) while
        # run_turn() is still executing on the worker thread — Context's
        # messages list/turn counter are plain, unsynchronized state, and
        # a Textual worker's cancel() only sets a flag the blocking
        # Agent.run() call never checks, so it cannot actually stop an
        # in-flight turn. Set True on the main thread right before
        # dispatching the worker; cleared back to False on the main
        # thread too, in _handle_event's "turn_complete" branch — every
        # mutation of this flag happens on the main thread, same as every
        # other piece of Tui state.
        self._turn_in_flight = False

    def compose(self) -> ComposeResult:
        yield RichLog(id="conversation", wrap=True, highlight=False, markup=False)
        yield Static(id="progress")
        yield Input(placeholder="Type a message…", id="input")
        yield Static(id="status")

    def on_mount(self) -> None:
        self.repl.on_output(self._on_repl_output)
        self.repl.logger.subscribe(lambda event: self._events.put(event))
        self.query_one("#conversation", RichLog).write(self.repl.banner())
        self._refresh_progress()
        self._refresh_status()
        self.set_interval(TICK_SECONDS, self._tick)
        self.query_one("#input", Input).focus()

    # ---- output routing --------------------------------------------------
    #
    # _on_repl_output is called from the turn's worker thread (see
    # _run_turn_worker below), never from the main/event-loop thread.
    # call_from_thread is Textual's documented safe way to touch a widget
    # from another thread — mutating RichLog directly here would be exactly
    # as unsafe as mutating a Bubble Tea model off its own event loop.

    def _on_repl_output(self, text: str) -> None:
        self.call_from_thread(self.query_one("#conversation", RichLog).write, text)

    # ---- tick: drain queued logger/turn-lifecycle events ------------------

    def _tick(self) -> None:
        drained = False
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)
            drained = True
        if drained:
            self._refresh_progress()
            self._refresh_status()

    def _handle_event(self, event: dict) -> None:
        phase = event.get("phase")
        if phase == "iteration":
            self._live_active = True
            self._live_iteration = event.get("n", 0)
            self._live_action = "Thinking…"
        elif phase == "tool_call":
            self._live_action = f"Calling tool: {event.get('name')}"
            self._live_tool_calls += 1
        elif phase == "tool_result":
            self._live_action = "Awaiting result…"
        elif phase == "response":
            # Logger._execution_metadata already normalizes usage across
            # backends (Anthropic's input_tokens, OpenAI's prompt_tokens,
            # Gemini's promptTokenCount, Ollama's prompt_eval_count) into
            # top-level input_tokens/output_tokens on this same event, so
            # read those directly rather than re-deriving from the raw,
            # backend-specific event["usage"] dict (which would only ever
            # match Anthropic's own key names).
            input_tokens = event.get("input_tokens")
            if input_tokens:
                self._session_input_tokens += input_tokens
        elif phase == "turn_complete":
            # Synthetic — pushed by _run_turn_worker's own finally block,
            # not by Logger. Logger has no "the whole turn is done" phase
            # of its own (mirrors Ruby's Tui, which pushes the same
            # synthetic event from launch_turn's ensure block). Always
            # fires exactly once per turn (success or error), so clearing
            # _turn_in_flight here — on the main thread, like every other
            # state mutation in this class — is enough; no need to also
            # clear it in the turn_error branch below.
            self._live_active = False
            self._live_iteration = 0
            self._live_tool_calls = 0
            self._turn_count += 1
            self._turn_in_flight = False
        elif phase == "turn_error":
            self._live_active = False
            self.query_one("#conversation", RichLog).write(f"[error] {event.get('error')}")

    # ---- rendering the two "live" zones -----------------------------------

    def _refresh_progress(self) -> None:
        if self._live_active:
            text = (
                f"⟳ {self._live_action}  "
                f"(iter {self._live_iteration} · {self._live_tool_calls} calls)"
            )
        else:
            text = f"[ready]   ctx {self._session_input_tokens}   {self._turn_count} turns"
        self.query_one("#progress", Static).update(text)

    def _refresh_status(self) -> None:
        ver = self.repl.version or "?.?.?"
        model = self.repl.model or "(model)"
        text = (
            f" boukensha v{ver} · {model} · ctx {self._session_input_tokens} "
            f"· {self.repl.context.tool_count} tools "
        )
        self.query_one("#status", Static).update(text)

    # ---- input handling ----------------------------------------------------

    def on_input_submitted(self, message: Input.Submitted) -> None:
        line = message.value.strip()
        self.query_one("#input", Input).value = ""
        if not line:
            return

        if line.startswith("/"):
            if line == "/clear" and self._turn_in_flight:
                self.query_one("#conversation", RichLog).write(
                    "(a turn is still running — /clear again once it finishes)"
                )
                return
            if self.repl.handle_command(line) == "quit":
                self.exit()
            return

        if self._turn_in_flight:
            self.query_one("#conversation", RichLog).write(
                "(still working on the previous message — please wait)"
            )
            return

        self._turn_in_flight = True
        self.query_one("#conversation", RichLog).write(f"> {line}")
        self._run_turn_worker(line)

    def action_clear_conversation(self) -> None:
        if self._turn_in_flight:
            self.query_one("#conversation", RichLog).write(
                "(a turn is still running — try Ctrl+L again once it finishes)"
            )
            return
        self.repl.handle_command("/clear")
        self._turn_count = 0
        conversation = self.query_one("#conversation", RichLog)
        conversation.clear()
        conversation.write(self.repl.banner())

    # ---- agent turn, on a background thread -------------------------------
    #
    # Agent/Client make blocking HTTP calls, so this must be a real OS
    # thread, not an asyncio task, or it would freeze the whole UI event
    # loop for the duration of every model call. thread=True is Textual's
    # supported idiom for exactly this — same role as Ruby's Thread.new.

    @work(thread=True, exclusive=True)
    def _run_turn_worker(self, line: str) -> None:
        try:
            self.repl.run_turn(line)
        except Exception as e:  # run_turn already handles LoopError/ApiError itself
            self._events.put({"phase": "turn_error", "error": str(e)})
        finally:
            self._events.put({"phase": "turn_complete"})
