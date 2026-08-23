# Python Port Plan — The REPL Loop (`08_the_repl_loop`)

Baseline for this port is `python/07_the_run_dsl`, copied verbatim into
`python/08_the_repl_loop` (`__pycache__/`, `.venv/` excluded — machine-local,
regenerated on install). This plan lists only the delta needed to bring that
copy up to `ruby/08_the_repl_loop`, as committed (already includes this
iteration's own inherited-template fixes — `BOUKENSHA_DIR`/`PROMPTS_DIR`
`../` counts, `provider_name`'s OpenAI mislabeling — none of which need
re-fixing in Python; see "Cross-check" below).

## What actually changed in Ruby (07 → 08)

```
$ diff -rq ruby/07_the_run_dsl ruby/08_the_repl_loop
Files 07_the_run_dsl/README.md and 08_the_repl_loop/README.md differ
Files 07_the_run_dsl/examples/example.rb and 08_the_repl_loop/examples/example.rb differ
Files 07_the_run_dsl/lib/boukensha/agent.rb and 08_the_repl_loop/lib/boukensha/agent.rb differ
Files 07_the_run_dsl/lib/boukensha/client.rb and 08_the_repl_loop/lib/boukensha/client.rb differ
Files 07_the_run_dsl/lib/boukensha/config.rb and 08_the_repl_loop/lib/boukensha/config.rb differ
Files 07_the_run_dsl/lib/boukensha/context.rb and 08_the_repl_loop/lib/boukensha/context.rb differ
Only in 08_the_repl_loop/lib/boukensha: repl.rb
Only in 08_the_repl_loop/lib/boukensha: version.rb
Files 07_the_run_dsl/lib/boukensha.rb and 08_the_repl_loop/lib/boukensha.rb differ
```

(`lib/boukensha/logger.rb` is **not** in this diff — both copies already
carry the OpenAI `provider_name` fix; see "Cross-check.")

1. **New `lib/boukensha/repl.rb`** — `Boukensha::Repl`, the interactive
   session loop. A plain object (no `Agent` subclass, no library beyond
   `loop`/`$stdin`/`$stdout`): `start` prints a banner, then loops printing
   `boukensha> `, reading one line, and either handling a built-in command
   (`/exit`, `/quit`, `/help`, `/quiet`, `/loud`, `/clear`) or forwarding the
   line to `run_turn`. `run_turn` builds a **fresh `Agent` every turn**
   around the **same shared** `context`/`registry`/`builder`/`client`/
   `logger`, appends the user's line to `context` first, calls `agent.run`,
   and prints the result — catching `LoopError`/`ApiError` per turn so one
   bad turn doesn't kill the session.

2. **New `lib/boukensha/version.rb`** — `Boukensha::VERSION = "0.8.0"`, used
   only by the REPL banner.

3. **`lib/boukensha.rb`** — the actual feature: adds `Boukensha.repl`, a
   class method with the same setup as `Boukensha.run` (config load,
   system/model/backend/api_key resolution, `Context`/`Registry`
   construction, `RunDSL` block eval, backend/builder/client/logger
   construction) but instead of building one `Agent` and calling it once, it
   builds a `Repl` (passing it `config_dir`, `provider`, `model`, `version`,
   `api_key` for the banner, plus every object `Agent` would have needed)
   and calls `.start`. Wraps the whole thing in `rescue Interrupt → puts
   "\nInterrupted."` and still `ensure`s `logger&.close`. Also trims
   `Boukensha.run`'s doc comment down to one line ("See step 6 for full
   documentation") now that `repl` exists alongside it — no behavior change,
   just doc upkeep; not relevant to the port.

