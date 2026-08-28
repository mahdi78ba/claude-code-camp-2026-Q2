# What "context" means here, why it matters, and how `boukensha` manages it

A simple explainer of the concept, then a technical walkthrough of how
`ruby/12_context` (and its Python port, `python/12_context`) actually
implement it — written to be readable without having read either
implementation first.

## What "context" means for an LLM agent

Every time `boukensha` calls the model, it doesn't send just the newest
message — it sends the **entire conversation so far**: the system prompt,
every user message, every assistant reply, every tool call and its
result, plus the full list of tool definitions the agent is allowed to
use. That whole bundle is called the **prompt**, and the model reads it
token by token before it can answer.

**The context window is the hard ceiling on how many tokens that bundle
can contain.** It's a property of the *model*, not something you tune —
`claude-haiku-4-5` currently accepts up to 200,000 tokens of input, full
stop. If the conversation history plus tool results plus tool
definitions ever exceeds that number, the API call fails outright — the
model literally cannot read a prompt longer than its window, no matter
how important the content is.

An agent like `boukensha` makes this worse than a normal chat, because
**every tool call adds to the history permanently**: a `look` command's
full room description, a file read's entire contents, a shell command's
output — all of it becomes part of every future prompt in that
conversation, forever, unless something actively prunes it. A
long-running MUD session or a multi-step coding task can realistically
generate tens of thousands of tokens of tool output in a single sitting.

## Why this needed its own step

Before `ruby/12_context` existed, `boukensha` had **no concept of the
context window at all** — it tracked a completely different number
(`token_budget`, defaulting to `8,192`) and displayed *that* as if it were
the usage ceiling. Two real bugs followed directly from that confusion
(both fixed in this step, per `ruby/12_context/README.md`):

1. `token_budget` (`8,192`) is actually `max_output_tokens` — a limit on
   how long *one reply* can be, completely unrelated to how much *input*
   the model can accept. Displaying it as "the limit" told the user the
   wrong ceiling entirely.
2. The number shown as "tokens used" was a **cumulative sum across the
   whole session** that only ever grew, even after `/clear` wiped the
   conversation — so a long session's display would eventually read
   "150,000 tokens used" while the actual next prompt might be a few
   hundred tokens, because the old messages were long gone but the
   counter never was.

Neither bug crashed anything by itself, but together they meant the one
number a user could see to judge "am I about to hit a wall?" was
answering a completely different question. Step 12 replaces it with a
number that's actually true, plus automatic action taken *before* the
real wall is hit.

## The three numbers, and why they're not the same thing

This is the single most important distinction in this step's design —
easy to conflate, since all three are "tokens":

| Name | What it actually measures | Who resets it, and when |
|---|---|---|
| `context_window` | The model's fixed input ceiling (a *fact about the model*, e.g. `200,000`) | Never — it's a constant for a given model |
| `current_tokens` | The `input_tokens` from the **most recent** API response — i.e. "what the *next* call will send" | Set after every response; reset to `0` by compaction or `/clear` |
| `turn_tokens` | The **cumulative** input+output tokens spent so far *this turn* (a spend budget, for `max_turn_tokens`) | Reset to `0` at the start of every turn |

