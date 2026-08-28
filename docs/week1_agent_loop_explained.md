# The Agent Loop, Explained — Registering Tools, Calling Them, Stopping, and Watching It Think

A simple explainer of *why* `Boukensha::Agent` is a loop at all, then a
technical walkthrough — grounded in the actual current code
(`ruby/12_context/lib/boukensha/agent.rb` and its Python twin,
`python/12_context/boukensha/agent.py`) and a **real captured session log**
— of how to register a tool, how a tool call actually happens, what stops
the loop, and how to see what happened after each step.

If you want the terser, more code-dense version of this same material, see
[`week1_agent_loop_architecture.md`](week1_agent_loop_architecture.md). This
doc is the "explain it like I'm reading this for the first time" version,
written to stand on its own.

---

## 1. Why a loop, in plain terms

A call to an LLM is a pure function: text in, text out. It cannot read a
file, run a command, or check a game state — it can only *say* what it
would like to happen next. So an "agent" is really just this pattern,
repeated:

```
1. Show the model the conversation so far (+ a list of tools it's allowed to ask for).
2. Read what it said.
3. If it asked to run a tool: actually run it, show it the result, go back to step 1.
4. If it gave a real answer instead: stop, that's the reply.
```

That's the entire agent loop. Everything in `05_agent_loop` and later steps
is: implementing that four-step cycle correctly, deciding when "actually
run it" means, and deciding when to give up if it never reaches step 4.

**Why this needed to be built at all, and not just called once:** a single
API call can only ever produce *text*. `Agent#run` is the object that turns
"the model wants to call `read_file`" into "Ruby's `File.read` actually
executes and the result gets shown back to the model" — and does that as
many times as needed, automatically, until the model is done.

---

## 2. The schema — the shapes involved

Five small pieces of state, three of them just plain structs:

| Piece | Shape | Held by |
|---|---|---|
| **`Tool`** | `name`, `description`, `parameters` (a JSON-Schema-shaped hash), `block` (the actual code to run) | `Context#tools`, a `{name => Tool}` hash |
| **`Message`** | `role` (`:user` / `:assistant` / `:tool_result`), `content`, `tool_use_id` (only set on `:tool_result`) | `Context#messages`, an ordered array — the transcript |
| **`Context`** | `system`, `messages`, `tools`, `context_window`, `current_tokens`, `turn_tokens` | the one object that survives between turns |
| **the normalized model response** | `{ stop_reason: "tool_use" \| "end_turn", content: [...] }` | returned by `PromptBuilder#parse_response`, read only by `Agent` |
| **one `content` block, tool-call variant** | `{"type"=>"tool_use", "id"=>"toolu_xyz", "name"=>"read_file", "input"=>{"path"=>"README.md"}}` | inside the response above |

That normalized `{stop_reason, content}` shape is the important one to
internalize: Anthropic, OpenAI, Gemini, and Ollama each describe "the model
wants to call a tool" completely differently on the wire (see
[`week1_agent_loop_architecture.md`](week1_agent_loop_architecture.md) §4
for the provider-by-provider comparison) — but every backend's
`parse_response` converts its provider's shape into this *one* shape before
`Agent` ever sees it. `Agent` itself contains **zero** provider-specific
code because of this.

---

## 3. Registering a tool

A tool is just: a name, a description (the *only* thing the model reads to
decide whether/how to call it), a parameters schema, and a block of real
code. There are two ways to register one — same underlying mechanism, two
entry points.

### 3a. Directly on a `Registry`

This is what's actually happening underneath everything else. Real,
complete example, lifted from `ruby/05_agent_loop/examples/example.rb`:

```ruby
registry.tool("read_file",
  description: "Read the contents of a file from disk",
  parameters: { path: { type: "string", description: "The file path to read" } }
) do |path:|
  File.read(File.expand_path(path, base_dir))
end
```

Python version (`python/05_agent_loop/examples/example.py` follows the same
shape — `block=` takes any callable):

```python
def read_file(path):
    return open(os.path.join(base_dir, path)).read()

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=read_file,
)
```

