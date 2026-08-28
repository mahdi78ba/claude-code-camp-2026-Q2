# Python Port Plan — Context Management (`12_context`)

Baseline for this port is `python/11_tui`, copied verbatim into
`python/12_context` (`.venv/`, `__pycache__/` excluded — machine-local,
regenerated on install; a fresh `.venv` was created for `12_context` and
`pip install -r requirements.txt` already run against it, so the copy
imports cleanly today at `VERSION == "0.11.0"`, pre-port). Confirmed
byte-identical to `11_tui` via `diff -rq --exclude=.venv
--exclude=__pycache__` before any of this plan's changes are applied.

This plan's delta is **only** `ruby/11_tui` → `ruby/12_context`, the same
way `11_tui.md` was `10` → `11`. It is *not* a re-port of MCP or the TUI
layer — both already have full parity in `python/11_tui` (confirmed by
inspection; see "Cross-check" below).

## Important scoping decision: `ruby/12_context` mixes two unrelated things — only one of them is this plan's delta

Diffing `ruby/11_tui` against `ruby/12_context` file-by-file turns up two
very different categories of change, and conflating them would make this
plan port things that were never step 12's actual content:

1. **Real "Step 12 — Context Management" content** — everything
   `ruby/12_context/README.md`'s own "What's new" section documents:
   accurate context tracking, colour-coded usage, auto-compaction,
   `Context#compact_messages!`, `/compact`, `Logger#compaction`, and the
   `context_window:` keyword. This is what this plan ports.
