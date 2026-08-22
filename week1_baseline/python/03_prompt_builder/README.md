# 03 · The Prompt Builder (Python port)

Python port of `week1_baseline/ruby/03_prompt_builder`.

Because LLM access, cost, and quality are constantly changing, we want to be
able to switch between multiple LLMs that drive the agent loop. There are
several SDKs that provide access to many LLMs, but in practice we only
really need to focus on top-tier models:

- anthropic family
- openai family
- gemini family
- ollama cloud (e.g. kimi, minimax, llama)

The Prompt Builder serializes `Context` into the exact format each API
expects. `PromptBuilder` delegates to whichever backend you construct it
with. **`PromptBuilder` does not call the API** — it only builds the
payload/headers/URL a real HTTP call would need.

Configuration is task-based, carried forward unchanged from the registry
step: the `player` task owns its provider, model, and prompt override
settings, and `Context` records the task the prompt is being built for.

## New Files

| File | Description |
|---|---|
| `boukensha/prompt_builder.py` | Delegates serialization to the active backend |
| `boukensha/backends/base.py` | Shared backend contract for model validation and model metadata |
| `boukensha/backends/anthropic.py` | Serializes context into the Anthropic API format |
| `boukensha/backends/ollama.py` | Serializes context into the Ollama API format |
| `boukensha/backends/ollama_cloud.py` | Serializes context into the Ollama Cloud API format |
| `boukensha/backends/openai.py` | Serializes context into the OpenAI Chat Completions format |
| `boukensha/backends/gemini.py` | Serializes context into the Gemini `generateContent` format |

`boukensha/config.py` and `boukensha/tasks/*` already carried the
`PROMPTS_DIR` constant and the `provider`/`model`/`system_prompt` task
helpers this step relies on — those were ported ahead of schedule in
`02_the_registry` and needed no changes here.

## How It Works

```
Context (Python objects)
        ↓
PromptBuilder
        ↓
Backend (Anthropic, OpenAI, Gemini, Ollama, or OllamaCloud)
        ↓
API Payload (plain dicts and lists)
        ↓
POST to API
```

## `boukensha.PromptBuilder`

| Member | Description |
|---|---|
| `to_messages()` | Delegates message serialization to the backend |
| `to_tools()` | Delegates tool serialization to the backend |
| `to_api_payload(*, max_output_tokens=1024)` | Assembles the complete payload ready to POST |
| `headers` (property) | Returns the correct headers for the backend |
| `url` (property) | Returns the correct endpoint URL for the backend |

## Backends

Each API has its own conventions for how data is expected. Anthropic and
Gemini are the most alike (system prompt as a top-level field), while
OpenAI and Ollama share the same `function`-wrapped tool schema.

Backends own their supported model table (`MODELS`, a class attribute).
A backend refuses to initialize with an unknown model — `UnsupportedModelError`
is raised at construction time, so `settings.yaml` cannot silently select an
unsupported or misspelled model. Each model entry carries:

| Key | Meaning |
|---|---|
| `context_window` | The model's known token context window |
| `cost_per_million["input"]` | USD input token price per million tokens, when known |
| `cost_per_million["output"]` | USD output token price per million tokens, when known |
| `usage_unit` | `"tokens"`, `"local_compute"`, or `"ollama_cloud_usage"` |
| `usage_level` | Ollama Cloud usage tier, when applicable |

Backend instances expose `context_window`, `input_token_cost_per_million`,
`output_token_cost_per_million`, `usage_unit`, `usage_level`, and
`estimate_cost(*, input_tokens, output_tokens)`. For local Ollama models,
token cost is `0.0`. For Ollama Cloud, public pricing is plan/usage based
rather than token based, so `estimate_cost` returns `None`.

The prices in this step are static tutorial data, current as of June 16,
2026, and should be reviewed whenever the selected model set changes.

### `boukensha.backends.Anthropic`

