# Week 1 Journal — Building an Agent Framework From Scratch, Twice

## Technical Goal

Week 0 was about getting an *existing* agent (Claude Code / the Agent SDK) to
play a MUD. Week 1 flips the question: **build the agent itself**, from raw
HTTP calls up to a full terminal app, with no Agent SDK involved anywhere.
The project is called **Boukensha** ("adventurer" in Japanese — fitting,
since its example task is still playing a MUD). It's built twice, in
parallel, as two independent implementations of the same design:

- **`week1_baseline/ruby/`** — the reference implementation, built first.
- **`week1_baseline/python/`** — a port of the same design, iteration by
  iteration, with its own review pass every time (not a blind translation).

Both are organized as **13 numbered iterations** (`00_config` →
`12_context`), each one a self-contained folder you can `cd` into and run,
that layer on top of the previous one. This journal is a guide to that whole
build: what each iteration is, in plain terms, plus a pointer to the specific
`.md` file(s) that go deeper if you want more than the summary here.

## How to read this journal

- Each numbered iteration below gets: **what it is** (one paragraph, no
  jargon), **the schema** (the data/config shape it introduces), and
  **where to go deeper** (the README(s) and any docs/ write-ups).
- Three topics — **MCP (tool integration with the MUD)**, **the Terminal
  UI**, and **Context management** — each got enough dedicated work to
  deserve their own section instead of being squeezed into one iteration's
  entry.
- The very end has a **full index**: every `.md` file this week produced,
  in one table, so nothing is orphaned.
- If you only read one extra doc after this journal, read
  [`week1_components_explained.md`](week1_components_explained.md) — it's
  the "how the pieces fit together" map with no code, and everything below
  assumes you roughly know that map.

---

## The big picture, before the numbers

Every iteration adds one layer. By the end (`12_context`), a single call
looks like this:

```
you type a message
        │
        ▼
   Context  ── remembers the conversation, the tools, the system prompt
        │
        ▼
   Registry ── the tool phonebook: register a tool once, dispatch it by name
        │
        ▼
PromptBuilder ── translates Context into whichever provider's JSON shape
        │              (Anthropic / OpenAI / Gemini / Ollama / Ollama Cloud)
        ▼
   Backend  ── owns that provider's wire format + model table + pricing
        │
        ▼
   Client   ── the actual HTTP POST, with retries
        │
        ▼
   Agent    ── the loop: call → tool_use? → dispatch via Registry → call again
        │           → end_turn? → done, save reply to Context
        ▼
   Logger   ── writes every phase to a .jsonl file (never to your screen)
        │
        ▼
  Repl / Tui ── the thing you actually see: prompt, banner, live progress
```

**The one idea to hold onto:** `Context` is the only object that survives
between turns. Everything else (`Agent`, `Client`, `Backend`) is cheap and
disposable — rebuilt fresh, or reused stateless, every call. That's the
entire mechanism behind "the REPL remembers what I said three questions
ago." Full walkthrough, no code:
[`week1_components_explained.md`](week1_components_explained.md).

---

## The iterations, one by one

### 00 · Configuration — *where do settings live?*

**Simple explanation:** before anything else can exist, the framework needs
to know which model to use, what API key to use, and what the agent's job
is. This step builds a `Config` class that reads a `~/.boukensha/` folder
(or a `BOUKENSHA_DIR` you point at instead) and answers those questions.

**Schema — `.boukensha/` directory:**
```
.boukensha/
  .env                 # secrets (API keys) — never committed
  settings.yaml         # everything else
  prompts/<task>/system.md   # optional per-task system prompt override
```
```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
mud:
  host: localhost
  port: 4000
```
Settings are organized by **task** — a role in the loop bound to its own
model. Only one task (`player`) exists in week1_baseline, but the shape
already supports more.

**Go deeper:** `ruby/00_config/README.md`, `python/00_config/README.md`.

---

### 01 · Struct Skeleton — *the three shapes everything else passes around*

**Simple explanation:** three plain data records that every later iteration
reuses without changing: a **Tool** (a capability + its description), a
**Message** (one line of conversation), and a **Context** (the whole bundle
— system prompt, messages, tools — needed to make one API call).

**Schema:**

| Struct | Fields | Plain description |
|---|---|---|
| `Tool` | `name`, `description`, `parameters`, `block` | A capability. `description` is the *only* thing the model ever sees. |
| `Message` | `role`, `content`, `tool_use_id` | One line of the transcript. `tool_use_id` pairs a tool's result back to the call that asked for it. |
| `Context` | `system`, `messages`, `tools`, `token_budget` | Everything needed for one API call. Nothing lives outside it. |

Ruby uses `Struct` (lightweight, readable); Python uses `@dataclass` for
`Tool`/`Message` and a plain class for `Context` (it holds behavior, not
just fields) — the same split Ruby makes.

**Go deeper:** `ruby/01_struct_skeleton/README.md`,
`python/01_struct_skeleton/README.md`,
[`week1_struct_skeleton_review.md`](week1_struct_skeleton_review.md) (code
review of the Ruby structs),
[`week1_struct_skeleton_python_port.md`](week1_struct_skeleton_python_port.md)
(what the Python port did and why).

