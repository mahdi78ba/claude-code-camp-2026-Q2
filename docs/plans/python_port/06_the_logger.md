# Python Port Plan — The Logger (`06_the_logger`)

Baseline for this port is `python/05_agent_loop`, already copied verbatim into
`python/06_the_logger` (`.venv/`, `__pycache__/` excluded — machine-local,
regenerated on install). This plan lists only the delta needed to bring that
copy up to `ruby/06_the_logger`, as committed (includes the off-by-one `../`
fixes and the `provider_name` OpenAI-mislabeling fix already made to the Ruby
side in this iteration).

## What actually changed in Ruby (05 → 06)

```
$ diff -rq ruby/05_agent_loop ruby/06_the_logger
Only in ruby/06_the_logger/lib/boukensha: logger.rb
Files .../lib/boukensha/agent.rb differ
Files .../lib/boukensha/config.rb differ
Files .../lib/boukensha/errors.rb differ
Files .../lib/boukensha/prompt_builder.rb differ
Files .../lib/boukensha.rb differ
Files .../examples/example.rb differ
Files .../README.md differ
```

1. **New `lib/boukensha/logger.rb`** — `Boukensha::Logger`. One method per
   run phase (`iteration`, `limit_reached`, `turn_end`, `prompt`, `tool_call`,
   `tool_result`, `response`, `raw`), each appending one JSON object (plus
   `session_id`/`at`) to `.boukensha/sessions/<session-id>.jsonl`. `response`
   also computes normalized token counts, provider/model/task labels, and
   `cost_usd` via the backend's `estimate_cost`.

2. **`lib/boukensha/agent.rb`** — wired up to a `logger:` (default
   `Logger.new`), replacing the `puts` debug lines:
   - `run`: logs `limit_reached` before the wind-down return; logs
     `iteration` and `prompt` at the top of each loop pass; logs `raw` right
     after the client call; on natural completion, extracts text, calls the
     new `log_response`, then `turn_end(reason: "completed", ...)`.
   - `wrap_up`: calls `log_response` and `turn_end(reason:, ...)` on both the
     success path and the `ApiError` rescue path.
   - `handle_tool_calls(content, response)` — now takes `response` too;
     logs the assistant's reasoning text (or a `"(tool use — N calls)"`
     placeholder) via `log_response` before dispatching; wraps
     `@registry.dispatch` in a rescue so a tool exception is logged as
     `tool_result(ok: false, error:)` instead of propagating.
   - New private `log_response(text:, response:)` (builds the `response`
     log call from the raw response + `@context.task` + `@builder.backend`)
     and `normalized_usage(response)` (reads `response["usage"]` →
     `response["usageMetadata"]` → Ollama's flat
     `prompt_eval_count`/`eval_count` keys, in that order).

3. **`lib/boukensha.rb`** — added a module-level singleton surface used by
   `Logger`: `Boukensha.config` (memoized `Config.new`), `Boukensha.debug!`
   / `Boukensha.debug?`, and (unused by `Logger`, shipped anyway)
   `Boukensha.quiet!` / `Boukensha.loud!` / `Boukensha.quiet?`. Also adds the
   `require_relative "boukensha/logger"` and an explicit
   `require_relative "boukensha/backends/base"` (already transitively
   required by each backend file — harmless, no behavior change).

4. **`lib/boukensha/prompt_builder.rb`** — added `attr_reader :backend` so
   `Agent#log_response` can read `@builder.backend`.

5. **`lib/boukensha/config.rb`** — dropped `mud_host` / `mud_port` /
   `mud_username` / `mud_password`. Whitespace-only alignment change on
   `@dir`, otherwise untouched.

6. **`lib/boukensha/errors.rb`** — dropped `LoopError` (it was never
   raised anywhere in `05_agent_loop` either — dead code removed, not a
   behavior change).

7. **`examples/example.rb`** / **`README.md`** — example now builds a
   `Logger` and passes it to `Agent.new`; README rewritten for Step 6 (see
   `ruby/06_the_logger/README.md`).

Items 5 and 6 are **not** logging features — they're unrelated cleanup that
happened to land in the same template snapshot. Flagged separately below
under "Judgment calls" rather than silently folded into the logging work.

## Cross-check against the current Python tree

