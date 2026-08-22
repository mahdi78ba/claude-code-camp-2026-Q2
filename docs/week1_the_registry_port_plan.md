# Python Port Plan — Tool Registry (`02_the_registry`)

Plan only — no `boukensha/` code has been written yet, beyond copying
`python/01_struct_skeleton` verbatim into `python/02_the_registry` as the
starting point. This document scopes exactly what to change next, and just
as importantly, what to leave alone.

## What actually changed in Ruby (01 → 02)

Confirmed with `diff -rq ruby/01_struct_skeleton ruby/02_the_registry`:

```
Files 01_struct_skeleton/README.md and 02_the_registry/README.md differ
Files 01_struct_skeleton/examples/example.rb and 02_the_registry/examples/example.rb differ
Only in 02_the_registry/lib/boukensha: errors.rb
Only in 02_the_registry/lib/boukensha: registry.rb
Files 01_struct_skeleton/lib/boukensha.rb and 02_the_registry/lib/boukensha.rb differ
```

`tool.rb`, `message.rb`, `context.rb`, `config.rb`, and everything under
`tasks/` are **byte-identical** between the two Ruby iterations. So the
entire delta is: two new files (`registry.rb`, `errors.rb`), one require
update (`boukensha.rb`), and a rewritten example/README. That delta is the
only thing this port should touch.

## Files to add / change in Python

### 1. `boukensha/errors.py` (new)

```python
class UnknownToolError(Exception):
    pass
```

- Ruby's `UnknownToolError < StandardError` is a flat, root-level custom
  error — no shared `Boukensha::Error` base exists yet (noted in the Ruby
  review as a seed for later, not needed now). Mirror that flatness: subclass
  plain `Exception`, not some deeper hierarchy, and don't invent a
  `BoukenshaError` base that doesn't exist on the Ruby side.
- Considered and rejected: subclassing `KeyError` (since dispatch is
  fundamentally "no such key in a dict"). Rejected to keep 1:1 parity with
  Ruby's own choice not to specialize the exception type — the Ruby version
  isn't `StandardError` subclassed for a *reason* tied to dict semantics,
  it's just a plain named error, so the Python port shouldn't add semantics
  Ruby doesn't have.

### 2. `boukensha/registry.py` (new)

```python
class Registry:
    def __init__(self, context):
        self.context = context

    def tool(self, name, *, description, parameters=None, block):
        tool = Tool(str(name), description, parameters or {}, block)
        self.context.register_tool(tool)
        return tool

    def dispatch(self, name, args=None):
        tool = self.context.tools.get(str(name))
        if tool is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**(args or {}))
```

Design decisions, called out explicitly since they're not mechanical:

- **`block` is an explicit keyword argument, not a decorator.** Ruby's
  `def tool(name, description:, parameters: {}, &block)` captures a
  `do...end` block implicitly. Python has no equivalent block-capture
  syntax. Two options were considered:
  - *(chosen)* keep `block` as a plain callable argument, called
    positionally/by keyword — e.g.
    `registry.tool("move", description="...", parameters={...}, block=lambda direction: ...)`.
    This preserves the same call shape `01_struct_skeleton`'s Python port
    already used for `Tool(...)` (a `lambda` passed as a value), so the two
    Python iterations stay stylistically consistent with each other, not
    just with Ruby.
  - *(rejected)* a `@registry.tool(...)` decorator (the more idiomatically
    "Pythonic" way to register a callback, à la Flask routes). Rejected
    because it changes the shape of the call site more than the Ruby
    iteration's actual change — the Ruby delta is "route registration
    through an object," not "change how callables get attached," and a
    decorator would blur that comparison for a learner reading both ports
    side by side. Worth revisiting once there's a Python-specific reason to
    prefer it.
- **`name.to_s` → `str(name)`.** Same purpose — coerce to a string key
  before storing so lookups in `dispatch` are guaranteed to match. Trivial
  translation, `str()` is `.to_s`'s direct Python equivalent here.