2. **An unrelated, pre-existing structural divergence**: `ruby/12_context`
   also replaced `Config`'s `tasks()`-hash / `Tasks::Player` pattern with
   flat `provider_type`/`model`/`system_prompt`/`agent_*` accessor
   methods, and correspondingly `Context` dropped its `task:` parameter,
   `Agent` dropped `task_settings:` and lost its task/backend-aware,
   multi-provider `_log_response`/`_normalized_usage` (Anthropic/OpenAI/
   Gemini/Ollama key-name normalization, cost estimation) in favor of a
   plain `response(text:, usage:, stop_reason:)` call, and `Repl` dropped
   `task_settings:` too. **None of this is mentioned anywhere in
   `ruby/12_context/README.md`**, and this exact tension was already
   flagged — and deliberately *not* ported — during this same session's
   own Ruby-side delta work (`docs/week1_config_troubleshooting.md`
   entries #33/#34/#41: "12_context's own provider_type/model/agent_*
   accessors — this step's own shape, already diverged from 11_tui's
   tasks()-hash approach — untouched"). It predates step 12 conceptually;
   it's an artifact of how this teaching repo's `12_context` starter
   happened to be shaped, not something step 12 is "about."

**Decision: category 2 is out of scope for this plan.** Python's existing
`task_settings`/`Tasks::Player`-based `Config`/`Context`/`Agent`/`Repl`
plumbing, and `Logger`'s richer multi-backend `response()` (normalized
usage across providers, cost estimation) stay exactly as they are —
porting category 2 would be a straight *regression* in Python (it would
delete working multi-backend support to match a Ruby file that itself
lost it as a side effect of an unrelated refactor, not as step 12 work).
The four genuinely new config knobs this step introduces
(`agent_max_turn_tokens`, `agent_compaction_threshold` — see below for why
only these two, not all four of Ruby's `agent_*` accessors, get ported)
are added as pure *additions* alongside the existing task-scoped
resolution, not a replacement of it.

## What actually changed in Ruby (11 → 12, cumulative) — the real delta

1. **New `Boukensha::Models` module** (`lib/boukensha/models.rb`) — a
   static `model → {context_window:}` table (`claude-opus-4-8`,
   `claude-sonnet-4-6`, `claude-haiku-4-5`, all `200_000`) plus
   `DEFAULT_CONTEXT_WINDOW = 32_000` for an unrecognized model id.
   `Models.context_window(model)` looks it up.
2. **`Context` gains real token/budget tracking** (`lib/boukensha/
   context.rb`):
   - `context_window:` (default `200_000`), `compaction_threshold:`
     (default `0.85`) — new constructor kwargs.
   - `current_tokens` (read/write) — the *last* response's
     `usage.input_tokens`, not a running sum. Set via `update_tokens(n)`.
   - `turn_tokens` (read-only) — cumulative input+output tokens *this
     turn only* (the spend budget, distinct from `current_tokens`'s
     window-pressure signal). `reset_turn_tokens` (called at the top of
     each turn) zeroes it; `add_turn_tokens(input, output)` accumulates.
   - `usage_fraction` (`current_tokens / context_window`, `0.0` if
     `context_window <= 0`) and `usage_pct` (rounded `%`).
   - `needs_compaction?(threshold: compaction_threshold)` —
     `usage_fraction >= threshold`.
   - `compact_messages!(target_fraction: 0.60)` — drops the oldest 40% of
     messages (`[(size * 0.40).ceil, size - 2].min`, floored at 0, so at
     least 2 messages always survive), resets `current_tokens` to `0`
     (the next response will report the true new size), returns the
     number of messages dropped. `target_fraction:` is accepted for API
     parity with Ruby but unused by the current drop-oldest-40% logic in
     *either* language — carry the same unused kwarg, don't "fix" it here
     (matches Ruby's own shape exactly; not this plan's problem to solve).
   - `clear_messages!` now also resets `current_tokens` to `0` (it didn't
     touch token state at all in `11_tui`, since `11_tui`'s `Context` had
     no token state).
3. **`Agent` gains a per-turn spend ceiling and automatic compaction**
   (`lib/boukensha/agent.rb`):
   - `max_turn_tokens:` — new constructor kwarg (`nil`/`0` disables it,
     same "trigger threshold, not hard cap" semantics as
     `max_iterations:`).
   - `token_limit_reached?` — `@max_turn_tokens.positive? &&
     @context.turn_tokens >= @max_turn_tokens` — checked every loop
     iteration alongside `iteration_limit_reached?`; either one triggers
     the same `wrap_up` path, just with `kind: "max_tokens"` logged
     instead of `"max_iterations"`.
   - `record_usage(response)` — called after *every* API response
     (including mid-turn tool-use responses, not just the turn's final
     one): calls both `context.add_turn_tokens(input, output)` **and**
     `context.update_tokens(input)`. This is what makes the context
     display always reflect what the *next* call will actually send.
   - `run` now starts with `context.reset_turn_tokens` then
     `compact_if_needed` (in that order), before the loop begins.
   - `compact_if_needed` — private; no-ops unless
     `context.needs_compaction?`; otherwise calls
     `context.compact_messages!` and `logger.compaction(before:,
     dropped:, context_window:)`.
   - `wrap_up` also calls `record_usage` on its own (wind-down) response.
4. **`Logger` gains two small additions** (`lib/boukensha/logger.rb`):
   - `prompt(messages:, tools:, context_window:)` — one new kwarg,
     included in the logged event. (Everything else about `prompt` is
     unchanged.)
   - `compaction(before:, dropped:, context_window:)` — new method,
     writes `{phase: "compaction", before:, dropped:, context_window:}`.
   - (Ruby's `response()` also lost its `task:`/`backend:` params in
     `12_context` — that's category 2, not ported; see above.)
5. **`Repl` gains `/compact` and threads `max_turn_tokens` through**
   (`lib/boukensha/repl.rb`):
   - `HELP` and the banner gain a `/compact` line.
   - `handle_command` gains an `"/compact"` branch: calls
     `context.compact_messages!`, outputs `"(compacted context — N
     messages dropped)"`, returns `"command"`.
   - Constructor gains `max_turn_tokens:`; `run_turn` passes it to the
     `Agent` it builds per turn (alongside `max_iterations:`/
     `max_output_tokens:`, which Python's `Repl` already threads through
     unchanged).
6. **`Boukensha.run`/`Boukensha.repl` gain a `context_window:` keyword**
   (`lib/boukensha.rb`): defaults to `Models.context_window(model)` when
   not given; passed into `Context.new` along with
   `compaction_threshold:`. (Ruby also re-sources `max_iterations:`/
   `max_output_tokens:`/`max_turn_tokens:` from its new flat
   `cfg.agent_*` accessors here instead of task-scoped ones — that
   re-sourcing is category 2; see the judgment call below for what
   Python does instead.)
7. **TUI (`lib/boukensha/tui.rb`)**:
   - Progress line (idle state) and status bar now show
     `ctx <current>/<window> (<pct>%)` — `current`/`window` both
     formatted via a `fmt_tokens` helper (`"7.7k"` style above 1000) —
     instead of a plain token count.
   - Colour-coded: grey (`< 70%`), yellow (`70–84%`), red (`>= 85%`), via
     a small `ctx_color(pct)` helper. A `⚠` appears in the status bar at
     `>= 85%`.
   - Subscribes to (already-generic) `Logger#subscribe` the same as
     before, but now also handles a `"compaction"` event: appends
     `"[context compacted — N messages dropped to free space]"` to the
     conversation view.
   - The live (in-progress) line's `↑`/`↓` token readout was *already*
     present in `11_tui`'s `tui.rb` (per-turn `turn_input_tokens`/
     `turn_output_tokens`, fed by the `"response"` event) — not new here,
     no Python action needed beyond what's already there.

## Cross-check against the current Python tree

| Ruby | Already in `python/11_tui`? |
|---|---|
| `Tools::Mcp` / `mcp_servers:` | Yes — `boukensha/tools/mcp.py`, `Config.mcp_servers()` |
| `Registry.registered()` | Yes — `boukensha/registry.py` |
| `Logger.subscribe()` | Yes — `boukensha/logger.py` |
| `Tui` four-zone layout, background worker, event queue | Yes — `boukensha/tui.py` |
| Multi-backend usage normalization / cost estimation in `Logger.response()` | Yes — richer than Ruby's *own* `12_context` (see scoping decision above) — **keep, don't touch** |

So the entire real delta for this plan is: the new `Models` module,
`Context`'s token/compaction machinery, `Agent`'s per-turn budget +
auto-compaction trigger, `Logger`'s two additions, `Repl`'s `/compact`,
`run()`/`repl()`'s `context_window:` keyword, and the TUI's context
display + compaction-event handling — nothing MCP- or TUI-*infrastructure*
related.

### Python's `tui.py` already has a bug this step exists to fix — a good sign, not a blocker

Ruby's own `README.md` says step 12 fixes exactly this: "the cumulative
session token sum was shown as usage, which grew without bound even after
`/clear`." Checking `python/11_tui/boukensha/tui.py` directly:
`self._session_input_tokens += input_tokens` on every `"response"` event,
**never reset**, shown in both `_refresh_progress`/`_refresh_status` as
`"ctx {self._session_input_tokens}"`. This is the *identical* pre-step-12
bug Ruby describes — confirming this step's Python delta is real,
necessary work, not a no-op cross-check like some of `11_tui.md`'s MCP
table entries were.

## Judgment calls (flag for the implementer, don't silently decide)

1. **Keep `task_settings`/`Tasks::Player` plumbing, or mechanically match
   `ruby/12_context`'s literal removal of it?** **Decided: keep.** See
   "Important scoping decision" above — removing it would delete working,
   already-ported, multi-backend functionality to chase an unrelated
   refactor that isn't step 12's content in the first place.
2. **Where do the two genuinely new settings.yaml knobs
   (`agent_max_turn_tokens`, `agent_compaction_threshold`) live in
   `Config`, if not replacing the task-scoped accessors?** Recommendation:
   two new, flat, additive methods on `Config` — `agent_max_turn_tokens()`
   and `agent_compaction_threshold()` — reading a *new*, separate
   `agent:` top-level settings.yaml block (mirroring Ruby's own
   `agent_max_turn_tokens`/`agent_compaction_threshold` accessors
   exactly, just without also duplicating the two knobs — `max_iterations`
   /`max_output_tokens` — Python already resolves perfectly well via
   `Tasks::Player`/`task_settings`). Defaults: `60_000` and `0.85`
   respectively, matching Ruby.
   ```python
   # config.py, alongside mcp_servers()
   def agent_max_turn_tokens(self):
       v = self.dig("agent", "max_turn_tokens")
       return 60_000 if v is None else int(v)

   def agent_compaction_threshold(self):
       v = self.dig("agent", "compaction_threshold")
       return 0.85 if v is None else float(v)
   ```
3. **`DEFAULT_CONTEXT_WINDOW` for an unrecognized model.** Recommendation:
   `32_000`, matching Ruby exactly — an arbitrary-but-conservative
   fallback, not something to independently re-derive.
4. **New module name/location for the model table.** Recommendation:
   `boukensha/models.py`, mirroring `lib/boukensha/models.rb` 1:1 — a
   flat dict + one lookup function, no class needed:
   ```python
   # boukensha/models.py
   TABLE = {
       "claude-opus-4-8": {"context_window": 200_000},
       "claude-sonnet-4-6": {"context_window": 200_000},
       "claude-haiku-4-5": {"context_window": 200_000},
   }
   DEFAULT_CONTEXT_WINDOW = 32_000

   def context_window(model):
       return TABLE.get(str(model), {}).get("context_window", DEFAULT_CONTEXT_WINDOW)
   ```
5. **TUI colour coding: Textual CSS classes vs. inline `Style` /
   `.styles.color` at render time?** Recommendation: set
   `widget.styles.color` directly inside `_refresh_progress`/
   `_refresh_status` based on `usage_pct` (a small `_ctx_color(pct)`
   helper returning a colour name/hex, same shape as Ruby's
   `ctx_color(pct)`) — simplest change to the two methods that already
   exist, no new CSS classes or stylesheet edits needed. What must be
   preserved is the *visual outcome* (grey/yellow/red thresholds, `⚠` at
   ≥85%), not the exact mechanism — matches `11_tui.md`'s own
   "implementation philosophy" section (Textual idiom over mechanical
   transliteration) .
6. **`VERSION` value.** Recommendation: `"0.12.0"` — same
   tracks-the-Ruby-step-number convention as every prior version bump in
   this series.
7. **`_session_input_tokens` naming in `tui.py`.** Since its meaning
   changes from "cumulative sum, never reset" to "current window
   pressure, reset by compaction," recommend renaming the attribute (e.g.
   `self._current_tokens`) rather than keeping the old name with new
   semantics — avoids a future reader assuming it's still a running sum
   from the name alone. Purely a naming call, not a behavior one.