Confirms which parts of the Ruby diff Python already handles differently
(and doesn't need porting) vs. what's genuinely new:

- **No off-by-one `../` bug class to port.** Ruby's `BOUKENSHA_DIR`/
  `PROMPTS_DIR` fixes (this iteration's entries #19/#22 in
  `docs/week1_config_troubleshooting.md`) are artifacts of hand-written
  relative-string literals. Python already resolves both via
  `Path(__file__).resolve()` (`config.py:26`, `example.py:18-19`) — no
  string-literal `../` count exists to get wrong. Nothing to change here.
- **`PromptBuilder.backend` already exists** (`prompt_builder.py:14`,
  a plain constructor attribute) — Ruby needed a new `attr_reader`, Python
  didn't.
- **`errors.py` already has `LoopError`**, added during the `05_agent_loop`
  port with a docstring that already anticipates it being unused (`"Not
  currently raised — Agent.run handles the iteration ceiling..."`). See
  "Judgment calls" below for whether to drop it now that Ruby has.
- **`config.py`'s `mud_host`/`mud_port`/etc. already have the entry #14 fix**
  (`is None` checks, not `or`-defaulting). See "Judgment calls" for whether
  to drop them now that Ruby has.
- **Backend model tables / `parse_response` / `estimate_cost` / `usage_unit`
  / `usage_level` / `context_window`** — all already present on
  `backends/base.py` and each concrete backend from the `05_agent_loop`
  port. Nothing new needed for `Logger.response`'s cost/usage math.
- **`requirements.txt`** — no new third-party dependency. The session-id
  suffix Ruby gets from `SecureRandom.hex(4)` has a direct stdlib
  equivalent: `secrets.token_hex(4)`.

## Files to add / change in Python

### 1. `boukensha/logger.py` — new, ported from `lib/boukensha/logger.rb`

Straight per-method port. Notable translation points, not literal renames:

- `File.open(path, "a")` + `puts`/`flush` → open in `"a"` mode
  (`encoding="utf-8"`) and either flush after every `write` or open with
  `buffering=1` (line-buffered) — match Ruby's guarantee that every event is
  durable on disk immediately, not just at process exit.
- `Time.now.iso8601` → `datetime.now().astimezone().isoformat()` (needs an
  explicit UTC-offset-aware timestamp — bare `datetime.now().isoformat()`
  is naive and won't match the `+HH:MM`-suffixed shape the README/log_viz
  examples show).
- `SecureRandom.hex(4)` → `secrets.token_hex(4)`; session id format stays
  `f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"`.
- `serialize_message` — Ruby's `Message#role`/`#content` → Python's
  `Message` dataclass fields, same shape (`{"role": ..., "content": ...}`).
- `provider_name(backend)` — **port the already-fixed version**, not a
  naive transliteration of the original buggy regex:
  ```python
  import re

  def _provider_name(backend):
      if backend is None:
          return None
      if isinstance(backend, backends.OpenAI):
          return "openai"
      name = type(backend).__name__
      return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
  ```
  Verify against all five backend classes the same way the Ruby fix was
  verified (entry #20): `Anthropic`→`anthropic`, `OpenAI`→`openai` (via the
  special case), `Gemini`→`gemini`, `Ollama`→`ollama`,
  `OllamaCloud`→`ollama_cloud`.
- `task_name(task)` — Ruby's `task&.respond_to?(:task_name)` → Python:
  `task.task_name() if hasattr(task, "task_name") else (str(task) if task else None)`.
  `Context.task` is a *class* (e.g. `Player`), and `task_name` is a
  `@classmethod` — call it, don't just check for the attribute.
- `usage_tokens`/`first_integer` — port the fallback-key search as-is
  (`input_tokens`/`prompt_tokens`/`promptTokenCount`/`prompt_eval_count`,
  and the output equivalents); Python's `dict.get` + a
  `try: int(value) except (TypeError, ValueError): None` mirrors Ruby's
  `Integer(value) rescue ArgumentError, TypeError`.
- `estimate_cost(backend, tokens)` — call `backend.estimate_cost(...)` only
  when both token counts are present, same as Ruby.
- `close()` — expose it (mirrors Ruby's unused-but-present method; see
  entry #20's "also noticed, not changed" note — still not called by
  `Agent`/`example.py` in this port either, same scope decision as Ruby).

### 2. `boukensha/agent.py` — wire up the logger

Port `agent.rb`'s diff onto the current `Agent` 1:1:
- `__init__`: add `logger=None` kwarg; default it internally
  (`self.logger = logger if logger is not None else Logger()` — Python
  can't use a mutable-looking default-arg expression the way Ruby's
  `logger: Logger.new` default does, but the effect is identical: a fresh
  `Logger` per `Agent` unless one is passed in).
- `run`: log `limit_reached` before `return self._wrap_up(...)`; log
  `iteration` and `prompt` each pass; log `raw` right after
  `self.client.call(...)`; on the non-tool-use branch, extract text, call
  `self._log_response(...)`, log `turn_end(reason="completed", ...)`, then
  return.
- `_wrap_up`: on success, fall back to `_fallback_message` if the text is
  blank, then `_log_response` + `turn_end(reason=reason, ...)` before
  returning; on `ApiError`, log `turn_end` there too before returning the
  fallback message.
- `_handle_tool_calls(self, content, response)` — gains the `response`
  param; compute `tool_calls` up front, log the reasoning/placeholder text
  via `_log_response`, then wrap `self.registry.dispatch(...)` in
  `try/except Exception` so a tool failure logs
  `tool_result(ok=False, error=str(e))` and still injects an
  `"ERROR: {type(e).__name__}: {e}"` tool-result message, matching Ruby's
  `rescue StandardError`.
- New `_log_response(self, *, text, response)` and
  `_normalized_usage(self, response)`, direct translations of the Ruby
  private methods (dict `.get` chained the same way: `usage` →
  `usageMetadata` → the two flat Ollama keys).
- Remove the two `print(...)` debug lines this replaces
  (`[iteration ...]` and the tool call/result prints) — same as Ruby
  dropping its `puts` calls in favor of `@logger.*`.

### 3. `boukensha/__init__.py` — module-level `config`/`debug` surface

Ruby's `Boukensha` module gains `config`, `debug!`, `debug?`, `quiet!`,
`loud!`, `quiet?` as module-level (not instance) state. Python has no
direct "reopen a module to add methods" equivalent, but module-level
functions + module-level variables give the same effect — the module
object itself is the singleton:

```python
_quiet = False
_debug = False
_config = None

def get_config():
    global _config
    if _config is None:
        _config = Config()
    return _config

def enable_debug():
    global _debug
    _debug = True

def is_debug():
    return _debug

def enable_quiet():
    global _quiet
    _quiet = True

def enable_loud():
    global _quiet
    _quiet = False

def is_quiet():
    return _quiet
```

Naming departs from Ruby's `!`/`?` suffixes (not legal in Python
identifiers) but keeps the getter/setter pairing recognizable:
`debug!`→`enable_debug`, `debug?`→`is_debug`, `quiet!`→`enable_quiet`,
`loud!`→`enable_loud`, `quiet?`→`is_quiet`. **`config` itself is named
`get_config`, not `config`**, for a reason specific to Python: `__init__.py`
already causes the `boukensha.config` *submodule* (the file defining the
`Config` class) to be exposed as the attribute `boukensha.config` the
moment it's imported — a plain side effect of Python's import system, not
an explicit binding. Defining a module-level function literally named
`config` in `__init__.py` would silently overwrite that submodule
reference (confirmed empirically: `import boukensha.config` would then
return the function, not the submodule). Ruby has no such collision —
`Config` (the class) and `config` (the method) are already distinct
identifiers there. Only `get_config()` and `is_debug()` are actually
consumed (by `Logger`, see below) — `enable_quiet`/`enable_loud`/
`is_quiet` are unused in this iteration in Python too, same as Ruby
(grep-confirmed: `Boukensha.quiet?`/`.loud!`/`.quiet!` have zero call
sites in `ruby/06_the_logger`), shipped for parity, not because anything
reads them yet.

