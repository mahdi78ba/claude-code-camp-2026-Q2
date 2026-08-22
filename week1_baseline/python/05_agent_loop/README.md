# 05 · The Agent Loop (Python port)

Python port of `week1_baseline/ruby/05_agent_loop`.

The Agent Loop is the heart of Boukensha. Everything built before this — the
structs, the registry, the prompt builder, the client — was setup. The loop
is where the agent actually does work.

## New Files

| File | Description |
|---|---|
| `boukensha/agent.py` | The agent loop — sends requests, dispatches tools, and knows when to stop |

## Updated Files

| File | Change |
|---|---|
| `boukensha/errors.py` | Added `LoopError`, reserved for runaway-agent conditions |
| `boukensha/__init__.py` | Exports `Agent` and `LoopError` |
| `boukensha/tasks/base.py` | Added `max_iterations`/`max_output_tokens` class methods (defaults `25`/`1024`) |
| `boukensha/prompt_builder.py` | `to_api_payload` gains a `tools=` keyword; added `parse_response`, delegating to the backend |
| `boukensha/client.py` | `call` gains a `tools=` keyword, threaded to `to_api_payload` |
| `boukensha/backends/*.py` | `to_payload` gains `tools=`; every backend gains `parse_response`; four of five gain a private `_assistant_message`/`_assistant_parts` inverse |
| `examples/example.py` | Wires up an `Agent` instead of one bare `client.call()` |

`boukensha/context.py`, `message.py`, `tool.py`, `registry.py`,
`backends/base.py`, `config.py`, and `tasks/player.py` needed **no
changes** — byte-identical to `04_api_client`'s copies on the Ruby side, so
nothing to port.

## How It Works

```
send messages to API
        ↓
stop_reason == "tool_use"?
    yes → extract tool calls
        → dispatch each tool via Registry
        → inject results as tool_result messages
        → go back to top
    no  → return final text response
```

## `boukensha.Agent`

| Method | Description |
|---|---|
| `run()` | Starts the loop and returns the final text response when the agent is done |

## Every Backend Speaks the Same Normalized Shape

Five providers means five different response formats — Anthropic nests
tool calls inside `content`, Ollama puts them in `message.tool_calls`,
OpenAI nests them under `choices[0].message.tool_calls`, and Gemini calls
them `functionCall` parts. Rather than teach the agent loop about each of
these, every backend implements `parse_response`, converting its raw
response into one common shape:

```python
{
    "stop_reason": "tool_use" | "end_turn",
    "content": [
        {"type": "text", "text": "..."},
        {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
    ],
}
```

`Agent` only ever sees this shape — it calls
`self.builder.parse_response(response)`, which delegates to the backend,
and never inspects a raw provider response.

The conversion also runs in reverse. When the conversation history is
replayed on the next request, Ollama, Ollama Cloud, OpenAI, and Gemini each
rebuild a provider-specific assistant message from the normalized `content`
blocks via a private `_assistant_message` (or `_assistant_parts`) method —
the inverse of `parse_response`. Anthropic's `content` list doubles as both
the normalized shape and the wire format, so it needs no extra conversion.

**Tool call IDs aren't universal.** Anthropic and OpenAI assign every tool
call a unique `id`, echoed back in the `tool_result`. Ollama, Ollama Cloud,
and Gemini don't assign call ids at all — those backends reuse the tool's
`name` as its `id` and match the `tool_result` back to the call by name.

## Task Configuration

This step uses the task-based configuration introduced in the earlier
baseline steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
    max_iterations: 25
    max_output_tokens: 1024
```

When `prompt_override.system` is true, Boukensha reads
`.boukensha/prompts/player/system.md`. Otherwise it falls back to this
step's shipped `prompts/system.md`. `max_iterations` controls model
round-trips per turn before wind-down, and `max_output_tokens` is passed to
each model reply.

Every backend still takes a `model=` keyword argument; `examples/example.py`
gets both provider and model from `tasks.player`, then builds the matching
backend. The backend validates the model at construction time and exposes
metadata such as `context_window`, `usage_unit`, and token cost estimates
for later logging steps.

## What the Loop Looks Like

Running the example produces output like this:

```
=== Boukensha Step 5: Agent Loop ===

[iteration 1/25]
  tool call → read_file({'path': 'README.md'})
  tool result → # 05 · The Agent Loop (Python port)...
[iteration 2/25]

