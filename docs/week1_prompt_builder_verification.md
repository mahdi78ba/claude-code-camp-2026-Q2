# Week 1 Verification — Prompt Builder Provider Config & Payload (`03_prompt_builder`)

Companion to [`week1_prompt_builder_review.md`](week1_prompt_builder_review.md)
(the code review). This doc covers the *runtime* verification: confirming
which provider is actually active, that it has the credentials it needs,
that the generated payload matches that provider's shape, and what changes
when you switch providers.

---

## 4. Provider configuration

### 4.1 Active provider comes from `.boukensha/settings.yaml`

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
```

`Boukensha::Config#tasks(:player)` reads this hash straight from YAML, and
`Tasks::Player.provider(settings)` / `.model(settings)` just index into it
(`lib/boukensha/tasks/base.rb`). There's no other place a provider gets
selected from — no env var override, no CLI flag in this iteration. Whatever
string is under `tasks.player.provider` is what `examples/example.rb`'s
`case provider when "anthropic" ... when "ollama" ...` branches on to decide
which `Backends::X` class to instantiate.

### 4.2 Required API key

`.boukensha/.env` currently defines exactly one key: `ANTHROPIC_API_KEY`.
That's correct and sufficient — the active provider is `anthropic`, and
`Backends::Anthropic.new(api_key: ENV.fetch("ANTHROPIC_API_KEY"), ...)` is
the only branch of `example.rb`'s backend `case` that actually executes for
the current settings. (Contents of `.env` are never printed or committed —
it's gitignored, confirmed via `git check-ignore -v .boukensha/.env`.)

### 4.3 Only the active provider needs credentials

`example.rb` uses `ENV.fetch("X_API_KEY")` (not `ENV["X_API_KEY"]`) for every
provider except `ollama` — `fetch` raises `KeyError` immediately if the key
is missing, rather than silently passing `nil` into the backend. This is why
you don't need `OPENAI_API_KEY` / `GEMINI_API_KEY` / `OLLAMA_API_KEY` set at
all right now: those branches of the `case` statement are never reached
unless `settings.yaml`'s `provider:` is changed to select them. `ollama`
itself needs no key ever — it's the one backend with no `api_key:` parameter
at all (`Backends::Ollama.new(host:, model:)`), since it talks to a local
`ollama serve` process instead of a hosted API.

**What to retain:** credentials are provider-scoped, not global. Configuring
every provider "just in case" is unnecessary work — only the `provider:`
value currently selected in `settings.yaml` needs a real key in `.env`.

---

## 5. Running and comparing payloads

### 5.1 / 5.2 — Run with the configured provider (Anthropic)

```sh
./week1_baseline/bin/ruby/03_prompt_builder
```

Produced (trimmed to structure):

```json
{
  "model": "claude-haiku-4-5",
  "system": "You are Boukensha, ...",
  "max_tokens": 1024,
  "tools": [ { "name": "look", "input_schema": { ... } }, ... ],
  "messages": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." },
    { "role": "user", "content": [
        { "type": "tool_result", "tool_use_id": "toolu_01X", "content": "..." }
    ]}
  ]
}
```

This matches the Anthropic shape documented in the README exactly: system
prompt as a **top-level `system:` field** (not inside `messages`), tools as
`input_schema` (Anthropic's own key name, not `parameters`), and the tool
result folded into a **`user`**-role message as a `tool_result` content
block — not a dedicated `tool` role.

### 5.3 — Switch provider + model, rerun, compare

Temporarily changed `.boukensha/settings.yaml`:

```diff
- provider: anthropic
- model: claude-haiku-4-5
+ provider: ollama
+ model: gemma4
```

(`ollama` was chosen for this comparison specifically because it needs no
API key — no `.env` change required to demonstrate a different payload
shape.) Reran the same runner, then reverted `settings.yaml` back to
`anthropic` / `claude-haiku-4-5` immediately after (confirmed via `git diff`
— tracked file, zero diff after revert).

Ollama's payload for the *identical* `Context* (same messages, same two
tools):

```json
{
  "model": "gemma4",
  "stream": false,
  "messages": [
    { "role": "system", "content": "You are Boukensha, ..." },
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." },
    { "role": "tool", "tool_name": "toolu_01X", "content": "..." }
  ],
  "tools": [
    { "type": "function", "function": { "name": "look", "parameters": { ... } } },
    ...
  ]
}
```

Side-by-side, from the exact same `Context`:

| | Anthropic | Ollama |
|---|---|---|
| System prompt | top-level `system:` | first message, `role: system` |
| Extra top-level field | `max_tokens` | `stream: false` |
| Tool schema key | `input_schema` | `function.parameters`, wrapped in `{type: "function", function: {...}}` |
| Tool result | `role: user`, content block `type: tool_result` | `role: tool`, `tool_name` |

**What to retain:** the *same* `Context`/`Registry` state produces
completely different wire formats depending only on which backend
`PromptBuilder` was constructed with — that's the entire point of this
iteration ("PromptBuilder delegates serialization to the active backend").
Nothing about `Context`, `Message`, or `Tool` changes when you swap
providers; only `to_payload`'s output shape does. This is also the fastest
way to sanity-check a new/changed backend: build one `Context`, run it
through every backend, and confirm the differences match what that
provider's actual API docs require (system placement, tool-result role,
tool-schema key) — a mismatch there means a real bug, not a stylistic
choice.

**Caution when doing this yourself:** switching `provider:` to `openai`,
`gemini`, or `ollama_cloud` for a comparison **will** raise `KeyError` at
`ENV.fetch("...API_KEY")` unless that key is actually set in `.env` — per
§4.3, only add a key for a provider you're deliberately testing, and remove
it again afterward if it was just for a one-off comparison rather than a
provider you're keeping configured.

---

## Retain — the short list

1. **One selection point:** `tasks.player.provider`/`.model` in
   `settings.yaml` is the only place the active provider/model is chosen —
   no other override path exists in this iteration.
2. **Credentials are scoped to the active provider only** — `example.rb`'s
   `ENV.fetch` per-branch means unconfigured providers fail loudly (`KeyError`)
   only if you actually select them, not before.
3. **`ollama` is the one backend with zero credential requirement** — best
   choice for comparing payload shapes without touching `.env` at all.
4. **Identical `Context`, different backend → different wire format** — this
   is the entire mechanism under test; the JSON *structure* differing per
   provider (not just field values) is the expected, correct behavior, not
   a bug.
5. **Revert scratch config changes immediately** — `settings.yaml` is a
   tracked file (`safe to commit` per its own header comment); a comparison
   run should end with `git diff` showing no leftover change, not with the
   repo defaulting to whichever provider you last tested.
