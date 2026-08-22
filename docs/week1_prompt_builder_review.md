# Week 1 Review — Prompt Builder (`03_prompt_builder`)

Everything technical for this iteration in one place: the setup/fix work
done to get it running, and the code review (how `PromptBuilder` delegates
to backends, what each backend does with a `Context`, and where the
per-backend interfaces actually diverge). Builds on
[`week1_the_registry_review.md`](week1_the_registry_review.md) — this
iteration doesn't touch `Registry` or tool dispatch at all, it adds a new,
independent concern: turning a `Context` (Ruby objects) into the exact JSON
shape a specific provider's HTTP API expects.

---

## Setup & fixes applied

1. **Directory audit** — `week1_baseline/ruby/03_prompt_builder` was already
   present (part of the initial commit), fully fleshed out (5 backends,
   `PromptBuilder`, `Tasks::Player`, README, example). No files needed
   copying in, no `*Zone.Identifier` files found.
2. **Fixed the same off-by-one `../` bug as entries #4/#8/#10** (now entry
   #11 in `week1_config_troubleshooting.md`) — `examples/example.rb` had
   3 `../` in its `BOUKENSHA_DIR` line instead of the required 4, so
   `settings.yaml` loaded as `{}` and `Tasks::Base.system_prompt` crashed on
   `nil`. Third occurrence of the exact same bug in three iterations
   reviewed so far — still latent in 04–08.
3. **Vendored gems locally** (`bundle config set --local path 'vendor/bundle'`
   then `bundle install`) — same one-time step as every prior iteration.
4. **Added a runner script** at `week1_baseline/bin/ruby/03_prompt_builder`,
   matching the 01/02 pattern.
5. **Verified output** — the runner now prints a complete, valid
   Anthropic-shaped request body (`model`, `system`, `max_tokens`, `tools`,
   `messages`) to stdout, matching the README's documented Anthropic format.