What `Registry#tool` actually does (`registry.rb` / `registry.py`, unchanged
since `02_the_registry`):

```ruby
def tool(name, description:, parameters: {}, &block)
  tool = Tool.new(name.to_s, description, parameters, block)
  @context.register_tool(tool)   # ← stored on Context, not on Registry itself
  tool
end
```

**The one non-obvious detail:** the `Registry` does not keep tools itself —
it writes them straight into `Context#tools`. That's deliberate: the
backend's `to_tools(ctx.tools)` (which builds the API's tool-list JSON) and
the registry's own `dispatch` (which runs them) both need to read from the
exact same source, so there's only ever one place a tool can be registered
or found.

### 3b. Through the `Boukensha.run` / `Boukensha.repl` DSL

Once you're past `07_the_run_dsl`, you don't touch `Registry` directly —
you get a narrower surface inside a block:

```ruby
Boukensha.run(task: "Summarize this file") do
  tool "read_file", description: "Read a file", parameters: {
    path: { type: "string", description: "Relative path" }
  } do |path:|
    File.read(path)
  end
end
```

`RunDSL#tool` (`run_dsl.rb`) is an 8-line pass-through — `self` inside that
block *is* a `RunDSL` instance wrapping the real `Registry`, so calling
`tool(...)` there is exactly the call in §3a, just without you having to
construct a `Registry` by hand first. In `10_standard_tool_library` and
later, setting `working_dir:` also auto-registers a whole starter set this
same way (`Tools::FileSystem.register(registry, working_dir: ...)` for
`pwd`/`read_file`/`write_file`/`delete_file`, `Tools::Shell.register` for
`run_command`, `Tools::Mcp.register` for one tool per tool an MCP server
reports) — same `registry.tool(...)` call underneath, just made on your
behalf.

### The `parameters:` schema

`parameters` is a plain hash that gets handed almost verbatim to the
model's own tool-schema field (`input_schema` for Anthropic, wrapped in a
`function` envelope for OpenAI/Ollama — see
`PromptBuilder`/`Backend#to_tools`). One entry per argument:

```ruby
parameters: {
  path:  { type: "string",  description: "Relative path to the file" },
  limit: { type: "integer", description: "Max bytes to read", default: 4096 }
}
```

The model reads this schema (plus `description`) to decide *what to put in
each field* — there's no separate "how do I call this" instruction
anywhere else. A vague `description` is the single most common reason a
model calls a tool wrong.

---

## 4. How a tool call actually happens — one dispatch, traced

This is `Agent#handle_tool_calls` (the part of the loop that runs when
`stop_reason == "tool_use"`), stepped through:

```
1. Model's response content includes:
     {"type"=>"tool_use", "id"=>"toolu_01Abc", "name"=>"read_file", "input"=>{"path"=>"README.md"}}

2. Agent adds the FULL assistant content block (including this tool_use item)
   to Context as one :assistant message.
       ctx.messages << Message.new(:assistant, content, nil)

3. For each tool_use block found:
       result = registry.dispatch("read_file", {"path" => "README.md"})
   which is:
       tool = ctx.tools["read_file"]                 # look it up by name
       tool.block.call(**{path: "README.md"})        # actually run your code
       # => "# Boukensha\n\n..."   (whatever your block returns)

4. The RETURN VALUE becomes a new message, paired back to the call by id:
       ctx.messages << Message.new(:tool_result, "# Boukensha\n\n...", "toolu_01Abc")

5. Loop repeats — Context now has 3 more messages than before this step,
   and the NEXT api call resends the whole transcript, so the model reads
   its own tool's result as part of the next prompt.
```

**Two rules enforced by code, not by any check, so they're worth stating
explicitly:**

- **The assistant message is added *before* the tool_result message(s).**
  Anthropic's API (and the others) reject a `tool_result` whose matching
  `tool_use` isn't already earlier in the sent history — get this order
  backwards and the *next* API call fails with a 400, several steps removed
  from the actual bug.
