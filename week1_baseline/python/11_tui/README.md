# Step 11 — A Terminal UI

Python port of `ruby/11_tui`. Boukensha now ships a full terminal UI (TUI)
built on [Textual](https://textual.textualize.io/). The plain
print()/input() REPL from step 10 is still there and can be selected with
`tui=False`.

There is no Python library that wraps Bubble Tea's own Go code, so
`boukensha/tui.py` is new code, not a line-for-line port of Ruby's
`tui.rb` — it targets the same four-zone layout and behavior, using
Textual's own idioms rather than reproducing Bubble Tea's mechanics where
Textual already does the equivalent job differently (e.g. reactive
re-rendering instead of a hand-written `view` re-run every tick). See
`docs/plans/python_port/11_tui.md` for the full reasoning, including why
Textual was chosen over `urwid`/`prompt_toolkit`/`blessed`.

## What's new

### `boukensha.tui.Tui`

New module/class. Wraps a `Repl` instance and replaces its raw
`print()`/`input()` I/O with a structured four-zone display:

```
┌──────────────────────────────────────────────┐
│  conversation viewport (scrollable)           │
├──────────────────────────────────────────────┤
│  ⟳ live progress line (hidden when idle)     │
├──────────────────────────────────────────────┤
│  boukensha> input box                         │
├──────────────────────────────────────────────┤
│  status line (always-on)                      │
└──────────────────────────────────────────────┘
```

The **progress line** shows the current action (`Thinking…` / `Calling
tool: X` / `Awaiting result…`), an iteration counter, and a tool-call
count while the agent is running. When idle it shows context tokens used
and turn count.

The **status line** always shows: version · model · context tokens used
· registered tool count.

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `Enter` | Submit input or slash command |
| `Ctrl+L` | Clear conversation history |
| `PageUp` / `PageDown` / arrows | Scroll conversation viewport (built into Textual's `RichLog`, no custom handling needed) |
| `Ctrl+C` / `Ctrl+Q` | Quit |

The agent runs on a background thread (Textual's `@work(thread=True)`)
so the UI stays responsive during long turns — typing, scrolling, and the
live progress line all keep working while a model call or tool call is
in flight.

One deliberate gap versus Ruby: Ruby's TUI can interrupt a single running
turn with `Esc` (`Thread#raise` into the turn's thread). Python has no
safe equivalent to injecting an exception into another thread, so that
specific keybinding isn't implemented — quitting the whole app still
works normally.

### `boukensha.repl()` — new `tui=` keyword

```python
boukensha.repl(tui=True)   # default — launches the Textual TUI
boukensha.repl(tui=False)  # falls back to the plain print()/input() REPL
```

The `--no-tui` CLI flag (handled in `examples/repl.py`) sets `tui=False`
from the command line.

### `Repl` refactored for composability

`Repl` no longer hard-codes `print()`/`input()`. Three methods are now
public so `Tui` (or any other front-end) can drive it:

| Method | Purpose |
|--------|---------|
| `on_output(callback)` | Route all REPL output through a callback instead of stdout |
| `handle_command(line)` | Process a slash command; returns `"quit"`, `"command"`, or `None` |
| `run_turn(line)` | Run one agent turn and route the result through `on_output` |

`banner()`, `logger`, `context`, `model`, and `version` are also public
(previously `_banner()` was private).

`/quiet` and `/loud` — and the module-level `enable_quiet()`/
`enable_loud()`/`is_quiet()` they toggled — are removed in this same
refactor. Neither was ever read anywhere, in either language, even before
this step (confirmed: `boukensha/logger.py` never checked the quiet
flag) — matching Ruby's own step-11 removal exactly.

### `Logger.subscribe()` — already existed, unchanged

`Logger.subscribe(callback)` (every structured log event broadcast to
subscribers, in addition to the JSONL file) was already present as of
step 10, in both languages — not a step-11 change. `Tui` uses it,
unmodified, to update the live progress line in real time without
polling.

## Run it

```sh
./week1_baseline/bin/python/11_tui              # Textual TUI (default)
./week1_baseline/bin/python/11_tui --no-tui      # plain REPL
```

This uses a new launcher, `examples/repl.py` — `examples/example.py` (the
step-10 MUD one-shot demo, using `boukensha.run()`) is unchanged and
still runs the same way it always did; it doesn't exercise the REPL/TUI
at all, same as Ruby's own carried-forward `example.rb`.

Requires `mud_manager --mcp` reachable on `$PATH` and a running CircleMUD
instance, plus `settings.yaml`'s `mcp_servers:` entry pointing at it —
same requirements step 10 already has, unchanged by this step.

```sh
cd python/11_tui
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Known limitations (carried over from the Ruby original, not fixed here)

Same as step 10's own list (`run_command` timeout cleanup, `allowed_commands`
being a first-token filter rather than a shell-aware sandbox, a malformed
tool call raising instead of returning an error string, MCP registration's
up-front connection cost, and no default `command:` fallback in
`tools.mcp` the way Ruby's gem-backed client has) — nothing about the TUI
layer changes any of those; see step 10's README for the full list.