## Files to add / change in Python

### 1. `requirements.txt` — unchanged

No new dependency — `Models`/`Context`/`Agent`/`Logger`/`Repl` changes are
all pure Python; the TUI changes only touch widgets `tui.py` already
imports.

### 2. `boukensha/version.py`

```python
VERSION = "0.12.0"
```

### 3. `boukensha/models.py` — new

See judgment call #4 above for the full content.

### 4. `boukensha/context.py` — add token/compaction state

```python
class Context:
    def __init__(self, *, task, system=None, working_dir=None,
                 context_window=200_000, compaction_threshold=0.85) -> None:
        self.task = task
        self.system = system
        self.working_dir = str(Path(working_dir).resolve()) if working_dir else None
        self.context_window = context_window
        self.compaction_threshold = compaction_threshold
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.current_tokens = 0
        self.turn_tokens = 0

    # ... register_tool, add_message unchanged ...

    def update_tokens(self, n) -> None:
        """Update the known context size from the last API response's input_tokens."""
        self.current_tokens = int(n or 0)

    def reset_turn_tokens(self) -> None:
        """Reset the cumulative per-turn spend counter. Called at the top of a turn."""
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens, output_tokens) -> None:
        """Add one API call's input+output tokens to the cumulative per-turn
        total — the spend budget, distinct from current_tokens (window
        pressure)."""
        self.turn_tokens += int(input_tokens or 0) + int(output_tokens or 0)

    @property
    def usage_fraction(self) -> float:
        if self.context_window <= 0:
            return 0.0
        return self.current_tokens / self.context_window

    @property
    def usage_pct(self) -> int:
        return round(self.usage_fraction * 100)

    def needs_compaction(self, *, threshold=None) -> bool:
        threshold = self.compaction_threshold if threshold is None else threshold
        return self.usage_fraction >= threshold

    def compact_messages(self, *, target_fraction=0.60) -> int:
        """Drop the oldest 40% of messages (keeping at least 2). Resets
        current_tokens to 0 (updated by the next API response). Returns
        the number of messages dropped."""
        drop_count = min(math.ceil(len(self.messages) * 0.40), len(self.messages) - 2)
        drop_count = max(drop_count, 0)
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    def clear_messages(self) -> None:
        self.messages = []
        self.current_tokens = 0

    # ... tool_count/turn_count/__str__ unchanged (import math at top) ...
```

