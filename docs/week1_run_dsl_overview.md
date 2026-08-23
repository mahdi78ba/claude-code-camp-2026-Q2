# `07_the_run_dsl` — `Boukensha.run` Overview

## 1. Simple explanation

Every prior step (`00`–`06`) required the caller to manually build and
connect six objects — `Context`, `Registry`, a `Backend`, `PromptBuilder`,
`Client`, `Logger` — before constructing an `Agent` and calling `.run`.
Step 7 collapses all of that into one method:

```ruby
result = Boukensha.run(task: "Read lib/boukensha.rb") do
  tool "read_file",
    description: "Read a file",
    parameters:  { path: { type: "string" } } do |path:|
    File.read(path)
  end
end
```

You describe **what** you want (a task, and the tools the agent is allowed
to use) — `Boukensha.run` figures out **how** to wire it together and
returns the agent's final text response.

## 2. Technical explanation

### `Boukensha.run` (`lib/boukensha.rb`)

A single class method that, per call:

1. Loads `Boukensha.config` — reads `.env` and `settings.yaml` from
   `BOUKENSHA_DIR` (default `~/.boukensha`).
2. Resolves defaults from `Tasks::Player`'s settings: `system` prompt,
   `model`, `backend`, and the matching API key
   (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GEMINI_API_KEY`/`OLLAMA_API_KEY`),
   unless the caller overrides them as keyword arguments.
3. Builds `Context.new(task:, system:)` and `Registry.new(ctx)`.
4. If a block was given, runs `RunDSL.new(registry).instance_eval(&block)`
   — this is where `tool` calls inside the block actually register tools
   on the registry (see below).
5. Instantiates the chosen backend (`Backends::Anthropic`, `OpenAI`,
   `Gemini`, `Ollama`, or `OllamaCloud`), then `PromptBuilder`, `Client`,
   `Logger` (writing to `.boukensha/sessions/<session-id>.jsonl` unless
   `log:` overrides the path), and finally `Agent`.
6. Adds `task` as the first user message and calls `agent.run`.
7. `ensure`s `logger.close` runs even if the agent raises.

### `Boukensha::RunDSL` (`lib/boukensha/run_dsl.rb`)

The object `self` becomes inside the block, via `instance_eval`. It
exposes exactly one method:

```ruby
def tool(name, description:, parameters: {}, &block)
  @registry.tool(name, description: description, parameters: parameters, &block)
end
```

This is a deliberately narrow surface — the block cannot reach `Context`,
`Client`, or any other internal object, only register tools.

### Call graph

```
Boukensha.run(task:, ...) { tool ... }
  └─ Config              (env/settings load)
  └─ Context, Registry   (constructed directly)
  └─ RunDSL#tool  ──────▶ Registry#tool   (block registers tools)
  └─ Backends::*          (constructed from resolved backend/model/api_key)
  └─ PromptBuilder, Client, Logger, Agent  (constructed directly)
  └─ Agent#run  ──▶ returns final text
```

Nothing here is new machinery — every object built inside `Boukensha.run`
is the same `Context`/`Registry`/`Backend`/`Client`/`Logger`/`Agent` from
steps `01`–`06`. Step 7 adds no new capability; it only relocates the
wiring from the caller's script into one reusable method.

## 3. Objective assessment

**What it removes:** ~20 lines of manual object construction per script
(see the README's before/after comparison) — every consumer of this
library no longer needs to know the six-object wiring order or which
constructor takes which dependency.

**What it costs:** less flexibility for advanced cases. `Boukensha.run`
always constructs a fresh `Agent` for one task and returns after one
`agent.run` call — there's no way to reuse a live `Context`/`Registry`
across multiple `Boukensha.run` calls (e.g., a multi-turn conversation
that persists tools already registered). Anyone who needs that has to
drop back to the manual step-5-style wiring.

**Verified behavior** (`./bin/ruby/07_the_run_dsl`, live Anthropic call):

- `session_start` log entry shows `task: "player"`, `model:
  "claude-haiku-4-5"`, `provider: "anthropic"` — confirming `Config`,
  `Tasks::Player` defaults, and the backend were all resolved correctly
  with zero explicit keyword arguments beyond `task:`.
- A `read_file` `tool_call`/`tool_result` pair appears in the log,
  confirming the block-registered tool (via `RunDSL#tool` →
  `Registry#tool`) was actually dispatched by the `Agent`, not just
  registered inertly.
- The run ends with `turn_end` (`reason: "completed"`) and the process
  exits `0`, with a correct final summary printed to stdout.

This confirms `Boukensha.run` is a pure convenience wrapper: identical
runtime behavior to the manual step-5 wiring, with the six-object
construction hidden behind one call.