---

### 02 · The Registry — *the tool phonebook*

**Simple explanation:** the model never calls a tool directly — it can't,
it's just text generation. It emits a *request* ("call `move` with
`direction='north'`"), and the **Registry** is the object that looks that
name up and actually runs the corresponding code.

**Schema — `Registry`:**

| Method | Does |
|---|---|
| `tool(name, description:, parameters:, &block)` | Register a new tool |
| `dispatch(name, args)` | Look up by name, run it, return the result |

Unknown tool name → `UnknownToolError`, raised loudly rather than swallowed
— a harness needs an explicit error boundary here.

**Go deeper:** `ruby/02_the_registry/README.md`,
`python/02_the_registry/README.md`,
[`week1_the_registry_review.md`](week1_the_registry_review.md),
[`week1_the_registry_port_plan.md`](week1_the_registry_port_plan.md).

---

### 03 · The Prompt Builder — *speaking five different dialects*

**Simple explanation:** every LLM provider wants the same information
(system prompt, message history, tool list) in a slightly different JSON
shape. `PromptBuilder` doesn't call anyone — it just translates a `Context`
into whichever shape the chosen **Backend** needs. Five backends exist:
Anthropic, OpenAI, Gemini, Ollama (local), Ollama Cloud.

**Schema — where the five backends actually diverge:**

| Concern | Anthropic / Gemini | OpenAI / Ollama / Ollama Cloud |
|---|---|---|
| System prompt | top-level `system`/`systemInstruction` field | folded into `messages` as a `role: system` entry |
| Tool result | wrapped in a `user` message | dedicated `role: tool` message type |
| Tool schema | `input_schema` | wrapped in a `function` envelope |
| Assistant role name | `assistant` (Anthropic) / `model` (Gemini) | `assistant` |

Each backend also owns its own **model table** — `context_window`,
`cost_per_million`, `usage_unit` — and refuses to construct with an unknown
model name, so a typo in `settings.yaml` fails loudly instead of silently
selecting nothing.