Full Problem/Fix/Why writeup lives in `week1_config_troubleshooting.md`
(entry #11).

---

## Code review

## `Boukensha::PromptBuilder` (`lib/boukensha/prompt_builder.rb`)

```ruby
class PromptBuilder
  def initialize(context, backend)
    @context = context
    @backend = backend
  end

  def to_messages    = @backend.to_messages(@context.messages)
  def to_tools       = @backend.to_tools(@context.tools)
  def to_api_payload(max_output_tokens: 1024) = @backend.to_payload(@context, max_output_tokens: max_output_tokens)
  def headers        = @backend.headers
  def url             = @backend.url
end
```

- **`PromptBuilder` holds no formatting logic of its own.** Every method is a
  one-line forward to `@backend`. It stores a `Context` and a backend
  instance and does nothing else — the class exists to give callers one
  provider-agnostic object (`builder.to_api_payload`, `builder.url`,
  `builder.headers`) instead of reaching into a specific `Backends::X`
  instance directly. This is the same "thin façade over storage it doesn't
  own" shape `Registry` had over `Context` in the previous iteration — here
  the façade is over formatting behavior instead of tool storage.
- **The delegation is not uniform in what data it passes.** `to_messages`
  passes only `@context.messages`; `to_api_payload` passes the whole
  `@context` object (so the backend can also reach `context.system` and
  `context.tools`). This split is exactly what causes the interface bug
  below.

## `Boukensha::Backends::Base` (`lib/boukensha/backends/base.rb`)

```ruby
def self.models       = const_get(:MODELS) rescue NotImplementedError(...)
def self.model_info(model) = models[model.to_s]
def self.validate_model!(model) = model_info(model) || raise(UnsupportedModelError, ...)

def configure_model(model)   # private, called from each subclass's initialize
  @model = self.class.validate_model!(model)
  @model_info = self.class.model_info(@model)
end
```

- **Every backend must define a `MODELS` constant** (a `Hash[String,
  Hash]`), or `self.models` raises `NotImplementedError` when first
  accessed. This is enforced structurally (via `const_get` + `rescue`), not
  by requiring subclasses to implement a method — a class that forgets
  `MODELS` fails the first time anything touches its model table, not at
  load time.
- **Model validation happens at construction, not at request-build time.**
  Every backend's `initialize` calls `configure_model(model)` before doing
  anything else. An unsupported model (typo, or a model retired from the
  table) raises `UnsupportedModelError` immediately when the backend object
  is created — `settings.yaml` cannot silently select a model the code
  doesn't know about, matching what the README claims ("A backend refuses to
  initialize with an unknown model").
- **Cost/context helpers degrade gracefully, in two different ways, both
  intentional:**
  - Local `Ollama` models: `cost_per_million: { input: 0.0, output: 0.0 }` →
    `estimate_cost` returns a real `0.0`, not `nil` — there is a price, and
    it's zero.
  - `OllamaCloud` models: `cost_per_million: { input: nil, output: nil }` →
    `estimate_cost`'s guard (`return nil unless input_token_cost_per_million
    && output_token_cost_per_million`) returns `nil` — the price is
    *unknown* (plan/usage-tier based), which is a different fact than "free."
    Confirmed by reading the guard, not just the README's claim.
- **One model-table field is defined but never read anywhere.**
  `OllamaCloud::MODELS["minimax-m3:cloud"]` has an `advertised_context_window:
  1_000_000` key alongside `context_window: 512_000` — no method on `Base`
  or elsewhere in `lib/` reads `advertised_context_window` (confirmed via
  grep). It's currently just inert documentation sitting in the hash, not a
  bug, but worth knowing it isn't exposed through `context_window` or any
  other accessor if you go looking for "why is the advertised number not
  showing up."

## The five backends — what's identical vs. what genuinely diverges

All five (`Anthropic`, `OpenAI`, `Gemini`, `Ollama`, `OllamaCloud`) implement
the same five methods (`to_messages`, `to_tools`, `to_payload`, `headers`,
`url`) and inherit `configure_model`/cost helpers from `Base`. Within that
shared shape:

| | Anthropic | Gemini | OpenAI | Ollama | OllamaCloud |
|---|---|---|---|---|---|
| System prompt placement | top-level `system:` field | top-level `systemInstruction:` field | folded into `messages` as `role: system` | folded into `messages` as `role: system` | folded into `messages` as `role: system` |
| `to_messages` arity | `(messages)` — 1 arg | `(messages)` — 1 arg | `(system, messages)` — 2 args | `(system, messages)` — 2 args | `(system, messages)` — 2 args |
| Assistant role name | `"assistant"` | `"model"` | `"assistant"` | `"assistant"` | `"assistant"` |
| Tool-result message shape | `role: user`, content block `type: tool_result`, keyed by `tool_use_id` | `role: user`, part `functionResponse: {name, response}` | `role: tool`, `tool_call_id` | `role: tool`, `tool_name` | `role: tool`, `tool_name` |
| Tool definition wrapper | flat, `input_schema` | wrapped in one `functionDeclarations:` array | wrapped in `{type: "function", function: {...parameters...}}` per tool | same `function`-wrapped shape as OpenAI | same `function`-wrapped shape as OpenAI |
| Auth header | `x-api-key` | `x-goog-api-key` | `Authorization: Bearer` | none (local, no key) | `Authorization: Bearer` |

Two things confirmed by reading the code, beyond what the README already
states:

- **`to_tools` marks every declared parameter as required, on all five
  backends, unconditionally**: `required: tool.parameters.keys.map(&:to_s)`.
  There is no concept of an *optional* tool parameter anywhere in this
  iteration — if a parameter is in the `parameters:` hash at all, every
  backend's JSON schema says it's required. Fine for the example's tools
  (`move`'s only parameter genuinely is required), but worth knowing before
  assuming an optional-parameter tool would "just work" — it would render as
  required in the request regardless.
- **Unhandled roles pass through unchanged** on every backend's `else`
  branch (`{ role: msg.role.to_s, content: msg.content }` /
  `parts: [{text: msg.content}]`), so any future role beyond
  `:user`/`:assistant`/`:tool_result` degrades to "treated like user/
  assistant text," not an error. Nothing rejects an unrecognized role today.

## A real interface bug: `PromptBuilder#to_messages` crashes for 3 of 5 backends

This is the most important finding in this iteration. `PromptBuilder`
calls:

```ruby
def to_messages = @backend.to_messages(@context.messages)   # ONE argument
```

But `Anthropic#to_messages` and `Gemini#to_messages` take **one** argument
(`messages`), while `OpenAI#to_messages`, `Ollama#to_messages`, and
`OllamaCloud#to_messages` take **two** (`system, messages`) — they fold the
system prompt into the messages array themselves. Verified directly:

```ruby
backend = Boukensha::Backends::Ollama.new(model: "gemma4")
builder = Boukensha::PromptBuilder.new(ctx, backend)
builder.to_messages
# => ArgumentError: wrong number of arguments (given 1, expected 2)
```

`builder.to_api_payload` works fine for **every** backend, because each
backend's own `to_payload` calls its *own* `to_messages` with the correct
arity internally (`to_messages(context.system, context.messages)` for the
3-arg group, `to_messages(context.messages)` for Anthropic/Gemini) — the bug
is only reachable through `PromptBuilder`'s own `to_messages`/`to_tools`
convenience methods, not through the payload path the example and README
actually exercise.

**What to retain:** treat `builder.to_api_payload` as the only currently-safe
entry point on `PromptBuilder` for OpenAI/Ollama/OllamaCloud backends.
`builder.to_messages` (and, by the same reasoning, code that assumes a
uniform `to_messages(messages)` signature across all backends) will raise
for three of the five providers. If a later iteration wants `to_messages`
to be genuinely backend-agnostic, either every backend needs the same
arity, or `PromptBuilder#to_messages` needs to pass `@context.system` too
(harmless for Anthropic/Gemini only if their `to_messages` is changed to
accept-and-ignore it, or given its own overload).

## A modeling gap worth flagging: no structured "assistant calls a tool" message

`example.rb` builds this three-message transcript:

```ruby
ctx.add_message(:user, "I just arrived in the dungeon. What's around me, and can you move north?")
ctx.add_message(:assistant, "Let me take a look around first.")
ctx.add_message(:tool_result, "A damp stone corridor stretches north. Torches flicker on the walls.", tool_use_id: "toolu_01X")
```

The `tool_result` message references `tool_use_id: "toolu_01X"`, but no
message in the transcript actually *is* an assistant tool-call for that id —
`Message` (`role, content, tool_use_id`) has no field for a tool name or
arguments on an assistant turn, only free-text `content`. On the real
Anthropic API, a `tool_result` content block must correspond to a preceding
assistant message containing a matching `tool_use` block, or the request is
rejected — the payload this example builds would not actually be accepted
if it were POSTed. This isn't a bug in this iteration (the README is explicit
that "PromptBuilder does not call the API"), but it's a real gap in the
object model to watch for once a later iteration (`04_api_client` /
`05_agent_loop`) starts round-tripping real tool calls: `Message` will need
a way to represent an assistant's tool-call intent (name + args + id), not
just its own `content` string.

