# Practical Guide — Seeing It Run: TUI, REPL, log_viz, Testing Each Component, and Multi-Agent

Every other week-1 doc explains *how the code works*. This one is the
opposite: **concrete commands to actually run, what you'll see on screen,
and how to test a piece in isolation** — from "watch the full TUI play a
MUD" down to "dispatch one tool with no API key and no network at all."
Every command/snippet below was actually run against the current code in
this repo (`ruby/12_context` / `python/12_context`) while writing this doc,
not guessed from reading source.

---

## 0. Prerequisites — the 60-second checklist

| Need | Where it comes from | Check it |
|---|---|---|
| An API key | `.boukensha/.env` — `ANTHROPIC_API_KEY=...` (or `OPENAI_API_KEY`/`GEMINI_API_KEY`/`OLLAMA_API_KEY`, matching whichever `provider:`/`model:` is set) | `grep API_KEY .boukensha/.env` |
| Model/provider/limits | `.boukensha/settings.yaml` — `agent:` block and (if you want the MUD tools) `mcp_servers:` | `cat .boukensha/settings.yaml` |
| A running MUD (only if you want `mud_*` tools to actually connect) | `docker compose up` from `week0_explore/infrastructure/` — starts CircleMUD on `localhost:4000` | `docker ps \| grep circlemud` |
| Ruby / Python installed | See [`week1_config_troubleshooting.md`](week1_config_troubleshooting.md) if not | `ruby -v`, `python3 -V` |

`BOUKENSHA_DIR` (which config folder to read) defaults to `~/.boukensha`;
every example script in this repo overrides it to point at this repo's own
`.boukensha/` instead, so you don't need to set it yourself unless you
want a different config.

**You do not need the MUD running, or even a valid API key,** for §4
below (testing components offline) — only for actually watching the agent
play.

---

## 1. The three things you can actually look at

### 1a. The plain REPL — text only, works everywhere

```sh
# Ruby — build+install the gem once (from week1_baseline/ruby/12_context):
#   gem build boukensha.gemspec && gem install boukensha-0.12.0.gem
# then, from the repo root, run it pointed at this step's code:
BOUKENSHA_DIR=$(pwd)/.boukensha BOUKENSHA_PATH=$(pwd)/week1_baseline/ruby/12_context boukensha --no-tui

# Python
./week1_baseline/bin/python/12_context --no-tui
```

You get a bare prompt:

```
boukensha> look
[tool_call: mud_look]
You are standing in the town square...
boukensha> /help
boukensha> /exit
```

This is the same `Repl` object underneath in both languages — same
transcript, same slash commands (`/help`, `/clear`, `/compact`, `/quiet`,
`/loud`, `/exit`/`/quit`), same tool calls — just without a redrawing
screen. Good for scripting, `tmux` panes, or anywhere a full TUI is
awkward.

### 1b. The TUI — a real, persistent screen

```sh
# Ruby — TUI is the default (tui: true), no flag needed
BOUKENSHA_DIR=$(pwd)/.boukensha BOUKENSHA_PATH=$(pwd)/week1_baseline/ruby/12_context boukensha

# Python — TUI is the default here too
./week1_baseline/bin/python/12_context
```

Four zones, top to bottom (both languages target this same layout — see
[`week1_tui_explained.md`](week1_tui_explained.md) for *why* it's these
four zones):

```
┌──────────────────────────────────────────────┐
│  conversation viewport (scrollable)           │
├──────────────────────────────────────────────┤
│  ⟳ live progress line (hidden when idle)     │  ← updates while a tool runs
├──────────────────────────────────────────────┤
│  boukensha> input box                         │
├──────────────────────────────────────────────┤
│  v0.12.0 · claude-haiku-4-5 · 3,377/200,000 tok · 30 tools · 00:04:12 │
└──────────────────────────────────────────────┘
```

Keyboard shortcuts:

| Key | Ruby TUI | Python TUI |
|---|---|---|
| `Enter` | Submit input/command | Submit input/command |
| `Esc` | **Interrupt the running turn** | not available (see below) |
| `Ctrl+L` | Clear conversation | Clear conversation |
| `PgUp`/`PgDn` | Scroll conversation | Scroll conversation |
| `Ctrl+C` / `Ctrl+D` | Quit | Quit |

