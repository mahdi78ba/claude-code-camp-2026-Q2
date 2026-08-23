# 06 · The Logger (Python port)

Python port of `week1_baseline/ruby/06_the_logger`.

`boukensha.Logger` records each agent run as structured JSON Lines. It is a
file logger, not user-facing display output.

## New Files

| File | Description |
|---|---|
| `boukensha/logger.py` | `boukensha.Logger` — writes one JSONL event per phase of an agent run |

## Updated Files

| File | Change |
|---|---|
| `boukensha/agent.py` | Takes a `logger=` keyword (defaults to a fresh `Logger()`); every phase of `run`/`_wrap_up`/`_handle_tool_calls` now logs instead of `print`-ing |
| `boukensha/__init__.py` | Adds the module-level `get_config()`/`enable_debug()`/`is_debug()`/`enable_quiet()`/`enable_loud()`/`is_quiet()` singleton `Logger` reads; exports `Logger`; drops `LoopError` |
| `boukensha/errors.py` | Drops `LoopError` — unused in either language, and the Ruby reference dropped it in this same step |
| `boukensha/config.py` | Drops `mud_host`/`mud_port`/`mud_username`/`mud_password` — unused since `04_api_client`, and the Ruby reference dropped them in this same step |
| `examples/example.py` | Builds a `Logger` and passes it to `Agent` |

`boukensha/prompt_builder.py` needed no change here — `backend` was already
a plain constructor attribute (`self.backend = backend`), where the Ruby
reference needed a new `attr_reader :backend` to give `Agent._log_response`
the same access.

## Session Logs

Each `Logger` instance creates a session id and writes one log file for that
session:

```text
.boukensha/sessions/<session-id>.jsonl
```

Every line is a complete JSON object with `session_id`, `at`, and `phase`
fields, plus phase-specific data. This keeps logs grep/tail friendly and
machine readable.

```json
{"phase":"session_start","session_id":"20260823T112446Z-32db4da6","at":"2026-08-23T11:24:46+00:00"}
{"phase":"iteration","n":1,"session_id":"20260823T112446Z-32db4da6","at":"2026-08-23T11:24:46+00:00"}
```

Model response lines include the active task, provider, model, normalized
token counts, and estimated USD cost when the backend has token pricing
data:

```json
{"phase":"response","task":"player","provider":"anthropic","model":"claude-haiku-4-5","input_tokens":1000,"output_tokens":100,"cost_usd":0.0015}
```

## Logger API

A plain object with one method per phase:

| Method | Phase | Logs |
|---|---|---|
| `iteration(n=, max=)` | `iteration` | loop counter |
| `limit_reached(kind=, n=, max=)` | `limit_reached` | the iteration ceiling tripping |
| `prompt(messages=, tools=)` | `prompt` | messages, tool names |
| `tool_call(name=, args=)` | `tool_call` | tool name and arguments |
| `tool_result(name=, result=, ok=, error=)` | `tool_result` | tool result, success flag, error message |
| `response(text=, usage=, stop_reason=, task=, backend=)` | `response` | response text, token usage, task/provider/model, estimated cost |
| `turn_end(reason=, iterations=, tokens=)` | `turn_end` | why and how the turn ended |
| `raw(data=)` | `raw` | raw provider response, only when debug is enabled |

The README in `ruby/06_the_logger` documents `prompt(messages:, tools:,
budget:)`, but no `budget` parameter exists in either language's actual
`prompt` method or its only call site (`Agent.run`) — a stale doc claim in
the Ruby reference, not a behavior to replicate. This table matches what
both languages' code actually does.

## Task Configuration

Step 6 uses the same task-based settings shape as `05_agent_loop`:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, the player task reads
`.boukensha/prompts/player/system.md`. Otherwise it falls back to this
step's shipped `prompts/system.md`.

Default usage:

```python
logger = Logger()
agent = Agent(context=ctx, registry=registry, builder=builder,
              client=client, logger=logger)
```

You can also provide a session id or override the destination directory:

```python
Logger(session_id="manual-session")
Logger(dir="/tmp/boukensha-sessions")
```

For compatibility, `log=` still accepts an explicit file path, but normal
iteration usage should write under `.boukensha/sessions`.

## Debug Events

Call `boukensha.enable_debug()` before running the agent to include raw
provider responses:

```python
import boukensha
boukensha.enable_debug()
```

## Design considerations (porting notes)

- **`get_config()`, not `config()`.** Ruby's `Boukensha.config` singleton
  has no naming conflict — `Config` (the class) and `config` (the method)
  are distinct Ruby identifiers. Python does: importing `boukensha.config`
  (the *submodule* that defines the `Config` class) already binds
  `boukensha.config` as an attribute of the `boukensha` package, purely as
  a side effect of Python's import system. A module-level function
  literally named `config` in `__init__.py` would silently overwrite that
  submodule reference — confirmed by testing it directly
  (`import boukensha.config` then returns the function, not the module).
  Named it `get_config()` instead to avoid the collision.