=== FINAL RESPONSE ===
Here are the files in the current directory: README.md, examples, boukensha.
The contents of README.md are...
```

## Considerations

**The assistant message must be stored before the tool result.** The
Anthropic API requires the assistant's `tool_use` block to appear in the
message history before its corresponding `tool_result`. `Agent._handle_tool_calls`
handles this by calling `context.add_message("assistant", content)` before
looping over the tool calls — get the order wrong and the API rejects the
request.

**The model can call multiple tools in one turn.** The loop handles this by
iterating over all `tool_use` blocks in a single response before making the
next API call.

**`max_iterations` is a turn ceiling, not a hard cap.** A poorly prompted
agent can loop forever if the model keeps calling tools. Boukensha stops
starting new work after `max_iterations` (25 by default) and makes one
short wrap-up call with `tools=[]`. This keeps the turn bounded while still
returning a useful final response.

**The agent has no way to stop itself.** The model signals it is done via
`stop_reason: "end_turn"`. Boukensha watches for that signal and exits the
loop. The agent never decides unilaterally to stop.

## Design considerations (porting notes)

- **No `args.transform_keys(&:to_sym)` equivalent needed before tool
  dispatch.** Ruby's keyword-splat requires symbol keys, so
  `handle_tool_calls` converts the model-supplied `input` hash's string
  keys to symbols before calling `tool.block.call(**args)`. Python's `**`
  unpacking accepts a plain string-keyed dict directly (`registry.dispatch`
  already did `tool.block(**(args or {}))` from `04_api_client` onward), so
  `Agent._handle_tool_calls` passes the parsed `input` dict straight
  through with no conversion step — a case where a literal translation
  would have added dead code.
- **`respond_to?` becomes `hasattr`.** `_resolve_max_iterations`/
  `_resolve_max_output_tokens` check
  `hasattr(self.context.task, "max_iterations")` in place of Ruby's
  `@context.task.respond_to?(:max_iterations)` — same "does this task class
  define it" guard, idiomatic per language. In practice `Tasks::Player`
  (Ruby) and `Player` (Python) both always define it via `Base`, so this
  guard is defensive rather than load-bearing today.
- **Private helper methods use a leading underscore** (`_resolve_max_iterations`,
  `_call_opts`, `_wrap_up`, `_fallback_message`, `_extract_text`,
  `_handle_tool_calls`), matching the existing convention from
  `backends/base.py`'s `_configure_model` rather than Ruby's `private`
  keyword, which has no direct Python equivalent.
- **`LoopError` is ported but unused**, exactly mirroring the Ruby
  reference: `Boukensha::LoopError` is declared in `errors.rb` but never
  raised anywhere in `agent.rb` — the iteration ceiling is handled by
  returning a wind-down response, not by raising. Kept for parity in case a
  later iteration starts using it.
- **The `../`-count path bugs the Ruby side hit in this iteration don't
  apply here.** `examples/example.py` already resolves `BOUKENSHA_DIR` via
  `Path(__file__).resolve().parents[4]` (computed, not hand-counted), so
  neither of the two off-by-one `../` bugs documented in
  `docs/week1_config_troubleshooting.md` (entries #15 and #16, both in
  `ruby/05_agent_loop`) has a Python equivalent to fix.

## Code layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `boukensha.Config`, including `PROMPTS_DIR` (unchanged) |
| `boukensha/tasks/base.py` | abstract `Base` — now also `max_iterations`/`max_output_tokens` |
| `boukensha/tasks/player.py` | concrete `Player` (unchanged) |
| `boukensha/tool.py` | `boukensha.Tool` dataclass (unchanged) |
| `boukensha/message.py` | `boukensha.Message` dataclass (unchanged) |
| `boukensha/context.py` | `boukensha.Context` class (unchanged) |
| `boukensha/errors.py` | `UnknownToolError`, `UnsupportedModelError`, `ApiError`, `LoopError` |
| `boukensha/registry.py` | `boukensha.Registry` (unchanged) |
| `boukensha/prompt_builder.py` | `boukensha.PromptBuilder` — now also `parse_response` |
| `boukensha/backends/` | one module per provider — now also `parse_response` (+ round-trip helpers) |
| `boukensha/client.py` | `boukensha.Client` — `call` now accepts `tools=` |
| `boukensha/agent.py` | `boukensha.Agent` — the loop |
| `boukensha/__init__.py` | top-level exports |
| `prompts/system.md` | default system prompt shipped with the library (unchanged) |
| `examples/example.py` | runnable smoke-test, drives a live multi-turn agent loop |

## Run

First run — set up the lesson-local virtualenv:

```bash
cd week1_baseline/python/05_agent_loop
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then run the example directly:

```bash
.venv/bin/python examples/example.py
```

Only the provider selected by `tasks.player.provider` in
`.boukensha/settings.yaml` needs credentials — `os.environ["X_API_KEY"]`
raises `KeyError` immediately if that provider's key is missing, mirroring
Ruby's `ENV.fetch` strictness. `ollama` needs no key at all (it talks to a
local `ollama serve` process).

**This example makes real, live HTTP requests** — one per loop iteration —
to the configured provider. Running it against
`anthropic`/`openai`/`gemini`/`ollama_cloud` consumes real API usage.

## Run via the repo's launcher

```sh
./week1_baseline/bin/python/05_agent_loop
```