The one real gap between the two: Ruby's TUI can cancel a turn mid-flight
with `Esc` (Ruby's `Thread#raise` can safely interrupt another thread);
Python has no equally safe way to inject an exception into a running
thread, so that keybinding simply doesn't exist there — `Ctrl+C` quits the
whole app instead of just the turn.

**Prefer the TUI for actually watching the agent work** — the progress
line shows `Calling tool: move` / `Awaiting result…` live, and the status
line's token counter changes color (grey → yellow at 70% → red at 85%,
`⚠`) the instant a response comes back, so you see context pressure and
auto-compaction happen in real time instead of after the fact.

### 1c. `log_viz` — a browser UI for *past* runs

Unlike the TUI (live, one session), `log_viz` is a small local web app
that reads every `.jsonl` file under `.boukensha/sessions/` and renders
them as a browsable, chat-style transcript — the practical way to review a
session after it's over, share what happened, or compare two runs.

```sh
cd week1_baseline/ruby/log_viz
bundle install
bundle exec ruby bin/log_viz
```

Then open **<http://localhost:4567>** in a browser:

- `/` — every session logged so far: start time, session id, task,
  provider/model mix, iteration count, token totals, cost.
- `/sessions/:id` — one session as a full transcript: the user's task,
  each assistant reply (with per-call token/cost), each `tool_call` +
  `tool_result` pair grouped by iteration, and raw MUD ANSI color codes
  rendered as real color (so a room description looks the way it would in
  a terminal).

It only *reads* the log files — nothing it does can affect a live run, and
because the log format itself is language-agnostic, a session produced by
the **Python** port renders exactly the same way — no `log_viz` changes
needed. Point it at a different sessions folder with
`LOG_VIZ_SESSIONS_DIR=/path/to/sessions bundle exec ruby bin/log_viz`.

---

## 2. Running (and smoke-testing) each numbered iteration standalone

Every iteration `00`–`12` is runnable on its own — useful for confirming
one specific piece works before assuming the problem is somewhere else.
Ruby and Python both ship `week1_baseline/bin/<lang>/<NN_name>` wrapper
scripts that `cd` into the right folder and run that step's own
`examples/example.rb` (or `.py`) — the whole content of one, verbatim:

```sh
#!/usr/bin/env bash
cd "$(dirname "$0")/../../ruby/05_agent_loop"
bundle exec ruby examples/example.rb
```

**There is also a `bin/` at the repo root** (`claude-code-camp-2026-Q2/bin/`,
one level above `week1_baseline/`) — but it is *not* a full mirror of these
per-step wrappers. It currently has exactly one entry, `bin/00_config`, and
that one runs Ruby's `00_config` example **inside a Docker container**
(`docker run ... ruby:3.3 ...`) rather than a local Ruby install — a
leftover from a machine that had no local Ruby toolchain (see
[`week1_config_troubleshooting.md`](week1_config_troubleshooting.md) for
that whole saga). `bin/python/00_config` at the repo root does the same for
Python, locally (no Docker). **For every other step, run the wrapper
directly from `week1_baseline/bin/<lang>/<NN_name>`** — that's the table
below.

