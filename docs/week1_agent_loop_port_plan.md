# Python Port Plan — Agent Loop (`05_agent_loop`)

Plan only — no `boukensha/` code has been written yet, beyond copying
`python/04_api_client` verbatim into `python/05_agent_loop` as the starting
point (`rsync -a --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc'`,
same precedent as the `01→02`/`02→03`/`03→04` ports). This document scopes
exactly what to change next, and just as importantly, what to leave alone.

## What actually changed in Ruby (04 → 05)

Confirmed with `diff -rq ruby/04_api_client ruby/05_agent_loop` plus a
per-file `diff -u` on everything it flagged as differing:

```
Only in 05_agent_loop/lib/boukensha: agent.rb
Files .../lib/boukensha.rb differ
Files .../lib/boukensha/errors.rb differ
Files .../lib/boukensha/config.rb differ
Files .../lib/boukensha/prompt_builder.rb differ
Files .../lib/boukensha/tasks/base.rb differ
Files .../lib/boukensha/client.rb differ
Files .../lib/boukensha/backends/{anthropic,ollama,openai,gemini,ollama_cloud}.rb differ
Files .../examples/example.rb differ
```

`context.rb`, `message.rb`, `tool.rb`, `registry.rb`, and
`backends/base.rb` are **byte-identical** between the two Ruby
iterations — no changes needed there on the Python side either.
`prompts/system.md` is also identical (it was already introduced in `04`,
not new here — the README's "New Files" table is cumulative from
`03_prompt_builder`, not a `04→05` delta).

The real, behavior-carrying delta:

1. **New class, `Boukensha::Agent`** (`lib/boukensha/agent.rb`, ~110 lines)
   — the loop itself: calls the client, parses the response via the
   builder, dispatches tool calls through the registry, and returns the
   final text once `stop_reason == "end_turn"` (or after one tools-disabled
   wind-down call if `max_iterations` is hit).
2. **`errors.rb`** — adds `LoopError < StandardError` (declared but not
   actually raised anywhere in `agent.rb` — the iteration ceiling is
   handled by returning a wind-down response, not raising. Still worth
   porting 1:1 for parity, since a later iteration may start using it.)
