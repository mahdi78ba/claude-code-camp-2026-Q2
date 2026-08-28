# What is a TUI, and how `boukensha`'s TUI is built

A simple explainer of the concept, then a walkthrough of how
`ruby/11_tui` actually implements one on top of the existing REPL —
written to be readable without prior Bubble Tea experience.

## What "TUI" means

**TUI = Terminal User Interface.** It's the middle ground between:

| | Plain CLI/REPL | TUI | GUI |
|---|---|---|---|
| Runs in | a terminal, line by line | a terminal, but takes over the whole screen | a window, with a mouse |
| Output | scrolls, one line per `puts` | fixed panes that redraw in place | pixels, widgets |
| Input | type a line, press Enter, wait | live: keystrokes, arrow keys, scrolling, all handled instantly | click, drag, type |
| Example | `irb`, `psql` | `htop`, `vim`, `lazygit` | any desktop app |

A TUI still only has text and a terminal to work with, but it uses ANSI
escape codes to move the cursor, clear regions, and color text — so
instead of an ever-scrolling log, you get fixed zones on screen (a status
bar that never scrolls away, a scrollable pane above it, etc.) that update
in place, many times a second if needed.

## Why `boukensha` has one

Steps 1–10 built `Boukensha::Repl`: read a line from `$stdin`, run the
agent, `puts` the result, loop. That's a real REPL, but every line ever
printed just scrolls past — there's no persistent "where am I / what's the
agent doing right now" view. Step 11 (`ruby/11_tui`) wraps that same REPL
in a real terminal UI: a scrollable conversation history, a live "the
agent is thinking / calling tool X" progress line, an input box, and an
always-visible status bar — without changing how the agent itself works.

## The library: Bubble Tea

`boukensha` uses [`charm`](https://github.com/charm-ruby/charm), Ruby
bindings for Charm's Go TUI libraries. The three actually used here
(`lib/boukensha/tui.rb` deliberately requires only these three, not all of
`charm` — see the comment at the top of that file for why):

- **`bubbletea`** — the TUI framework itself (the "engine")
- **`lipgloss`** — styling (colors, backgrounds, bold)
- **`bubbles`** — pre-built widgets (`Viewport` for scrolling text,
  `TextArea` for the input box)

Bubble Tea follows **The Elm Architecture** — the same pattern Elm/Redux
popularized: one place holds all the state (the *Model*), and the only way
state changes is by handling an incoming *Message* and returning a new
Model. Three methods, every Bubble Tea program implements all three:

```ruby
def init            # called once at startup
  [self, some_first_command]
end

def update(msg)      # called every time something happens (keypress, tick, ...)
  # ...mutate state based on msg...
  [self, next_command_or_nil]
end

def view             # called after every update — return the full screen as a string
  "...whatever should be on screen right now..."
end
```

You never write `print` calls yourself for the live parts of the screen —
you just describe, in `view`, what the screen should look like *given the
current state*, and the framework figures out how to redraw the terminal
efficiently.

## The four zones, and where they come from

```
┌──────────────────────────────────────────────┐
│  conversation viewport (scrollable)           │  <- Bubbles::Viewport
├──────────────────────────────────────────────┤
│  ⟳ live progress line (hidden when idle)     │  <- plain string, built from Logger events
├──────────────────────────────────────────────┤
│  boukensha> input box                         │  <- Bubbles::TextArea
├──────────────────────────────────────────────┤
│  status line (always-on)                      │  <- plain string, styled with Lipgloss
└──────────────────────────────────────────────┘
```

`Boukensha::Tui#view` (`lib/boukensha/tui.rb`) is literally:

```ruby
def view
  sync_viewport if @dirty
  [
    @viewport.view,      # zone 1
    render_progress,     # zone 2
    render_input,        # zone 3
    render_status        # zone 4
  ].join("\n")
end
```

Four small methods, each returning a string for its own zone, joined
together. That's the whole rendering story.

## The key idea: `Tui` wraps `Repl`, it doesn't replace it

This is the part worth understanding, not just the widget layout. `Tui`
does **not** reimplement the agent loop, tool dispatch, or conversation
handling — all of that is still exactly the same `Boukensha::Repl` from
step 10. `Repl` was only refactored to stop assuming it owns the
terminal:

| Before (plain REPL) | After (composable `Repl`) |
|---|---|
| `puts result` directly | `output(result)` → calls a registered callback if one exists, else `puts` |
| `gets` in a `loop` | same loop, but `Tui` drives input via keypresses instead |
| slash commands handled inline in `start` | pulled out into `handle_command(input)`, returns `:quit` / `:command` / `nil` |
| — | `run_turn(input)` and `banner` made public so an outside caller can invoke them |

So `Tui#start` does this:

```ruby
@repl.on_output { |str| @conversation << str.to_s; @dirty = true }   # capture what Repl would have puts'd
@repl.logger.subscribe { |event| @events << event }                  # capture structured log events too
Bubbletea::Runner.new(self, alt_screen: true, ...).run                # hand control to the Bubble Tea event loop
```

Every `Enter` keypress calls `@repl.handle_command(input)` (for `/exit`,
`/clear`, ...) or, for a normal message, runs the agent **on a background
thread** (`Thread.new { @repl.run_turn(input) }`) so the UI keeps
redrawing (spinner, elapsed seconds, live token counts) while the model
call and tool calls are in flight. `Logger#subscribe` is what makes the
live progress line possible — every `:iteration` / `:tool_call` /
`:response` event the agent already emits gets pushed into a `Queue`,
drained once per tick, and turned into `render_progress`'s spinner +
counters. None of that required touching `Agent` or `Client` at all.

## What actually happens on a keypress or a tick

```ruby
def update(msg)
  case msg
  when Bubbletea::WindowSizeMessage  # terminal resized -> resize viewport
  when TickMsg                       # ~60ms heartbeat -> advance spinner, drain log events
  when Bubbletea::KeyMessage         # a real keypress -> handle_key(msg)
  end
  [self, cmd]
end
```

`TickMsg` is how the spinner animates and the clock in the status bar
updates even though nothing was typed — `init` schedules one tick, and
each tick re-schedules the next, forever, until `:quit` is returned.

## Building and running it

Packaging/build/install steps (gemspec, `gem build`, `gem install`, the
`mcp_servers:` config schema) are covered in
`docs/week1_tui_gem_build_install.md` — this doc is about the TUI concept
and code, that one's about turning this directory into the `boukensha`
command. Short version, once installed:

```sh
boukensha              # tui: true by default — the real Bubble Tea screen
boukensha --no-tui      # tui: false — falls back to the plain step-10-style REPL
```

`--no-tui` exists specifically so the same agent/tool code is testable
(and usable) even on a dumb terminal or in a script, without Bubble Tea in
the loop at all — see `Boukensha.repl(tui:)` in `lib/boukensha.rb`.

## One real gotcha worth knowing

Bubble Tea's native (Go) extension reads keyboard input one `read()` call
at a time; the copy of it originally shipped had a bug where, if more than
one byte arrived in a single `read()` (fast typing, a paste, or anything
that writes to the terminal in one burst), everything after the first byte
was silently dropped — including `Enter` itself. Fixed upstream in
`ruby/11_tui/patches/bubbletea/` (a C-level patch + a script that
reapplies it after every gem reinstall, since the fix lives inside a
precompiled native gem and doesn't survive a reinstall on its own). See
`docs/week1_config_troubleshooting.md` entry #37 for a live repro and why
this sandbox specifically can't rebuild it (no C compiler installed).
