# Python Port Plan — A Terminal UI (`11_tui`)

Baseline for this port is `python/10_standard_tool_library`, copied
verbatim into `python/11_tui` (`.venv/`, `__pycache__/` excluded —
machine-local, regenerated on install; a fresh `.venv` was created for
`11_tui` and `pip install -r requirements.txt` already run against it, so
the copy imports cleanly today at `VERSION == "0.10.0"`, pre-port).
Confirmed byte-identical to `10_standard_tool_library` via `diff -rq
--exclude=.venv --exclude=__pycache__` before any of this plan's changes
are applied.

This plan's delta is **only** `ruby/10_standard_tool_library` →
`ruby/11_tui`, the same way `10_standard_tool_library.md` was `08` → `10`.
It is *not* a re-port of MCP — confirmed by inspection that
`python/10_standard_tool_library` already has full MCP parity with Ruby's
own `10_standard_tool_library` (`boukensha/config.py`'s `mcp_servers()` /
`_resolve_env()`, `boukensha/registry.py`'s `registered()`,
`boukensha/tools/mcp.py`, and `boukensha/logger.py`'s `subscribe()` are
all already present and correct). None of that is step 11's work in either
language — see "Cross-check" below.

## What actually changed in Ruby (10 → 11, cumulative)

1. **`Boukensha::Tui`** (new, `lib/boukensha/tui.rb`) — wraps a `Repl`
   instance and replaces its raw `puts`/`gets` I/O with a four-zone
   terminal display (conversation viewport, live progress line, input
   box, always-on status bar), built on the `charm` gem (Bubble Tea +
   Lip Gloss + Bubbles). Elm-architecture: `init`/`update(msg)`/`view`.
   Agent turns run on a background `Thread`; `Logger#subscribe` events
   feed a `Queue` drained once per ~60ms tick to animate the progress
   line without polling the agent itself.
2. **`Repl` refactored for composability** (`lib/boukensha/repl.rb`):
   `on_output(&block)` (route output through a callback instead of
   `puts`), `handle_command(input)` (returns `:quit` / `:command` / `nil`
   instead of handling commands inline inside `start`), `run_turn(input)`
   made public, `banner`/`logger`/`context`/`model`/`version` exposed as
   readers. `/quiet` and `/loud` commands — and the `Boukensha.quiet!`/
   `loud!`/`quiet?` module state they toggled — were **removed entirely**
   in this same refactor (confirmed: nothing in Ruby's `logger.rb` ever
   read `Boukensha.quiet?` even in `10_standard_tool_library` — it was
   dead state before 11 deleted it).
3. **`Boukensha.repl` gained a `tui:` keyword** (default `true`); when
   true and `Tui` is defined, `Tui.new(repl).start` runs instead of
   `repl.start`.
4. **`boukensha_loader.rb`'s `--no-tui` CLI flag** — sets `tui: false`
   when launching the packaged `boukensha` executable directly. This is
   the same *packaging/CLI-invocation* category of change the
   `10_standard_tool_library.md` plan already decided has no Python
   counterpart (see that plan's "Why 09 is skipped" — Python has no
   installed-executable/loader layer to attach a flag to). Not skipped
   *here* the same way, though — Python still needs *some* way to launch
   the REPL/TUI at all, since it never had a `bin/boukensha` in the first
   place. See judgment call #3.
5. **`Logger#subscribe`** — already existed, byte-identical, in Ruby's
   *own* `10_standard_tool_library` (`ruby/10_standard_tool_library/lib/
   boukensha/logger.rb:72`). Not a step-11 change in Ruby at all — no
   action needed here either, beyond what Python already has.

## Cross-check against the current Python tree

Everything MCP/tool-library-related that a naive "diff Ruby 10 vs Ruby
11" might suggest porting is **already present** in
`python/10_standard_tool_library` (and therefore already in the fresh
`11_tui` copy):

