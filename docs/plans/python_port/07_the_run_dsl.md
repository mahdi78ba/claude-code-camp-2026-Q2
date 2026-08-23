# Python Port Plan — The Run DSL (`07_the_run_dsl`)

Baseline for this port is `python/06_the_logger`, copied verbatim into
`python/07_the_run_dsl` (`__pycache__/`, `.venv/` excluded — machine-local,
regenerated on install). This plan lists only the delta needed to bring that
copy up to `ruby/07_the_run_dsl`, as committed (already includes the
inherited-template fixes made to the Ruby side in this iteration:
`BOUKENSHA_DIR`/`PROMPTS_DIR` `../` counts, `provider_name`'s OpenAI
mislabeling — none of which need re-fixing in Python, see "Cross-check"
below).

## What actually changed in Ruby (06 → 07)

```
$ diff -rq ruby/06_the_logger ruby/07_the_run_dsl
Only in ruby/07_the_run_dsl/lib/boukensha: run_dsl.rb
Files .../lib/boukensha.rb differ
Files .../lib/boukensha/config.rb differ
Files .../lib/boukensha/context.rb differ
Files .../lib/boukensha/errors.rb differ
Files .../lib/boukensha/logger.rb differ
Files .../examples/example.rb differ
Files .../README.md differ
```

1. **New `lib/boukensha/run_dsl.rb`** — `Boukensha::RunDSL`. A tiny host
   object: `self` becomes this instance inside a `Boukensha.run` block via
   `instance_eval`. Exposes exactly one method, `tool`, which forwards to
   `@registry.tool`. Deliberately narrow — the block can't reach `Context`,
   `Client`, or any other internal object.

2. **`lib/boukensha.rb`** — the actual feature: adds `Boukensha.run`, a
   class method that:
   - Loads `config` (`.env`/`settings.yaml` from `BOUKENSHA_DIR`).
   - Resolves `system`/`model`/`backend`/`api_key` from `Tasks::Player`
     settings unless the caller passed them explicitly (each via `||=`,
     i.e. only `nil` triggers the fallback, not falsy-but-present values).
   - Builds `Context`/`Registry` directly, then runs
     `RunDSL.new(registry).instance_eval(&block) if block`.
   - Constructs the backend (`Anthropic`/`OpenAI`/`Gemini`/`Ollama`/
     `OllamaCloud`) from a `case` on `backend`, raising `ArgumentError` on
     an unknown symbol.
   - Builds `PromptBuilder`/`Client`/`Logger`/`Agent`, adds `task` as the
     first user message, calls `agent.run`, and closes the logger in an
     `ensure` block (runs even if `agent.run` raises).
   - Also adds `require_relative "boukensha/run_dsl"` at the bottom.

3. **`examples/example.rb`** / **`README.md`** — example rewritten to call
   `Boukensha.run(task: ...) do ... tool ... end` instead of manually
   building the six objects; README rewritten for Step 7 (see
   `ruby/07_the_run_dsl/README.md`, already reviewed in the prior session
   turn).

4. **`lib/boukensha/config.rb`** — re-adds `mud_host`/`mud_port`/
   `mud_username`/`mud_password`, which `06_the_logger`'s own port plan
   (`docs/plans/python_port/06_the_logger.md`, "Judgment calls" §1)
   deliberately dropped from both languages as unused dead code. Ruby has
   now restored them in this snapshot; see "Judgment calls" below for why
   this reverses that earlier recommendation.

5. **`lib/boukensha/errors.rb`** — re-adds `LoopError < StandardError`,
   same situation as #4: `06_the_logger`'s plan dropped it from both
   languages (§2 of the same "Judgment calls" section), Ruby has now
   restored it.

6. **`lib/boukensha/logger.rb`** — adds two new methods, `turn(n:)` (writes
   `phase: "turn"`) and `subscribe(&block)` (registers a callback invoked
   with every logged event from `write_log`). Neither is called anywhere in
   `07_the_run_dsl` — `Agent#run` still only calls `iteration`/
   `limit_reached`/`prompt`/`raw`/`turn_end`/`response`/`tool_call`/
   `tool_result`, none of which is `turn`. Purely additive, unused surface.