`current_tokens / context_window` is the number that actually answers
"how full is the window right now" — that's `usage_fraction`/`usage_pct`.
`turn_tokens` answers a different question entirely ("has this single
turn spent too much, regardless of window pressure") and exists purely as
a separate circuit breaker, the same conceptual role `max_iterations`
already played for tool-call count.

## How it's technically handled

### 1. `Context` carries the state

Ruby (`lib/boukensha/context.rb`) and Python (`boukensha/context.py`)
both extend the existing message-list object with:

```ruby
# ruby/12_context/lib/boukensha/context.rb
def initialize(system:, context_window: 200_000, working_dir: nil, compaction_threshold: 0.85)
  @context_window       = context_window
  @compaction_threshold = compaction_threshold
  @current_tokens       = 0
  @turn_tokens          = 0
  ...
end

def usage_fraction
  @context_window > 0 ? @current_tokens.to_f / @context_window : 0.0
end

def needs_compaction?(threshold: compaction_threshold)
  usage_fraction >= threshold
end

def compact_messages!(target_fraction: 0.60)
  drop_count = [(@messages.size * 0.40).ceil, @messages.size - 2].min
  drop_count = [drop_count, 0].max
  @messages = @messages.drop(drop_count)
  @current_tokens = 0
  drop_count
end
```

Compaction is deliberately simple — **drop the oldest 40% of messages,
always keep at least 2** (so there's never a completely empty
conversation) — not a summarization step, not a smart "keep what
matters" heuristic. It trades conversational memory for a hard guarantee:
after compacting, usage is back near `60%` of the window, immediately.

### 2. `Models` answers "how big is this model's window?"

A new, tiny lookup table (`lib/boukensha/models.rb` /
`boukensha/models.py`) — `context_window` is a fact about the model, so
the caller never has to know or configure it by hand:

```ruby
module Boukensha
  module Models
    TABLE = {
      "claude-opus-4-8"   => { context_window: 200_000 },
      "claude-sonnet-4-6" => { context_window: 200_000 },
      "claude-haiku-4-5"  => { context_window: 200_000 },
    }.freeze
    DEFAULT_CONTEXT_WINDOW = 32_000   # unknown model -> conservative default

    def self.context_window(model)
      TABLE.dig(model.to_s, :context_window) || DEFAULT_CONTEXT_WINDOW
    end
  end
end
```

`Boukensha.run`/`.repl` call `Models.context_window(model)` automatically
whenever the caller doesn't pass `context_window:` explicitly.

### 3. `Agent` checks and updates on every turn

Two things happen that didn't before, right in the turn loop
(`lib/boukensha/agent.rb`):

```ruby
def run
  @context.reset_turn_tokens   # fresh spend budget for this turn
  compact_if_needed            # ...checked BEFORE the first API call

  loop do
    return wrap_up("max_tokens") if token_limit_reached?   # new circuit breaker
    ...
    response = @client.call(**call_opts)
    ...
    record_usage(response)     # updates BOTH current_tokens and turn_tokens
    ...
  end
end

def record_usage(response)
  usage = response["usage"] || {}
  @context.add_turn_tokens(usage["input_tokens"], usage["output_tokens"])
  @context.update_tokens(usage["input_tokens"])
end

def compact_if_needed
  return unless @context.needs_compaction?
  before  = @context.current_tokens
  dropped = @context.compact_messages!
  @logger.compaction(before: before, dropped: dropped, context_window: @context.context_window)
end
```

The compaction check runs **at the start of the turn, before any API
call** — so a conversation that crossed the threshold on its *previous*
turn gets trimmed before it can ever actually overflow the window on this
one. `record_usage` runs after **every** response, including mid-turn
tool-use responses, not just the turn's final answer — so the display
always reflects what the very next call will send, not what was true
several tool calls ago.

### 4. The REPL and TUI surface it

`/compact` (`lib/boukensha/repl.rb`) does exactly what the automatic path
does, on demand:

```
boukensha> /compact
(compacted context — 12 messages dropped)
```

The TUI (`lib/boukensha/tui.rb` / `boukensha/tui.py`) shows
`current_tokens`/`context_window` live, colour-coded, and reacts to the
new `"compaction"` log event by writing a line straight into the
conversation view — whether compaction happened automatically or by hand
makes no difference to what the user sees:

```
[context compacted — 12 messages dropped to free space]
```

| Usage | Colour | Meaning |
|---|---|---|
| `< 70%` | grey | normal |
| `70–84%` | yellow | approaching limit |
| `>= 85%` | red, `⚠` shown | compaction imminent / already triggered |

## A real, captured example

This is genuine output from live sessions run against this repo (both
languages), not a mocked transcript — see
`docs/week1_config_troubleshooting.md` entries #44 and #45–46 for the
full verification logs.

**Normal growth, across two real turns**, `ruby/12_context` TUI:

```
[ready]   ctx 0 / 200.0k (0%)   0 turns          # boot
...agent connects to the MUD, looks around, checks score, checks exits...
[ready]   ctx 4.6k / 200.0k (2%)   1 turns        # after turn 1
...second message...
[ready]   ctx 4.9k / 200.0k (2%)   2 turns        # after turn 2 — grew, didn't reset
```

**Manual `/compact`**, same session:

```
boukensha> /compact
(compacted context — 5 messages dropped)
[ready]   ctx 0 / 200.0k (0%)   2 turns           # usage reset; turn count untouched
```

**Automatic compaction firing on its own** — proven with a deliberately
tiny `context_window: 2000` (the real mechanism, just a smaller number,
so it's cheap and fast to trigger on purpose instead of needing a real
200k-token conversation):

```
> Say hi in one word.
  [ready]   ctx 3.8k / 2.0k (190%)  ⚠            # already over threshold
> Say bye in one word.
[context compacted — 1 messages dropped to free space]   # <- nobody typed /compact
  [ready]   ctx 3.8k / 2.0k (191%)   2 turns
```

Note the second `[ready]` line still reads `191%` — compaction ran at the
very *start* of that turn (based on the *previous* turn's leftover
`current_tokens`), then the turn's own response pushed usage straight
back over the threshold again immediately, since the window is
artificially tiny here. Against a real `200_000`-token window this
oscillation isn't visible — one compaction reliably buys a huge amount of
headroom.

## Schema

### `Context`'s shape (both languages, field-for-field)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `context_window` | integer | `200_000` | Model's input ceiling |
| `compaction_threshold` | float | `0.85` | Trigger point, as a fraction of `context_window` |
| `current_tokens` | integer | `0` | Last response's `input_tokens`; the window-pressure signal |
| `turn_tokens` | integer | `0` | Cumulative input+output spent this turn; reset every turn |
| `usage_fraction` | float, derived | — | `current_tokens / context_window` |
| `usage_pct` | integer, derived | — | `round(usage_fraction * 100)` |

### The two structured log events (`Logger`, JSON Lines)

Every agent run writes one JSON object per line to
`~/.boukensha/sessions/<id>.jsonl` (or `~/.boukensha/sessions/*.jsonl` in
Python). These are the two shapes this step added or changed, as JSON
Schema:

```json
{
  "$id": "prompt-event",
  "type": "object",
  "properties": {
    "phase":           { "const": "prompt" },
    "message_count":   { "type": "integer" },
    "messages":        { "type": "array", "items": { "type": "object" } },
    "tool_count":      { "type": "integer" },
    "tools":           { "type": "array", "items": { "type": "string" } },
    "context_window":  { "type": "integer", "description": "new in step 12" },
    "session_id":      { "type": "string" },
    "at":              { "type": "string", "format": "date-time" }
  },
  "required": ["phase", "message_count", "tool_count", "context_window", "session_id", "at"]
}
```

```json
{
  "$id": "compaction-event",
  "type": "object",
  "description": "New in step 12. Emitted whenever auto- or manual compaction runs.",
  "properties": {
    "phase":           { "const": "compaction" },
    "before":          { "type": "integer", "description": "current_tokens immediately before compacting" },
    "dropped":         { "type": "integer", "description": "number of messages removed" },
    "context_window":  { "type": "integer" },
    "session_id":      { "type": "string" },
    "at":              { "type": "string", "format": "date-time" }
  },
  "required": ["phase", "before", "dropped", "context_window", "session_id", "at"]
}
```

A real `"compaction"` line, exactly as written by the code (from this
session's own verification run):

```json
{"phase": "compaction", "before": 1900, "dropped": 1, "context_window": 2000, "session_id": "...", "at": "2026-08-28T..."}
```

### `settings.yaml`'s `agent:` block

The two knobs a user can actually configure (everything else in the
table above is either a model fact or runtime-computed state, not
something you set):

```yaml
agent:
  max_turn_tokens: 60000          # 0 disables the per-turn spend ceiling
  compaction_threshold: 0.85      # fraction of context_window that triggers auto-compaction
```

## Ruby vs. Python, at a glance

| Concept | Ruby | Python |
|---|---|---|
| Per-model window lookup | `Boukensha::Models.context_window(model)` | `boukensha.models.context_window(model)` |
| Compaction | `Context#compact_messages!` (bang, Ruby convention) | `Context.compact_messages()` (no bang — not a Python convention) |
| Threshold check | `Context#needs_compaction?` | `Context.needs_compaction()` |
| Cross-backend token extraction for tracking | Anthropic-only (`response["usage"]["input_tokens"]`) — `ruby/12_context`'s own `Logger`/`Agent` dropped the multi-backend normalization `ruby/11_tui` had (an unrelated, pre-existing simplification — not this step's actual content) | Reuses the existing multi-backend `Logger._usage_tokens` (kept, not dropped — see `docs/plans/python_port/12_context.md`'s scoping decision), so tracking works across every backend Python already supports logging for, not just Anthropic |
| Where it's wired up | `Boukensha.run`/`.repl` (`lib/boukensha.rb`) | `run()`/`repl()` (`boukensha/__init__.py`) |

## One real gotcha worth knowing

`current_tokens` only ever reflects the **last** response's input size —
right after a `/clear` or a compaction, it reads `0`, even though the
system prompt and tool definitions alone are already a real, nonzero
number of tokens. It isn't lying: `0` genuinely means "we haven't made a
call since the reset, so we don't yet know the true size of the next
prompt" — the display catches up the moment the next response comes back.
Don't read a freshly-compacted `0%` as "the conversation is empty";
read it as "we don't have a fresh measurement yet."