| Ruby | Already in Python's `10_standard_tool_library`? |
|---|---|
| `Tools::Mcp` / `mcp_servers:` | Yes — `boukensha/tools/mcp.py`, `Config.mcp_servers()` |
| `Registry#registered?` | Yes — `boukensha/registry.py` |
| `Logger#subscribe` | Yes — `boukensha/logger.py:79` |

So the entire real delta for this plan is the TUI layer itself, the
`Repl` composability refactor, and the `repl()`/launcher changes needed
to reach it — nothing tool/MCP-related.

## No Python equivalent of `charm`/Bubble Tea exists — `textual` selected

Unlike the MCP port (which reused a hand-rollable JSON-RPC protocol, no
new dependency needed), there is no existing Python code anywhere in this
repo that plays the role Bubble Tea plays in Ruby, and no drop-in
equivalent exists on PyPI either — `charm`/Bubble Tea is a Go library
with Ruby bindings; nothing in the Python ecosystem wraps that same Go
code. A real, independent library choice has to be made for Python, not
a mechanical "find the Python port of this gem."

Checked what's actually usable in this sandbox (unlike the Ruby side,
where `charm`'s Go-backed native gems couldn't be fetched or compiled at
all): this sandbox **does** have real PyPI network access, and
`textual==8.2.8` installs cleanly — pure Python (plus `rich`,
`markdown-it-py`, `pygments`; no C/Go compiler needed). `urwid`,
`prompt_toolkit`, and `blessed` also resolve, but Textual is the only one
of the four with a reactive, widget-tree-based architecture in the same
spirit as Bubble Tea's Elm architecture (declare what the screen should
show given the current state; let the framework handle the actual
terminal diffing/redraw), rather than requiring the low-level manual
redraw code `urwid`/`blessed`/raw `curses` would need.

**Decision: `textual`, pinned `==8.2.8`** — this is settled, not open for
re-litigation in judgment call #1 below (kept there only to record why,
for anyone reading just that section).

## Implementation philosophy: same purpose, not a mechanical transliteration

The table below exists to help a reader who knows Ruby's `tui.rb`
orient themselves in Textual's vocabulary — it is **not** a spec saying
"reproduce each Bubble Tea mechanism 1:1." Where Textual has a more
idiomatic way to get the same *user-facing* result (four zones that stay
visible and update live; typing is never blocked while the agent is
working; tool calls and turn progress are visible as they happen), prefer
Textual's own idiom over hand-copying Ruby's specific implementation
choice. Concretely:

- It's fine — encouraged, even — to use Textual **reactive attributes**
  (`reactive(...)` + `watch_*` methods) to drive the progress/status
  lines instead of manually re-rendering every zone's full string on
  every tick the way `tui.rb`'s `view` does; Textual already re-renders
  only what changed when a reactive value updates, so there's no need to
  reimplement Ruby's own `@dirty` flag/manual diffing at all.
- It's fine to lean on Textual's built-in `Footer`/`Header` widgets, CSS
  layout, or other built-ins where they get the same visual result with
  less code, rather than hand-building every zone from a bare `Static`
  just because Ruby built its status bar from a bare string.
- What must be preserved is the *behavior*, not the mechanism: a
  scrollable conversation history, a live indicator of what the agent is
  currently doing (thinking / calling tool X / awaiting a result), an
  input box that keeps accepting keystrokes while a turn runs in the
  background, and a status bar showing model/context/tool-count — same
  as Ruby's four zones do, however Textual chooses to render them
  internally.
- The one place this repo's own experience says "don't improvise, mirror
  Ruby's decision deliberately" is **thread-safety**: Ruby's
  `Queue`-drained-on-a-tick pattern for logger events, and its
  `on_output` callback, both exist specifically to avoid mutating UI
  state from a non-main thread. Textual widgets have the exact same
  constraint (`call_from_thread` exists precisely because touching
  widgets off the main thread is unsafe). This is a correctness
  requirement carried over for a real reason, not a style choice to
  optionally match — see judgment call #5.

