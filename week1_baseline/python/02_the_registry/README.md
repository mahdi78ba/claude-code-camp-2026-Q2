# 02 · The Tool Registry (Python port)

Python port of `week1_baseline/ruby/02_the_registry`. The Tool Registry is
how BOUKENSHA manages what capabilities the agent can use.

It has two jobs:
  1. storing tools
  2. dispatching tools when asked

Configuration and the `Tool`/`Message`/`Context` data structures are
unchanged from `01_struct_skeleton` — this iteration only adds the registry
below and a rewritten `examples/example.py` that routes registration and
dispatch through it.

## New Files

| File | Description |
|---|---|
| `boukensha/registry.py` | The `Registry` class — registers tools and dispatches calls |
| `boukensha/errors.py` | Boukensha-specific error classes |

## How It Works

The agent NEVER calls a tool directly.
It emits a structured request (name and args) and the Registry looks up the tool and runs it.

```
Agent:    "Hey registry call move with direction='north'"
Registry: "looking up 'move' in the tool table"
Registry: "Found it now calling the block with the provided args"
Registry: "Here's the result"
Agent:    "Thanks buddy"
Registry: "Thats why you pay me the big tokes"
```

## `boukensha.Registry`

| Method | Description |
|---|---|
| `tool(name, *, description, parameters=None, block)` | Registers a new tool on the context |
| `dispatch(name, args=None)` | Looks up a tool by name and calls it with the provided args |

## `boukensha.UnknownToolError`

Raised when `dispatch` is called with a name that has no registered tool.
A harness needs explicit error boundaries — an unrecognised tool name should never silently fail.

**Example:**
```
UnknownToolError: No tool registered as 'flee'
```

## Design considerations (porting notes)

- **`block` is a plain keyword argument, not a decorator.** Ruby's
  `def tool(name, description:, parameters: {}, &block)` captures a
  `do...end` block implicitly — Python has no equivalent syntax. Rather than
  reach for a `@registry.tool(...)` decorator (arguably more idiomatic
  Python), `tool()` takes `block` as an explicit callable argument, matching
  how `01_struct_skeleton`'s Python port already passed tool callables in as
  `lambda`s. This keeps the two Python iterations consistent with each
  other, not just with Ruby.
- **No string/symbol key translation in `dispatch`.** Ruby's `dispatch`
  does `args.transform_keys(&:to_sym)` before splatting args into the
  tool's block, because Ruby draws a hard line between String-keyed and
  Symbol-keyed hashes, and a block declared with keyword parameters
  (`|message:|`) only accepts Symbol keys. **Python has no such
  distinction** — dict keys and `**kwargs` are always strings — so the
  Python `dispatch` has no equivalent conversion step. This isn't a missing
  feature; the problem that line solves in Ruby doesn't exist in Python.
- **`UnknownToolError`** subclasses plain `Exception`, mirroring Ruby's own
  choice not to introduce a shared `Boukensha::Error` base class yet.

## Code layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `boukensha.Config` class (unchanged from `01_struct_skeleton`) |
| `boukensha/tasks/base.py` | abstract `Base` (unchanged) |
| `boukensha/tasks/player.py` | concrete `Player` (unchanged) |
| `boukensha/tool.py` | `boukensha.Tool` dataclass (unchanged) |
| `boukensha/message.py` | `boukensha.Message` dataclass (unchanged) |
| `boukensha/context.py` | `boukensha.Context` class (unchanged) |
| `boukensha/errors.py` | `boukensha.UnknownToolError` |
| `boukensha/registry.py` | `boukensha.Registry` |
| `boukensha/__init__.py` | top-level exports |
| `prompts/system.md` | default system prompt shipped with the library |
| `examples/example.py` | runnable smoke-test |

## Run

```bash
./week1_baseline/bin/python/02_the_registry
```
(Mirrors how the Ruby reference's `bin/ruby/02_the_registry` runner was
added after this iteration's implementation work.)

First run — set up the lesson-local virtualenv:

```bash
cd week1_baseline/python/02_the_registry
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then run the example directly:

```bash
.venv/bin/python examples/example.py
```

Expected output (values from your `.boukensha/`):

```
=== Boukensha Step 2: Tool Registry ===

Config:  #<Boukensha::Config dir=/home/mahdi/claude-code-camp-2026-Q2/.boukensha tasks=player>
Context: #<Context task=player turns=0 tools=2>
Tools:
  #<Tool name=move description=Move the player in a direction (north, so params=[:direction]>
  #<Tool name=shout description=Shout a message so everyone in the zone c params=[:message]>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
```
