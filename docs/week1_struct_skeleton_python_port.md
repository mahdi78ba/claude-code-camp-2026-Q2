# Week 1 — Python Port of the Struct Skeleton (`01_struct_skeleton`)

What was done, the choices made along the way, how each ported component
works, the core Python features used, and what running it actually showed.

---

## What was done

1. **Duplicated** `week1_baseline/python/00_config` →
   `week1_baseline/python/01_struct_skeleton` (via `rsync`, excluding
   `.venv`/`__pycache__` — those are machine-local build artifacts, not part
   of the lesson template). `Config`/`Tasks::Base`/`Tasks::Player` came
   along unchanged; only they existed in `00_config`.
2. **Ported the new Ruby code** from `ruby/01_struct_skeleton/lib/boukensha/`
   — `tool.rb`, `message.rb`, `context.rb` — into three new Python modules,
   plus updated `boukensha/__init__.py`'s exports and rewrote
   `examples/example.py` and `README.md` to match.
3. **Added a runner**, `bin/python/01_struct_skeleton`, mirroring the one
   already added for Ruby (`bin/ruby/01_struct_skeleton`).
4. **Ran it and reviewed the generated code** before anything gets
   committed.

## Choices made

Two decisions were explicitly put to the user before writing any code
(via a Plan-mode design pass), because they set a precedent for every
future Ruby→Python iteration, not just this one:

- **`Tool` and `Message` → `@dataclass`.** Ruby expresses both as
  lightweight `Struct.new(...)`. Python's stdlib `dataclasses` is the
  direct equivalent — auto-generated `__init__`, declared fields, mutable
  by default. This is the **first dataclass in the Python port**
  (`00_config` is 100% plain classes with explicit `__init__`), so it was
  confirmed rather than assumed.
- **`Tool.__str__`'s `params=` mirrors Ruby's symbol formatting exactly**
  — `params=[:direction]`, not the more Pythonic `params=['direction']`.
  Chosen so the two runtimes' output stays byte-for-byte comparable while
  both ports are being verified side by side.

Two smaller calls were made without asking, low-stakes and consistent with
precedent already set in `docs/week1_struct_skeleton_review.md`:

- **`examples/example.py` mirrors, rather than "fixes," a Ruby quirk**:
  the Ruby example's `system_prompt(...)` call omits `default_prompts_dir`.
  Verified this still resolves real text on this checkout (the repo's
  `.boukensha/settings.yaml` has `prompt_override.system: true` and
  `.boukensha/prompts/player/system.md` exists), so porting it literally is
  faithful parity, not a broken port.
- **The Python README drops `token_budget` from `Context`'s field table
  entirely**, rather than documenting it as "planned." The Ruby review
  already flagged `token_budget` as documented-but-not-implemented in the
  Ruby code; the Python README should describe what the code actually does.

`Context` itself was **not** made a dataclass — matching Ruby's own
deliberate choice to keep `Context` a plain class, since it carries
behavior (`register_tool`, `add_message`, counters) and a required field
(`task`), not just a flat tuple of values.

## The components, Ruby → Python

### `Tool` (`tool.rb` → `tool.py`)

Ruby:
```ruby
Tool = Struct.new(:name, :description, :parameters, :block) do
  def to_s
    "#<Tool name=#{name} description=#{description.to_s[0..40]} params=#{parameters.keys}>"
  end
end
```

Python:
```python
@dataclass(repr=False)
class Tool:
    name: str
    description: str
    parameters: dict
    block: Callable[..., str]

    def __str__(self) -> str:
        params = ", ".join(f":{k}" for k in self.parameters.keys())
        return (
            f"#<Tool name={self.name} description={self.description[:41]} "
            f"params=[{params}]>"
        )

    __repr__ = __str__
```
`description[:41]` reproduces Ruby's *inclusive* `description.to_s[0..40]`
41-char slice (Python slicing is exclusive of the end index, so `[0..40]`
inclusive → `[:41]`). The `params` line hand-builds a `:key`-per-item string
to visually match Ruby's symbol array rather than relying on Python's
native list `repr`.

### `Message` (`message.rb` → `message.py`)

Ruby:
```ruby
Message = Struct.new(:role, :content, :tool_use_id) do
  def to_s
    id_tag = tool_use_id ? " [#{tool_use_id}]" : ""
    "#<Message role=#{role}#{id_tag} content=#{content.to_s[0..60]}...>"
  end
end
```

Python:
```python
@dataclass(repr=False)
class Message:
    role: str
    content: str
    tool_use_id: str | None = None

    def __str__(self) -> str:
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        return f"#<Message role={self.role}{id_tag} content={self.content[:61]}...>"

    __repr__ = __str__
```
Same inclusive-slice translation (`[0..60]` → `[:61]`), same
always-append-`"..."` behavior (even for content shorter than 61 chars) —
kept as-is, not "fixed," to match Ruby's actual behavior. `tool_use_id`
defaults to `None`, same as Ruby's Struct field defaulting to `nil`.

### `Context` (`context.rb` → `context.py`)

Ruby:
```ruby
class Context
  attr_reader :task, :system, :messages, :tools

  def initialize(task:, system: nil)
    @task, @system, @messages, @tools = task, system, [], {}
  end

  def register_tool(tool) = @tools[tool.name] = tool
  def add_message(role, content, tool_use_id: nil) = @messages << Message.new(role, content, tool_use_id)
  def tool_count = @tools.size
  def turn_count = @messages.size

  def to_s
    "#<Context task=#{task&.task_name} turns=#{turn_count} tools=#{tool_count}>"
  end
end
```