7. **`lib/boukensha/context.rb`** — whitespace-only realignment of instance
   variable assignment spacing, plus loss of a trailing newline. No
   behavior change; not ported (nothing to port — Python's formatting is
   independent of Ruby's).

Items 4–6 are **not** Run DSL features — they're unrelated template drift
that happened to land in the same snapshot, exactly like `06_the_logger`'s
own plan flagged its config/errors cleanup separately from the logging
work. Flagged under "Judgment calls" below rather than silently folded into
the DSL port.

## Cross-check against the current Python tree

Confirms which parts of the Ruby diff Python already handles differently
(and doesn't need porting) vs. what's genuinely new:

- **No off-by-one `../` bug class to port.** Same as every prior port plan
  in this series — Python resolves `BOUKENSHA_DIR`/`PROMPTS_DIR` via
  `Path(__file__).resolve()`, not hand-written `../` string literals, so
  there was never a wrong count to inherit.
- **`Logger._provider_name` already has the OpenAI special case** (ported
  during `06_the_logger`, see that plan's step 1) — nothing to change here
  even though Ruby's fix for this same bug landed fresh in this session's
  `07_the_run_dsl` work (it was carrying the pre-fix template bug forward
  from before `06_the_logger`'s Ruby fix; Python's port already reflects
  the fixed behavior).
- **`PromptBuilder.backend` already exists** — unchanged on both sides
  (`prompt_builder.rb`/`prompt_builder.py` are identical between 06 and 07
  in Ruby; nothing to port).
- **`Agent`, `Client`, `Context`, `Registry`, `Tool`, `Message`,
  `Tasks::Base`/`Tasks::Player`, all five backends** — zero diff between
  `ruby/06_the_logger` and `ruby/07_the_run_dsl`. Nothing to touch; `run()`
  (item 2 below) is pure composition over all of these, already fully
  ported.
- **`config.py`'s `mud_host`/`mud_port` already have the entry #14 fix**
  (`is None` checks) sitting in git history even though the properties
  were removed from `06_the_logger`'s copy — re-adding them (see Judgment
  call #1) means restoring the already-correct fixed version, not
  redoing the fix.

## Files to add / change in Python

### 1. `boukensha/run_dsl.py` — new, ported from `lib/boukensha/run_dsl.rb`

```python
"""The Boukensha.run() DSL surface.

Python port of Boukensha::RunDSL.
"""

from __future__ import annotations

from typing import Any, Callable


class RunDSL:
    """Passed to the `configure` callback given to `boukensha.run()`.

    Exposes exactly one method, `tool`, mirroring Ruby's `RunDSL` — the
    caller can register tools but cannot reach the `Context`, `Client`, or
    any other internal object.
    """

    def __init__(self, registry) -> None:
        self._registry = registry

    def tool(self, name, *, description: str, parameters: dict | None = None,
             block: Callable[..., Any]):
        return self._registry.tool(
            name, description=description, parameters=parameters or {}, block=block
        )
```

**Language-level adaptation, not a literal translation:** Ruby's
`Boukensha.run(task: ...) do ... tool ... end` works because `instance_eval`
rebinds `self` inside the block to the `RunDSL` instance, so a bare `tool`
call resolves as `self.tool` automatically. Python has no equivalent to
`instance_eval` — there's no way to make a bare `tool(...)` call inside a
lambda/function silently resolve against an arbitrary receiver. The
Pythonic equivalent is an explicit parameter: `run()` takes a `configure`
callable, invokes it as `configure(dsl)` where `dsl` is the `RunDSL`
instance, and the caller writes `dsl.tool(...)` instead of a bare `tool`.
This preserves the actual design intent (a single, narrow method surface
for registering tools, no access to internals) exactly — only the syntax
for "reaching" that surface changes, not what's reachable.

### 2. `boukensha/__init__.py` — add `run()`

Ruby's `Boukensha.run` becomes a module-level function, consistent with
how `Boukensha.config`/`.debug!`/etc. already became `get_config()`/
`enable_debug()` in the `06_the_logger` port. No `get_`-prefix collision
issue here (there's no `boukensha.run` submodule), so the name can match
Ruby exactly: `boukensha.run(...)`.

```python
def run(*, task, system=None, model=None, backend=None, api_key=None,
        ollama_host="http://localhost:11434", log=None,
        max_output_tokens=None, configure=None):
    cfg = get_config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())

    if system is None:
        system = task_class.system_prompt(
            task_settings, user_prompts_dir=cfg.user_prompts_dir,
            default_prompts_dir=Config.PROMPTS_DIR,
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)
    if api_key is None:
        api_key = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY"),
            "gemini": os.environ.get("GEMINI_API_KEY"),
            "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
        }.get(backend)

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

    if configure is not None:
        configure(RunDSL(registry))

    if backend == "anthropic":
        be = backends.Anthropic(api_key=api_key, model=model)
    elif backend == "openai":
        be = backends.OpenAI(api_key=api_key, model=model)
    elif backend == "gemini":
        be = backends.Gemini(api_key=api_key, model=model)
    elif backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=model)
    elif backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=api_key, model=model)
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. Use 'anthropic', 'openai', "
            f"'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = (
        task_class.max_output_tokens(task_settings)
        if max_output_tokens is None else max_output_tokens
    )
    logger = Logger(log=log, snapshot={
        "task": task_class.task_name(),
        "max_iterations": effective_max_iterations,
        "max_output_tokens": effective_max_output_tokens,
        "model": model,
        "provider": backend,
    })
    agent = Agent(
        context=ctx, registry=registry, builder=builder, client=client,
        logger=logger, task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()
```

Translation notes, not just renames:

- **Every `||=` in Ruby becomes an explicit `is None` check, not `or`.**
  This is the same bug class flagged by
  [[feedback_port_review_rigor]] and entries #14/#17/#18 in
  `docs/week1_config_troubleshooting.md`: Ruby's `||=`/`||` only fall back
  on `nil`/`false`, so a caller-supplied falsy-but-meaningful value (most
  importantly `max_output_tokens=0`, but in principle `system=""` or
  `api_key=""` too) must survive untouched. Using Python's `or` here would
  silently discard a `0` the caller explicitly asked for, exactly like the
  bug entry #17 found and fixed in `Agent._call_opts`. **This is the
  single most important correctness point in this port** — verify it with
  an explicit `max_output_tokens=0` test case (see Verification plan).
- **`task_class.provider(task_settings)` returns a plain string** (e.g.
  `"anthropic"`), not a Ruby symbol — matches how `example.py`'s existing
  `if provider == "anthropic": ...` chain already compares strings.
  `run()`'s backend dispatch is the same if/elif chain, just now living in
  library code instead of example code.
- **`ensure logger&.close` → `try/finally: logger.close()`.** Ruby's
  `logger&.close` guards against `logger` being `nil` if the method raised
  before the `Logger.new` line executed; in the Python translation
  `logger` is always assigned before the `try` block starts (it can't be
  unbound when `finally` runs), so the safe-navigation guard isn't needed
  — just call `logger.close()` directly.
- **`RunDSL` is imported and instantiated inline** (`configure(RunDSL(registry))`)
  rather than pre-built and passed to a decorator-style API — matches
  Ruby's `RunDSL.new(registry).instance_eval(&block) if block` doing the
  construction and invocation in the same statement.
- Add `run` to `__all__`, and `from .run_dsl import RunDSL` alongside the
  existing `from .logger import Logger` import.

### 3. `examples/example.py` — rewritten to use `boukensha.run()`

Direct translation of `ruby/07_the_run_dsl/examples/example.rb`:

```python
"""Boukensha Step 7: The Run DSL — Python port smoke test."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boukensha  # noqa: E402

# Config is loaded automatically inside boukensha.run() — system prompt,
# model, and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by
# default. You can still override any of them as keyword arguments.
repo_root = Path(__file__).resolve().parents[4]
os.environ.setdefault("BOUKENSHA_DIR", str(repo_root / ".boukensha"))

print("=== Boukensha Step 7: The Run DSL ===")
print()
print(f"Config: {boukensha.get_config()}")
print()

base_dir = Path(__file__).resolve().parent.parent


def configure(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
        block=lambda path: (base_dir / path).read_text(),
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
        block=lambda path: ", ".join(
            f.name for f in (base_dir / path).iterdir() if not f.name.startswith(".")
        ),
    )


result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    configure=configure,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
```

Note the size drop this mirrors on the Ruby side: no manual `Context`/
`Registry`/backend-`if`-chain/`PromptBuilder`/`Client`/`Logger`/`Agent`
construction — `boukensha.run()` does all of it. `BOUKENSHA_DIR` is still
set explicitly in the example (same reasoning as every prior Python
example: makes the smoke test find *this repo's* `.boukensha/` without
requiring a real `~/.boukensha` to exist).

### 4. `README.md` — full rewrite, not a port

Same treatment as every prior step's README in this series: translate
`ruby/07_the_run_dsl/README.md`'s content (the `RunDSL`/`Boukensha.run`
explanation, the options table, the before/after code comparison, the run
example) into the Python-flavored equivalent — `boukensha.run(task=...)`
instead of `Boukensha.run(task:)`, `dsl.tool(...)` inside a `configure`
callback instead of a bare `tool` call inside a block (call out the
`instance_eval`-has-no-Python-equivalent adaptation explicitly, don't
present it as if Python had the identical syntax), `./bin/python/
07_the_run_dsl` as the run command.

### 5. `bin/python/07_the_run_dsl` — new runner

Mirror `bin/python/06_the_logger` verbatim, path bumped:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../python/07_the_run_dsl"

# Prefer the lesson-local virtualenv if it exists, else fall back to python3.
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

exec "$PY" examples/example.py
```

## Judgment calls (flag for the implementer, don't silently decide)

1. **Re-add `mud_host`/`mud_port`/`mud_username`/`mud_password` to
   `config.py`?** `06_the_logger`'s port plan recommended dropping these
   from both languages specifically *because* Ruby had dropped them in
   that snapshot, with the explicit reasoning "keeps Python structurally
   in sync with the current Ruby reference." Ruby's `07_the_run_dsl`
   restores them (unchanged from `02`–`05`'s versions, `is None`-style
   fix already baked in). Applying the same stated policy forward means
   the conclusion now flips: **re-add them**, matching Ruby exactly. They
   remain unused through this step in both languages (no MUD-connection
   feature exists yet) — this is pure structural parity with the current
   snapshot, not a functional need.
2. **Re-add `LoopError` to `errors.py`/`__init__.py`'s `__all__`?** Same
   situation and same reversal as #1 — Ruby restored it, so Python should
   too, still unused, still dead code, still shipped for reference parity.
3. **Port `Logger.turn()`/`Logger.subscribe()`?** Unlike #1/#2 these
   aren't a "re-add" — they're new in this Ruby snapshot and nothing in
   `06_the_logger`'s plan ever considered them. Same underlying policy
   applies, though: the established convention in this repo (see
   `06_the_logger`'s own `enable_quiet`/`enable_loud`/`is_quiet` — "unused
   ... shipped for parity") is 1:1 structural parity with the current
   Ruby reference regardless of call sites. Recommendation: **port both**,
   as direct translations —
   ```python
   def turn(self, *, n):
       self._write_log({"phase": "turn", "n": n})

   def subscribe(self, callback):
       self._subscribers = getattr(self, "_subscribers", [])
       self._subscribers.append(callback)
   ```
   and have `_write_log` call every subscriber after writing, matching
   Ruby's `@subscribers&.each { |s| s.call(event) }`. Neither is called by
   `Agent`/`example.py` in this port either — flag this explicitly in the
   port commit message, same as `06_the_logger`'s own "also noticed, not
   changed" note about `Logger#close` never being called.

All three are small, mechanical, and low-risk either way; call them out
explicitly in the port commit message so a future diff against Ruby
doesn't need to rediscover this reasoning (same practice `06_the_logger`'s
plan followed).

## Unchanged — carry forward as-is

`boukensha/client.py`, `boukensha/context.py`, `boukensha/message.py`,
`boukensha/registry.py`, `boukensha/tool.py`, `boukensha/tasks/*.py`,
`boukensha/agent.py`, `boukensha/prompt_builder.py`, `boukensha/backends/*.py`
(model tables, `parse_response`, `estimate_cost`, `_provider_name`'s OpenAI
fix, etc.), `requirements.txt`. None of these appear in the Ruby 06→07 diff
beyond the config/errors/logger cleanup already called out in "Judgment
calls."

## Verification plan

Same two-layer approach as every prior port in this series:

1. **Offline**, no live API:
   - Call `boukensha.run(task="...", max_output_tokens=0, configure=...)`
     against a fake/monkeypatched backend and assert the `Logger`
     `session_start` snapshot's `max_output_tokens` field is `0`, not the
     task's configured default — this is the critical `is None`-vs-`or`
     regression test called out above, and the one thing a live smoke test
     (which only ever exercises the real, truthy, configured value) can
     never catch.
   - Assert `run()` raises `ValueError` for an unknown `backend=` string,
     matching Ruby's `ArgumentError` case-else branch.
   - Assert a `RunDSL` instance only exposes `tool` (no accidental leak of
     `_registry` as a public attribute a caller could mutate directly).
2. **Live smoke test**: run `./bin/python/07_the_run_dsl` for real against
   the Anthropic backend (matching `.boukensha/settings.yaml`), then
   compare the resulting `.boukensha/sessions/<id>.jsonl` against the real
   `ruby/07_the_run_dsl` session already on disk from this iteration's
   Ruby work (verified in this session: `session_start` with
   `provider: "anthropic"`, one `read_file` `tool_call`/`tool_result` pair,
   `turn_end`) — same phases, same field names, values naturally differing
   (session id, timestamps, token counts).
3. Confirm `log_viz` can list and render the Python-generated session
   exactly like the Ruby one, same as every prior step's verification —
   no `log_viz` changes expected, the JSONL format is language-agnostic.