Also: import and re-export `Logger` (`from .logger import Logger`), add it
to `__all__`.

### 4. `examples/example.py`

- Import `Logger` from `boukensha`.
- Build one: `logger = Logger()` (mirrors Ruby's default-dir behavior —
  writes under `boukensha.get_config().dir`'s `sessions/`, i.e.
  `<repo-root>/.boukensha/sessions/` via the existing `BOUKENSHA_DIR`
  override already set earlier in this same file).
- Pass `logger=logger` into `Agent(...)`.
- Update the banner strings (`"=== Boukensha Step 5: Agent Loop ==="` →
  `"=== Boukensha Step 6: The Logger ==="`), matching `ruby/06_the_logger`'s
  `example.rb`.

### 5. `README.md` — full rewrite, not a port

Same treatment as `05_agent_loop`'s README (`week1_agent_loop_port_plan.md`
§9): translate `ruby/06_the_logger/README.md`'s content (session log
format, the phase/method table, task configuration, debug events, run
example) into the Python-flavored equivalent — Python session/method names
(`Logger()`, `logger.iteration(n=..., max=...)`, etc.), `./bin/python/
06_the_logger` as the run command, `LOG_VIZ_SESSIONS_DIR` unaffected
(that's `log_viz`, not this step). Carry forward the same flagged
discrepancy note from the Ruby troubleshooting log (entry #20): the
README's documented `prompt(messages:, tools:, budget:)` signature doesn't
match either language's actual `prompt(messages, tools)` — don't invent a
`budget` parameter to make the doc "true", just note the same discrepancy
in the Python README's own words if it's carried over verbatim.

### 6. `bin/python/06_the_logger` — new runner

Mirror `bin/python/05_agent_loop` verbatim, path bumped to
`python/06_the_logger` (checked directly, not from memory):
```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../python/06_the_logger"

# Prefer the lesson-local virtualenv if it exists, else fall back to python3.
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

exec "$PY" examples/example.py
```

## Judgment calls (flag for the implementer, don't silently decide)

1. **Drop `mud_host`/`mud_port`/`mud_username`/`mud_password` from
   `config.py`?** Ruby dropped the equivalent methods in this same
   snapshot. They're unused in both languages through `06_the_logger` (only
   a future `08_the_repl_loop`-equivalent would need them). Dropping keeps
   Python structurally in sync with the current Ruby reference; keeping
   them is harmless dead code with an already-fixed bug (entry #14) sitting
   dormant. Recommendation: **drop them**, matching Ruby exactly — re-add
   whenever the Python port reaches the iteration that actually needs MUD
   connection settings, the same way Ruby will presumably re-add its own.
2. **Drop `LoopError` from `errors.py`/`__init__.py`'s `__all__`?** Same
   situation — Ruby dropped it, Python's copy is unused but has a docstring
   explaining why it exists. Recommendation: **drop it** for the same
   sync-with-reference reason, since nothing in this repo raises or catches
   it in either language.

Both are one-line-per-file removals; call them out explicitly in the port
commit message so a future diff against Ruby doesn't need to rediscover
this reasoning.

## Unchanged — carry forward as-is

`boukensha/client.py`, `boukensha/context.py`, `boukensha/message.py`,
`boukensha/registry.py`, `boukensha/tool.py`, `boukensha/tasks/*.py`,
`boukensha/prompt_builder.py` (already has `backend` exposed),
`boukensha/backends/*.py` (model tables, `parse_response`,
`estimate_cost`, etc.), `requirements.txt`. None of these appear in the
Ruby 05→06 diff beyond the `config.rb`/`errors.rb` cleanup already called
out above.

## Verification plan

Same two-layer approach as the `05_agent_loop` port
(`week1_agent_loop_port_plan.md`, confirmed in
`docs/week1_config_troubleshooting.md` entries #17/#18):

1. **Offline**, no live API: instantiate one of each of the five backend
   classes and assert `_provider_name` matches the string that selects that
   class in `example.py`'s `if provider == "..."` chain (mirrors the Ruby
   verification for entry #20). Also exercise `Logger` directly against a
   fake `Context`/response dict — one `session_start` write, one
   `response` write with a known `usage` dict, assert the resulting JSONL
   line's `cost_usd`/`input_tokens`/`output_tokens`/`provider` fields.
2. **Live smoke test**: run `./bin/python/06_the_logger` for real against
   the Anthropic backend (matching `.boukensha/settings.yaml`), then
   inspect the resulting `.boukensha/sessions/<id>.jsonl` line-by-line
   against both the README's documented shape and the real
   `ruby/06_the_logger` session already on disk from this iteration's Ruby
   work — same phases, same field names, values naturally differing
   (different session id, timestamps, token counts).
3. Confirm `log_viz` (already fixed to look at `.boukensha/sessions/`) can
   list and render the Python-generated session exactly like it does the
   Ruby ones — the JSONL format is language-agnostic by design, so no
   `log_viz` changes should be needed to view a Python session.