Python:
```python
class Context:
    def __init__(self, *, task, system=None) -> None:
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role, content, *, tool_use_id=None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        task_name = None if self.task is None else self.task.task_name()
        return f"#<Context task={task_name} turns={self.turn_count} tools={self.tool_count}>"

    __repr__ = __str__
```
`task` is **required and keyword-only** (`*, task, ...` — no positional
form), matching Ruby's required `task:`; `system` is keyword-only with a
default, matching `system: nil`. `tools` is a `dict` keyed by `tool.name`,
not a list — so, deliberately mirroring Ruby, registering two tools with
the same name silently overwrites the first. `task_name = None if ... else
...` mirrors Ruby's `task&.task_name` — a plain `None`-check, not
`getattr(task, "task_name", lambda: None)()`, because Ruby's `&.` only
guards against `nil`; it does *not* swallow a genuinely missing method. A
`getattr` fallback would hide that case instead of raising, which would be
a subtle behavioral drift from what the Ruby actually does.

## Python features used to build the port

- **`dataclasses.dataclass`** — the mechanism for `Tool`/`Message`. Auto-
  generates `__init__`, `__eq__`, and field storage from type-annotated
  class attributes; `repr=False` was passed to suppress the auto-generated
  `__repr__` since a custom Ruby-style one was needed instead.
- **`__str__` / `__repr__ = __str__`** — Python's two string-conversion
  hooks (`str(x)` and `repr(x)`/interactive display) pointed at the same
  method, so both always show the Ruby-style `#<...>` form. This mirrors
  the pattern already used by `Config` in `00_config`.
- **`from __future__ import annotations`** — deferred evaluation of type
  hints, letting `str | None` (Python 3.10+ union syntax) work as a type
  annotation even if the running interpreter is slightly older, and
  letting `Context` reference `Tool`/`Message` without import-order issues.
- **Keyword-only parameters (`*,`)** — `def __init__(self, *, task,
  system=None)` and `def add_message(self, role, content, *,
  tool_use_id=None)` forbid positional calls for those arguments, the
  Python equivalent of Ruby's `key:`/`key: default` method signatures.
- **`@property`** — used for `tool_count`/`turn_count`, exposing them as
  plain attribute reads (`ctx.tool_count`, no parens) while computing them
  on demand from `len(...)`, matching Ruby's endless-method getters
  (`def tool_count = @tools.size`).
- **f-strings with slicing** (`self.description[:41]`, `self.content[:61]`)
  — Python string slicing (`s[:n]`) is the direct equivalent of Ruby's
  `s[0..n-1]`; the off-by-one translation (`0..40` → `:41`) was the one
  place this needed care.
- **`dict`/`list` as the two collection types** — `messages: list[Message]`
  (an ordered sequence, appended to) and `tools: dict[str, Tool]` (keyed
  lookup by name) — direct equivalents of Ruby's `Array`/`Hash`.
- **`typing.Callable[..., str]`** — the type hint for `Tool.block`, a
  function of arbitrary arguments returning a string, matching Ruby's
  duck-typed `->(direction) { ... }` lambda field.

## How it was executed

```bash
cd week1_baseline/python/01_struct_skeleton
python3 -m venv .venv                        # lesson-local virtualenv
.venv/bin/pip install -r requirements.txt    # PyYAML + python-dotenv (unchanged deps — Tool/Message/Context need only stdlib)
```
Then, via the new runner (which auto-detects and uses `.venv/bin/python`
if present, else falls back to plain `python3`):
```bash
cd week1_baseline
./bin/python/01_struct_skeleton
```

## Observations from execution

- **Exit code 0, no errors**, both directly (`.venv/bin/python
  examples/example.py`) and through the new runner script.
- **Output is byte-for-byte identical to the Ruby run** — confirmed with
  `diff <(./bin/ruby/01_struct_skeleton) <(.venv/bin/python examples/example.py)`,
  which returned no differences:
  ```
  === Boukensha Step 1: Struct Skeleton ===

  Config:   #<Boukensha::Config dir=/home/mahdi/claude-code-camp-2026-Q2/.boukensha tasks=player>
  Context:  #<Context task=player turns=2 tools=1>
  Tool:     #<Tool name=move description=Move the player in a direction (north, so params=[:direction]>
  Messages:
    #<Message role=user content=Explore north and tell me what you find....>
    #<Message role=assistant content=Sure, let me head north and take a look....>
  ```
- **One real issue found on code review, before commit**: `context.py`
  type-hinted `self.tools` as `dict[str, "Tool"]` but never imported `Tool`
  into that module — a dangling forward-reference string, inconsistent
  with the adjacent `Message` import which *is* used unquoted. Fixed by
  adding `from .tool import Tool` and dropping the quotes. Re-ran
  afterward — still exit 0, output unchanged. (Harmless at runtime because
  `from __future__ import annotations` defers all annotation evaluation,
  but would break if anything ever called `typing.get_type_hints()` on
  `Context`.)
- **No new dependencies needed** — `Tool`/`Message`/`Context` are built
  entirely from the standard library (`dataclasses`, `typing`), so
  `requirements.txt` is untouched from `00_config`.
- **`.venv/`/`__pycache__/` correctly stay out of git** — confirmed via
  `git check-ignore -v` against the existing repo-root `.gitignore` rules;
  nothing extra was needed there.