| Bubble Tea (Ruby) — for orientation only | Textual (Python) |
|---|---|
| `Model#init` | `App.compose()` / `on_mount` |
| `Model#update(msg)` | message handlers (`@on(Input.Submitted)`, etc.) + reactive attributes |
| `Model#view` (hand-written, re-run every tick) | reactive attributes + `watch_*` — Textual re-renders only what changed |
| `Bubbletea.tick` | `self.set_interval(seconds, callback)` |
| `Bubbles::Viewport` | `RichLog` (or `Log`) widget — scrollable, `.write(text)` |
| `Bubbles::TextArea` | `Input` widget — `Input.Submitted` message on Enter |
| `Lipgloss::Style` | Textual CSS (`styles.background`, `.tcss` stylesheet, or inline `Style` objects) |
| a background `Thread` per turn | `@work(thread=True)` worker (Textual's threaded-worker decorator) |
| `Queue` drained on tick | same pattern, kept deliberately (see above): `queue.Queue`, drained by a `set_interval` callback |

## Files to add / change in Python

### 1. `requirements.txt` — add `textual`

```
PyYAML==6.0.3
python-dotenv==1.2.2
textual==8.2.8
```

### 2. `boukensha/version.py`

```python
VERSION = "0.11.0"
```

Same version-tracks-Ruby-step-number convention the `10` plan already
established (its own judgment call about `VERSION`).

### 3. `boukensha/__init__.py` — drop dead `quiet` state; `repl()` gains `tui=`

Remove `_quiet`, `enable_quiet`, `enable_loud`, `is_quiet`, and their
`__all__` entries (matching Ruby's own removal — confirmed dead in
*either* language even before this port, per this plan's own
`10_standard_tool_library.md`-inherited comment in `__init__.py`: "unused
in this iteration in either language, shipped for parity"). Keep
`get_config`/`enable_debug`/`is_debug` untouched.

`repl()` signature gains one new keyword, and the final dispatch changes:

```python
def repl(*, system=None, model=None, backend=None, api_key=None,
          ollama_host="http://localhost:11434", log=None,
          max_output_tokens=None, working_dir=None, allowed_commands=None,
          shell_timeout=30, mcp=None, configure=None, tui=True):
    ...
    repl_obj = Repl(
        context=ctx, registry=registry, builder=builder, client=client,
        logger=logger, task_settings=task_settings,
        max_iterations=effective_max_iterations,
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
```

The local `from .tui import Tui` (rather than a top-level import) means
`boukensha` itself never hard-requires `textual` to be installed — only
`tui=True` (the default) does. Mirrors why Ruby's own `require_relative
"boukensha/tui"` at the bottom of `boukensha.rb` is *not* conditional
there (Ruby's `charm` require happens unconditionally at load time — a
known, already-documented rough edge on the Ruby side, see
`docs/week1_config_troubleshooting.md` entries about the sandbox lacking
`charm`). Python doesn't have to inherit that rough edge since nothing
else in `boukensha/__init__.py` needs `textual` loaded eagerly.

### 4. `boukensha/repl.py` — composability refactor

```python
class Repl:
    def __init__(self, *, ..., mcp_servers=None, ...):
        ...
        self.turn = 0
        self._output_cb = None

    def on_output(self, callback):
        """Route every string this Repl would otherwise print through
        `callback` instead. Used by Tui."""
        self._output_cb = callback

    def _output(self, text=""):
        if self._output_cb:
            self._output_cb(str(text))
        else:
            print(text)

    def banner(self):          # was _banner — now public
        ...

    def handle_command(self, line):
        """Handle a slash command. Returns "quit", "command", or None
        (not a command). Output goes through self._output."""
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
        return None

    def run_turn(self, line):   # was _run_turn — now public
        self.turn += 1
        self.logger.turn(n=self.turn)
        self.context.add_message("user", line)
        agent = Agent(context=self.context, registry=self.registry,
                       builder=self.builder, client=self.client,
                       logger=self.logger, task_settings=self.task_settings,
                       max_iterations=self.max_iterations,
                       max_output_tokens=self.max_output_tokens)
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
                line = input(PROMPT) if not self._output_cb else None
            except EOFError:
                break
            ...
            result = self.handle_command(line)
            if result == "quit":
                break
            if result == "command":
                continue
            self.run_turn(line)
```

Drop `/quiet`/`/loud` from `HELP` and from `handle_command` entirely, and
drop `from . import enable_loud, enable_quiet` from the top of the file
— matching Ruby's removal exactly (see "What actually changed" #2). The
banner's `mcp servers:` line and `_mcp_status_string` stay exactly as
they are today (rename to `mcp_status_string`, drop the leading
underscore, same reasoning as `banner`/`run_turn`).

### 5. `boukensha/tui.py` — new

No Ruby file to port line-for-line (see the library-choice section
above) — this is genuinely new code, sketched here at architecture level
for the implementer to build out and test properly (flagged again under
Judgment calls, since the exact widget tree is a real design decision,
not a mechanical translation):

```python
import queue
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import RichLog, Input, Static

class Tui(App):
    CSS = """
    #progress { height: 1; }
    #status   { height: 1; dock: bottom; }
    """

    def __init__(self, repl):
        super().__init__()
        self.repl = repl
        self._events = queue.Queue()
        self._live = {"active": False, "action": "idle", "iteration": 0,
                      "tool_calls": 0, "turn_input_tokens": 0,
                      "turn_output_tokens": 0}
        self._session_input_tokens = 0
        self._turn_count = 0

    def compose(self) -> ComposeResult:
        yield RichLog(id="conversation", wrap=True, highlight=False)
        yield Static(id="progress")
        yield Input(placeholder="Type a message…", id="input")
        yield Static(id="status")

    def on_mount(self):
        self.repl.on_output(self._on_repl_output)
        self.repl.logger.subscribe(lambda event: self._events.put(event))
        self.query_one("#conversation", RichLog).write(self.repl.banner())
        self.set_interval(0.1, self._tick)
        self.query_one("#input", Input).focus()

    def _on_repl_output(self, text):
        # Called from the agent's worker thread — must not touch widgets
        # directly. Route through call_from_thread, same reasoning as
        # Ruby's Queue-drained-on-tick: no cross-thread UI mutation.
        self.call_from_thread(self.query_one("#conversation", RichLog).write, text)

    def _tick(self):
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)
        self.query_one("#progress", Static).update(self._render_progress())
        self.query_one("#status", Static).update(self._render_status())

    def _handle_event(self, event):
        phase = event.get("phase")
        if phase == "iteration":
            self._live["active"] = True
            self._live["iteration"] = event.get("n", 0)
        elif phase == "tool_call":
            self._live["action"] = f"Calling tool: {event.get('name')}"
            self._live["tool_calls"] += 1
        elif phase == "response":
            usage = event.get("usage") or {}
            self._session_input_tokens += usage.get("input_tokens", 0)
        elif phase == "turn_complete":
            self._live["active"] = False
            self._turn_count += 1

    def on_input_submitted(self, message: Input.Submitted):
        line = message.value.strip()
        self.query_one("#input", Input).value = ""
        if not line:
            return
        if line.startswith("/"):
            if self.repl.handle_command(line) == "quit":
                self.exit()
            return
        self.query_one("#conversation", RichLog).write(f"> {line}")
        self._run_turn_worker(line)

    @work(thread=True)
    def _run_turn_worker(self, line):
        self.repl.run_turn(line)

    def _render_progress(self):
        if self._live["active"]:
            return f"⟳ {self._live['action']}  (iter {self._live['iteration']} · {self._live['tool_calls']} calls)"
        return f"[ready]  ctx {self._session_input_tokens}  {self._turn_count} turns"

    def _render_status(self):
        return (f" boukensha v{self.repl.version} · {self.repl.model} "
                f"· ctx {self._session_input_tokens} · {self.repl.context.tool_count} tools ")
```

This sketch keeps the same four zones, in the same order, as Ruby's
`tui.rb` — that's the *purpose* being preserved (a reviewer familiar with
the Ruby file should recognize the layout immediately) — and keeps the
`queue.Queue`-drained-on-a-timer pattern for the reason given above
(thread safety, not style). It is a **starting point, not a required
shape**: `_render_progress`/`_render_status` returning plain strings for
a `Static` to `.update()` is the simplest thing that works, but if the
implementer finds Textual's `reactive()` + `watch_*` mechanism cleaner
for the progress/status text specifically (per the philosophy section
above), that's a fine substitution — the four-zone layout, the
non-blocking input, and the live tool-call visibility are what this port
actually needs to preserve, not this exact method-by-method shape.

### 6. `examples/repl.py` — new

A thin launcher mirroring `examples/example.py`'s config bootstrap
(`sys.path` setup, `BOUKENSHA_DIR` default, `boukensha.get_config()`
print), but calling `boukensha.repl()` instead of `boukensha.run()`:

```python
"""Boukensha Step 11: A Terminal UI — interactive launcher.

Launches the REPL (Textual TUI by default; pass tui=False, or run with
--no-tui, for the plain print()/input() REPL from step 10).
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import boukensha  # noqa: E402

repo_root = Path(__file__).resolve().parents[4]
os.environ.setdefault("BOUKENSHA_DIR", str(repo_root / ".boukensha"))

no_tui = "--no-tui" in sys.argv
boukensha.repl(tui=not no_tui)
```

`examples/example.py` (the step-10 MUD one-shot demo) is **unchanged** —
same status Ruby gives its own carried-forward `examples/example.rb`.

### 7. `bin/python/11_tui` — new runner

Same shape as `bin/python/10_standard_tool_library`, pointed at the new
launcher instead of the one-shot demo:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../python/11_tui"
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi
exec "$PY" examples/repl.py "$@"
```

`"$@"` passthrough is what lets `--no-tui` reach `examples/repl.py`'s
`sys.argv` check.

### 8. `README.md` — full rewrite, not a port

Same convention as the `10` plan's own README item: describe what's new
for step 11 (the `Tui` class/four-zone layout, `Repl`'s composability
refactor, `repl(tui=)`, how to run it), not a diffed rewrite of the
step-10 README.

## Judgment calls (flag for the implementer, don't silently decide)

1. **TUI library: `textual` vs. `urwid`/`prompt_toolkit`/`blessed`?**
   **Decided, not open: `textual`**, pinned `==8.2.8` (confirmed
   pip-installable in this sandbox with no compiler, unlike Ruby's
   `charm` — real dependency choice, since no library wraps Bubble Tea's
   actual Go code for Python). Its reactive/App-based model is the
   closest existing analog to Bubble Tea's Elm architecture, and it ships
   the two widgets (`RichLog`, `Input`) this layout most directly needs,
   out of the box. Kept in this list only so the "why" is recorded
   alongside the other calls, not because it's still undecided.
2. **Drop `/quiet`/`/loud` and the module-level quiet state?**
   Recommendation: **yes** — matches Ruby's own step-11 removal exactly,
   and both were already dead code in Python's `10_standard_tool_library`
   (nothing ever reads `is_quiet()`; the existing `__init__.py` comment
   already says so). Removing dead code that Ruby also removed is not
   scope creep here — it's tracking the same source step Ruby tracks.
3. **How does Python "launch the TUI" at all, with no gem/loader/`bin/
   boukensha` equivalent?** Recommendation: a new `examples/repl.py` +
   `bin/python/11_tui`, leaving `examples/example.py` (the MUD one-shot
   demo) untouched — not folding TUI-launch logic into the existing demo
   script, and not inventing a `BOUKENSHA_PATH`-style loader Python has
   never had (that whole category was already ruled out of scope by the
   `10` plan's "Why 09 is skipped" reasoning, and nothing about step 11
   changes that reasoning).
4. **Background turn execution: `threading.Thread` directly, or
   Textual's `@work(thread=True)` decorator?** Recommendation:
   **`@work(thread=True)`** — it's Textual's supported idiom for exactly
   this ("run blocking code without freezing the UI"), handles
   thread lifecycle/cancellation for you, and `self.call_from_thread(...)`
   is the documented safe way back onto the main loop — directly
   analogous to Ruby's hand-rolled `Thread.new` + `Queue`, just using the
   framework's own primitive instead of reimplementing it.
5. **Cross-thread UI updates: call widget methods directly from the
   logger-subscriber callback (which fires on the turn's worker thread),
   or queue-and-drain-on-a-timer like Ruby does?** Recommendation:
   **queue-and-drain**, matching Ruby's own design exactly (`@events =
   Queue.new`, drained every tick) — Textual widgets are not
   thread-safe to mutate directly from a non-main thread any more than
   Bubble Tea's are; `call_from_thread` for the `on_output` path and a
   `queue.Queue` + `set_interval` for logger events both exist in the
   sketch above for this reason, not by accident.
6. **`VERSION` value.** Recommendation: `"0.11.0"` — same
   tracks-the-Ruby-step-number convention as every prior version bump in
   this series (see the `10` plan's own version judgment call).

## Unchanged — carry forward as-is

`boukensha/agent.py`, `boukensha/client.py`, `boukensha/config.py`,
`boukensha/context.py`, `boukensha/errors.py`, `boukensha/message.py`,
`boukensha/prompt_builder.py`, `boukensha/registry.py`, `boukensha/tool.py`,
`boukensha/run_dsl.py`, `boukensha/tasks/*.py`, `boukensha/backends/*.py`,
`boukensha/tools/*.py` (file_system/shell/mcp — already fully ported),
`boukensha/logger.py` (already has `subscribe`), `examples/example.py`,
`prompts/system.md`. None of these have any Python-relevant change in the
Ruby `10` → `11` diff.

## Verification plan

Same two-layer approach as every prior port in this series:

1. **Offline, no live API, no Textual rendering needed:**
   - Unit-test `Repl.handle_command` directly: `/exit`/`/quit` return
     `"quit"`; `/clear` resets `self.turn` to 0 and returns `"command"`;
     `/help` returns `"command"`; a non-slash line returns `None`.
   - Confirm `Repl.on_output` actually redirects: register a callback,
     call `repl.run_turn(...)` (against a stubbed `Agent`/`Client` that
     returns a canned string, no real API call), assert the callback
     received the output and nothing was printed to real stdout.
   - Confirm `boukensha.repl(tui=False)` still reaches
     `Repl.start()`'s plain `input()`/`print()` loop unchanged — i.e.
     that this port didn't silently make `tui=True` mandatory.
   - Import `boukensha.tui.Tui` and instantiate it against a stub `Repl`
     (no real Textual app run — just `compose()`/construction) to catch
     import-time errors (missing `textual` install, typo'd widget names)
     without needing a live terminal.
2. **Live, with `textual`'s own test harness**: Textual ships `App.run_test()`
   (an `async with app.run_test() as pilot:` context that drives the app
   without a real terminal) — use it to simulate typing a message via
   `pilot.press(*"hello")` + `pilot.press("enter")` and assert the
   conversation `RichLog` gained the expected `"> hello"` line, against a
   `Repl` wired to a stub backend (no real Anthropic call, no real MUD).
3. **Full live smoke test**: `./bin/python/11_tui` for real, against the
   Anthropic backend and a running CircleMUD instance (same setup Ruby's
   own `11_tui` uses), matching the acceptance shape of
   `docs/week1_config_troubleshooting.md` entry #37 (ask the agent where
   it is, issue a movement command, confirm the room actually changes,
   confirm MCP tool calls appear live in the progress line). Also run
   `./bin/python/11_tui --no-tui` and confirm it's the same plain REPL
   step 10 already had, just via the new `examples/repl.py` entry point.
