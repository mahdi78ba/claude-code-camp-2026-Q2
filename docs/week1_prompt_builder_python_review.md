# Week 1 Review — Prompt Builder Python Port (`python/03_prompt_builder`)

Companion to [`week1_prompt_builder_port_plan.md`](week1_prompt_builder_port_plan.md)
(the plan) and the Ruby-side
[`week1_prompt_builder_review.md`](week1_prompt_builder_review.md) /
[`week1_prompt_builder_verification.md`](week1_prompt_builder_verification.md).
This doc covers what was actually built, how it was verified, and what to
retain going into `04_api_client`.

---

## What was done

1. **Copied `python/02_the_registry` → `python/03_prompt_builder`** verbatim
   (`.venv`/`__pycache__` excluded), same precedent as the `01 → 02` copy.
2. **Wrote the port plan** (`docs/week1_prompt_builder_port_plan.md`) from a
   confirmed `diff -rq ruby/02_the_registry ruby/03_prompt_builder`, then
   cross-checked it against the existing Python tree and found the delta
   was narrower than the raw Ruby diff suggested — `Config.PROMPTS_DIR` and
   `Tasks::Base`'s provider/model/prompt-override methods were already
   ported ahead of schedule in `02_the_registry`.
3. **Implemented the port**, in dependency order: `errors.py`
   (`UnsupportedModelError`) → `backends/base.py` → the five backend
   modules → `backends/__init__.py` → `prompt_builder.py` →
   `boukensha/__init__.py` export update → `examples/example.py` rewrite →
   `README.md`.
4. **Added the runner** `bin/python/03_prompt_builder`, mirroring
   `bin/python/02_the_registry`'s "prefer lesson-local `.venv`, else
   `python3`" shape.
5. **Verified**: byte-diffed the two Python lesson trees, confirmed the
   example runs clean end-to-end against real `.boukensha/` config, and
   independently re-tested the model-validation and cost-estimation
   behavior described below.

Full Problem/Fix/Why entries (if any surfaced) belong in
`week1_config_troubleshooting.md`; none were needed for this port — no
environment or config bugs were hit, unlike the Ruby side's recurring
`BOUKENSHA_DIR` off-by-one.

---

## Code review

### `boukensha.PromptBuilder` (`boukensha/prompt_builder.py`)

```python
class PromptBuilder:
    def __init__(self, context, backend):
        self.context = context
        self.backend = backend

    def to_messages(self):
        return self.backend.to_messages(self.context.messages)

    def to_tools(self):
        return self.backend.to_tools(self.context.tools)

    def to_api_payload(self, *, max_output_tokens=1024):
        return self.backend.to_payload(self.context, max_output_tokens=max_output_tokens)

    @property
    def headers(self):
        return self.backend.headers

    @property
    def url(self):
        return self.backend.url
```

- Pure delegator, same shape as Ruby's — no formatting logic of its own.
  Same "thin façade over storage/behavior it doesn't own" pattern
  `Registry` had over `Context` in the previous iteration.
- `headers`/`url` are Python `@property`, not methods — matches Ruby's
  paren-less zero-arg method calls and the existing `Context.tool_count`/
  `turn_count` property convention already established in earlier
  iterations.
- **The delegation is not uniform in what data it passes** — same as
  Ruby: `to_messages` passes only `context.messages`; `to_api_payload`
  passes the whole `context` so the backend can also reach `context.system`
  and `context.tools`. This split is what causes the interface asymmetry
  below, ported faithfully from Ruby rather than "fixed."

### `boukensha.backends.Base` (`boukensha/backends/base.py`)

```python
class Base:
    MODELS: dict = {}

    @classmethod
    def validate_model(cls, model): ...   # raises UnsupportedModelError if unknown

    def _configure_model(self, model):
        self.model = self.validate_model(model)
        self.model_info = self.model_info_for(self.model)
```

- **Idiom substitution, not a mechanical translation**: Ruby enforces
  "every backend must define `MODELS`" via `const_get(:MODELS)` raising
  `NameError` (caught and re-raised as `NotImplementedError`) the first
  time it's touched. Python has no equivalent constant-lookup-with-rescue
  idiom, so the port uses a plain class attribute (`MODELS: dict = {}` on
  `Base`) that every concrete backend overrides. A backend that forgets to
  define `MODELS` fails the same way Ruby's does — lazily, the first time
  `validate_model` runs against an empty table — just via a different
  mechanism (empty-dict lookup vs. `const_get` exception).
- **Model validation is fail-fast, at construction time** — every
  backend's `__init__` calls `self._configure_model(model)` before doing
  anything else. Verified directly: constructing any of the five backends
  with `model="nonexistent"` raises `UnsupportedModelError` immediately,
  listing the sorted supported models — matches Ruby's behavior exactly
  (spot-checked interactively for all five backends, not just asserted
  from reading the code).