- **`debug!`/`debug?` become `enable_debug()`/`is_debug()`.** Python
  identifiers can't end in `!` or `?`. Same pairing pattern applied to
  `quiet!`/`loud!`/`quiet?` → `enable_quiet()`/`enable_loud()`/
  `is_quiet()`, even though only `get_config()` and `is_debug()` are
  actually read by `Logger` — the quiet/loud trio is unused in this
  iteration in both languages, shipped for parity.
- **`provider_name` ports the already-fixed Ruby version, not a literal
  transliteration of the original.** A generic CamelCase→snake_case
  transform mislabels `backends.OpenAI` as `"open_ai"` (verified directly:
  the same lowercase→uppercase-boundary regex that correctly turns
  `OllamaCloud` into `ollama_cloud` also splits `OpenAI`'s trailing
  acronym). `Logger._provider_name` special-cases
  `isinstance(backend, backends.OpenAI)` ahead of the generic transform,
  mirroring the fix already made to `ruby/06_the_logger/lib/boukensha/logger.rb`
  rather than reintroducing a bug the Ruby side already found and fixed.
- **No off-by-one `../`-count bugs to port**, same conclusion as
  `05_agent_loop`'s porting notes: Python resolves every default path via
  `Path(__file__).resolve()`, not hand-written relative-string literals, so
  the bug class documented repeatedly against the Ruby side
  (`docs/week1_config_troubleshooting.md`) has no Python equivalent.
- **Session id and timestamp use the standard library, no new
  dependency.** `SecureRandom.hex(4)` → `secrets.token_hex(4)`;
  `Time.now.iso8601` → `datetime.now().astimezone().isoformat()` (needs the
  explicit `astimezone()` call — a bare `datetime.now().isoformat()` is
  timezone-naive and won't carry a UTC offset the way Ruby's `iso8601`
  always does).
- **`Logger.close()` is ported but not called anywhere**, matching the
  Ruby reference exactly: harmless for this short-lived example script (the
  OS reclaims the file descriptor at process exit), worth revisiting once a
  longer-lived process (a REPL loop / TUI iteration) can create many
  `Logger` instances in one run.
- **Dropped `mud_*` config properties and `LoopError`.** Both were already
  unused dead code in the Python port (carried forward from
  `04_api_client`/`05_agent_loop` respectively); the Ruby reference dropped
  their equivalents in this same step. Removed here to keep the two
  languages structurally in sync — not a logging feature, just unrelated
  cleanup that landed in the same upstream snapshot.

## Code layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `boukensha.Config` (no `mud_*` properties as of this step) |
| `boukensha/tasks/base.py` | abstract `Base` (unchanged) |
| `boukensha/tasks/player.py` | concrete `Player` (unchanged) |
| `boukensha/tool.py` | `boukensha.Tool` dataclass (unchanged) |
| `boukensha/message.py` | `boukensha.Message` dataclass (unchanged) |
| `boukensha/context.py` | `boukensha.Context` class (unchanged) |
| `boukensha/errors.py` | `UnknownToolError`, `UnsupportedModelError`, `ApiError` |
| `boukensha/registry.py` | `boukensha.Registry` (unchanged) |
| `boukensha/prompt_builder.py` | `boukensha.PromptBuilder` (unchanged) |
| `boukensha/backends/` | one module per provider (unchanged) |
| `boukensha/client.py` | `boukensha.Client` (unchanged) |
| `boukensha/agent.py` | `boukensha.Agent` — the loop, now logging every phase |
| `boukensha/logger.py` | `boukensha.Logger` — the session logger |
| `boukensha/__init__.py` | top-level exports + the `get_config`/debug/quiet singleton |
| `prompts/system.md` | default system prompt shipped with the library (unchanged) |
| `examples/example.py` | runnable smoke-test, drives a live agent loop with logging on |

## Run

First run — set up the lesson-local virtualenv:

```bash
cd week1_baseline/python/06_the_logger
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
to the configured provider, and writes a real `.boukensha/sessions/*.jsonl`
file as a side effect.

## Run via the repo's launcher

```sh
./week1_baseline/bin/python/06_the_logger
```

## Viewing the logs

`week1_baseline/ruby/log_viz` (a small Sinatra app) reads
`.boukensha/sessions/*.jsonl` directly — the format is language-agnostic,
so a session generated by this Python example renders exactly like one
generated by `ruby/06_the_logger`, no `log_viz` changes needed:

```sh
cd week1_baseline/ruby/log_viz
bundle exec ruby bin/log_viz
```

Then open <http://localhost:4567>.
