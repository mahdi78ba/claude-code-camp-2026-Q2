# Python Port Plan — Prompt Builder (`03_prompt_builder`)

Plan only — no `boukensha/` code has been written yet, beyond copying
`python/02_the_registry` verbatim into `python/03_prompt_builder` as the
starting point (`.venv/` and `__pycache__/` excluded from the copy, same as
the `01 → 02` port). This document scopes exactly what to change next, and
just as importantly, what to leave alone.

## What actually changed in Ruby (02 → 03)

Confirmed with `diff -rq ruby/02_the_registry ruby/03_prompt_builder`
(vendor/bundle noise stripped):

```
Files 02_the_registry/README.md and 03_prompt_builder/README.md differ
Files 02_the_registry/examples/example.rb and 03_prompt_builder/examples/example.rb differ
Only in 03_prompt_builder/lib/boukensha: backends
Files 02_the_registry/lib/boukensha/config.rb and 03_prompt_builder/lib/boukensha/config.rb differ
Files 02_the_registry/lib/boukensha/context.rb and 03_prompt_builder/lib/boukensha/context.rb differ
Files 02_the_registry/lib/boukensha/errors.rb and 03_prompt_builder/lib/boukensha/errors.rb differ
Only in 03_prompt_builder/lib/boukensha: prompt_builder.rb
Files 02_the_registry/lib/boukensha.rb and 03_prompt_builder/lib/boukensha.rb differ
Only in 03_prompt_builder: prompts
```

`tool.rb`, `message.rb`, `registry.rb`, and everything under `tasks/` are
**byte-identical** between the two Ruby iterations. Two of the files the
diff flags as "differ" are cosmetic only:

- `context.rb` — the only change is a trailing newline at EOF. No behavior
  change.
- `config.rb` — adds one constant, `PROMPTS_DIR = File.expand_path("../../prompts", __dir__).freeze`.

That means the real, behavior-carrying delta is: one new constant
(`Config::PROMPTS_DIR`), one new error class (`UnsupportedModelError`), one
new file (`prompt_builder.rb`), a new `backends/` directory (six files: a
shared `Base` plus five providers), a new `prompts/system.md`, six new
`require_relative` lines, and a rewritten example/README.

