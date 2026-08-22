# 04 · The API Client (Python port)

Python port of `week1_baseline/ruby/04_api_client`.

The API Client takes the payload assembled by `PromptBuilder` and sends it
to the API. One HTTP POST, one response. No tool loop yet — just proving
the round trip works.

## New Files

| File | Description |
|---|---|
| `boukensha/client.py` | Makes the HTTP request and parses the response |

## Updated Files

| File | Change |
|---|---|
| `boukensha/errors.py` | Added `ApiError` for failed HTTP requests |
| `boukensha/__init__.py` | Exports `Client` and `ApiError` |
| `prompts/system.md` | New default system prompt text |
| `examples/example.py` | Swaps the toy `look`/`move` tools for real filesystem tools and makes a live API call |

`boukensha/config.py` and `boukensha/tasks/base.py` needed **no changes** —
both fixes the Ruby reference makes in this step (`settings.yaml` error
text, a defensive `isinstance` guard in `fetch`) were already present in
the Python port, carried over from `03_prompt_builder`. `boukensha/backends/*.py`
are also unchanged — no backend logic changed in this step on the Ruby side.

## How It Works

```
PromptBuilder
      ↓
Client
      ↓
POST to API endpoint
      ↓
Raw JSON response
```

## `boukensha.Client`

| Method | Description |
|---|---|
| `call(*, max_output_tokens=1024)` | POSTs the payload and returns the parsed JSON response |

## Task Configuration

This step uses the task-based configuration carried forward unchanged from
the earlier baseline steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, Boukensha reads
`.boukensha/prompts/player/system.md`. Otherwise it falls back to this
step's shipped `prompts/system.md`.

Each backend validates the configured model at construction time.
Unsupported model names raise `UnsupportedModelError`, and supported models
expose backend-owned metadata such as `context_window`, `usage_unit`, and
token cost estimates for later logging steps.

## No Dependencies

`Client` uses Python's standard `urllib.request` module. No pip packages,
no `pip install` beyond what `00_config` already needed (`PyYAML`,
`python-dotenv`). This mirrors the Ruby reference's own choice to use
stdlib `net/http` instead of a gem — the HTTP call itself is trivial and
should be visible, not hidden behind a library.

Ruby's `net/http` needs a commented-out workaround for
`OpenSSL::X509::DEFAULT_CERT_FILE` resolving to a macOS-only path that
doesn't exist on Linux/WSL2 — see the Ruby README's "OpenSSL Certificate"
section. **`urllib.request` has no equivalent caveat**: Python's `ssl`
module picks up the OS's default CA trust store automatically on every
platform this project targets, so there's nothing to configure or work
around here. This is a place where the Python port is genuinely simpler
than the Ruby reference, not just differently-shaped.

## What the Response Looks Like

The raw response shape differs between backends. This is what you get back
from `client.call()` before any processing:

### Anthropic
```json
{
  "id": "msg_01XY",
  "type": "message",
  "role": "assistant",
  "content": [
    { "type": "text", "text": "Sure, let me read that file." }
  ],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 42, "output_tokens": 18 }
}
```

### Ollama
```json
{
  "model": "llama3.2",
  "message": {
    "role": "assistant",
    "content": "Sure, let me read that file."
  },
  "done_reason": "stop",
  "done": true
}
```

When the model wants to call a tool the response looks different.
Anthropic uses `stop_reason: "tool_use"` and adds a `tool_use` block to
`content`. Ollama adds a `tool_calls` array to `message`. Handling those
differences is the job of step 5 — the Agent Loop.

## Considerations

**The client raises `ApiError` on failure.** A non-2xx response means
something went wrong — bad API key, malformed payload, server error.
Boukensha surfaces this explicitly rather than returning a confusing
`None` or partial response.

**`urlopen` raises where `Net::HTTP` returns.** Ruby's `Net::HTTP#request`
never raises for a non-2xx status — the caller checks
`response.is_a?(Net::HTTPSuccess)` after the fact. Python's
`urllib.request.urlopen` raises `urllib.error.HTTPError` (itself a subclass
of `URLError`) for any status ≥ 400, and wraps lower-level
connection/timeout/SSL failures in `urllib.error.URLError`. `Client.call`'s
two `except` clauses map onto Ruby's two retry paths (retryable status
codes vs. transient connection errors) using each language's own
error-surfacing convention — catching the raw Python exception types a
literal translation might reach for (`socket.timeout`, `ConnectionError`,
`ssl.SSLError`) would never match, since `urlopen` always wraps them in
`URLError` first.