---

## Retain — the short list

1. **`PromptBuilder` is a pure delegator.** All provider-specific logic
   lives in `Backends::X`; `PromptBuilder` just gives callers one object
   with a stable method set instead of five backend classes with slightly
   different shapes.
2. **Model validation is fail-fast, at backend construction time**
   (`configure_model` inside every `initialize`) — not deferred to when a
   payload is built.
3. **Cost estimation distinguishes "free" (`0.0`, local Ollama) from
   "unknown" (`nil`, Ollama Cloud)** — don't conflate the two when reading
   `estimate_cost`'s return value.
4. **`builder.to_api_payload` is the only interface-safe method today** —
   `builder.to_messages`/`builder.to_tools` bypass each backend's own
   argument handling and will raise `ArgumentError` for OpenAI/Ollama/
   OllamaCloud (2-arg `to_messages`) if called directly, since
   `PromptBuilder` always calls the 1-arg form.
5. **Every backend requires all declared tool parameters** — there is no
   optional-parameter concept in the generated JSON schema, on any provider.
6. **The `Message` struct still can't represent an assistant's own tool call**
   (only a `tool_result`'s `tool_use_id`) — a gap to watch once real API
   round-trips start in later iterations, not something to fix here.
7. **The off-by-one `BOUKENSHA_DIR` `../` bug is now confirmed in 3 of 12
   iterations reviewed** (`00`, `01`, `02`, and now `03`) — expect it in
   04–08 too and fix on sight rather than re-diagnosing.