Python naming convention already established in this file (`snake_case`
methods, no `!`/`?` suffixes — e.g. `clear_messages` not `clear_messages!`)
is kept: `compact_messages`/`needs_compaction`, not
`compact_messages!`/`needs_compaction?`.

### 5. `boukensha/agent.py` — per-turn budget + auto-compaction

```python
def __init__(self, *, context, registry, builder, client, logger=None,
             task_settings=None, max_iterations=None, max_turn_tokens=None,
             max_output_tokens=None):
    ...
    self._max_turn_tokens = int(max_turn_tokens or 0)  # 0 = disabled
    ...

def run(self):
    self.context.reset_turn_tokens()
    self._compact_if_needed()

    while True:
        if self._iteration_limit_reached():
            ...
            return self._wrap_up("max_iterations")
        if self._token_limit_reached():
            self.logger.limit_reached(
                kind="max_tokens", n=self.context.turn_tokens, max=self._max_turn_tokens
            )
            return self._wrap_up("max_tokens")

        self._iteration += 1
        self.logger.iteration(n=self._iteration, max=self._max_iterations)
        self.logger.prompt(messages=self.context.messages, tools=self.context.tools,
                            context_window=self.context.context_window)

        response = self.client.call(**self._call_opts())
        self.logger.raw(data=response)
        parsed = self.builder.parse_response(response)
        self._record_usage(response)

        if parsed["stop_reason"] == "tool_use":
            self._handle_tool_calls(parsed["content"], response)
        else:
            text = self._extract_text(parsed["content"])
            self._log_response(text=text, response=response)
            self.logger.turn_end(reason="completed", iterations=self._iteration)
            self.context.add_message("assistant", text)
            return text

def _token_limit_reached(self):
    return self._max_turn_tokens > 0 and self.context.turn_tokens >= self._max_turn_tokens

def _record_usage(self, response):
    usage = self._normalized_usage(response) or {}
    self.context.add_turn_tokens(usage.get("input_tokens"), usage.get("output_tokens"))
    self.context.update_tokens(usage.get("input_tokens"))

def _compact_if_needed(self):
    if not self.context.needs_compaction():
        return
    before = self.context.current_tokens
    dropped = self.context.compact_messages()
    self.logger.compaction(before=before, dropped=dropped,
                            context_window=self.context.context_window)
```