**Two independent, identically-bounded retry paths.** Retryable HTTP
status codes (408/409/429/500/502/503/504) and transient network errors
(`URLError`) are each retried up to `MAX_RETRIES = 3` times with
exponential backoff (`BASE_RETRY_DELAY * 2 ** (attempt - 1)` → 0.5s, 1s,
2s) — a real `time.sleep` in the request path. A non-retryable error (e.g.
a 400/401/403, surfaced as `HTTPError` but not in
`RETRYABLE_STATUS_CODES`) is not retried and raises `ApiError` immediately.

## Design considerations (porting notes)

Carried forward from `03_prompt_builder`, unchanged in this step (no
backend logic changed in the Ruby reference):

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
  with the correct arity internally, which is exactly the entry point
  `Client.call` uses — **`Client` never triggers this gap.**
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
  `Message.role` is always a plain string, so backends branch on the
  string value directly (`if msg.role == "tool_result":`) with no
  conversion step.
- **`backends` is a subpackage, not flattened top-level exports** —
  mirrors the existing `boukensha.tasks` precedent, so
  `boukensha.backends.Anthropic` reads the same way `boukensha.tasks.Player`
  already does.
- **`Config.PROMPTS_DIR` and the example's `BOUKENSHA_DIR` are both
  computed dynamically** (`Path(__file__).resolve()...`), not via a
  hand-written `../`-count string. This sidesteps the class of off-by-one
  bugs the Ruby side hit repeatedly across iterations (documented in
  `docs/week1_config_troubleshooting.md`, entries #4/#8/#10/#11/#12/#13) —
  nothing to audit here, by construction.

New in this step:

- **`urllib.error.HTTPError` before `urllib.error.URLError`.** `HTTPError`
  is a subclass of `URLError`, so the `except` clauses in `Client.call`
  must handle `HTTPError` first — catching `URLError` first would also
  catch every `HTTPError` and misroute non-2xx responses into the
  transient-retry path instead of the status-code-based one.

## Code layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `boukensha.Config`, including `PROMPTS_DIR` (unchanged) |
| `boukensha/tasks/base.py` | abstract `Base` — `provider`/`model`/`system_prompt` (unchanged) |
| `boukensha/tasks/player.py` | concrete `Player` (unchanged) |
| `boukensha/tool.py` | `boukensha.Tool` dataclass (unchanged) |
| `boukensha/message.py` | `boukensha.Message` dataclass (unchanged) |
| `boukensha/context.py` | `boukensha.Context` class (unchanged) |
| `boukensha/errors.py` | `UnknownToolError`, `UnsupportedModelError`, `ApiError` |
| `boukensha/registry.py` | `boukensha.Registry` (unchanged) |
| `boukensha/prompt_builder.py` | `boukensha.PromptBuilder` (unchanged) |
| `boukensha/backends/` | one module per provider, plus the shared `Base` (unchanged) |
| `boukensha/client.py` | `boukensha.Client` — the HTTP request/retry logic |
| `boukensha/__init__.py` | top-level exports |
| `prompts/system.md` | default system prompt shipped with the library |
| `examples/example.py` | runnable smoke-test, makes a live API call |

## Run

First run — set up the lesson-local virtualenv:

```bash
cd week1_baseline/python/04_api_client
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

**This example makes a real, live HTTP request** to the configured
provider — unlike `03_prompt_builder`, which only built the payload.
Running it against `anthropic`/`openai`/`gemini`/`ollama_cloud` consumes
real API usage.

Expected output (values from your `.boukensha/`, provider `anthropic`):

```
=== Boukensha Step 4: API Client ===

Config: #<Boukensha::Config dir=/home/mahdi/claude-code-camp-2026-Q2/.boukensha tasks=player>
Provider: anthropic
Model: claude-haiku-4-5
Sending request to https://api.anthropic.com/v1/messages...

Raw response:
{
  "id": "msg_01...",
  "type": "message",
  "role": "assistant",
  "content": [ { "type": "tool_use", "name": "list_directory", "input": { "path": "." }, "id": "toolu_01..." } ],
  "stop_reason": "tool_use",
  "usage": { "input_tokens": ..., "output_tokens": ... }
}
```

## Run via the repo's launcher

```sh
./week1_baseline/bin/python/04_api_client
```