| Step | Ruby command | Python command | Hits the live API? | Needs MUD running? |
|---|---|---|---|---|
| 00 Config | `bin/00_config` (repo root, Docker) or `cd week1_baseline/ruby/00_config && bundle exec ruby examples/example.rb` | `week1_baseline/bin/python/00_config` | No | No |
| 01 Struct Skeleton | `week1_baseline/bin/ruby/01_struct_skeleton` | `week1_baseline/bin/python/01_struct_skeleton` | No | No |
| 02 Registry | `week1_baseline/bin/ruby/02_the_registry` | `week1_baseline/bin/python/02_the_registry` | No | No |
| 03 Prompt Builder | `week1_baseline/bin/ruby/03_prompt_builder` | `week1_baseline/bin/python/03_prompt_builder` | No (builds a payload, doesn't send it) | No |
| 04 API Client | `week1_baseline/bin/ruby/04_api_client` | `week1_baseline/bin/python/04_api_client` | **Yes** | No |
| 05 Agent Loop | `week1_baseline/bin/ruby/05_agent_loop` | `week1_baseline/bin/python/05_agent_loop` | **Yes** | No |
| 06 Logger | `week1_baseline/bin/ruby/06_the_logger` | `week1_baseline/bin/python/06_the_logger` | **Yes** | No |
| 07 Run DSL | `week1_baseline/bin/ruby/07_the_run_dsl` | `week1_baseline/bin/python/07_the_run_dsl` | **Yes** | No |
| 08 REPL Loop | `week1_baseline/bin/ruby/08_the_repl_loop` | `week1_baseline/bin/python/08_the_repl_loop` | **Yes** | No |
| 09 Global Executable | `week1_baseline/bin/ruby/09_global_executable` *(Ruby only)* | *(no Python equivalent — see the journal)* | **Yes** | No |
| 10 Standard Tool Library | *(run manually — see below)* | `week1_baseline/bin/python/10_standard_tool_library` | **Yes** | **Yes** (MUD demo) |
| 11 TUI | *(run manually — see below)* | `week1_baseline/bin/python/11_tui` | **Yes** | **Yes** |
| 12 Context | *(run manually — see below)* | `week1_baseline/bin/python/12_context [--no-tui]` | **Yes** | **Yes** |

**A real gap worth knowing, not a mistake in this table:** `bin/ruby/`
only goes up to `09_global_executable` — there's no `bin/ruby/10`, `/11`,
`/12` wrapper. For Ruby's later steps, run the example directly instead:

```sh
cd week1_baseline/ruby/10_standard_tool_library && bundle exec ruby examples/example.rb
cd week1_baseline/ruby/12_context             && ruby examples/example.rb        # one-shot demo
# or, for the actual REPL/TUI (see §1b) — install the gem once, then:
BOUKENSHA_DIR=$(pwd)/.boukensha BOUKENSHA_PATH=$(pwd)/week1_baseline/ruby/12_context boukensha
```

`ruby/12_context/examples/example.rb` itself is a **one-shot** demo
(`Boukensha.run`, asks the agent one task and exits) — the interactive
REPL/TUI on the Ruby side is only reachable through the installed
`boukensha` gem executable, pointed at whichever step's code you want via
`BOUKENSHA_PATH`. Python instead ships a dedicated `examples/repl.py` per
step from `11_tui` onward, which is what `bin/python/11_tui` and
`bin/python/12_context` actually run.

---

## 3. What you'll see, iteration by iteration (early steps)

A quick sanity check for the earliest steps — what "it worked" looks like,
so you know a wrapper actually ran something real and didn't silently
no-op:

```
$ week1_baseline/bin/ruby/02_the_registry
=== BOUKENSHA Step 2: The Registry ===
Registered tools: ["read_file", "list_directory"]
Dispatching read_file(path: "README.md")...
=> "# Boukensha\n\n..."
Dispatching unknown_tool...
=> Boukensha::UnknownToolError: No tool registered as 'unknown_tool'
```

```
$ week1_baseline/bin/ruby/05_agent_loop
=== BOUKENSHA Step 5: Agent Loop ===
Config: #<Boukensha::Config ...>
Provider: anthropic
Model: claude-haiku-4-5
Max iterations: 25
[iteration 1/25]
  tool call → read_file({"path"=>"README.md"})
  tool result → # The Agent Loop...
[iteration 2/25]
=== FINAL RESPONSE ===
## Summary  ...
```

If a step's wrapper instead prints a stack trace immediately, it's almost
always one of: missing API key (`04` onward), CRLF line endings on the
wrapper script, or a wrong relative path inside it — all three are
entries #1–#3 in
[`week1_config_troubleshooting.md`](week1_config_troubleshooting.md).

---

## 4. Testing a component in isolation — no API key, no network, no MUD

This is the most practical section if you want to change something and
verify it without spending API credits or needing Docker running. Drive
the real objects directly from a one-liner or an interactive shell
(`irb`/`python3 -i`). **Both snippets below were actually executed against
this repo's current code to write this doc** — copy-paste them as-is.

### 4a. `Registry` + `Context` + `Tool` dispatch — Ruby

```sh
cd week1_baseline/ruby/12_context
ruby -Ilib -e '
require "boukensha/context"
require "boukensha/registry"
require "boukensha/errors"

ctx = Boukensha::Context.new(system: "test", context_window: 200_000)
registry = Boukensha::Registry.new(ctx)

registry.tool("add", description: "Add two numbers", parameters: {
  a: { type: "integer" }, b: { type: "integer" }
}) { |a:, b:| a + b }

puts "Registered tools: #{ctx.tools.keys}"
puts "Dispatch add(2,3) => #{registry.dispatch("add", {"a"=>2,"b"=>3})}"
begin
  registry.dispatch("nope", {})
rescue => e
  puts "Unknown tool raised: #{e.class}: #{e.message}"
end
'
```

Output (verified):
```
Registered tools: ["add"]
Dispatch add(2,3) => 5
Unknown tool raised: Boukensha::UnknownToolError: No tool registered as 'nope'
```

### 4b. The same test — Python

```sh
cd week1_baseline/python/12_context
python3 -c '
import sys; sys.path.insert(0, ".")
from boukensha.context import Context
from boukensha.registry import Registry

ctx = Context(task=None, system="test", context_window=200_000)
registry = Registry(ctx)

registry.tool("add", description="Add two numbers",
              parameters={"a": {"type": "integer"}, "b": {"type": "integer"}},
              block=lambda a, b: a + b)

print("Registered tools:", list(ctx.tools.keys()))
print("Dispatch add(2,3) =>", registry.dispatch("add", {"a": 2, "b": 3}))
try:
    registry.dispatch("nope", {})
except Exception as e:
    print(f"Unknown tool raised: {type(e).__name__}: {e}")
'
```

Output (verified):
```
Registered tools: ['add']
Dispatch add(2,3) => 5
Unknown tool raised: UnknownToolError: No tool registered as 'nope'
```

**One real, verified divergence worth knowing if you try this yourself:**
Python's `Context(...)` still requires a `task=` keyword argument (pass
`None` if you don't have one, as above); Ruby's `Context.new(...)` (as of
this same `12_context` step) takes no `task:` at all — the whole
`Tasks::Player` class was removed on the Ruby side and its settings
(`max_iterations` etc.) moved to a flat `agent:` config block (see
[`week1_agent_loop_explained.md`](week1_agent_loop_explained.md#6-max_iterations-max_turn_tokens-and-what-stop-really-means)),
while the Python port still resolves per-task settings through
`context.task`. Neither is wrong — they're just at different points of the
same refactor — but it means a `Context.new` snippet copied from Ruby
needs `task=None` added to run unmodified in Python.

### 4c. `PromptBuilder` — see the exact JSON sent to the provider, without sending it

Useful for checking "did my tool/message actually get shaped correctly"
before ever making a real HTTP call:

```sh
cd week1_baseline/ruby/12_context
ruby -Ilib -e '
require "boukensha/context"
require "boukensha/registry"
require "boukensha/prompt_builder"
require "boukensha/backends/anthropic"
require "json"

ctx = Boukensha::Context.new(system: "You are a test agent.", context_window: 200_000)
registry = Boukensha::Registry.new(ctx)
registry.tool("ping", description: "Ping", parameters: {}) { "pong" }
ctx.add_message(:user, "hello")

backend = Boukensha::Backends::Anthropic.new(api_key: "fake-key-not-sent", model: "claude-haiku-4-5")
builder = Boukensha::PromptBuilder.new(ctx, backend)

puts JSON.pretty_generate(builder.to_api_payload)
'
```

Output (verified — this is the *real* payload shape Anthropic receives,
built entirely offline):
```json
{
  "model": "claude-haiku-4-5",
  "system": "You are a test agent.",
  "max_tokens": 1024,
  "tools": [
    { "name": "ping", "description": "Ping",
      "input_schema": { "type": "object", "properties": {}, "required": [] } }
  ],
  "messages": [ { "role": "user", "content": "hello" } ]
}
```

The fake API key is never used — `to_api_payload` only *builds* the
request; nothing here opens a socket. Swap `Backends::Anthropic` for
`Backends::OpenAI`/`Gemini`/`Ollama`/`OllamaCloud` to see the same
`Context` translated into each provider's own wire shape side by side —
exactly the comparison table in
[`week1_agent_loop_architecture.md`](week1_agent_loop_architecture.md) §4,
now reproducible yourself in under 10 lines.

### 4d. Testing an MCP server directly — bypass Boukensha entirely

An MCP server is just a subprocess that speaks JSON-RPC over stdio (see
[`week1_mcp_servers_and_agent_components_explained.md`](week1_mcp_servers_and_agent_components_explained.md) §1)
— you can talk to it by hand, with no Boukensha code involved at all, to
confirm the server itself works before wiring it into an agent:

```sh
printf '%s\n%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual-test","version":"1.0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | mud_manager --mcp
```

You should get back one JSON object per line: an `initialize` result
(server name/version), then a `tools/list` result listing all 27 tools
(`mud_connect`, `look`, `move`, ... — the full list is in
[`week1_mcp_servers_and_agent_components_explained.md`](week1_mcp_servers_and_agent_components_explained.md) §4).
This works even **without** a MUD running or connected — listing tools
doesn't require a live game connection, only *calling* `mud_connect`
would. Swap `mud_manager --mcp` for any other server's launch command to
smoke-test it the same way before adding it to `settings.yaml`.

---

## 5. Watching a run live, from the log instead of the screen

If you'd rather watch structured events than a rendered UI (e.g. over SSH,
or piping into `jq`), tail the session file directly while a run is in
progress:

```sh
tail -f "$(ls -t .boukensha/sessions | head -1 | xargs -I{} echo .boukensha/sessions/{})"
# or, once you know it's the newest file:
tail -f .boukensha/sessions/*.jsonl | tail -1
```

Pretty-print each line as it arrives:

```sh
tail -f .boukensha/sessions/<session-id>.jsonl | while read -r line; do
  echo "$line" | python3 -m json.tool --compact 2>/dev/null || echo "$line"
done
```

Every event's `phase` field (`iteration`, `tool_call`, `tool_result`,
`response`, `turn_end`, ...) and what it means is the full table in
[`week1_agent_loop_explained.md`](week1_agent_loop_explained.md#b-the-session-log--one-json-object-per-line-forever).

---

## 6. Agent vs. "subagent" — what actually exists here

Straight answer: **`week1_baseline` has no subagent / multi-agent
orchestration feature.** `Agent`, `Registry`, `Context`, etc. describe
exactly **one** agent, running one loop, in one process. Searching the
whole `week1_baseline` tree for "subagent" (or any spelling of it) returns
**zero** matches — the only place that word appears in this repo at all is
week **0**'s docs (`explore_architectures.md`, `week0_journal.md`), which
used a completely different codebase: Claude Code's own Agent SDK, driving
two *existing* Claude agents (`dummy` the Warrior, `Smarty` the Mage) in
parallel, each with independent memory. That's a different tool built on a
different SDK — not something `Boukensha` (this week's framework) has, or
was trying to reproduce.

**The closest practical analog you can actually do with `Boukensha`:**
since CircleMUD is a real multiplayer server, nothing stops you from
running **two independent `boukensha` processes** at once, each with its
own character/session — not one agent orchestrating a sub-agent, just two
separate agents that happen to be logged into the same world simultaneously:

```sh
# terminal 1
MUD_NAME=dummy  BOUKENSHA_DIR=$(pwd)/.boukensha BOUKENSHA_PATH=$(pwd)/week1_baseline/ruby/12_context boukensha
# terminal 2
MUD_NAME=smarty BOUKENSHA_DIR=$(pwd)/.boukensha BOUKENSHA_PATH=$(pwd)/week1_baseline/ruby/12_context boukensha
```

Each gets its own `Context`, its own session log, its own `log_viz` entry
— there's no coordination between them, no shared memory, no one agent
calling the other as a tool. If you actually want real sub-agent
orchestration (one agent spawning/dispatching others, shared or per-agent
memory, a supervising loop), that's the pattern week 0 explored — see
[`explore_architectures.md`](explore_architectures.md) and
[`week0_journal.md`](week0_journal.md) — and would be new work on top of
`Boukensha`, not something to go looking for inside `week1_baseline` as it
stands today.

---

## 7. Cheat sheet

```
plain REPL (ruby)     →  boukensha --no-tui           (BOUKENSHA_DIR / BOUKENSHA_PATH set)
TUI (ruby, default)   →  boukensha
plain REPL (python)   →  ./week1_baseline/bin/python/12_context --no-tui
TUI (python, default) →  ./week1_baseline/bin/python/12_context
past sessions, browser→  cd week1_baseline/ruby/log_viz && bundle exec ruby bin/log_viz   → http://localhost:4567
run one iteration     →  week1_baseline/bin/<ruby|python>/<NN_name>   (see §2's table for exceptions)
test Registry offline →  §4a/4b — no API key, no network
test PromptBuilder    →  §4c — builds the real payload, sends nothing
test an MCP server    →  §4d — raw JSON-RPC over stdio, no Boukensha code
watch a run live       →  tail -f .boukensha/sessions/<id>.jsonl
"subagents"            →  not a week1_baseline feature — see §6
```

---

## Go deeper

- [`week1_config_troubleshooting.md`](week1_config_troubleshooting.md) —
  every environment/setup problem hit this week, Problem → Fix → Why.
- [`week1_agent_loop_explained.md`](week1_agent_loop_explained.md) — the
  loop these commands actually run, and the full session-log event table.
- [`week1_mcp_servers_and_agent_components_explained.md`](week1_mcp_servers_and_agent_components_explained.md) —
  what an MCP server is, how many we run, how to add one.
- [`week1_tui_explained.md`](week1_tui_explained.md) — the concept behind
  the TUI shown in §1b (Elm Architecture, Bubble Tea vs. Textual).
- [`week1_journal.md`](week1_journal.md) — the full guide this doc is one
  entry in.