`_wrap_up` gains one line — `self._record_usage(response)` — right after
its own successful `client.call(...)`, mirroring Ruby's `wrap_up` calling
`record_usage` on the wind-down response too. `_normalized_usage` is
already keyed on Anthropic's `input_tokens`/`output_tokens` names as its
top-level normalized output (per the existing docstring/comment in
`tui.py` referencing this same normalization) — `_record_usage` above
reads exactly those two keys back out, so no change needed to
`_normalized_usage` itself.

### 6. `boukensha/logger.py` — two additions

```python
def prompt(self, *, messages, tools, context_window):
    self._write_log({
        "phase": "prompt",
        "message_count": len(messages),
        "messages": [self._serialize_message(m) for m in messages],
        "tool_count": len(tools),
        "tools": list(tools.keys()),
        "context_window": context_window,
    })

def compaction(self, *, before, dropped, context_window):
    self._write_log({
        "phase": "compaction", "before": before, "dropped": dropped,
        "context_window": context_window,
    })
```

(Exact private-method names — `_write_log`/`_serialize_message` — should
match whatever this file already calls them; adjust to match, this is
illustrative of the two new/changed call shapes, not a literal diff.)
`response()` is **not** touched (see scoping decision above).

### 7. `boukensha/config.py` — two new additive accessors