- **Cost helpers degrade in two different, both-intentional ways** —
  reverified interactively, not just read from source:
  - Local `Ollama` models → `estimate_cost(...)` returns a real `0.0`
    (there is a price, and it's zero).
  - `OllamaCloud` models → `estimate_cost(...)` returns `None` (the price
    is *unknown*, plan/usage-tier based) — the guard is
    `if input_cost is None or output_cost is None: return None`, so `0.0`
    and `None` are never conflated.

### The five backends — mechanical port, with two intentional non-mechanical decisions

All five (`Anthropic`, `Gemini`, `Ollama`, `OllamaCloud`, `OpenAI`) are
close to line-for-line translations of their Ruby counterparts (model
tables, URLs, header shapes copied verbatim as static tutorial data). Two
decisions were deliberate, not automatic:

1. **`to_messages` arity stays inconsistent across backends — reproduced,
   not normalized.** `Anthropic.to_messages(messages)` and
   `Gemini.to_messages(messages)` take one argument; `Ollama`,
   `OllamaCloud`, and `OpenAI`'s `to_messages(system, messages)` take two,
   because those three fold the system prompt into the messages array
   themselves. Since `PromptBuilder.to_messages()` always calls the
   1-argument form, calling `builder.to_messages()` against an
   Ollama/OpenAI/OllamaCloud backend raises `TypeError` — verified
   interactively:

   ```
   >>> builder = PromptBuilder(ctx, Ollama(model="gemma4"))
   >>> builder.to_messages()
   TypeError: Ollama.to_messages() missing 1 required positional argument: 'messages'
   ```

   `builder.to_api_payload()` works for all five, because each backend's
   own `to_payload` calls its *own* `to_messages` with the correct arity
   internally. This is the Python-side confirmation of the exact bug the
   Ruby review flagged as "the most important finding in that iteration" —
   preserved deliberately so the two ports stay behaviorally identical,
   not quietly fixed on one side only.
2. **No String/Symbol role branching needed.** Ruby's backends `case` on
   `msg.role` as a Symbol; the Python `Message.role` field has been a
   plain string since `01_struct_skeleton`, so backends branch with
   `if msg.role == "tool_result":` directly — no conversion layer, same
   reasoning as the Registry port's simplified `dispatch` (no
   `transform_keys(&:to_sym)` equivalent needed either).

Confirmed identical to Ruby, not just assumed:

- **Every backend marks every declared parameter as required**,
  unconditionally (`required: list(tool.parameters.keys())`) — no
  optional-tool-parameter concept exists in either language's version.
- **Unhandled roles pass through unchanged** on every backend's `else`
  branch — a future role beyond `user`/`assistant`/`tool_result` degrades
  to "treated like plain text," not an error, on both sides.
- **`backends` is a subpackage** (`boukensha.backends.Anthropic`, etc.),
  not flattened into top-level `boukensha` exports — deliberately mirrors
  the existing `boukensha.tasks` precedent (`boukensha.tasks.Player`)
  rather than inventing a new export shape for this iteration.

---

## Verification performed

Beyond the plan's own smoke-test step, this round of review added:

1. **Byte-diff against `02_the_registry`** (`diff -rq`, `.venv`/
   `__pycache__` excluded) — confirmed `config.py`, `context.py`,
   `message.py`, `registry.py`, `tool.py`, `tasks/*`, `prompts/system.md`,
   and `requirements.txt` are **untouched**, exactly matching the plan's
   scope guard. Only `errors.py`, `__init__.py`, `examples/example.py`,
   `README.md`, `prompt_builder.py`, and `backends/` (new) differ.
2. **Runner smoke test**: `./bin/python/03_prompt_builder` exits `0` and
   prints a complete, valid Anthropic-shaped payload (`model`, `system`,
   `max_tokens`, `tools`, `messages`) — matches the Ruby runner's
   documented output shape field-for-field.
3. **Model-validation fail-fast check** (all five backends, good model +
   bad model) — see snippet above; every backend raises
   `UnsupportedModelError` immediately on an unknown model, none defer the
   failure to payload-build time.
4. **Cost-degradation check** (`Ollama` → `0.0`, `OllamaCloud` → `None`)
   — confirmed interactively, not just from reading the guard clause.
5. **`to_messages` arity-bug reproduction** — confirmed `builder.to_messages()`
   raises for `Ollama` and works for `Anthropic`, matching the Ruby-side
   finding exactly.

---

## Retain — the short list

1. **`PromptBuilder` is a pure delegator** — no formatting logic lives on
   it; everything provider-specific is in `backends/*`.
2. **Model validation is fail-fast, at backend construction** — an
   unsupported/misspelled model in `settings.yaml` fails loudly and
   immediately, on both Ruby and Python.
3. **Cost estimation distinguishes "free" (`0.0`, local Ollama) from
   "unknown" (`None`, Ollama Cloud)** — don't conflate the two when
   reading `estimate_cost`'s return value.
4. **`builder.to_api_payload()` is the only interface-safe `PromptBuilder`
   method today** for OpenAI/Ollama/OllamaCloud backends — `to_messages()`/
   `to_tools()` bypass each backend's own argument handling and will raise
   for the 2-arg group. This is a real Ruby-reference asymmetry, faithfully
   ported, not a Python bug to "fix" independently of the Ruby source.
5. **Every backend requires all declared tool parameters** — no optional
   schema fields exist yet, on either side.
6. **`Config.PROMPTS_DIR` and `Tasks::Base`'s provider/model/prompt
   resolution were already correct before this port started** — verify
   existing code against a new Ruby diff before assuming everything in the
   diff needs porting; some of it may already be done.
7. **Going forward**: as more ports accumulate, later iterations
   (`04_api_client` onward) get a real review pass — model-table parity
   checks, arity/behavior reproduction checks, byte-diff against the prior
   Python iteration — before staging/committing, not just "the example
   script didn't raise."