Talks to `https://api.anthropic.com/v1/messages`. Requires an
`ANTHROPIC_API_KEY`. Supported models are listed in
`boukensha.backends.Anthropic.MODELS`.

### `boukensha.backends.Ollama`

Talks to `http://localhost:11434/api/chat`. Requires `ollama serve` running
locally. No API key needed. Supported models are listed in
`boukensha.backends.Ollama.MODELS`.

### `boukensha.backends.OllamaCloud`

Talks to `https://ollama.com/api/chat`. Requires an `OLLAMA_API_KEY`.
Supported models are listed in `boukensha.backends.OllamaCloud.MODELS`.

### `boukensha.backends.OpenAI`

Talks to `https://api.openai.com/v1/chat/completions`. Requires an
`OPENAI_API_KEY`. Supported models are listed in
`boukensha.backends.OpenAI.MODELS`.

### `boukensha.backends.Gemini`

Talks to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`.
Requires a `GEMINI_API_KEY`. Supported models are listed in
`boukensha.backends.Gemini.MODELS`.

### System Prompt

Anthropic and Gemini send the system prompt as a top-level field, separate
from the messages array. Ollama and OpenAI put it inside the messages array
as a `role: system` message.

```json
// Anthropic
{ "system": "You are a MUD player assistant.", "messages": [ ... ] }

// Gemini
{ "systemInstruction": { "parts": [{ "text": "You are a MUD player assistant." }] }, "contents": [ ... ] }

// Ollama / OpenAI
{ "messages": [ { "role": "system", "content": "You are a MUD player assistant." }, ... ] }
```

### Tool Results

Anthropic wraps tool results in a user message. Ollama and OpenAI use their
own `role: tool` message type (with slightly different identifier fields).
Gemini wraps results in a `functionResponse` part on a `user` message.

```json
// Anthropic
{ "role": "user", "content": [{ "type": "tool_result", "tool_use_id": "toolu_01X", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }] }

// Ollama
{ "role": "tool", "tool_name": "look", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }

// OpenAI
{ "role": "tool", "tool_call_id": "toolu_01X", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }

// Gemini
{ "role": "user", "parts": [{ "functionResponse": { "name": "toolu_01X", "response": { "content": "A damp stone corridor stretches north. Torches flicker on the walls." } } }] }
```

### Tool Definitions

Anthropic uses `input_schema`. Ollama and OpenAI wrap everything in a
`function` envelope with `parameters`. Gemini wraps tools in a
`functionDeclarations` array.

```json
// Anthropic
{ "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "input_schema": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } }

// Ollama / OpenAI
{ "type": "function", "function": { "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "parameters": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } } }

// Gemini
{ "functionDeclarations": [ { "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "parameters": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } } ] }
```

### Message Roles

Anthropic, Ollama, and OpenAI all use `assistant` for the model's turn.
Gemini calls it `model`.

```json
// Anthropic / Ollama / OpenAI
{ "role": "assistant", "content": "Let me take a look around first." }

// Gemini
{ "role": "model", "parts": [{ "text": "Let me take a look around first." }] }
```

## Design considerations (porting notes)

- **`to_messages` arity is deliberately inconsistent across backends —
  ported as-is, not fixed.** `Anthropic.to_messages(messages)` and
  `Gemini.to_messages(messages)` take one argument. `Ollama.to_messages`,
  `OllamaCloud.to_messages`, and `OpenAI.to_messages` take **two**
  (`system, messages`), because those three fold the system prompt into
  the messages array themselves rather than sending it as a separate
  top-level field. `PromptBuilder.to_messages()` always calls
  `backend.to_messages(self.context.messages)` with a single argument, so
  it works for Anthropic/Gemini but raises `TypeError` for
  Ollama/OpenAI/OllamaCloud (mirrors Ruby's `ArgumentError` for the same
  three backends). `PromptBuilder.to_api_payload()` works for all five,
  because each backend's own `to_payload` calls its *own* `to_messages`
  with the correct arity internally. **Treat `to_api_payload()` as the only
  currently-safe `PromptBuilder` entry point for OpenAI/Ollama/OllamaCloud**
  — this is a real, pre-existing asymmetry in the Ruby reference, not a
  Python-specific bug, so it is intentionally not normalized away.
- **`MODELS` is a plain class attribute, not a classmethod override.**
  Ruby enforces "every backend must define `MODELS`" via `const_get(:MODELS)`
  raising `NameError` if missing. Python's equivalent idiom is a class
  attribute a subclass is expected to override — `Base.MODELS` defaults to
  `{}` rather than raising `NotImplementedError`, since forgetting to
  define it fails naturally the first time `validate_model` is called
  against an empty table (every model lookup fails), which is the same
  practical outcome as Ruby's lazy failure, achieved the more idiomatic
  Python way.
- **`headers` and `url` are properties, not methods**, on both the
  backends and `PromptBuilder` — matching Ruby's paren-less no-arg method
  calls and the existing `Context.tool_count`/`turn_count` property
  convention already established in `01_struct_skeleton`/`02_the_registry`.
- **No String/Symbol role branching needed.** Ruby's backends `case` on
  `msg.role` as a Symbol (`:assistant`, `:tool_result`); the Python port's
  `Message.role` is always a plain string (the convention established in
  prior iterations), so backends branch on the string value directly
  (`if msg.role == "tool_result":`) with no conversion step — same
  reasoning as the Registry port's simplified `dispatch`.
- **`backends` is a subpackage, not flattened top-level exports** —
  mirrors the existing `boukensha.tasks` precedent, so
  `boukensha.backends.Anthropic` reads the same way `boukensha.tasks.Player`
  already does.
- **Every backend marks all declared tool parameters as required**,
  unconditionally (`required: list(tool.parameters.keys())`) — there is no
  concept of an optional tool parameter in this iteration, on either
  language's side.
- **Unhandled roles pass through unchanged** on every backend's `else`
  branch — any future role beyond `user`/`assistant`/`tool_result`
  degrades to "treated like plain text," not an error.

## Code layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `boukensha.Config`, including `PROMPTS_DIR` (unchanged from `02_the_registry`) |
| `boukensha/tasks/base.py` | abstract `Base` — `provider`/`model`/`system_prompt` (unchanged) |
| `boukensha/tasks/player.py` | concrete `Player` (unchanged) |
| `boukensha/tool.py` | `boukensha.Tool` dataclass (unchanged) |
| `boukensha/message.py` | `boukensha.Message` dataclass (unchanged) |
| `boukensha/context.py` | `boukensha.Context` class (unchanged) |
| `boukensha/errors.py` | `boukensha.UnknownToolError`, `boukensha.UnsupportedModelError` |
| `boukensha/registry.py` | `boukensha.Registry` (unchanged) |
| `boukensha/prompt_builder.py` | `boukensha.PromptBuilder` |
| `boukensha/backends/` | one module per provider, plus the shared `Base` |
| `boukensha/__init__.py` | top-level exports |
| `prompts/system.md` | default system prompt shipped with the library |
| `examples/example.py` | runnable smoke-test |

## Run

First run — set up the lesson-local virtualenv:

```bash
cd week1_baseline/python/03_prompt_builder
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

Expected output (values from your `.boukensha/`, provider `anthropic`):

```
=== Boukensha Step 3: Prompt Builder ===

Config: #<Boukensha::Config dir=/home/mahdi/claude-code-camp-2026-Q2/.boukensha tasks=player>
Provider: anthropic
Model: claude-haiku-4-5
{
  "model": "claude-haiku-4-5",
  "system": "...",
  "max_tokens": 1024,
  "tools": [ { "name": "look", "input_schema": { ... } }, { "name": "move", "input_schema": { ... } } ],
  "messages": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." },
    { "role": "user", "content": [ { "type": "tool_result", "tool_use_id": "toolu_01X", "content": "..." } ] }
  ]
}
```
