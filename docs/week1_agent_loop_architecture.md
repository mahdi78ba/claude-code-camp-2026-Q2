# Week 1 — Agent Loop Architecture (`05_agent_loop`)

How `Boukensha::Agent` wires together `Client`, `PromptBuilder`, `Registry`,
and `Context` into one working loop. Brief, technical, code-grounded — not a
bug hunt (that's [`week1_config_troubleshooting.md`](week1_config_troubleshooting.md),
entries #15/#16 for this iteration).

---

## 1. The pieces and how they relate

```
Config (settings.yaml, .env)
  └─ Tasks::Player  → provider, model, system prompt, iteration/token limits
        │
        ▼
Context ──────────────┐  holds: task, system prompt, messages[], tools{}
        │              │
        ▼              ▼
Registry          Backend (Anthropic/OpenAI/Gemini/Ollama/OllamaCloud)
  register/dispatch     to_payload / parse_response / to_messages / to_tools
  tools by name              │
        ▲                    ▼
        │              PromptBuilder  (thin pass-through to the backend)
        │                    │
        │                    ▼
        └──────────────  Client  (HTTP POST, retries, JSON parse)
                               │
                               ▼
                            Agent.run   ← the loop
```

Each box is a single-responsibility object; `Agent` is the only thing that
holds references to all of them and drives the sequence. No object reaches
around another — e.g. `Client` never touches `Context` directly, only
`PromptBuilder`.

| Object | Owns | Does NOT know about |
|---|---|---|
| `Context` | task, system prompt, message history, registered tools | HTTP, providers |
| `Registry` | tool name → `Tool` lookup, dispatch | HTTP, providers |
| `Backend` (5 of them) | provider wire format, model table, response→normalized-shape conversion | HTTP transport, retry policy |
| `PromptBuilder` | delegates every call straight to the configured backend | which backend it's using — pure delegation |
| `Client` | HTTP POST + retry/backoff + JSON decode | message/tool shape, providers |
| `Agent` | the loop: call → parse → branch on `stop_reason` → repeat or return | HTTP details, provider wire format |

## 2. Wiring it up (`examples/example.rb`)

```ruby
ctx      = Boukensha::Context.new(task: Boukensha::Tasks::Player, system: system_prompt)
registry = Boukensha::Registry.new(ctx)          # registry writes into ctx's tools{}
backend  = Boukensha::Backends::Anthropic.new(api_key: ENV.fetch("ANTHROPIC_API_KEY"), model: model)
builder  = Boukensha::PromptBuilder.new(ctx, backend)
client   = Boukensha::Client.new(builder)
agent    = Boukensha::Agent.new(context: ctx, registry: registry, builder: builder,
                                 client: client, task_settings: player_settings)
```

Five objects, four of them handed a reference to something built just above
— `Registry` wraps `ctx`, `PromptBuilder` wraps `ctx` + `backend`, `Client`
wraps `builder`, `Agent` wraps all four. Swapping providers only means
constructing a different `Backends::*` — nothing else in this chain changes.

Tools are registered on `registry`, which stores them **on the shared
`ctx`**, not on the registry itself:

```ruby
registry.tool("read_file", description: "...", parameters: { path: { type: "string", ... } }) do |path:|
  File.read(File.expand_path(path, base_dir))
end
```

`Registry#tool` builds a `Tool` struct (`name`, `description`, `parameters`,
the block) and calls `ctx.register_tool(tool)` — so `Context#tools` is the
single source of truth both the backend (for `to_tools`, building the API's
tool schema) and the registry (for `dispatch`) read from.

## 3. One turn of `Agent#run`

```ruby
def run
  loop do
    return wrap_up("max_iterations") if iteration_limit_reached?
    @iteration += 1
    response = @client.call(**call_opts)
    parsed   = @builder.parse_response(response)
    if parsed[:stop_reason] == "tool_use"
      handle_tool_calls(parsed[:content])   # adds assistant + tool_result messages, loops again
    else
      return extract_text(parsed[:content]) # done
    end
  end
end
```

Concretely, from the verified run of this iteration:

```
[iteration 1/25]
  tool call → read_file({"path"=>"README.md"})
  tool result → # The Agent Loop...
[iteration 2/25]
=== FINAL RESPONSE ===
## Summary  ...
```

Step by step:

1. **`client.call`** — `PromptBuilder#to_api_payload` asks the backend to
   build the wire payload (`Backends::Anthropic#to_payload`: model, system
   prompt, `to_tools(ctx.tools)`, `to_messages(ctx.messages)`), then `Client`
   POSTs it to `builder.url` with `builder.headers`, retrying transient
   network errors and 408/409/429/500/502/503/504 up to 3 times with
   exponential backoff (0.5s, 1s, 2s), and JSON-decodes the response.
2. **`builder.parse_response(response)`** — delegates to
   `Backends::Anthropic#parse_response`, which reduces the provider's raw
   JSON to one shape every backend agrees on:
   ```ruby
   { stop_reason: "tool_use" | "end_turn",
     content: [ {"type"=>"text","text"=>"..."},
                {"type"=>"tool_use","id"=>"...","name"=>"read_file","input"=>{"path"=>"README.md"}} ] }
   ```
   `Agent` only ever inspects this normalized hash — never a raw
   Anthropic/OpenAI/Gemini/Ollama response. That's what lets one `Agent`
   class work unmodified against 5 different providers.
3. **`stop_reason == "tool_use"` → `handle_tool_calls`:**
   ```ruby
   @context.add_message(:assistant, content)          # tool_use block stored FIRST
   content.select { |b| b["type"] == "tool_use" }.each do |block|
     result = @registry.dispatch(block["name"], block["input"])
     @context.add_message(:tool_result, result.to_s, tool_use_id: block["id"])
   end
   ```
   `Registry#dispatch` looks up the `Tool` by name in `ctx.tools` and calls
   its block with the model-supplied `input` as keyword args — this is the
   literal connection between "the model decided to call `read_file`" and
   "Ruby's `File.read` actually runs." The assistant message is added
   *before* the tool_result message, because Anthropic's API rejects a
   `tool_result` that doesn't have its matching `tool_use` already earlier
   in history — get this order backwards and the next `client.call` 400s.
4. **Loop repeats** — `ctx.messages` now has 3 entries (user, assistant
   tool_use, tool_result), so the next `client.call` replays the full
   history. On iteration 2 the model has the file contents and returns
   `stop_reason: "end_turn"`, so `Agent#run` calls `extract_text` and
   returns — no more tool calls needed.
5. **If the model never stops** — once `@iteration >= max_iterations` (25 by
   default, from `tasks.player.max_iterations` in `settings.yaml`), the loop
   makes exactly one more call with `tools: []` and a wind-down directive
   instructing the model not to call tools, so the turn always ends with a
   real (if incomplete) answer instead of an exception.

## 4. Why every backend implements `parse_response` (and its inverse)

Five providers, five response shapes for "the model wants to call a tool":

| Provider | Tool call lives at | Call id? |
|---|---|---|
| Anthropic | `content[]` items with `"type"=>"tool_use"` | yes, echoed in `tool_result` |
| OpenAI | `choices[0].message.tool_calls[]` | yes |
| Gemini | a `functionCall` part | no — name reused as id |
| Ollama / Ollama Cloud | `message.tool_calls[]` | no — name reused as id |

`parse_response` converts provider → normalized shape; each backend's
private `assistant_message`/`assistant_parts` does the reverse conversion
when `to_messages` replays an assistant turn from `ctx.messages` back into
that provider's wire format on the *next* request. Anthropic is the only
backend where these are the same shape (its own `content` array), so it
needs no extra conversion step — this is why `Anthropic#parse_response` is a
two-line method while `OpenAI`/`Gemini`/`Ollama` need the extra private
helper.

## 5. Config → task → runtime, end to end

```yaml
# .boukensha/settings.yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override: { system: true }   # → reads .boukensha/prompts/player/system.md
    max_iterations: 25                   # → Agent's loop ceiling
    max_output_tokens: 1024              # → passed to every client.call
```

`Config#tasks(:player)` returns this hash; `Tasks::Player` (a 2-line
subclass of `Tasks::Base`) reads `provider`/`model`/`prompt_override`/
`max_iterations`/`max_output_tokens` out of it with string/symbol-tolerant
lookups. `example.rb` uses `Tasks::Player.provider(settings)` to pick which
`Backends::*` class to construct and `Tasks::Player.system_prompt(...)` to
resolve the system prompt — `prompt_override.system: true` means "prefer the
user's own file over this step's shipped default," falling back to
`prompts/system.md` if the user file doesn't exist.

## 6. Retain — the shape to remember

1. **`Context` is the shared mutable state** — `Registry`, `Backend`
   (via `to_messages`/`to_tools`), and `Agent` all read/write it; nothing
   else holds independent state.
2. **The normalized `{stop_reason, content}` shape is the contract between
   `Agent` and every `Backend`** — adding a 6th provider means writing
   `parse_response`/`to_messages`/`to_tools`/`to_payload` for it; `agent.rb`
   itself never changes.
3. **Assistant-message-before-tool-result is a hard ordering requirement**,
   enforced by `handle_tool_calls`'s statement order, not by any check —
   reordering those two lines breaks the very next API call.
4. **The iteration ceiling is a trigger, not a cap** — hitting it doesn't
   raise; it swaps to one final tools-disabled call so the turn always
   returns text.