See judgment call #2 above for the full content (`agent_max_turn_tokens()`,
`agent_compaction_threshold()`).

### 8. `boukensha/repl.py` — `/compact` + `max_turn_tokens`

```python
HELP = """Commands:
  /clear    wipe conversation history (tools stay)
  /compact  drop oldest 40% of messages to free context
  /exit     leave the REPL
  /help     show this message
"""

class Repl:
    def __init__(self, *, ..., max_turn_tokens=None, ...):
        ...
        self.max_turn_tokens = max_turn_tokens
        ...

    def banner(self):
        ...
        # add "  /compact         free context (drop oldest messages)\n"
        # to the banner body, same spot as Ruby's tui.rb / repl.rb banner.

    def handle_command(self, line):
        ...
        elif line == "/compact":
            dropped = self.context.compact_messages()
            self._output(f"(compacted context — {dropped} messages dropped)")
            return "command"
        return None

    def run_turn(self, line):
        ...
        agent = Agent(
            context=self.context, registry=self.registry, builder=self.builder,
            client=self.client, logger=self.logger, task_settings=self.task_settings,
            max_iterations=self.max_iterations, max_turn_tokens=self.max_turn_tokens,
            max_output_tokens=self.max_output_tokens,
        )
        ...
```

### 9. `boukensha/__init__.py` — `run()`/`repl()` gain `context_window=`

```python
from . import models  # new

def run(*, task, system=None, model=None, backend=None, api_key=None,
        ollama_host="http://localhost:11434", log=None,
        context_window=None, max_output_tokens=None, working_dir=None,
        allowed_commands=None, shell_timeout=30, mcp=None, configure=None):
    cfg = get_config()
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())
    ...
    if context_window is None:
        context_window = models.context_window(model)
    ...
    ctx = Context(task=task_class, system=system, working_dir=working_dir,
                  context_window=context_window,
                  compaction_threshold=cfg.agent_compaction_threshold())
    ...
    agent = Agent(
        context=ctx, registry=registry, builder=builder, client=client,
        logger=logger, task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_turn_tokens=cfg.agent_max_turn_tokens(),
        max_output_tokens=effective_max_output_tokens,
    )
    ...
```