**Important cross-check against the current Python tree:** the Python port
already anticipated part of this iteration. `python/02_the_registry` already
has `Config.PROMPTS_DIR` (`config.py`) and a full `tasks/base.py` with
`provider`, `model`, `prompt_override`, `prompt`, and `system_prompt` — all
of the "provider/model/prompt resolution" surface `example.rb` calls into in
this step already exists on the Python side and needs **no changes**. So
this port is narrower than the Ruby diff suggests: it's really just
`errors.py` (one addition), `prompt_builder.py` (new), `backends/` (new),
`prompts/system.md` (already identical — verify, don't rewrite), and the
example/README rewrite.

## Files to add / change in Python

### 1. `boukensha/errors.py` (add one class, keep the existing one)

```python
class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with a model it doesn't support."""
```

Same flatness rule as `UnknownToolError` in the previous port: mirror
Ruby's `UnsupportedModelError < StandardError` as a plain `Exception`
subclass, not a shared `BoukenshaError` base that doesn't exist on the Ruby
side.

### 2. `boukensha/backends/__init__.py` + `base.py` (new package)

Ruby's `Backends::Base` is a class with **class-level** model-table lookup
(`self.models`, `self.model_info`, `self.validate_model!`) and
**instance-level** cost/window accessors that read from the instance's
resolved `@model_info`. Port structure, not idiom-for-idiom mechanically —
Python has no `const_get`/`NameError`-based "must define MODELS" check, so
use a class attribute that concrete subclasses are required to set, and
raise `NotImplementedError` from the base if it's missing:

```python
class Base:
    MODELS: dict = {}

    @classmethod
    def model_info_for(cls, model):
        return cls.MODELS.get(str(model))

    @classmethod
    def validate_model(cls, model):
        model = str(model)
        info = cls.model_info_for(model)
        if info is not None:
            return model
        supported = ", ".join(sorted(cls.MODELS.keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. Supported models: {supported}"
        )

    def __init__(self):
        self.model = None
        self.model_info = None

    def _configure_model(self, model):
        self.model = self.validate_model(model)
        self.model_info = self.model_info_for(self.model)

    @property
    def context_window(self):
        return self.model_info["context_window"]

    @property
    def input_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self):
        return self.model_info["usage_unit"]

    @property
    def usage_level(self):
        return self.model_info.get("usage_level")

    def estimate_cost(self, *, input_tokens, output_tokens):
        i, o = self.input_token_cost_per_million, self.output_token_cost_per_million
        if i is None or o is None:
            return None
        return (input_tokens * i + output_tokens * o) / 1_000_000.0
```

- `MODELS` as a plain class attribute (not requiring `NotImplementedError`
  via a classmethod override) is the more Pythonic equivalent of Ruby's
  `const_get(:MODELS)` pattern — every concrete backend still must define
  it, but Python subclasses overriding a class attribute is the idiomatic
  way, not forcing every backend to implement a `models()` classmethod.
- `_configure_model` mirrors Ruby's `private def configure_model(model)` —
  called from each subclass's `__init__`, not from `Base.__init__` itself
  (Ruby's base has no `initialize` at all; each backend defines its own and
  calls `configure_model` explicitly). Keep that shape: `Base.__init__` just
  sets `model`/`model_info` to `None` as a documented contract, concrete
  `__init__`s call `self._configure_model(model)`.

### 3. `boukensha/backends/anthropic.py`, `gemini.py`, `ollama.py`, `ollama_cloud.py`, `openai.py` (new)

Direct, mechanical ports of the five Ruby backend classes. Model tables,
URLs, and header shapes translate 1:1 (Ruby hash → Python dict, `.freeze` →
nothing needed, Python dicts aren't frozen but nothing in this codebase
mutates a `MODELS` table at runtime). Two things to get right, not just
translate literally:

- **`to_messages` arity is genuinely inconsistent between backends in
  Ruby, and the Python port should reproduce that inconsistency exactly —
  not "fix" it.** `Anthropic#to_messages(messages)` and
  `Gemini#to_messages(messages)` take one argument. `Ollama#to_messages`,
  `OllamaCloud#to_messages`, and `OpenAI#to_messages` take **two**
  (`system, messages`), because those three backends fold the system prompt
  into the messages array as a `role: system` entry rather than sending it
  as a separate top-level field. This means `PromptBuilder#to_messages`
  (which always calls `@backend.to_messages(@context.messages)` with a
  single argument) works for Anthropic/Gemini but would raise
  `ArgumentError` if called against Ollama/OpenAI/OllamaCloud — those three
  only ever get exercised through `to_payload`, never through
  `PromptBuilder#to_messages` directly, in the current example. This is a
  real, pre-existing asymmetry in the Ruby reference (same category as the
  `Tool.parameters` validation gap flagged in the registry port) — port it
  faithfully, and note it in the README's Considerations section rather
  than silently normalizing all five backends to the same signature.
- **`case msg.role` on a Ruby `Message` compares Symbols**
  (`:assistant`, `:tool_result`); the Python `Message.role` field is
  whatever the caller passed to `Context.add_message` — in the existing
  Python examples that's always a plain string (`"user"`, `"assistant"`,
  `"tool_result"`), consistent with `01_struct_skeleton`/`02_the_registry`'s
  established convention of using strings where Ruby uses Symbols (see the
  Registry port's note on `str(name)` vs. `.to_s`). So branch on the string
  value directly (`if msg.role == "tool_result":` / `elif msg.role ==
  "assistant":`), no symbol/string conversion needed — same reasoning as
  the Registry port's dispatch simplification, applied here too.
- `tool.parameters.keys().map(&:to_s)` → Python parameter dict keys are
  already strings (again, no symbol/string split to bridge), so
  `required` is just `list(tool.parameters.keys())`.

Model tables (names, `context_window`, `cost_per_million`,
`usage_unit`, `usage_level`) are copied verbatim from the Ruby source —
they're static tutorial data, not something to "improve" or re-derive.

### 4. `boukensha/prompt_builder.py` (new)

Direct port — `PromptBuilder` has no Ruby-specific idiom to translate
around, it's a thin delegator:

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

Ruby's `headers`/`url` are zero-arg methods; expose them as Python
properties rather than methods to keep call sites (`builder.headers`,
`builder.url`) matching the Ruby call shape (`builder.headers`, no
parens... though Ruby methods are always called without parens for
no-arg methods, so this is a judgment call either way). Properties read
better here since both are pure derived values with no side effect,
consistent with how `Context.tool_count`/`turn_count` are already
properties in the existing Python port rather than methods.

### 5. `boukensha/config.py` — already done, verify only

`PROMPTS_DIR` already exists in the current Python `config.py` and already
points at `<lesson>/prompts` (the Ruby equivalent of
`File.expand_path("../../prompts", __dir__)` relative to `lib/boukensha/`).
**No change needed** — confirm the constant is present after the copy and
move on.

### 6. `boukensha/tasks/base.py` / `player.py` — already done, verify only

`provider`, `model`, `prompt_override`, `prompt`, and `system_prompt` (with
`default_prompts_dir`) all already exist in the copied
`python/02_the_registry` tree. **No change needed.**

### 7. `boukensha/__init__.py` — extend exports

Add the new names, mirroring `lib/boukensha.rb`'s six new
`require_relative` lines:

```python
from .errors import UnknownToolError, UnsupportedModelError
from .prompt_builder import PromptBuilder
from .backends import Base as BackendBase
from .backends.anthropic import Anthropic
from .backends.gemini import Gemini
from .backends.ollama import Ollama
from .backends.ollama_cloud import OllamaCloud
from .backends.openai import OpenAI
```

Consider whether backends belong in the top-level `boukensha` namespace at
all, or should stay under `boukensha.backends.*` the way `Tasks::Base` /
`Tasks::Player` already live under `boukensha.tasks` rather than being
re-exported flat. **Decision: mirror the existing `tasks` precedent** —
expose a `backends` subpackage (`from . import backends`) rather than
flattening `Anthropic`/`Gemini`/etc. into the top-level `__init__.py`, so
`boukensha.backends.Anthropic` reads the same way
`boukensha.tasks.Player` already does. Add `PromptBuilder` and the two
error classes to `__all__`; add `backends` to `__all__` alongside the
existing `tasks` entry.

### 8. `examples/example.py` — rewrite to match Ruby's new `example.rb`

Same structural change as Ruby: add a `look` tool (no params), keep `move`
(with the new `description` key on the `direction` parameter — the Ruby
diff adds `description: "The direction to move"` to that parameter's
schema, carry that over), drop the `shout`/`flee`/`dispatch` demonstration
block entirely (this step's example stops demonstrating registry dispatch
and starts demonstrating payload building), seed the context with three
messages (`user`, `assistant`, `tool_result` with a `tool_use_id`), resolve
`provider`/`model` from `Player`, branch to construct the matching backend
(reading API keys from `os.environ`, matching Ruby's `ENV.fetch`
strictness — let a missing required env var raise, don't default it), and
print the pretty-printed JSON payload (`json.dumps(..., indent=2)` for
Ruby's `JSON.pretty_generate`).

One Python-specific note: Ruby's `case provider ... when "anthropic" ...
else raise ArgumentError` maps to a plain `if/elif/else: raise ValueError`
chain in Python — no need for a dict-dispatch table here, since matching
the Ruby control flow shape 1:1 is more valuable for a learner comparing
both examples than a "more Pythonic" lookup table would be (same
reasoning the Registry port used to reject a decorator-based `tool()` API).

### 9. `prompts/system.md` — verify only

Already byte-identical to Ruby's new `prompts/system.md`
("You are a MUD player assistant...") since the file was copied over from
`02_the_registry` where it already existed unchanged. Confirmed with `diff`
before writing this plan — no action needed.

### 10. `requirements.txt` — no change

`PromptBuilder` only serializes to plain dicts; it does not perform HTTP
requests in this step (same on the Ruby side — no HTTP gem is required by
`03_prompt_builder`'s `Gemfile` beyond what `00_config` already had). No new
Python dependency is introduced.

### 11. `README.md` — port content, with one Python-specific addition

Port the structure of Ruby's `03_prompt_builder/README.md` (intro,
New Files table, architecture diagram, `PromptBuilder` method table,
per-backend sections, the System Prompt / Tool Results / Tool Definitions /
Message Roles comparison tables, Considerations, Expected Output). Add a
short "Porting note" under Considerations calling out the `to_messages`
arity asymmetry documented in item 3 above (Anthropic/Gemini take one arg,
Ollama/OpenAI/OllamaCloud take two) as a faithfully-ported Ruby quirk, not
a Python bug — same treatment the Registry port's README gave the
string/symbol dispatch gotcha it deliberately did *not* carry over.

## Explicitly NOT touched (scope guard)

Per "only port the differences introduced in the Ruby Prompt Builder step,"
these stay exactly as copied from `02_the_registry`, untouched:

- `boukensha/tool.py`, `boukensha/message.py`, `boukensha/registry.py` —
  byte-identical on the Ruby side between `02` and `03`; no reason to
  touch the Python versions.
- `boukensha/config.py`, `boukensha/tasks/*` — the one real Ruby change
  here (`Config::PROMPTS_DIR`) and the task provider/model/prompt-override
  surface the example now exercises were **already ported ahead of time**
  in `02_the_registry`. Verify, don't rewrite.
- `boukensha/context.py` — Ruby's only change was a missing trailing
  newline; not a code change, nothing to port.
- A `week1_baseline/bin/python/03_prompt_builder` runner — out of scope
  for this "prepare the port" step, same precedent as the Registry plan
  (the Ruby runner script and the Python runner script are both added in a
  separate later step, not during the port's own preparation).

## Order of implementation (for the follow-up "do the port" step)

1. `boukensha/errors.py` — add `UnsupportedModelError`
2. `boukensha/backends/base.py`
3. `boukensha/backends/anthropic.py`, `gemini.py`, `ollama.py`,
   `ollama_cloud.py`, `openai.py`
4. `boukensha/backends/__init__.py` — export the five backend classes
   plus `Base`
5. `boukensha/prompt_builder.py`
6. `boukensha/__init__.py` — export update (`PromptBuilder`,
   `UnsupportedModelError`, `backends` subpackage)
7. `examples/example.py` rewrite
8. `README.md` rewrite
9. Run `.venv/bin/python examples/example.py` (after `python3 -m venv
   .venv && .venv/bin/pip install -r requirements.txt`, since
   `03_prompt_builder` was copied without its own `.venv`) with a real or
   dummy `ANTHROPIC_API_KEY` set (whichever provider `settings.yaml`'s
   `player` task selects) and diff its printed JSON payload against the
   Ruby example's output for structural parity, the same way the previous
   two ports were cross-checked.