4. **`lib/boukensha/config.rb`** — `resolve_dir` gains a **new middle tier**:
   ```ruby
   # 1. Explicit override
   return Pathname.new(ENV["BOUKENSHA_DIR"]).expand_path.to_s if ENV["BOUKENSHA_DIR"]
   # 2. .boukensha in the current working directory   ← NEW
   cwd_dir = Pathname.new(Dir.pwd).join(".boukensha")
   return cwd_dir.to_s if cwd_dir.directory?
   # 3. ~/.boukensha default
   Pathname.new(DEFAULT_DIR).expand_path.to_s
   ```
   Previously it was just `ENV.fetch("BOUKENSHA_DIR", nil) || DEFAULT_DIR`
   (2 tiers). This is a genuine new feature, not a formatting change — a
   `.boukensha/` directory sitting in whatever directory the REPL happens to
   be launched from is now found automatically, without setting
   `BOUKENSHA_DIR` at all.

5. **`lib/boukensha/context.rb`** — adds `clear_messages!` (empties
   `@messages`, leaves `@tools`/`@system` alone) — backs the REPL's `/clear`.
   Plus a trailing-newline-only fix, not worth porting (Python's formatting
   is independent of Ruby's).

6. **`lib/boukensha/agent.rb`** — `Agent#run`'s three return points now
   persist the final text as an `:assistant` message *before* returning, not
   just returning it:
   ```ruby
   # normal completion (run, ~line 52)
   @context.add_message(:assistant, text)
   return text
   # wrap_up success (~line 94)
   @context.add_message(:assistant, text)
   text
   # wrap_up's ApiError rescue (~line 99)
   @context.add_message(:assistant, msg)
   msg
   ```
   All **three** call sites need the same treatment — easy to port only the
   first and miss the other two, since they're in different methods
   (`run` vs `wrap_up`) and one is inside a `rescue`. Harmless for a
   one-shot `Boukensha.run` (context is discarded right after), but a REPL
   that reuses `context` across turns would silently drop the agent's own
   answer from history on any turn that happened to hit the iteration limit,
   if only the main path were fixed.

7. **`lib/boukensha/client.rb`** — the generic non-2xx branch gains a
   401-specific message before the generic one:
   ```ruby
   unless response.is_a?(Net::HTTPSuccess)
     if response.code.to_i == 401
       raise ApiError, "authentication failed (401) — check your API key"
     end
     raise ApiError, "API request failed after ... (#{response.code}): #{response.body}"
   end
   ```
   Purely a clearer error message for the one failure mode a REPL user is
   most likely to actually hit interactively (a bad/missing key) — no change
   to retry behavior, no new status code added to the retry set.

8. **`examples/example.rb`** / **`README.md`** — example rewritten to call
   `Boukensha.repl do ... tool ... end` instead of `Boukensha.run(task:
   ...)`; no longer sets `ENV["BOUKENSHA_DIR"]` itself (moved to
   `bin/ruby/08_the_repl_loop`, which now exports it before invoking Ruby —
   see `docs/week1_repl_loop_overview.md` §"BOUKENSHA_DIR moved out"); tool
   descriptions reworded for a persistent multi-turn session rather than a
   single task; README rewritten for Step 8 (see
   `ruby/08_the_repl_loop/README.md`, already reviewed —
   `docs/week1_repl_loop_review.md`).

## Cross-check against the current Python tree

Which parts of the Ruby diff Python already handles differently (nothing to
port) vs. what's genuinely new work:

- **No off-by-one `../` bug class to port**, same as every prior plan in
  this series — Python resolves `BOUKENSHA_DIR`/`PROMPTS_DIR` via
  `Path(__file__).resolve()`, never a hand-written `../` count.
- **`Logger._provider_name` already has the OpenAI special case, `turn()`
  and `subscribe()` already exist** (all ported during `06`/`07`, per that
  plan's Judgment call #3) — confirmed by grep, nothing to change in
  `logger.py`.
- **Item #4 above (`resolve_dir`'s new cwd tier) is real, new Python work.**
  `Config._resolve_dir` currently reads:
  ```python
  def _resolve_dir(self) -> str:
      raw = os.environ.get("BOUKENSHA_DIR") or self.DEFAULT_DIR
      return str(Path(raw).expanduser().resolve())
  ```
  — still the old 2-tier version. This needs the same 3-tier logic Ruby just
  added (see file plan below).
- **Item #6 above (`Agent` persisting its own reply) is real, new Python
  work.** `agent.py`'s `run`/`_wrap_up` still just `return text`/`return
  msg` at all three points, matching Ruby's *pre-08* shape exactly (verified
  by grep: no `add_message` calls anywhere in `_wrap_up`, and `run`'s
  `else` branch returns `text` with no `add_message` first).
- **Item #7 above (401-specific `ApiError` message) is real, new Python
  work.** `client.py`'s HTTP layer uses `urllib.request`, which raises
  `urllib.error.HTTPError` for any non-2xx status (unlike Ruby's
  `Net::HTTP`, which returns a response object and needs an explicit
  `unless response.is_a?(Net::HTTPSuccess)` check afterward) — so the 401
  check lands inside the existing `except urllib.error.HTTPError` branch,
  not as a new post-loop check. Different control flow, same user-facing
  behavior.
- **`Context.clear_messages()` doesn't exist yet** — needs adding (item #5).
- **No `Repl` class, no `repl()` function, no version constant exist yet**
  — all new (items #1–#3).
- **`Agent`, `Registry`, `Tool`, `Message`, `PromptBuilder`,
  `Tasks::Base`/`Tasks::Player`, all five backends** are otherwise unchanged
  between `ruby/07_the_run_dsl` and `ruby/08_the_repl_loop` (confirmed by the
  `diff -rq` above listing only `agent.rb`/`client.rb`/`config.rb`/
  `context.rb`/`boukensha.rb` plus the two new files) — nothing else to
  touch.

## Files to add / change in Python

### 1. `boukensha/version.py` — new

```python
"""Boukensha version string.

Python port of Boukensha::VERSION (lib/boukensha/version.rb). Used only by
the REPL banner.
"""

VERSION = "0.8.0"
```

A dedicated module rather than a bare `__version__` in `__init__.py`, to
mirror Ruby's dedicated `version.rb` file 1:1 — same reasoning as
`run_dsl.py` getting its own file in the `07_the_run_dsl` port.

### 2. `boukensha/context.py` — add `clear_messages`

```python
def clear_messages(self) -> None:
    """Drop all conversation history, keeping tools and system prompt intact.

    Used by the REPL's `/clear` command.
    """
    self.messages = []
```

Direct translation of `Context#clear_messages!` — Python has no `!`
naming convention, so the trailing bang is simply dropped (matching how
every other Ruby `!`-method in this codebase, e.g. `debug!`/`quiet!`, has
already been ported as `enable_debug`/`enable_quiet` with no bang).

### 3. `boukensha/agent.py` — persist the final reply, all three return points

```python
# run(), else branch (~line 60-63)
text = self._extract_text(parsed["content"])
self._log_response(text=text, response=response)
self.logger.turn_end(reason="completed", iterations=self._iteration)
self.context.add_message("assistant", text)          # NEW
return text

# _wrap_up(), success path (~line 104-109)
text = self._extract_text(self.builder.parse_response(response)["content"])
if not text.strip():
    text = self._fallback_message(reason)
self._log_response(text=text, response=response)
self.logger.turn_end(reason=reason, iterations=self._iteration)
self.context.add_message("assistant", text)          # NEW
return text

# _wrap_up(), ApiError except block (~line 99-102)
except ApiError:
    msg = self._fallback_message(reason)
    self.logger.turn_end(reason=reason, iterations=self._iteration)
    self.context.add_message("assistant", msg)        # NEW
    return msg
```

All three, matching the Ruby diff exactly — miss one and a REPL session
that happens to hit the iteration limit on some turn silently loses that
turn's answer from history on the next round-trip, without raising or
logging anything wrong (the bug would only surface as "the agent seems to
have forgotten what it just said," and only on the specific turns that
wrap up rather than complete normally).

### 4. `boukensha/client.py` — 401-specific `ApiError` message

```python
except urllib.error.HTTPError as e:
    if self._retryable_status(e.code) and attempts <= self.MAX_RETRIES:
        time.sleep(self._retry_delay(attempts))
        continue

    if e.code == 401:
        raise ApiError("authentication failed (401) — check your API key") from e

    body_text = e.read().decode("utf-8", errors="replace")
    suffix = "" if attempts == 1 else "s"
    raise ApiError(
        f"API request failed after {attempts} attempt{suffix} "
        f"({e.code}): {body_text}"
    ) from e
```

The 401 check goes **before** `e.read()` is called for the generic message
— a `401` response body isn't needed for the clearer message, and
`HTTPError.read()` can only be called once per exception object.

### 5. `boukensha/config.py` — three-tier `_resolve_dir`

```python
def _resolve_dir(self) -> str:
    # 1. Explicit override
    env_dir = os.environ.get("BOUKENSHA_DIR")
    if env_dir:
        return str(Path(env_dir).expanduser().resolve())

    # 2. .boukensha in the current working directory
    cwd_dir = Path.cwd() / ".boukensha"
    if cwd_dir.is_dir():
        return str(cwd_dir)

    # 3. ~/.boukensha default
    return str(Path(self.DEFAULT_DIR).expanduser().resolve())
```

Also update the module docstring's resolution-order comment (currently says
"1. `BOUKENSHA_DIR` ... 2. `~/.boukensha`") to list all three tiers, matching
Ruby's `config.rb` comment update in the same diff.

### 6. `boukensha/repl.py` — new, ported from `lib/boukensha/repl.rb`

```python
"""The interactive REPL session loop.

Python port of Boukensha::Repl. Wraps the same primitives as a single
boukensha.run() call, but instead of running once it stays alive: reads a
line from the user, runs the agent, prints the reply, and loops back to
the prompt. The Context is shared across every turn, so conversation
history accumulates naturally.

Built-in commands (not sent to the agent): /help, /quiet, /loud, /clear,
/exit, /quit.
"""

from __future__ import annotations

from . import enable_quiet, enable_loud
from .agent import Agent
from .errors import ApiError, LoopError

PROMPT = "boukensha> "

HELP = """Commands:
  /quiet   suppress logging output
  /loud    re-enable logging output
  /clear   wipe conversation history (tools stay)
  /exit    leave the REPL
  /help    show this message
"""


class Repl:
    def __init__(self, *, context, registry, builder, client, logger,
                 config_dir=None, provider=None, model=None, version=None,
                 api_key=None, task_settings=None, max_iterations=None,
                 max_output_tokens=None):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.task_settings = task_settings
        self.max_iterations = max_iterations
        self.max_output_tokens = max_output_tokens
        self.config_dir = config_dir
        self.provider = provider
        self.model = model
        self.version = version
        self.api_key = api_key
        self.turn = 0

    def start(self):
        print(self._banner())

        while True:
            try:
                line = input(PROMPT)
            except EOFError:            # Ctrl-D
                break

            line = line.strip()
            if not line:
                continue

            if line in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif line == "/help":
                print(HELP)
                continue
            elif line == "/quiet":
                enable_quiet()
                print("(logging suppressed — type /loud to re-enable)")
                continue
            elif line == "/loud":
                enable_loud()
                print("(logging enabled)")
                continue
            elif line == "/clear":
                self.context.clear_messages()
                self.turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(line)

    # ---------- private -----------------------------------------------

    def _banner(self):
        key_status = "✓ API key set" if (self.api_key and self.api_key.strip()) else "✗ API key not set"
        provider_line = f"{self.provider or 'default'} ({self.model or 'default'})  {key_status}"
        config_exists = bool(self.config_dir) and Path(self.config_dir).is_dir()
        config_line = self.config_dir if config_exists else f"{self.config_dir or '(default)'}  ✗ directory not found"
        ver = self.version or "?.?.?"
        pad = " " * (9 - len(ver))

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){pad}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            "\n"
            "  /quiet or /loud   toggle logging\n"
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def _run_turn(self, line):
        self.turn += 1
        self.logger.turn(n=self.turn)
        self.context.add_message("user", line)

        agent = Agent(
            context=self.context, registry=self.registry, builder=self.builder,
            client=self.client, logger=self.logger, task_settings=self.task_settings,
            max_iterations=self.max_iterations, max_output_tokens=self.max_output_tokens,
        )
        try:
            result = agent.run()
        except LoopError as e:
            print(f"\n[error] {e}")
            return
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
            return

        print()
        print(result)
```

Translation notes, not just renames:

- **`$stdin.gets` + manual `print PROMPT; $stdout.flush` becomes Python's
  `input(PROMPT)`** — a single built-in call that prints the prompt,
  flushes, and reads one line, so the manual flush Ruby needs has no
  Python equivalent to port (there's nothing to forget). **EOF is the one
  place this needs care**: Ruby's `$stdin.gets` returns `nil` on EOF
  (checked with `break unless input`); Python's `input()` *raises*
  `EOFError` instead of returning a sentinel, so the port needs
  `try/except EOFError: break` around the read, not an `is None` check.
- **Ruby's `input.chomp.strip` becomes `line.strip()`** — Python's
  `input()` never includes the trailing newline in the first place (unlike
  `$stdin.gets`), so there's no `chomp` equivalent needed; `strip()` alone
  covers the same "trim surrounding whitespace" intent.
- **The `case input when ... end` becomes an `if`/`elif` chain** — no
  direct `case` equivalent for string literals pre-3.10 pattern matching;
  an `if`/`elif` chain is the idiomatic and simplest match here, not a
  `match` statement (this project's other ports haven't used `match`
  elsewhere, and introducing it for exactly one method would be
  inconsistent style).
- **`Boukensha.quiet!`/`.loud!` become the already-ported
  `enable_quiet()`/`enable_loud()`** module functions (from `06_the_logger`)
  — no new module-level state needed, just calling what already exists.
- **The banner's `" " * (9 - ver.length)` padding logic ports literally** —
  `" " * (9 - len(ver))`, same off-by-nothing arithmetic, no adjustment
  needed since Python string length and Ruby string length agree for the
  ASCII version string used here.
- **Ctrl-C is deliberately *not* caught inside `Repl.start`**, matching
  Ruby exactly — the `KeyboardInterrupt` (Python's `Interrupt` equivalent)
  is left to propagate out of `start()` and is caught one level up, in
  `repl()` (see file 7 below), exactly mirroring where Ruby's
  `Boukensha.repl` catches `Interrupt` rather than `Repl#start` catching it
  itself. Porting the catch to the wrong level would be a behavior change,
  not a language-idiom adjustment.

### 7. `boukensha/__init__.py` — add `repl()`, wire up `Repl`/`VERSION`

```python
from .version import VERSION
from .repl import Repl

def repl(*, system=None, model=None, backend=None, api_key=None,
          ollama_host="http://localhost:11434", log=None,
          max_output_tokens=None, configure=None):
    cfg = get_config()
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

    repl_obj = Repl(
        context=ctx, registry=registry, builder=builder, client=client,
        logger=logger, task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
        config_dir=cfg.dir, provider=backend, model=model,
        version=VERSION, api_key=api_key,
    )
    try:
        repl_obj.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

Add `"VERSION"`, `"Repl"`, and `"repl"` to `__all__`.

Translation notes:

- **`rescue Interrupt` becomes `except KeyboardInterrupt`** — Python's name
  for the signal Ruby calls `Interrupt` (both fire on Ctrl-C / `SIGINT`).
- **`ensure logger&.close` becomes `finally: logger.close()`** — same
  reasoning as `run()`'s port: `logger` is always assigned before the
  `try` block starts here too, so the safe-navigation guard isn't needed.
- Every `||=`/fallback in the setup section is **identical to `run()`'s
  existing `is None` checks** — this setup code is a near-verbatim copy of
  `run()` minus the `task` parameter, so no new correctness pitfall here
  beyond what `run()`'s port plan (07) already called out and fixed.

### 8. `examples/example.py` — rewritten to use `boukensha.repl()`

Direct translation of `ruby/08_the_repl_loop/examples/example.rb`. Since
`BOUKENSHA_DIR` moved out of the Ruby example into its launcher this
session (see `docs/week1_repl_loop_overview.md`), the Python example keeps
setting it explicitly for now — consistent with **every prior Python
example in this series**, none of which have had that setup moved into
their `bin/python/*` runner. Flagged explicitly under "Judgment calls"
below rather than silently diverging from the Ruby side's latest state.

```python
"""Boukensha Step 8: The REPL Loop — Python port smoke test."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boukensha  # noqa: E402

# Config is loaded automatically inside boukensha.repl() — system prompt,
# model, and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by
# default.
repo_root = Path(__file__).resolve().parents[4]
os.environ.setdefault("BOUKENSHA_DIR", str(repo_root / ".boukensha"))

print(f"Config: {boukensha.get_config()}")
print()

# The base directory tools will operate relative to — the step 7 folder
# makes a good playground since it already has source files to read.
base_dir = Path(__file__).resolve().parents[2] / "07_the_run_dsl"


def configure(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "File path (relative to the working directory)"}},
        block=lambda path: (base_dir / path).resolve().read_text(),
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "Directory path (relative to the working directory, or '.' for root)"}},
        block=lambda path: ", ".join(
            sorted(f.name for f in (base_dir / path).resolve().iterdir() if not f.name.startswith("."))
        ),
    )


boukensha.repl(configure=configure)
```

Note `dsl.tool(...)` again, not a bare `tool(...)` — same
`instance_eval`-has-no-Python-equivalent adaptation as `07_the_run_dsl`'s
`run()` port, unchanged here since `RunDSL` itself doesn't change between
the two Ruby steps.

### 9. `README.md` — full rewrite, not a port

Same treatment as every prior step: translate
`ruby/08_the_repl_loop/README.md`'s content (the `Repl`/`Boukensha.repl`
explanation, the built-in command table, the step-6-vs-step-7 comparison
table, the `Context#clear_messages!`/`Agent#run` change callouts, the
example transcript) into the Python-flavored equivalent —
`boukensha.repl(configure=...)` instead of `Boukensha.repl do ... end`,
`dsl.tool(...)` instead of a bare `tool` call, `./bin/python/08_the_repl_loop`
as the run command. Also note in the Python README (the Ruby one doesn't,
since it predates that fix) that `EOFError` — not a `None` sentinel — is how
Python's REPL loop detects Ctrl-D, since a reader coming from the Ruby
README would otherwise expect the same `nil`-check idiom.

### 10. `bin/python/08_the_repl_loop` — new runner

Mirror `bin/python/07_the_run_dsl` verbatim, path bumped:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../python/08_the_repl_loop"

# Prefer the lesson-local virtualenv if it exists, else fall back to python3.
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

exec "$PY" examples/example.py
```

## Judgment calls (flag for the implementer, don't silently decide)

1. **Should `BOUKENSHA_DIR` setup move out of `examples/example.py` and into
   `bin/python/08_the_repl_loop`, mirroring what was just done on the Ruby
   side (`bin/ruby/08_the_repl_loop` now exports it)?** Recommendation:
   **no, not yet** — every other Python example in this series
   (`00`–`07`) still sets `BOUKENSHA_DIR` inline, and moving it only for
   `08` would make this the one Python example that looks different from
   its siblings for a reason a reader can't see just by looking at
   `08_the_repl_loop/` in isolation. If this cleanup is wanted across the
   Python side, it should land as a deliberate, cross-cutting pass over
   all `bin/python/*` runners at once (a follow-up, not part of this
   iteration's port) — same reasoning `06_the_logger`'s plan used when it
   deferred config/errors cleanup it didn't consider in-scope.
2. **`_resolve_dir`'s new cwd-directory tier — use `Path.cwd()` or
   `os.getcwd()`?** Recommendation: **`Path.cwd()`**, for consistency with
   every other path operation in `config.py` already going through
   `pathlib` rather than mixing in raw `os.path`/`os.getcwd` string
   handling.
3. **Port `Repl`'s banner as an f-string-per-line (shown above) or a single
   triple-quoted template?** Recommendation: **the per-line f-string
   concatenation shown above** — the box-drawing characters and the
   dynamically-computed padding (`pad`) are easiest to keep correct and
   readable as separate literal lines rather than fighting indentation
   inside a triple-quoted block that also needs an f-string substitution
   mid-line.

## Unchanged — carry forward as-is

`boukensha/registry.py`, `boukensha/tool.py`, `boukensha/message.py`,
`boukensha/prompt_builder.py`, `boukensha/tasks/*.py`,
`boukensha/backends/*.py` (model tables, `parse_response`, `estimate_cost`,
etc.), `boukensha/logger.py` (already has `turn()`/`subscribe()`/the OpenAI
`_provider_name` fix from prior ports), `requirements.txt`. None of these
appear in the Ruby 07→08 diff.

## Verification plan

Same two-layer approach as every prior port in this series:

1. **Offline**, no live API:
   - Construct a `Context`, call `clear_messages()` after adding a few
     messages, assert `context.messages == []` and `context.tools` is
     unchanged — the direct unit-level check for item #2.
   - Run `Agent.run()`/`_wrap_up()` against a fake/monkeypatched `Client`
     for all three return paths (normal completion, wind-down success,
     wind-down `ApiError`) and assert `context.messages[-1]` is the
     `"assistant"` message with the expected text in every case — this is
     the one thing a live smoke test is unlikely to ever exercise for the
     wind-down paths (would need an actual 25-iteration tool-call loop or a
     forced `ApiError` to trigger naturally).
   - Feed a fake `urllib.error.HTTPError(code=401, ...)` through `Client`
     and assert the raised `ApiError`'s message is exactly "authentication
     failed (401) — check your API key", not the generic attempt-count
     message.
   - Create a temp directory, `cd` into it, unset `BOUKENSHA_DIR`, make a
     `.boukensha/` subdirectory there, and assert `Config().dir` resolves
     to that cwd-relative path rather than `~/.boukensha` — the regression
     test for item #4's new middle tier specifically (a live smoke test
     always runs with `BOUKENSHA_DIR` set, so it can never exercise tier 2).
   - Drive `Repl.start()` with `builtins.input` monkeypatched to return a
     canned sequence of lines ending in `/exit`, and assert: (a) the second
     line's `Agent` sees the first line's exchange in `context.messages`,
     (b) `/clear` empties `context.messages`, (c) EOF (raise `EOFError` from
     the patched `input`) breaks the loop without printing "Goodbye." —
     mirrors the live Ctrl-D-vs-`/exit` asymmetry already documented for
     Ruby in `docs/week1_repl_loop_review.md` §2.3.
2. **Live smoke test**: run `./bin/python/08_the_repl_loop` for real against
   the Anthropic backend, typing a few questions (including one that
   references an earlier answer) plus `/clear` plus `/exit`, and compare
   the resulting `.boukensha/sessions/<id>.jsonl` against the real
   `ruby/08_the_repl_loop` session already verified in this iteration's
   Ruby work (`docs/week1_config_troubleshooting.md` entry #25: two `turn`
   entries, each restarting its own `iteration` count at 1) — same phases,
   same field names, values naturally differing (session id, timestamps,
   token counts).
3. Confirm `log_viz` can list and render the Python-generated session
   exactly like the Ruby one — no `log_viz` changes expected, the JSONL
   format is language-agnostic.