3. **`prompt_builder.rb`** — `to_api_payload` gains a `tools:` keyword
   (passed through to the backend, `nil` by default meaning "compute from
   context as before"); new `parse_response(response)` method, a pure
   delegate to `@backend.parse_response`.
4. **`client.rb`** — `call` gains a `tools:` keyword, threaded straight
   into `to_api_payload`. This is what lets `Agent#wrap_up` send
   `tools: []` for the final call without needing a second code path.
5. **`tasks/base.rb`** — adds `DEFAULT_MAX_ITERATIONS = 25`,
   `DEFAULT_MAX_OUTPUT_TOKENS = 1024`, class methods `max_iterations`/
   `max_output_tokens` (both read via a new private `integer_setting`
   helper: `Integer(value)` if present, else the default), read the same
   way `provider`/`model` already are.
6. **Every backend** (`anthropic`, `ollama`, `ollama_cloud`, `openai`,
   `gemini`):
   - `to_payload` gains the same `tools:` keyword as the Ruby `Client`
     change above (`tools.nil? ? to_tools(context.tools) : tools`).
   - gains `parse_response`, normalizing that provider's raw response into
     `{stop_reason: "tool_use" | "end_turn", content: [...]}` — the shared
     contract `Agent` is written against. Anthropic's is a 2-line pass
     through (`content` already *is* the normalized shape); Ollama/
     OllamaCloud/OpenAI/Gemini each build `content` from a different raw
     location (`message.tool_calls`, `choices[0].message.tool_calls`, a
     `functionCall` part) and — since none of those four assign call ids —
     reuse the tool **name** as the `id`.
   - Ollama/OllamaCloud/OpenAI/Gemini also gain a private
     `assistant_message`/`assistant_parts` helper, wired into `to_messages`
     for `msg.role == :assistant`, that rebuilds that provider's own
     assistant-turn wire format from the normalized `content` blocks (the
     inverse of `parse_response`) — needed because `Agent` stores the
     assistant's `tool_use` blocks straight into `Context#messages`, and on
     the *next* `client.call` that history gets replayed through
     `to_messages` again. Anthropic needs no such helper — its `content`
     array already round-trips as-is.
7. **`examples/example.rb`** — rewritten to build and run an `Agent`
   instead of making one bare `client.call` and printing the raw JSON:
   registers `read_file`/`list_directory` resolved against a `base_dir`
   (`File.expand_path("..", __dir__)`, i.e. the iteration root, not the
   process's cwd), sends a task-shaped opening message ("Read the README.md
   file and summarise..."), constructs the `Agent` with `task_settings:`,
   and prints `agent.run`'s final text instead of a raw response dump.

**Not part of the behavior delta — skip:**

- `config.rb`'s diff is purely a Ruby syntax change (multi-line `def...end`
  → one-line endless `def foo = ...`), zero behavior change. Nothing to
  port — `config.py` is already correct.
- `boukensha.rb`'s diff is one `require_relative "boukensha/agent"` line —
  the Python equivalent is one import line in `__init__.py` (below), not a
  structural change.

## Cross-check against the current Python tree

Two things the Ruby side had to actively work around this iteration are
**already handled correctly in Python, by construction**, so no fix-parity
work is needed:

- **The `PROMPTS_DIR`/`BOUKENSHA_DIR` off-by-one `../`-count bug class**
  (troubleshooting log entries #4/#8/#10/#11/#12/#13, and now #15/#16 for
  this very iteration) cannot occur in Python: `config.py`'s `PROMPTS_DIR`
  is `Path(__file__).resolve().parent.parent / "prompts"` and
  `example.py`'s repo-root resolution is
  `Path(__file__).resolve().parents[4]` — both computed from the actual
  file location, not a hand-counted `../` string. Nothing to audit here.
- **`Registry.dispatch` already calls `tool.block(**(args or {}))`** — a
  plain dict from `json.loads` already has string keys, which Python's `**`
  unpacking accepts directly against `def block(*, path): ...`-style
  keyword parameters. Ruby's `handle_tool_calls` needs
  `args.transform_keys(&:to_sym)` because Ruby keyword-splat requires
  symbol keys; **no equivalent transform is needed in the Python `Agent`**
  — this is a case where the literal-translation instinct would add dead
  code.
- **`config.py`'s `mud_host`/`mud_port` already use explicit `is None`
  checks** (fixed in entry #14, during the `04_api_client` port review) —
  not touched by this iteration's Ruby diff, confirmed still correct.

## Files to add / change in Python

### 1. `boukensha/errors.py` — add `LoopError`

```python
class LoopError(Exception):
    """Reserved for runaway-agent conditions. Not currently raised —
    Agent.run handles the iteration ceiling by returning a wind-down
    response instead, matching Boukensha::LoopError's current usage."""
```

### 2. `boukensha/prompt_builder.py`

```python
def to_api_payload(self, *, max_output_tokens=1024, tools=None):
    return self.backend.to_payload(
        self.context, max_output_tokens=max_output_tokens, tools=tools
    )

def parse_response(self, response):
    return self.backend.parse_response(response)
```

### 3. `boukensha/client.py`

```python
def call(self, *, max_output_tokens=1024, tools=None):
    body = json.dumps(
        self.builder.to_api_payload(
            max_output_tokens=max_output_tokens, tools=tools
        )
    ).encode("utf-8")
    ...
```

### 4. `boukensha/tasks/base.py`

```python
DEFAULT_MAX_ITERATIONS = 25
DEFAULT_MAX_OUTPUT_TOKENS = 1024

@classmethod
def max_iterations(cls, settings):
    return cls._integer_setting(settings, "max_iterations", cls.DEFAULT_MAX_ITERATIONS)

@classmethod
def max_output_tokens(cls, settings):
    return cls._integer_setting(settings, "max_output_tokens", cls.DEFAULT_MAX_OUTPUT_TOKENS)

@classmethod
def _integer_setting(cls, settings, key, default):
    value = cls._fetch(settings, key)
    return default if value is None else int(value)
```

### 5. Every `boukensha/backends/*.py` — `to_payload` + `parse_response` (+ assistant round-trip for 4 of 5)

`to_payload` everywhere gains the same shape:
```python
def to_payload(self, context, *, max_output_tokens=1024, tools=None):
    return {
        ...,
        "tools": self.to_tools(context.tools) if tools is None else tools,
    }
```

`anthropic.py` — normalize (no assistant round-trip needed):
```python
def parse_response(self, response):
    stop_reason = "tool_use" if response.get("stop_reason") == "tool_use" else "end_turn"
    return {"stop_reason": stop_reason, "content": response.get("content") or []}
```

`ollama.py` / `ollama_cloud.py` — normalize (call id = tool name) plus the
inverse for replay:
```python
def parse_response(self, response):
    message = response.get("message") or {}
    tool_calls = message.get("tool_calls") or []
    content = []
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})
    for tc in tool_calls:
        fn = tc.get("function") or {}
        content.append({"type": "tool_use", "id": fn.get("name"),
                         "name": fn.get("name"), "input": fn.get("arguments") or {}})
    return {"stop_reason": "tool_use" if tool_calls else "end_turn", "content": content}

def _assistant_message(self, content):
    blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
    text = "".join(b["text"] for b in blocks if b["type"] == "text")
    tool_blocks = [b for b in blocks if b["type"] == "tool_use"]
    message = {"role": "assistant", "content": text}
    if tool_blocks:
        message["tool_calls"] = [
            {"function": {"name": b["name"], "arguments": b["input"]}} for b in tool_blocks
        ]
    return message
```
wired into `to_messages` as `elif msg.role == "assistant": conversation.append(self._assistant_message(msg.content))`.

`openai.py` — same shape as Ollama, but call ids are real (`tc["id"]`),
arguments are a JSON *string* that needs `json.loads` on the way in and
`json.dumps` on the way back out (`requirements.txt`/stdlib already covers
`json`, no new dependency):
```python
def parse_response(self, response):
    message = (response.get("choices") or [{}])[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    content = []
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})
    for tc in tool_calls:
        fn = tc.get("function") or {}
        content.append({"type": "tool_use", "id": tc.get("id"), "name": fn.get("name"),
                         "input": json.loads(fn.get("arguments") or "{}")})
    return {"stop_reason": "tool_use" if tool_calls else "end_turn", "content": content}
```

`gemini.py` — parts-based, call id = function name, plus `_assistant_parts`
(returns a list of parts, not a whole message, mirroring Ruby's
`assistant_parts` vs. everyone else's `assistant_message`):
```python
def parse_response(self, response):
    parts = (((response.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []
    content, tool_used = [], False
    for part in parts:
        if part.get("functionCall"):
            fc = part["functionCall"]
            content.append({"type": "tool_use", "id": fc.get("name"),
                             "name": fc.get("name"), "input": fc.get("args") or {}})
            tool_used = True
        elif part.get("text"):
            content.append({"type": "text", "text": part["text"]})
    return {"stop_reason": "tool_use" if tool_used else "end_turn", "content": content}
```

### 6. `boukensha/agent.py` — new, ported from `lib/boukensha/agent.rb`

Straight structural port: `MAX_ITERATIONS = 25`, `WRAP_UP_OUTPUT_TOKENS =
400`, the same wind-down directive text, `run()` as a `while True` loop
mirroring Ruby's `loop do`. Two deliberate non-literal spots:

- No `args.transform_keys(&:to_sym)` equivalent before calling
  `self.registry.dispatch(name, args)` — established above, not needed in
  Python.
- `resolve_max_iterations`/`resolve_max_output_tokens` use
  `getattr(self.context.task, "max_iterations", None)` in place of Ruby's
  `respond_to?` check, since `Tasks::Player` is a plain class (classmethods
  via `@classmethod`), not an instance — same "does this task class define
  it" question, Python idiom instead of Ruby's.

### 7. `boukensha/__init__.py`

Add `from .agent import Agent` and `from .errors import ... LoopError`;
extend `__all__` with `"Agent"` and `"LoopError"`.

### 8. `examples/example.py` — rewrite to build and run an `Agent`

Mirrors the Ruby `example.rb` rewrite: resolve tool paths against
`Path(__file__).resolve().parent` (this lesson's root, already how
`example.py` resolves `repo_root` today — no new path-resolution pattern
needed), change the opening message to the same
"Read the README.md file and summarise..." prompt, construct
`Agent(context=ctx, registry=registry, builder=builder, client=client,
task_settings=player_settings)`, replace the raw `client.call()` +
`json.dumps` print with `result = agent.run()` and a `=== FINAL RESPONSE
===` print, matching the Ruby transcript shape used to verify `05_agent_loop`
(`[iteration N/25]` progress lines, then the final summary).

### 9. `README.md` — needs a full rewrite, not a port

The copied file still describes `04_api_client` ("Step 4", raw
`client.call`). This isn't a code port — it's just stale content from the
copy step — but it needs to be replaced with `05_agent_loop`'s own README
content (Python-flavored, same precedent as `03`/`04`'s own READMEs) before
this iteration's port can be considered complete. Flagging here so it isn't
missed; not attempted in this planning pass.

### Unchanged — carry forward as-is

`context.py`, `message.py`, `tool.py`, `registry.py`,
`backends/base.py`, `config.py`, `tasks/player.py`, `tasks/__init__.py`,
`backends/__init__.py`, `prompts/system.md`, `requirements.txt` — no Ruby
change to port, and (per the cross-check above) no latent Python-only fix
needed either.
