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
import threading

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

    # Thresholds for context-usage colour coding (mirrors ruby/12_context's
    # tui.rb CTX_WARN_PCT/CTX_ALERT_PCT).
    CTX_WARN_PCT = 70
    CTX_ALERT_PCT = 85

    def __init__(self, repl):
        super().__init__()
        self.repl = repl
        self._events: queue.Queue = queue.Queue()
        self._live_active = False
        self._live_action = "idle"
        self._live_iteration = 0
        self._live_tool_calls = 0
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
        self._main_thread_id = threading.get_ident()
        self.repl.on_output(self._on_repl_output)
        self.repl.logger.subscribe(lambda event: self._events.put(event))
        self.query_one("#conversation", RichLog).write(self.repl.banner())
        self._refresh_progress()
        self._refresh_status()
        self.set_interval(TICK_SECONDS, self._tick)
        self.query_one("#input", Input).focus()

    # ---- output routing --------------------------------------------------
    #
    # _on_repl_output fires from two different threads depending on what
    # produced the output: a running agent turn (_run_turn_worker, below)
    # calls it from its own worker thread, but a slash command handled
    # synchronously inside on_input_submitted (e.g. /clear, /compact) calls
    # it from the main/event-loop thread instead -- Repl.handle_command
    # routes every command's output through this same callback either way.
    # call_from_thread is Textual's documented safe way to touch a widget
    # from another thread, but it *requires* being called from a different
    # thread than the app's own -- calling it from the main thread itself
    # raises "call_from_thread method must run in a different thread from
    # the app". So: call the widget directly when already on the main
    # thread, and only hop via call_from_thread when actually crossing
    # threads.

    def _on_repl_output(self, text: str) -> None:
        conversation = self.query_one("#conversation", RichLog)
        if threading.get_ident() == self._main_thread_id:
            conversation.write(text)
        else:
            self.call_from_thread(conversation.write, text)

    # ---- tick: drain queued logger/turn-lifecycle events ------------------

    def _tick(self) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)
        # Refresh unconditionally, not just when an event drained: a
        # synchronous slash command (/compact, /clear) changes
        # self.repl.context directly, with no logger event to signal it
        # (ruby/12_context's tui.rb has the same property -- render_progress/
        # render_status are recomputed fresh on every tick regardless of
        # what triggered it, not gated behind "something happened this
        # tick"). Cheap: both methods are just string formatting + one
        # widget .update() call each, at TICK_SECONDS (0.1s) cadence.
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
        elif phase == "compaction":
            dropped = event.get("dropped")
            self.query_one("#conversation", RichLog).write(
                f"[context compacted — {dropped} messages dropped to free space]"
            )
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

    def _fmt_tokens(self, n) -> str:
        n = int(n or 0)
        return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

    def _ctx_color(self, pct):
        """None below the warning threshold -- inherits the CSS-defined
        default (already a muted grey) rather than fighting the stylesheet
        with a redundant explicit colour for the common case."""
        if pct >= self.CTX_ALERT_PCT:
            return "red"
        if pct >= self.CTX_WARN_PCT:
            return "yellow"
        return None

    def _refresh_progress(self) -> None:
        progress = self.query_one("#progress", Static)
        if self._live_active:
            text = (
                f"⟳ {self._live_action}  "
                f"(iter {self._live_iteration} · {self._live_tool_calls} calls)"
            )
            progress.styles.color = None
        else:
            ctx = self.repl.context
            pct = ctx.usage_pct
            used = self._fmt_tokens(ctx.current_tokens)
            window = self._fmt_tokens(ctx.context_window)
            text = f"[ready]   ctx {used}/{window} ({pct}%)   {self._turn_count} turns"
            progress.styles.color = self._ctx_color(pct)
        progress.update(text)

    def _refresh_status(self) -> None:
        status = self.query_one("#status", Static)
        ver = self.repl.version or "?.?.?"
        model = self.repl.model or "(model)"
        ctx = self.repl.context
        pct = ctx.usage_pct
        used = self._fmt_tokens(ctx.current_tokens)
        window = self._fmt_tokens(ctx.context_window)
        warn = " ⚠" if pct >= self.CTX_ALERT_PCT else ""
        text = (
            f" boukensha v{ver} · {model} · ctx {used}/{window} ({pct}%){warn} "
            f"· {ctx.tool_count} tools "
        )
        # The status bar's own background (set in CSS) is already dark, so
        # only the alert threshold gets an explicit colour override here --
        # yellow-on-dark at the warn threshold reads worse than it does on
        # #progress's plain background, so this bar only escalates for red.
        status.styles.color = "red" if pct >= self.CTX_ALERT_PCT else None
        status.update(text)

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