**Go deeper:** `ruby/03_prompt_builder/README.md` (full request/response
JSON examples for all five providers), `python/03_prompt_builder/README.md`,
[`week1_prompt_builder_review.md`](week1_prompt_builder_review.md) (found a
real interface bug in `to_messages`' inconsistent arity across backends),
[`week1_prompt_builder_verification.md`](week1_prompt_builder_verification.md)
(runtime proof, not just code reading),
[`week1_prompt_builder_port_plan.md`](week1_prompt_builder_port_plan.md) /
[`week1_prompt_builder_python_review.md`](week1_prompt_builder_python_review.md).

---

### 04 · The API Client — *proving the round trip*

**Simple explanation:** takes the payload `PromptBuilder` assembled and
actually sends it — one HTTP POST, one response, no tool loop yet. Ruby uses
stdlib `net/http`, Python uses stdlib `urllib.request` — no HTTP libraries,
on purpose, so the call itself stays visible instead of hidden behind a gem.

**Schema — retry behavior:**

| Failure | Behavior |
|---|---|
| Retryable status (408/409/429/500/502/503/504) | retried up to 3× with exponential backoff (0.5s → 1s → 2s) |
| Transient network error | same retry path |
| Any other non-2xx (e.g. 400/401) | raised immediately as `ApiError`, no retry |

**Go deeper:** `ruby/04_api_client/README.md`, `python/04_api_client/README.md`,
[`week1_api_client_review.md`](week1_api_client_review.md),
[`week1_api_client_python_review.md`](week1_api_client_python_review.md)
(the Python-specific review — this is where the Python-vs-Ruby "falsy value"
bug class first showed up, see **Observations** below),
[`week1_api_client_port_plan.md`](week1_api_client_port_plan.md).

---

### 05 · The Agent Loop — *the heart of the framework*

**Simple explanation:** everything before this was setup. `Agent#run` is the
actual loop: send the conversation, check if the model wants to call a tool,
run it via the Registry if so, feed the result back in, repeat — until the
model gives a final answer instead of a tool call.

**Schema — the loop, and the normalized response shape every backend must produce:**

```
send messages to API
        ↓
stop_reason == "tool_use"?
    yes → extract tool calls → dispatch each via Registry
        → inject results as tool_result messages → loop again
    no  → return final text
```
```json
{
  "stop_reason": "tool_use" | "end_turn",
  "content": [
    { "type": "text", "text": "..." },
    { "type": "tool_use", "id": "...", "name": "...", "input": { ... } }
  ]
}
```
Every backend implements `parse_response` to produce exactly this shape (and
its inverse, to rebuild a provider-specific assistant message on replay) —
`Agent` itself never sees a raw provider response. `max_iterations` (default
25) is a turn ceiling: past it, the agent makes one short wrap-up call with
tools disabled rather than looping forever.

**Go deeper:** `ruby/05_agent_loop/README.md`, `python/05_agent_loop/README.md`,
[`week1_agent_loop_architecture.md`](week1_agent_loop_architecture.md) (how
the pieces wire together, code-grounded),
[`week1_agent_loop_port_plan.md`](week1_agent_loop_port_plan.md).

---

### 06 · The Logger — *a black box, not a display*

**Simple explanation:** every run writes one JSON object per line
(JSON Lines) to `.boukensha/sessions/<session-id>.jsonl` — one file logger,
never printed to the screen. This is what makes a run replayable/inspectable
after the fact, and it's what `log_viz` (below) reads.

**Schema — one event per phase:**

| Phase | Logs |
|---|---|
| `session_start` | session id, timestamp |
| `iteration` | loop counter |
| `prompt` | messages, tool names |
| `tool_call` / `tool_result` | tool name + args / result, success flag |
| `response` | text, token usage, task/provider/model, estimated USD cost |
| `turn_end` | why and how the turn ended |
| `raw` | the raw provider response (only when `Boukensha.debug!` is on) |

**Go deeper:** `ruby/06_the_logger/README.md`, `python/06_the_logger/README.md`,
[`week1_logger_session_summary.md`](week1_logger_session_summary.md) (plain-
language recap, good starting point if the schema above feels dry).

---

### 07 · The Run DSL — *`Boukensha.run`, the "hello world" entry point*

**Simple explanation:** every prior step made you manually build and wire
six objects together (`Context`, `Registry`, `Backend`, `PromptBuilder`,
`Client`, `Logger`) before you could even ask the agent one question. This
step hides all of that behind one call:

```ruby
Boukensha.run(task: "Read lib/boukensha.rb") do
  tool "read_file", description: "Read a file", parameters: { path: {...} } do |path:|
    File.read(path)
  end
end
```

Python has no `instance_eval`, so the same idea becomes an explicit
`configure(dsl)` callback instead of a bare block — same narrow surface
(`dsl.tool(...)`), different syntax to reach it.

**Go deeper:** `ruby/07_the_run_dsl/README.md`, `python/07_the_run_dsl/README.md`,
[`week1_run_dsl_overview.md`](week1_run_dsl_overview.md).

---

### 08 · The REPL Loop — *one turn becomes many*

**Simple explanation:** `Boukensha.run` does one task and throws the
`Context` away. `Boukensha.repl` keeps that same `Context` alive across many
turns — reads a line, runs the agent, prints the reply, loops — so question
3 can reference something said in question 1.

**Schema — built-in commands:**

| Command | Effect |
|---|---|
| `/quiet` / `/loud` | suppress / re-enable logging output |
| `/clear` | wipe conversation history, keep tools registered |
| `/help` | list commands |
| `/exit`, `/quit`, Ctrl-D | leave |

The key implementation change: the agent's final reply now gets **saved
into `Context`** before returning (previously discarded, harmless for a
one-shot `.run`, but a REPL needs the transcript to persist).

**Go deeper:** `ruby/08_the_repl_loop/README.md`,
`python/08_the_repl_loop/README.md`,
[`week1_repl_loop_overview.md`](week1_repl_loop_overview.md),
[`week1_repl_loop_review.md`](week1_repl_loop_review.md).

---

### 09 · Global Executable — *`boukensha`, the command (Ruby only)*

**Simple explanation:** packages the whole framework as a real RubyGem so
that, once installed, typing `boukensha` from *any* directory launches the
REPL — no `cd`, no `bundle exec`. There is deliberately **no Python
equivalent** — Python already has its own per-step launcher
(`bin/python/<step>`), so the Python port skips straight from `08` to `10`.

**Schema — the resolution chain** (which code + which config to load):

| Priority | Selects | Source |
|---|---|---|
| 1 | **code** | `BOUKENSHA_PATH` env var → a specific step folder |
| 2 | **code** | `~/.boukensharc` → a permanent default path |
| 3 | **code** | the gem's own bundled snapshot (fallback) |
| — | **config** | `BOUKENSHA_DIR` (independent chain, from step 00) |

`BOUKENSHA_PATH` (which *code* runs) and `BOUKENSHA_DIR` (which *config* it
reads) are intentionally separate axes — you can run step 4's code against
the same shared `~/.boukensha` everything else uses.

**Go deeper:** `ruby/09_global_executable/README.md`,
[`week1_global_executable_overview.md`](week1_global_executable_overview.md)
(the fullest doc of the week — walks through actually building, installing,
and configuring the gem for real, including two real bugs found only by
doing the install rather than reading the code: a missing `dotenv` runtime
dependency, and `bin/boukensha` shipped without its executable bit),
[`week1_global_executable_review.md`](week1_global_executable_review.md)
(scoped to `boukensha_loader.rb` specifically).

---

### 10 · Standard Tool Library — *tools stop being hand-registered*

**Simple explanation:** instead of writing `tool "read_file" do ... end`
yourself every time, Boukensha now ships a **standard library** of tools out
of the box, auto-registered when you set `working_dir:`.

**Schema:**

| Module | Tools |
|---|---|
| `FileSystem` | `pwd`, `list_directory`, `read_file`, `write_file`, `delete_file`, `search_files` (grep) |
| `Shell` | `run_command` (timeout + optional allow-list of executables) |
| `Mcp` *(Python names it explicitly; Ruby's arrived via later refactor — see the MCP section below)* | one tool per tool the configured MCP server(s) report |

All filesystem paths are relative to `working_dir`; absolute paths and `..`
escapes are rejected. This is also the iteration where MUD gameplay stopped
being a hand-written, MUD-specific tool set and became **just another
configured MCP server** — that whole arc is big enough to get its own
section below.

**Go deeper:** `ruby/10_standard_tool_library/README.md`,
`python/10_standard_tool_library/README.md`,
[`week1_standard_tool_library_review.md`](week1_standard_tool_library_review.md)
(known limitations: `run_command`'s timeout doesn't fully kill the child
process; `allowed_commands` is a first-token filter, not a real sandbox — a
shell-injection-shaped gap worth knowing about, not fixed by design),
[`week1_python_standard_tool_library_and_mcp.md`](week1_python_standard_tool_library_and_mcp.md)
(plain-language reference for the Python port of this whole step).

---

### 11 · Terminal UI — *see the agent think*

Covered in its own section below (**The Terminal UI**) — it's substantial
enough to deserve one.

### 12 · Context Management — *don't silently blow past the window*

Covered in its own section below (**Context Management**).

---

## The MCP integration arc — five parts, one running story

This was the week's biggest sustained design effort — not one iteration, but
a whole arc of plan → design → implement → review → fix → merge that runs
underneath (and eventually becomes part of) iterations 10–12. The short
version: **MUD gameplay went from "hand-written tools baked into the
agent" to "just another MCP server the agent happens to be configured to
talk to."**

1. **The problem** ([`week1_mcp_integration_plan.md`](week1_mcp_integration_plan.md)):
   `week0_explore/mud_manager/` — the gem that knows how to speak CircleMUD
   (sockets, telnet IAC codes, login state machine) — needed to be reachable
   from *both* the Ruby and the Python agent, without either one containing
   MUD-specific protocol code. Decision: use **MCP (Model Context
   Protocol)** as the boundary — spawn `mud_manager` as a subprocess, talk
   JSON-RPC over stdio, register one Boukensha tool per MCP tool the server
   reports.

2. **The design** ([`week1_mcp_architecture_design.md`](week1_mcp_architecture_design.md),
   later generalized in
   [`week1_generic_mcp_architecture_design.md`](week1_generic_mcp_architecture_design.md)):
   a language-specific agent must contain **zero** MUD-protocol code. One
   generic bridge component registers tools from *any* configured MCP
   server, without knowing what domain it serves.

3. **Self-review caught real bugs before implementation**
   ([`week1_mcp_refactor_plan_review.md`](week1_mcp_refactor_plan_review.md)):
   the first design draft had a code bug in its own sketch (a `command: nil`
   fallback that didn't do what it claimed) — found by reading the plan back
   adversarially instead of trusting it, then folded into a sign-off doc
   ([`week1_mcp_final_design.md`](week1_mcp_final_design.md)) before anything
   was built.

4. **Implementation, in parts:** a standalone MCP server package first
   (`ruby/13_mcp_server/`, reviewed in
   [`week1_mcp_server_review.md`](week1_mcp_server_review.md)), then wired
   into the Standard Tool Library
   ([`week1_mcp_standard_tool_library_integration.md`](week1_mcp_standard_tool_library_integration.md)),
   then a config schema update
   ([`week1_mcp_server_config_update.md`](week1_mcp_server_config_update.md)),
   then a startup bug hunt
   ([`week1_mcp_part4_startup_debug.md`](week1_mcp_part4_startup_debug.md),
   [`week1_mcp_startup_config_review.md`](week1_mcp_startup_config_review.md)),
   then live verification against a real CircleMUD
   ([`week1_mcp_part4_verification.md`](week1_mcp_part4_verification.md),
   [`week1_mcp_part4_mud_communication_test.md`](week1_mcp_part4_mud_communication_test.md),
   [`week1_mcp_part4_tool_behavior_review.md`](week1_mcp_part4_tool_behavior_review.md)),
   then a genericity audit — is this actually protocol-generic, or still
   secretly MUD-specific? ([`week1_mcp_genericity_review.md`](week1_mcp_genericity_review.md),
   [`week1_mcp_review_and_gaps.md`](week1_mcp_review_and_gaps.md),
   [`week1_mcp_part3_review.md`](week1_mcp_part3_review.md),
   [`week1_mcp_generic_implementation.md`](week1_mcp_generic_implementation.md),
   [`week1_mcp_validation.md`](week1_mcp_validation.md)).

5. **The merge** ([`week1_mud_manager_mcp_merge_plan.md`](week1_mud_manager_mcp_merge_plan.md) →
   [`week1_mud_manager_mcp_merge_result.md`](week1_mud_manager_mcp_merge_result.md)):
   the MCP server package (`mud_mcp`) and the MUD protocol gem
   (`mud_manager`) were two separate gems, one depending on the other —
   consolidated into a single `mud_manager` gem (`MudManager::Mcp::*`
   namespace) so there's one thing to install, not two.

**End state, in schema form** — `settings.yaml`'s `mcp_servers:` list
replaced the old MUD-specific `mud:` block:

```yaml
mcp_servers:
  - name: mud
    command: ["mud_manager", "--mcp"]
    env: { MUD_HOST: "localhost", MUD_PASSWORD: "$MUD_PASSWORD" }
    # prefix: "mud_"   ← optional, disambiguates a tool-name collision
    #                     between two servers
```

A server that fails to spawn, times out its handshake (10s), or errors is
warned about and simply absent — one bad server doesn't take the others
down. **Python has no `mud_manager` package to depend on** — instead
`python/10_standard_tool_library`'s `boukensha.tools.mcp` carries its own
small, hand-rolled MCP client (newline-delimited JSON-RPC over stdio) that
spawns and speaks to the exact same `mud_manager --mcp` server process; only
the *client* is reimplemented, not the server.

---

## The Terminal UI (iteration 11)

**Simple explanation:** the plain REPL (step 08–10) just scrolls text past
you forever. Step 11 wraps the same `Repl` in a real terminal UI — a
persistent, redrawing screen instead of an ever-growing log — **without
changing how the agent itself works at all**. `Repl` was refactored so it no
longer assumes it owns the terminal (`on_output`, `handle_command`,
`run_turn` became public, callback-driven); `Tui` just drives those instead
of `puts`/`gets`.

**Schema — the four zones:**

```
┌──────────────────────────────────────────────┐
│  conversation viewport (scrollable)           │
├──────────────────────────────────────────────┤
│  ⟳ live progress line (hidden when idle)     │  ← driven by Logger#subscribe
├──────────────────────────────────────────────┤
│  boukensha> input box                         │
├──────────────────────────────────────────────┤
│  status line (always-on): version · model ·   │
│  context tokens used/max · tool count         │
└──────────────────────────────────────────────┘
```

Ruby is built on **Bubble Tea** (via the `charm` gem) — the Elm Architecture
(`init` / `update` / `view`, one state object, redraw driven by messages).
Python has no equivalent binding to Bubble Tea's Go internals, so
`python/11_tui` is genuinely new code built on **Textual**, targeting the
same four zones with Textual's own idioms (reactive re-rendering,
`@work(thread=True)` for the background agent thread) rather than a
line-for-line port. One deliberate gap: Ruby's TUI can interrupt a running
turn with `Esc`; Python has no safe way to inject an exception into another
thread, so that one keybinding doesn't exist on the Python side.

**Go deeper:** `ruby/11_tui/README.md`, `python/11_tui/README.md`,
[`week1_tui_explained.md`](week1_tui_explained.md) (the concept explainer —
what a TUI even is, Elm Architecture, worth reading even with zero Bubble
Tea background), [`week1_tui_gem_build_install.md`](week1_tui_gem_build_install.md)
(packaging/build/install mechanics for this step specifically).

---

## Context Management (iteration 12)

**Simple explanation:** an LLM call has no memory of its own — every call
resends the *entire* conversation so far, and every tool result (a room
description, a file's contents) becomes part of every future prompt,
forever, unless something prunes it. Before this step, Boukensha had no
concept of the model's actual context window at all — it displayed
`token_budget` (8,192, actually the *output* length limit) as if it were the
input ceiling, and showed a cumulative session total that only ever grew,
even after `/clear`. Both numbers were answering the wrong question. Step 12
fixes that with real tracking plus automatic compaction.

**Schema — the three numbers, and why they're not interchangeable:**

| Name | What it measures | Resets when |
|---|---|---|
| `context_window` | the model's fixed input ceiling (a model fact, e.g. `200,000`) | never |
| `current_tokens` | the *last* response's `input_tokens` — "what the next call will send" | on compaction or `/clear` |
| `turn_tokens` | cumulative spend *this turn* (a separate circuit breaker) | at the start of every turn |

**Schema — auto-compaction:** at the start of each turn, if
`current_tokens / context_window ≥ 0.85`, drop the oldest 40% of messages
(always keep at least 2), reset `current_tokens` to 0:

```
[context compacted — 12 messages dropped to free space]
```

| Usage | Colour shown in TUI/status line |
|---|---|
| < 70% | grey |
| 70–84% | yellow |
| ≥ 85% | red, `⚠` shown |

Manual equivalent: the `/compact` REPL command. Every compaction (auto or
manual) emits a `"compaction"` log event (`before`, `dropped`,
`context_window`) that the TUI subscribes to and renders directly in the
conversation view.

**One real gotcha, worth internalizing:** right after `/clear` or a
compaction, `current_tokens` reads `0` — that's not a lie, it means "no call
has happened since the reset, so we don't know the next prompt's true size
yet," not "the conversation is empty" (the system prompt + tools alone are
already nonzero tokens).

**Go deeper:** `ruby/12_context/README.md` (Python's own `python/12_context/README.md`
is stale — see **Observations** below, use the Ruby one plus the doc below
instead),
[`week1_context_management_explained.md`](week1_context_management_explained.md)
— the single best doc from this week: concept explainer, full code
walkthrough for both languages side by side, real captured TUI output
including auto-compaction actually firing, and complete JSON Schema for the
two new log event types. Read this one directly if you read nothing else
from this section.

---

## Log Viz — watching a session after the fact

**Simple explanation:** a small Sinatra app (`ruby/log_viz/`) that turns
`.boukensha/sessions/*.jsonl` into a readable, chat-style transcript in the
browser — session list at `/`, one rendered transcript per session at
`/sessions/:id`, with token/cost breakdowns and MUD ANSI color codes
converted to real color. It only reads `.jsonl` files, never writes. Because
the log format is language-agnostic, a session generated by the Python port
renders identically — no `log_viz` changes needed to view a Python run.

**Go deeper:** `ruby/log_viz/README.md`.

---

## Observations — what actually broke, and the patterns behind it

Two living documents captured almost everything that went wrong this week,
in detail. Rather than repeat them here, this section pulls out the
*patterns* — the recurring bug classes worth carrying into future work.

**1. The `../`-count bug, six times in a row.** Nearly every iteration's
`examples/example.rb` computes `BOUKENSHA_DIR` by hand-counting `../`
segments from its own file location back to the repo root. Copy the file
forward to a new iteration without re-verifying the count, and it silently
resolves to a directory that doesn't exist — `Config` then loads with empty
settings and crashes several frames away from the real cause (a `nil.fetch`
deep inside task resolution), not at the path itself. Confirmed in
`00_config` through `06_the_logger`, one iteration at a time, because each
folder ships its *own independent copy* — fixing it once does not propagate
forward. **The general lesson, stated once and then true forever:** a
relative path built by counting `../` characters is not self-checking;
`File.expand_path(relative, base)` produces a valid-looking wrong path just
as happily as a right one. Python's port sidesteps the entire bug class by
computing paths from `Path(__file__).resolve()` instead of counting
characters — a structural fix, not a per-file one.

**2. Ruby-truthy vs. Python-truthy, twice.** Ruby's only falsy values are
`nil` and `false` — `0` and `""` are truthy. A line like
`config.dig(:mud, :port) || 4000` only falls back to the default for a
*missing* value. The naive Python translation, `value or 4000`, silently
discards a legitimately-configured `0` or `""` too, because Python's falsy
set is much larger. Found twice by an explicit code-review pass (not by the
smoke test, which happened to use non-zero, non-empty values both times) —
once in `Config.mud_port`, once in `Agent._call_opts`'s handling of
`max_output_tokens: 0`. The fix pattern is always the same: an explicit
`is None` check, not a bare `or`.

**3. A stale README is a real trap.** `python/12_context/README.md`
currently still contains **step 11's TUI content**, verbatim — the file was
never updated when `12_context` was built. The actual code
(`boukensha/context.py`) does implement compaction correctly (verified
directly — `needs_compaction`, `compact_messages`, `compaction_threshold`
are all present and match the Ruby reference); only the README drifted.
This is exactly the kind of gap a "did it run" smoke test cannot catch,
because nothing reads its own README at runtime — worth a documentation
pass before this iteration is considered fully closed out.

**4. A generic identifier-casing transform is a known blind spot for
acronyms — and the fix itself fell victim to pattern #1.**
`Logger#provider_name` auto-derives a lowercase provider string from a
backend's class name via a CamelCase→snake_case regex — correct for
`Anthropic`/`Gemini`/`Ollama`/`OllamaCloud`, but it mangled `OpenAI` into
`"open_ai"` (every other reference to the string elsewhere in the codebase
is `"openai"`, no underscore). Anyone filtering session logs by
`provider: "openai"` would have silently missed every OpenAI session. Fixed
by special-casing `OpenAI` ahead of the generic transform
(`week1_config_troubleshooting.md`, entry 20) — first in `06_the_logger`,
confirmed present through `09_global_executable`. But because each
iteration folder is its own independent copy (same structural issue as
pattern #1), **the fix never made it into `10_standard_tool_library` or
`11_tui`, and as of `12_context` — the current head of the Ruby port — the
bug is back**: `ruby/12_context/lib/boukensha/logger.rb`'s
`provider_name` is the plain generic gsub again, no special case. The
Python port didn't regress the same way — `_provider_name` in
`python/12_context/boukensha/logger.py` still carries the special case,
all the way from `06_the_logger` through `12_context`. Worth a fix in
`ruby/12_context` before this is called done.

**5. "It works" only proves the path it exercised.** Several bugs above
were invisible to a clean live run precisely because the run only exercised
one branch (one provider, one non-zero config value, the happy path). The
practice that actually caught them: a real code-review pass plus small
offline test harnesses (fake client/builder, no live API) built
specifically to exercise the branches a smoke test can't reach — the
wind-down path, the error path, a zero-valued config. This is now the
project's working definition of "verified," not just "ran once and printed
something plausible."

**Full detail on all of the above, plus environment setup (Docker vs. native
Ruby, Bundler permission errors, gitignore anchoring rules, and more):**
[`week1_config_troubleshooting.md`](week1_config_troubleshooting.md) — a
long, chronological, Problem → Fix → Why log, kept up to date as new issues
surface. Worth skimming even just for the Docker vs. native Ruby comparison
table if you're setting up a machine from scratch.

---

## Technical Conclusions

- **Building the loop from scratch made the "why" of an agent SDK visible.**
  Assistant-message-before-tool-result ordering, the five different tool-
  result wire shapes, retry/backoff, iteration ceilings — none of this is
  exotic, but it's exactly the kind of plumbing a framework normally hides.
  Building it once made every later week's use of a real SDK legible instead
  of magic.
- **A port is not a translation — it needs its own review pass.** Nearly
  every real bug this week (the falsy-value pair, the acronym-casing miss,
  the deliberately-preserved-not-fixed backend asymmetries) was found by
  treating the Python side as code to review, not just code to make run.
  Worth keeping as a standing rule for every future port.
- **Context is genuinely the only stateful thing in the whole design.**
  Every other object (`Agent`, `Client`, `Backend`) is disposable and
  stateless-by-construction. That single design choice is what makes both
  the REPL and the TUI simple to build on top of — neither had to reinvent
  conversation memory, they just kept pointing at the same `Context`.
- **MCP turned out to be the right seam for the tool boundary.** Two
  languages, one protocol server, zero MUD-specific code in either agent —
  the multi-part design/review/merge arc was worth the overhead precisely
  because it kept paying off through iterations 10, 11, and 12 without
  needing to be revisited each time.

**Still open (for later):**
- `ruby/12_context/lib/boukensha/logger.rb`'s `provider_name` has
  regressed to the unfixed `"open_ai"` bug (see Observation 4) — the
  special case is present in `06_the_logger`–`09_global_executable` and in
  every Python iteration, but missing from `10_standard_tool_library`
  onward in Ruby. Needs re-applying at the current head.
- `python/12_context/README.md` needs an actual rewrite (see Observation 3).
- `run_command`'s shell-injection-shaped gap (`allowed_commands` is a
  first-token filter, not a real sandbox) is documented but not fixed, in
  both languages.
- The Ruby TUI's `Esc`-to-interrupt has no safe Python equivalent yet.

---

## Full document index

Every `.md` file this week produced, grouped by what it's about. All paths
are relative to `docs/` unless otherwise noted.

### Iteration READMEs (the primary source for each step)

| Iteration | Ruby | Python |
|---|---|---|
| 00 Config | `week1_baseline/ruby/00_config/README.md` | `week1_baseline/python/00_config/README.md` |
| 01 Struct Skeleton | `week1_baseline/ruby/01_struct_skeleton/README.md` | `week1_baseline/python/01_struct_skeleton/README.md` |
| 02 Registry | `week1_baseline/ruby/02_the_registry/README.md` | `week1_baseline/python/02_the_registry/README.md` |
| 03 Prompt Builder | `week1_baseline/ruby/03_prompt_builder/README.md` | `week1_baseline/python/03_prompt_builder/README.md` |
| 04 API Client | `week1_baseline/ruby/04_api_client/README.md` | `week1_baseline/python/04_api_client/README.md` |
| 05 Agent Loop | `week1_baseline/ruby/05_agent_loop/README.md` | `week1_baseline/python/05_agent_loop/README.md` |
| 06 Logger | `week1_baseline/ruby/06_the_logger/README.md` | `week1_baseline/python/06_the_logger/README.md` |
| 07 Run DSL | `week1_baseline/ruby/07_the_run_dsl/README.md` | `week1_baseline/python/07_the_run_dsl/README.md` |
| 08 REPL Loop | `week1_baseline/ruby/08_the_repl_loop/README.md` | `week1_baseline/python/08_the_repl_loop/README.md` |
| 09 Global Executable | `week1_baseline/ruby/09_global_executable/README.md` | *(no Python equivalent)* |
| 10 Standard Tool Library | `week1_baseline/ruby/10_standard_tool_library/README.md` | `week1_baseline/python/10_standard_tool_library/README.md` |
| 11 TUI | `week1_baseline/ruby/11_tui/README.md` | `week1_baseline/python/11_tui/README.md` |
| 12 Context | `week1_baseline/ruby/12_context/README.md` | `week1_baseline/python/12_context/README.md` *(stale — see Observations)* |
| Log Viz | `week1_baseline/ruby/log_viz/README.md` | — |

### Per-iteration plans / reviews (`docs/`)

| Topic | Plan | Review / Verification |
|---|---|---|
| Struct Skeleton | — | [`week1_struct_skeleton_review.md`](week1_struct_skeleton_review.md), [`week1_struct_skeleton_python_port.md`](week1_struct_skeleton_python_port.md) |
| Registry | [`week1_the_registry_port_plan.md`](week1_the_registry_port_plan.md) | [`week1_the_registry_review.md`](week1_the_registry_review.md) |
| Prompt Builder | [`week1_prompt_builder_port_plan.md`](week1_prompt_builder_port_plan.md) | [`week1_prompt_builder_review.md`](week1_prompt_builder_review.md), [`week1_prompt_builder_python_review.md`](week1_prompt_builder_python_review.md), [`week1_prompt_builder_verification.md`](week1_prompt_builder_verification.md) |
| API Client | [`week1_api_client_port_plan.md`](week1_api_client_port_plan.md) | [`week1_api_client_review.md`](week1_api_client_review.md), [`week1_api_client_python_review.md`](week1_api_client_python_review.md) |
| Agent Loop | [`week1_agent_loop_port_plan.md`](week1_agent_loop_port_plan.md) | [`week1_agent_loop_architecture.md`](week1_agent_loop_architecture.md) |
| Logger | — | [`week1_logger_session_summary.md`](week1_logger_session_summary.md) |
| Run DSL | — | [`week1_run_dsl_overview.md`](week1_run_dsl_overview.md) |
| REPL Loop | — | [`week1_repl_loop_overview.md`](week1_repl_loop_overview.md), [`week1_repl_loop_review.md`](week1_repl_loop_review.md) |
| Global Executable | — | [`week1_global_executable_overview.md`](week1_global_executable_overview.md), [`week1_global_executable_review.md`](week1_global_executable_review.md) |
| Standard Tool Library | — | [`week1_standard_tool_library_review.md`](week1_standard_tool_library_review.md), [`week1_python_standard_tool_library_and_mcp.md`](week1_python_standard_tool_library_and_mcp.md) |
| TUI | — | [`week1_tui_explained.md`](week1_tui_explained.md), [`week1_tui_gem_build_install.md`](week1_tui_gem_build_install.md) |
| Context | — | [`week1_context_management_explained.md`](week1_context_management_explained.md) |

### The MCP integration arc (chronological)

| Order | Doc |
|---|---|
| 1 | [`week1_mcp_integration_plan.md`](week1_mcp_integration_plan.md) — Part 1, the plan |
| 2 | [`week1_mcp_architecture_design.md`](week1_mcp_architecture_design.md) — Part 2, initial design |
| 3 | [`week1_mcp_server_review.md`](week1_mcp_server_review.md) — Part 3, reviewing the generated server |
| 4 | [`week1_mcp_standard_tool_library_integration.md`](week1_mcp_standard_tool_library_integration.md) — Part 4, wiring in |
| 5 | [`week1_mcp_server_config_update.md`](week1_mcp_server_config_update.md) |
| 6 | [`week1_mcp_part4_startup_debug.md`](week1_mcp_part4_startup_debug.md) |
| 7 | [`week1_mcp_startup_config_review.md`](week1_mcp_startup_config_review.md) |
| 8 | [`week1_mcp_part4_verification.md`](week1_mcp_part4_verification.md) |
| 9 | [`week1_mcp_part4_mud_communication_test.md`](week1_mcp_part4_mud_communication_test.md) |
| 10 | [`week1_mcp_part4_tool_behavior_review.md`](week1_mcp_part4_tool_behavior_review.md) |
| 11 | [`week1_mcp_part3_review.md`](week1_mcp_part3_review.md) — obsolete-scaffolding cleanup |
| 12 | [`week1_mcp_review_and_gaps.md`](week1_mcp_review_and_gaps.md) — Part 5, gap review |
| 13 | [`week1_mcp_genericity_review.md`](week1_mcp_genericity_review.md) — how generic is it, really |
| 14 | [`week1_generic_mcp_architecture_design.md`](week1_generic_mcp_architecture_design.md) — Part 2 redo, generalized |
| 15 | [`week1_mcp_refactor_plan_review.md`](week1_mcp_refactor_plan_review.md) — self-review, bugs found pre-implementation |
| 16 | [`week1_mcp_final_design.md`](week1_mcp_final_design.md) — design sign-off |
| 17 | [`week1_mcp_generic_implementation.md`](week1_mcp_generic_implementation.md) |
| 18 | [`week1_mcp_validation.md`](week1_mcp_validation.md) |
| 19 | [`week1_mud_manager_mcp_merge_plan.md`](week1_mud_manager_mcp_merge_plan.md) |
| 20 | [`week1_mud_manager_mcp_merge_result.md`](week1_mud_manager_mcp_merge_result.md) |

### Meta / cross-cutting docs

| Doc | What it's for |
|---|---|
| [`week1_components_explained.md`](week1_components_explained.md) | How every object fits together — read this first |
| [`week1_context_management_explained.md`](week1_context_management_explained.md) | Context/compaction concept + full walkthrough |
| [`week1_tui_explained.md`](week1_tui_explained.md) | What a TUI is + how boukensha's is built |
| [`week1_config_troubleshooting.md`](week1_config_troubleshooting.md) | Living Problem → Fix → Why log, every environment/code issue hit |
| [`week1_journal.md`](week1_journal.md) | This document |

---

*Full week-0 write-up, for context on what came before this:
[`week0_journal.md`](week0_journal.md).*