Same shape added to `repl()`, plus threading `max_turn_tokens=
cfg.agent_max_turn_tokens()` into the `Repl(...)` constructor call
alongside the existing `max_iterations=`/`max_output_tokens=`. Note this
keeps `effective_max_iterations`/`effective_max_output_tokens` sourced
from `task_class`/`task_settings` exactly as `11_tui` already does (see
judgment call #1) — only `context_window` and `max_turn_tokens` are newly
threaded through, and only the latter comes from `Config` directly
(`max_iterations`/`max_output_tokens` stay task-scoped).

### 10. `boukensha/tui.py` — context display + compaction event

- Rename `self._session_input_tokens` → `self._current_tokens` (judgment
  call #7), initialized to `0`.
- In `_handle_event`, replace the `"response"` branch's
  `self._session_input_tokens += input_tokens` with
  `self._current_tokens = input_tokens` (assignment, not accumulation —
  this is the actual bug fix step 12 exists to make). Add a new branch:
  ```python
  elif phase == "compaction":
      dropped = event.get("dropped")
      self.query_one("#conversation", RichLog).write(
          f"[context compacted — {dropped} messages dropped to free space]"
      )
  ```
- `_refresh_progress`/`_refresh_status`: read `self.repl.context.
  context_window`/`.usage_pct` (via `self.repl.context`, already exposed)
  instead of formatting `self._current_tokens` alone — e.g.
  `f"ctx {self._current_tokens}/{ctx_window} ({pct}%)"` — and set
  `.styles.color` on the `Static` per judgment call #5's
  `_ctx_color(pct)` helper. Add the `⚠` marker to `_refresh_status` at
  `pct >= 85`.
- `on_mount`'s `self.repl.logger.subscribe(...)` call is unchanged — the
  new `"compaction"` event flows through the exact same `queue.Queue` +
  `_tick()` drain every other event already uses; no new wiring needed,
  only a new `elif` branch in the already-existing dispatch.

### 11. `README.md` — full rewrite, not a diffed port

Same convention as the `11_tui.md` plan's own README item: describe
step 12's actual "what's new" (accurate context tracking, colour coding,
auto-compaction, `/compact`, `Logger.compaction()`, `context_window=`),
in Python's own terms — not a line-by-line translation of Ruby's
`README.md`, and *not* mentioning the category-2 config refactor this
plan deliberately didn't port.

## Unchanged — carry forward as-is

`boukensha/client.py`, `boukensha/errors.py`, `boukensha/message.py`,
`boukensha/prompt_builder.py`, `boukensha/registry.py`, `boukensha/tool.py`,
`boukensha/run_dsl.py`, `boukensha/tasks/*.py`, `boukensha/backends/*.py`,
`boukensha/tools/*.py` (file_system/shell/mcp — already fully ported),
`examples/example.py`, `examples/repl.py`, `prompts/system.md`. Also
unchanged, deliberately, despite `ruby/12_context` touching the
equivalent Ruby files: `Config.tasks()`/task-scoped resolution,
`Context.task`, `Agent`'s `task_settings`/multi-backend
`_normalized_usage`/cost-estimation plumbing, `Logger.response()` — see
"Important scoping decision" above.

## Verification plan

Same two-layer approach as every prior port in this series, plus a third
layer specific to this step (proving *automatic* compaction fires, not
just that the code compiles) — mirrors exactly how this was verified on
the Ruby side (`docs/week1_config_troubleshooting.md` entry #44):

1. **Offline, no live API:**
   - `Context` unit tests: `usage_fraction`/`usage_pct` arithmetic at a
     few known `(current_tokens, context_window)` pairs; `0.0`/`0%` when
     `context_window <= 0`; `needs_compaction()` flips at exactly the
     threshold; `compact_messages()`'s drop count and the "at least 2
     survive" floor across message-list sizes of 0, 1, 2, 3, 5, 100;
     confirms `current_tokens` resets to `0` after `compact_messages()`
     and after `clear_messages()`.
   - `Agent` unit test against a stubbed `Client`/`Registry` (no real
     API): confirm `record_usage` updates both `context.turn_tokens`
     (cumulative) and `context.current_tokens` (latest only, not summed)
     after each stubbed response; confirm a turn that exceeds a tiny
     stubbed `max_turn_tokens` triggers `_wrap_up("max_tokens")` the same
     way `max_iterations` does today.
2. **A cheap, deterministic *automatic*-compaction test** — same trick
   used for the Ruby verification: construct a `Context` with a
   deliberately tiny `context_window` (e.g. `2000`) so a single stubbed
   response's `input_tokens` already exceeds the 85% threshold, then
   confirm the *next* `Agent.run()` call's `_compact_if_needed()` fires
   on its own (no manual `/compact`) before making its first API call of
   that turn — assert `logger.compaction` was invoked and
   `context.messages` shrank. Cheap and fast because it never needs a
   real, long conversation to actually reach 85% of a real 200k window.
3. **Live smoke test**: `./bin/python/12_context` (new runner, same shape
   as `bin/python/11_tui`, just pointed at this directory) both with and
   without `--no-tui`, against the real Anthropic backend and the live
   MUD MCP server — confirm the status bar shows `ctx <n>/<window> (<pct>
   %)` with correct colour at low usage, send enough turns (or use a
   small `context_window` override) to cross 85% and confirm both the
   `⚠` marker appears and `[context compacted — N messages dropped to
   free space]` shows up in the conversation view unprompted, then
   `/compact` by hand and confirm it also works. Matches the acceptance
   shape of `docs/week1_config_troubleshooting.md` entry #44 on the Ruby
   side (same task, same checks, just in Python).
