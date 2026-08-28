# Step 11 — A Terminal UI

Boukensha now ships a full terminal UI (TUI) built on the [`charm`](https://github.com/charm-ruby/charm) gem (bubbletea + lipgloss + bubbles). The plain REPL from step 10 is still there and can be selected with `tui: false`.

## What's new

### `Boukensha::Tools::Mcp` (carried forward from step 10)

This step now tracks step 10's later `Tools::Mcp` refactor (it originally
shipped on the pre-refactor step 10, which used a MUD-specific
`Tools::Mud`). `Tools::Mcp.register(registry, servers:)` is the generic
bridge to any number of configured MCP servers — for the MUD case, that's
`mud_manager`'s own bundled MCP server, spawned as a subprocess and proxied
tool-for-tool into the registry — rather than a hand-registered, MUD-specific
tool set living directly in this process.

Config moved with it: `settings.yaml`'s `mud:` block is gone, replaced by an
`mcp_servers:` list (`config.mcp_servers`), and `Boukensha.run`/`.repl` take
`mcp:` instead of `mud:`. `mud_manager` bumped to `~> 0.3` accordingly. See
step 10's README for the full `mcp_servers:` config shape and
`Tools::Mcp`'s collision-handling/`prefix:` behavior — this step didn't
change any of that, just adopted it.

### `Boukensha::Tui`

New class. Wraps a `Repl` instance and replaces its raw `puts`/`gets` I/O with a structured four-zone display:

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

The **progress line** shows a spinner, current action, iteration counter (`n/MAX`), elapsed seconds, token counts (↑ in / ↓ out), and tool call count while the agent is running. When idle it shows context usage and turn count.

The **status line** always shows: version · model · context tokens used/max · registered tool count · wall-clock time.

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `Enter` | Submit input or slash command |
| `Esc` | Interrupt the running agent turn |
| `Ctrl+L` | Clear conversation history |
| `PgUp` / `PgDn` | Scroll conversation viewport |
| `Ctrl+C` / `Ctrl+D` | Quit |

The agent runs in a background thread so the UI stays responsive during long turns.

### `Boukensha.repl` — new `tui:` keyword

```ruby
Boukensha.repl(tui: true)   # default — launches charm TUI
Boukensha.repl(tui: false)  # falls back to plain terminal REPL
```

The `--no-tui` CLI flag sets `tui: false` from the command line.

### `Repl` refactored for composability

`Repl` no longer hard-codes `puts`/`gets`. Three methods are now public so `Tui` (or any other front-end) can drive it:

| Method | Purpose |
|--------|---------|
| `on_output(&block)` | Route all REPL output through a callback instead of stdout |
| `handle_command(input)` | Process a slash command; returns `:quit`, `:command`, or `nil` |
| `run_turn(input)` | Run one agent turn and route the result through `on_output` |

`banner`, `logger`, `context`, `model`, and `version` are also exposed as readers.

### `Logger#subscribe`

```ruby
logger.subscribe { |event| ... }
```

Every structured log event (`:iteration`, `:tool_call`, `:tool_result`, `:response`, etc.) is now broadcast to all registered subscribers as well as being written to the JSONL file. `Tui` uses this to update the live progress line in real time without polling.

## Run Example

The TUI is interactive, so it's run via the global `boukensha` executable
rather than `examples/example.rb` (that file is the step 10 MUD demo — it
doesn't exercise the TUI. It now uses `Tools::Mcp` like the rest of this
step; only its `BOUKENSHA_DIR` path depth was fixed, see
`docs/week1_config_troubleshooting.md`).

```sh
# Build and install this step's gem. If a later step's gem is already
# installed, `boukensha` will keep launching that version's loader instead —
# remove it first:
gem uninstall boukensha

gem build boukensha.gemspec
gem install boukensha-0.11.0.gem

# launches the charm TUI:
BOUKENSHA_DIR=/home/andrew/Sites/Claude-Code-Camp/.boukensha BOUKENSHA_PATH=~/Sites/Claude-Code-Camp/week1_baseline/11_tui boukensha

# plain REPL (no charm dependency required):
BOUKENSHA_PATH=~/Sites/boukensha/11_tui boukensha --no-tui
```

``sh
bundle exec bin/boukensha
```