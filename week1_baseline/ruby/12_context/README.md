# Step 12 — Context Management

When you call an LLM directly you are responsible for the context window. There is no auto-compacting. This step adds proper token tracking, visual warnings, and automatic compaction so the agent never silently blows past the limit.

## What's new

### Accurate context tracking

`Context` now maintains two distinct token counts:

| Attribute | What it measures |
|-----------|-----------------|
| `context_window` | The model's maximum input token capacity (default 200,000 for Anthropic) |
| `current_tokens` | Tokens actually used in the most recent API call (`usage.input_tokens` from the response) |

Previously `token_budget` (8,192) was displayed as the limit — that was the *output* `max_tokens`, not the context window. And the cumulative session token sum was shown as usage, which grew without bound even after `/clear`. Both are fixed.

The Agent updates `current_tokens` after every API response (including mid-turn tool-use calls), so the display always reflects what the next call will actually send.

### Context colour coding

The progress and status lines now colour the context indicator based on how full the window is:

| Usage | Colour | Meaning |
|-------|--------|---------|
| < 70% | Grey | Normal |
| 70–84% | Yellow | Approaching limit |
| ≥ 85% | Red | Compaction imminent |

A `⚠` symbol also appears in the status bar at 85%+.

### Auto-compaction

At the start of each agent turn, if `current_tokens / context_window ≥ 0.85`, the Agent automatically compacts the context before making any API call:

```
[context compacted — 12 messages dropped to free space]
```

Compaction drops the oldest 40% of messages (keeping at least 2) and resets `current_tokens` to 0. The first API call after compaction will report the true new size.

### `Context#compact_messages!`

```ruby
dropped = context.compact_messages!(target_fraction: 0.60)
# => 12  (number of messages dropped)
```

### `/compact` command

Manual compaction from the REPL or TUI:

```
boukensha> /compact
(compacted context — 12 messages dropped)
```

### `Logger#compaction` event

```json
{"phase":"compaction","before":172000,"dropped":12,"context_window":200000}
```

Emitted whenever auto- or manual compaction runs. The TUI subscribes to this event to display the compaction notice in the conversation view.

### `Boukensha.run` / `Boukensha.repl` — `context_window:` keyword

`token_budget:` is replaced by `context_window:` (default `200_000`):

```ruby
Boukensha.repl(context_window: 128_000)  # for a smaller model
```

### `Boukensha::Tools::Mcp` (carried forward from step 11)

This step now tracks step 11's `Tools::Mcp` refactor (it originally forked
from the pre-refactor `Tools::Mud`, which registered MUD gameplay tools
directly in-process against a live CircleMUD connection).
`Tools::Mcp.register(registry, servers:)` is the generic bridge to any
number of configured MCP servers — for the MUD case, that's
`mud_manager`'s own bundled MCP server, spawned as a subprocess and proxied
tool-for-tool into the registry — rather than a hand-registered,
MUD-specific tool set living directly in this process.

Config moved with it: `settings.yaml`'s `mud:` block is gone, replaced by an
`mcp_servers:` list (`config.mcp_servers`), and `Boukensha.run`/`.repl` take
`mcp:` instead of `mud:`. `mud_manager` bumped to `~> 0.3` accordingly. See
step 10/11's README for the full `mcp_servers:` config shape and
`Tools::Mcp`'s collision-handling/`prefix:` behavior — this step didn't
change any of that, just adopted it (context-window tracking and
compaction, above, are this step's own addition on top).

## Run the demo

gem uninstall boukensha

gem build boukensha.gemspec
gem install boukensha-0.12.0.gem

```sh
ruby examples/example.rb

# via the global executable:
BOUKENSHA_DIR=~/Sites/Claude-Code-Camp/.boukensha BOUKENSHA_PATH=~/Sites/Claude-Code-Camp/week1_baseline/12_context boukensha