- **`args.transform_keys(&:to_sym)` has no Python equivalent — and shouldn't
  be ported at all.** This is the most important non-mechanical decision in
  this plan. Ruby needs that line because Ruby draws a hard distinction
  between String and Symbol hash keys, and a block declared with keyword
  parameters (`|message:|`) only accepts Symbol keys — so a String-keyed
  hash (`{"message" => "..."}`, the shape real JSON args would arrive in)
  has to be converted before `**`-splatting it into the call. **Python has
  no such distinction**: `**kwargs` and dict keys are just strings, always.
  A dict like `{"message": "..."}` splats directly into
  `def block(message): ...` with no conversion step. So the Python
  `dispatch` is, correctly, one line simpler than Ruby's — not an
  incomplete port, a reflection of Python not having the problem Ruby's
  extra line exists to solve.
- **No `Tool.parameters` vs. call-arg validation** — same gap as Ruby,
  ported faithfully as a gap: an unregistered name raises `UnknownToolError`,
  but calling a *known* tool with the wrong keyword arguments just raises
  Python's own `TypeError: block() missing 1 required positional argument`
  from inside the call, same asymmetry flagged in the Ruby review.

### 3. `boukensha/__init__.py` — extend exports

Add, mirroring `lib/boukensha.rb`'s two new `require_relative` lines:

```python
from .errors import UnknownToolError
from .registry import Registry
```

Add both names to `__all__` as well.

### 4. `examples/example.py` — rewrite to match Ruby's new `example.rb`

Same structural change as the Ruby example: replace the direct
`ctx.register_tool(Tool(...))` calls with `registry.tool(...)` calls, add a
`Registry(ctx)` construction, and add the three `dispatch` calls (`shout`,
`move`, and the `flee` call that demonstrates catching `UnknownToolError`).
Since Python has no string/symbol gotcha to demonstrate (see above), the
two working `dispatch` calls can just pass plain string-keyed dicts without
any special framing — there's no "watch this get converted" moment to call
out in the printed output, unlike the Ruby version's narration.

### 5. `README.md` — port content, with one Python-specific addition

Port the structure of Ruby's `02_the_registry/README.md` (New Files table,
"How It Works" narrative, `Registry`/`UnknownToolError` method tables,
Expected Output). Add a short "Porting note" the Ruby README doesn't need:
call out explicitly that the Ruby README's "Considerations" section (the
string→symbol dispatch gotcha) is Ruby-specific and does not apply to the
Python port, so a learner comparing both READMEs isn't left looking for
code that was deliberately not carried over.

## Explicitly NOT touched (scope guard)

Per "only port the changes introduced in the Ruby Registry iteration,"
these stay exactly as copied from `01_struct_skeleton`, untouched:

- `boukensha/tool.py`, `boukensha/message.py`, `boukensha/context.py` —
  Ruby made zero changes to `Tool`/`Message`/`Context` in this iteration
  (confirmed by the `diff -rq` above); no reason for the Python versions to
  change either.
- `boukensha/config.py`, `boukensha/tasks/*` — likewise unchanged on the
  Ruby side.
- `prompts/system.md`, `requirements.txt` — no new dependency was
  introduced by the Registry iteration on either side (Ruby's Registry
  needs nothing beyond what `Gemfile` already had).
- A `week1_baseline/bin/python/02_the_registry` runner — out of scope for
  this "prepare the port" step, same way the Ruby side's runner was added
  in a separate later step (`week1_baseline/bin/ruby/02_the_registry`), not
  during the Ruby port's own preparation.

## Order of implementation (for the follow-up "do the port" step)

1. `boukensha/errors.py`
2. `boukensha/registry.py`
3. `boukensha/__init__.py` export update
4. `examples/example.py` rewrite
5. `README.md` rewrite
6. Run `.venv/bin/python examples/example.py` (after `python3 -m venv .venv &&
   .venv/bin/pip install -r requirements.txt`, since `02_the_registry` was
   copied without its own `.venv`) and diff its output against the Ruby
   example's output for parity, the same way `01_struct_skeleton`'s two
   ports were cross-checked.