- **An unknown tool name raises loudly.** `Registry#dispatch` raises
  `UnknownToolError` rather than silently no-op'ing if the model asks for a
  tool that was never registered — `Agent` catches this (and any other
  exception a tool's own block raises) and turns it into a normal
  `tool_result` string (`"ERROR: UnknownToolError: No tool registered as
  'X'"`) instead of crashing the whole turn. **The model sees its own
  mistake and gets to react to it on the next iteration**, the same way it
  reacts to a successful result.

---

## 5. The full loop, iteration by iteration

```
Agent#run
│
├─ reset_turn_tokens, compact context if over threshold
│
└─ loop:
     ├─ hit max_iterations? ──yes──▶ wrap_up("max_iterations")  [see §6]
     ├─ hit max_turn_tokens? ─yes──▶ wrap_up("max_tokens")      [see §6]
     ├─ iteration += 1
     ├─ send the whole Context to the model (Client#call)
     ├─ parse_response → { stop_reason, content }
     │
     ├─ stop_reason == "tool_use"?
     │     yes → handle_tool_calls (§4) → loop again
     │     no  → extract_text(content), save as :assistant message, RETURN
```

Concretely, from a real captured run (`.boukensha/sessions/*.jsonl` —
more on reading these in §7) of the MUD-playing `player` task:

```
[iteration 1] model replies with text + a tool_use block → mud_connect({})
              tool_result: "already connected to localhost:4000"
[iteration 2] model calls two more tools (look around, etc.)
[iteration 3] model returns stop_reason: end_turn → loop exits, turn_end
```

Three iterations, three round trips to the API, one final answer. Nothing
about this shape changes whether the task takes 1 iteration or 24 — it's
the same four-step cycle from §1, just repeated.

---

## 6. `max_iterations`, `max_turn_tokens`, and what "stop" really means

There are exactly **three** ways a turn can end, and only one of them means
"the model actually finished":

| Way it ends | Trigger | What happens |
|---|---|---|
| **Completed** | model returns `stop_reason: "end_turn"` (no more tool calls) | `extract_text`, save as `:assistant` message, return it — this is the normal case |
| **`max_iterations` reached** | `@iteration >= max_iterations` (default **25**) | one final wind-down call, see below |
| **`max_turn_tokens` reached** | `context.turn_tokens >= max_turn_tokens` (default **60,000**, a separate spend budget — matches the example session log above) | same wind-down call |

All three defaults (`max_iterations: 25`, `max_turn_tokens: 60_000`,
`max_output_tokens: 1024`) live in one place, `Config#agent_max_iterations`
/ `#agent_max_turn_tokens` / `#agent_max_output_tokens`
(`ruby/12_context/lib/boukensha/config.rb`), each reading an optional
override from an `agent:` block in `settings.yaml`:

```yaml
agent:
  max_iterations: 25        # 0 or omitted → the built-in default (25); explicit 0 disables the ceiling
  max_turn_tokens: 60000     # same "0/omit = default, negative-or-zero after that = disabled" rule
  max_output_tokens: 1024
```

(Earlier iterations — `05_agent_loop` through roughly `09_global_executable`
— read these same three numbers per-task, off `tasks.player.max_iterations`
etc. instead. By `12_context`, the whole `Tasks::Player` class is gone and
they moved to this single top-level `agent:` block — a good example of
"the current head is the source of truth, not an earlier step's README.")

**Both limits are checked at the *top* of each loop pass, before starting a
new iteration** — so they never interrupt a tool call already in flight,
they only stop a *new* one from starting.

### Why a limit at all

Nothing guarantees a model calls tools a bounded number of times — a model
can get stuck in a call/re-call cycle, or a task can just genuinely need
more turns than is reasonable to keep paying for. `max_iterations` is the
circuit breaker on "number of actions taken"; `max_turn_tokens` is a second,
independent circuit breaker on "money/tokens spent," because a handful of
iterations against a huge tool result can burn far more tokens than 25 tiny
ones. Either one tripping ends the turn the same way.

### The important part: **a limit is a trigger, not a hard cap**

Hitting a limit does **not** raise an exception or truncate mid-thought. It
swaps to exactly **one more** API call, with tools turned off entirely and
a short directive telling the model to wrap up instead of act:

```ruby
WRAP_UP_DIRECTIVE = <<~MSG.strip
  You have reached your action limit for this turn. Do not call any more tools.
  Briefly summarize what you accomplished, what is still unfinished, and the
  single next action you would take.
MSG

def wrap_up(reason)
  @context.add_message(:user, WRAP_UP_DIRECTIVE)
  response = @client.call(tools: [], max_output_tokens: WRAP_UP_OUTPUT_TOKENS)  # tools: [] — no more calls possible
  text = extract_text(...)
  text = fallback_message(reason) if text.strip.empty?
  @context.add_message(:assistant, text)
  text
end
```

So a turn **always** ends with a real (if incomplete) reply the caller can
show a user — never a stack trace, never silence. This wrap-up call:

- runs *outside* the counted loop (doesn't increment `@iteration`, doesn't
  re-check either limit, so it can't re-trigger itself),
- still counts its own tokens toward the turn's reported total,
- falls back to a deterministic string (`"I reached my 25-action limit for
  this turn before finishing (max_iterations). Ask me to continue and I'll
  pick up from here."`) if even *that* call fails (`ApiError`) — the one
  case where the loop guarantees output without calling the API at all.

`0` (or `nil`) for either limit disables it — an explicit opt-out, not a
default.

---

## 7. "Observation" — seeing what happened after each iteration

If you've seen the ReAct pattern (Thought → Action → Observation, repeat)
described elsewhere, here's the exact mapping onto Boukensha's names:

| ReAct term | Boukensha's name for it | Where it lives |
|---|---|---|
| Thought | the text part of a `response` (before/alongside a tool call) | `content` blocks with `"type"=>"text"`, logged as `plan` or `response` |
| Action | a `tool_call` | the `tool_use` block dispatched via `Registry#dispatch` |
| **Observation** | a `tool_result` | the tool's return value, added to `Context` as a `:tool_result` message |

The **observation is not shown to a human by default** — `Agent` never
`puts`s anything (see [`week1_logger_session_summary.md`](week1_logger_session_summary.md)).
It's written to two places: back into `Context#messages` (so the *model*
sees it on the next iteration), and to a structured log line (so *you* can
see it after the fact, or live). Four ways to actually look at it:

### a) In-process — inspect `Context` directly

The most direct way, useful in a REPL or a script:

```ruby
agent.run
ctx.messages.each { |m| puts m }
# #<Message role=user content=Read the README.md file and summarise...>
# #<Message role=assistant content=[{"type"=>"tool_use","name"=>"read_file",...}]>
# #<Message role=tool_result [toolu_01Abc] content=# Boukensha\n\nA framework for...>
# #<Message role=assistant content=This framework lets you build an agent...>
```

### b) The session log — one JSON object per line, forever

Every run writes to `.boukensha/sessions/<session-id>.jsonl` (see
`06_the_logger`). This is a **real excerpt**, taken directly from a session
in this repo, showing exactly what an iteration → tool call → observation
looks like on disk:

```jsonc
{"phase":"iteration","n":1,"max":25, ...}
{"phase":"response","text":"I'll connect to the MUD and take a look around.",
 "stop_reason":"tool_use","usage":{"input_tokens":3377,"output_tokens":98},
 "cost_usd":0.003867, ...}
{"phase":"tool_call","name":"mud_connect","args":{}, ...}
{"phase":"tool_result","name":"mud_connect",
 "result":"already connected to localhost:4000","ok":true,"error":null, ...}
{"phase":"iteration","n":2,"max":25, ...}
 ... (two more tool_call/tool_result pairs this iteration) ...
{"phase":"iteration","n":3,"max":25, ...}
{"phase":"response","text":"...", "stop_reason":"end_turn", ...}
{"phase":"turn_end","reason":"completed","iterations":3,"tokens":11782, ...}
```

Read one live while a run is in progress with `tail -f`:

```bash
tail -f .boukensha/sessions/$(ls -t .boukensha/sessions | head -1)
```

Every phase this file can contain, one row each:

| `phase` | Fires when | Key fields |
|---|---|---|
| `session_start` | once, at the very top | `task`, `model`, `provider`, `max_iterations`, `max_turn_tokens`, `context_window` |
| `turn` / `iteration` | once per user turn / once per loop pass | `n`, `max` |
| `prompt` | right before each API call | `messages`, `tools`, `context_window` |
| `raw` | only when `Boukensha.debug!` is on | the *unparsed* provider response — for debugging `parse_response` itself |
| `reasoning` | a `reasoning`-type content block was present | `text`, `redacted` |
| `plan` | preamble text alongside a tool call | `text` |
| `response` | a normal (non-tool) or wrap-up reply | `text`, `usage`, `stop_reason`, `cost_usd` |
| **`tool_call`** | a tool is about to be dispatched | `name`, `args` — the **action** |
| **`tool_result`** | right after dispatch returns (or raises) | `name`, `result`, `ok`, `error` — **the observation** |
| `limit_reached` | either ceiling trips | `kind` (`"max_iterations"`/`"max_tokens"`), `n`, `max` |
| `compaction` | context got auto-pruned (see `12_context`) | `before`, `dropped`, `context_window` |
| `turn_end` | always, exactly once per turn | `reason` (`"completed"`/`"max_iterations"`/`"max_tokens"`), `iterations`, `tokens` |

### c) `log_viz` — the same log, rendered as a readable transcript

`ruby/log_viz` is a small local web app that reads these `.jsonl` files and
renders them as a chat-style transcript with the `tool_call`/`tool_result`
pairs shown inline, plus a token/cost breakdown per turn. No changes needed
to view a Python-generated session — the log format is language-agnostic.

### d) The TUI — watching it live, not after the fact

`11_tui`'s live progress line subscribes to the logger directly
(`Logger#subscribe`) and shows `Calling tool: mud_connect` /
`Awaiting result…` while an iteration is in flight, then the status line's
token counter updates the instant the `response` event lands. See
[`week1_tui_explained.md`](week1_tui_explained.md).

---

## 8. Cheat sheet

```
register a tool         →  registry.tool(name, description:, parameters:) { |args| ... }
                            (or `tool ...` inside a Boukensha.run/.repl block)
call the agent           →  agent.run                       # runs the whole loop, returns final text
model wants a tool?      →  parsed[:stop_reason] == "tool_use"
model is done?           →  parsed[:stop_reason] == "end_turn"
where a tool actually runs → Registry#dispatch → tool.block.call(**args)
where the result goes    →  Context#messages, as a :tool_result Message (this is "the observation")
loop ceiling (# of actions) → max_iterations (default 25)      — settings.yaml: agent.max_iterations
loop ceiling (spend)     →  max_turn_tokens (default 60,000) — settings.yaml: agent.max_turn_tokens
hitting a ceiling        →  ONE more call, tools: [], wind-down text — never an exception
watch it happen          →  tail -f .boukensha/sessions/<id>.jsonl   (tool_call / tool_result / turn_end)
```

---

## Go deeper

- [`week1_agent_loop_architecture.md`](week1_agent_loop_architecture.md) —
  the terser, more code-grounded companion to this doc; also covers *why*
  every backend implements `parse_response` and its inverse.
- [`week1_agent_loop_port_plan.md`](week1_agent_loop_port_plan.md) — what
  changed going from Ruby to Python for this step.
- [`week1_logger_session_summary.md`](week1_logger_session_summary.md) —
  more on the `.jsonl` log format itself.
- [`week1_context_management_explained.md`](week1_context_management_explained.md) —
  what `compact_if_needed` (called at the top of every `run`) actually does,
  and the three token numbers (`context_window`/`current_tokens`/
  `turn_tokens`) referenced in §6 above.
- [`week1_config_troubleshooting.md`](week1_config_troubleshooting.md),
  entries #15/#16 — real bugs found in this step during review, not just a
  smoke test.
- [`week1_journal.md`](week1_journal.md) — the full week-1 guide this doc is
  one entry in.
