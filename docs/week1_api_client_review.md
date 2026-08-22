# Week 1 Review — API Client (`04_api_client`)

Everything technical for this iteration in one place: the setup/fix work
done to get it running, and the code review (`Client`'s retry/error
handling, the new `Backends::Base`/model-table machinery, and the two
constant-loading paths that carry over from prior iterations). Builds on
[`week1_prompt_builder_review.md`](week1_prompt_builder_review.md) — this
iteration adds the piece that review predicted was missing: an actual HTTP
round trip to the provider, via `Boukensha::Client`.

---

## Setup & fixes applied

1. **Directory audit** — `week1_baseline/ruby/04_api_client` was already
   present (part of the initial commit), fully fleshed out (`Client`, a new
   `Backends::Base` with per-backend `MODELS` tables, `Tasks::Base`/`Player`,
   README, example). No files needed copying in, and a filesystem-wide
   search found zero `*Zone.Identifier` files anywhere in the repo (the root
   `.gitignore` already excludes them, and none exist on disk regardless).
2. **Fixed the same off-by-one `../` bug as entries #4/#8/#10/#11** (see
   entry #12 below) — `examples/example.rb` shipped with 3 `../` in its
   `BOUKENSHA_DIR` line instead of the required 4. Fourth occurrence of the
   identical bug across five iterations reviewed so far.
3. **Found and fixed a second, related off-by-one — this time in shipped
   library code, not just the example script** (entry #13 below):
   `Config::PROMPTS_DIR` in `lib/boukensha/config.rb` used
   `File.expand_path("../../../prompts", __dir__)` (3 `../`) instead of the
   correct `"../../prompts"` (2 `../`) that `03_prompt_builder`'s copy of
   the same file uses. One `../` too many walks past the iteration's own
   `prompts/` directory entirely. This one didn't crash the smoke test only
   because `.boukensha/settings.yaml` has `prompt_override.system: true`
   *and* `.boukensha/prompts/player/system.md` exists — the user-prompt path
   is checked first and short-circuits before `PROMPTS_DIR` is ever read. If
   either of those weren't true, `system_prompt` would silently return `nil`
   instead of raising, since `read_default_prompt` returns `nil` for a
   missing file rather than erroring.
4. **Vendored gems locally** (`bundle config set --local path 'vendor/bundle'`
   then `bundle install`) — same one-time step as every prior iteration.
   `Gemfile` only declares `dotenv`; `Client` itself uses stdlib `net/http`,
   no new gems.
5. **Added a runner script** at `week1_baseline/bin/ruby/04_api_client`,
   matching the 01/02/03 pattern (LF endings, `chmod +x`).
6. **Verified with a real, live API call** — the runner sent one request to
   `https://api.anthropic.com/v1/messages` (`claude-haiku-4-5`, one user
   turn, two tools offered) using the key already present in
   `.boukensha/.env` (provisioned by the user specifically "for lesson 04
   onward" per that file's own comment). Response came back
   `stop_reason: "tool_use"` selecting `list_directory`, matching the
   README's documented Anthropic response shape. Total usage: 777 input /
   53 output tokens on `claude-haiku-4-5`.

Full Problem/Fix/Why writeup lives in `week1_config_troubleshooting.md`
(entries #12 and #13).

---

## Code review

### `Boukensha::Client` (`lib/boukensha/client.rb`)

```ruby
def call(max_output_tokens: 1024)
  ...
  loop do
    attempts += 1
    begin
      response = http.request(request)
    rescue *TRANSIENT_ERRORS => e
      raise ApiError, "..." if attempts > MAX_RETRIES
      sleep retry_delay(attempts)
      next
    end
    if retryable_response?(response) && attempts <= MAX_RETRIES
      sleep retry_delay(attempts)
      next
    end
    break
  end
  raise ApiError, "..." unless response.is_a?(Net::HTTPSuccess)
  JSON.parse(response.body)
end
```

- **Two independent retry paths, both bounded by the same `MAX_RETRIES =
  3`:** transient exceptions (`EOFError`, connection resets, SSL errors,
  timeouts — listed explicitly in `TRANSIENT_ERRORS`, not a blanket
  `rescue`) and retryable HTTP status codes (408/409/429/500/502/503/504).
  A non-retryable error (e.g. `ArgumentError`, or a 400/401/403) is not
  rescued by either path and propagates immediately — only the specific
  transient conditions get retried.
- **Exponential backoff** (`BASE_RETRY_DELAY * 2**(attempt - 1)` → 0.5s,
  1s, 2s) is a real `sleep` in the request path — calling `client.call`
  against a provider that returns 429s repeatedly will block the caller for
  several seconds before raising, not something visible from the method
  signature.
- **Off-by-one risk in the retry counter is not actually present, but is
  easy to misread.** The transient-error branch checks `attempts >
  MAX_RETRIES` while the retryable-response branch checks `attempts <=
  MAX_RETRIES` — different comparison operators for what looks like the
  same "have we retried enough" question. Traced through by hand: both
  produce identical behavior (attempt 4 is where the exception path stops
  retrying and where the response path's condition first goes false), so
  this is not a bug, just two ways of writing the same threshold that are
  worth not assuming are typos of each other if touched later.
- **SSL cert path is deliberately left to the OS default**, per the
  comment in the code — `http.ca_file = OpenSSL::X509::DEFAULT_CERT_FILE`
  is commented out because that constant resolves to a macOS-only path
  (`/usr/lib/ssl/cert.pem`) that doesn't exist on Linux/WSL2. Confirmed
  working as-is: the live call in this session used `https://` (SSL
  enabled) and succeeded without setting `ca_file`.
- **`ApiError` (new in this iteration, added to `errors.rb`) is used for
  every failure mode** — transient-retry exhaustion, retryable-status
  exhaustion, and any non-2xx response — so callers get one exception type
  to rescue regardless of *why* the request ultimately failed, at the cost
  of losing the original exception class in the transient-retry case (it's
  interpolated into the message string, not chained/wrapped).

### `Boukensha::Backends::Base` (`lib/boukensha/backends/base.rb`)

New in this iteration — each backend that previously only knew `to_messages`/
`to_tools`/`to_payload`/`headers`/`url` now also inherits from `Base` and
gains a `MODELS`-table contract:

- **`self.models` uses `const_get(:MODELS)` guarded by `rescue NameError`**,
  not `respond_to?`/`const_defined?` — a subclass that forgets to define
  `MODELS` fails the first time anything calls `.models` (i.e., the first
  time that backend is constructed, via `configure_model`), not at
  `require` time.
- **Model validation happens at construction, before any request is
  built.** Every backend's `initialize` calls `configure_model(model)`
  immediately, which calls `self.class.validate_model!(model)` — an
  unsupported model name raises `UnsupportedModelError` right away, so
  `settings.yaml` cannot silently select a model the code doesn't
  recognize. Confirmed this is enforced for the actual configured model
  (`claude-haiku-4-5`) during the live run — construction succeeded because
  it's present in `Anthropic::MODELS`.
- **Cost/context helpers degrade in two different, intentional ways**:
  local `Ollama` models carry `cost_per_million: { input: 0.0, output: 0.0
  }` (a real, known price of zero), while `OllamaCloud` models carry `{
  input: nil, output: nil }` (an *unknown*, plan-based price) —
  `estimate_cost`'s guard (`return nil unless input_token_cost_per_million
  && output_token_cost_per_million`) correctly returns `0.0` for the former
  and `nil` for the latter, not conflating "free" with "unpriced."
- **`OllamaCloud::MODELS["minimax-m3:cloud"]` still carries the same inert
  `advertised_context_window` field noted in the `03_prompt_builder` review**
  — no accessor on `Base` reads it (confirmed via grep across `lib/`); it's
  unchanged from the prior iteration and remains just documentation sitting
  in the hash.

### `Boukensha::Tasks::Base` / `Tasks::Player` (new in this iteration)

- **Generalizes the provider/model/prompt lookups that `Config` used to own
  directly.** `fetch` reads either string or symbol keys from a settings
  hash (`settings["provider"] || settings[:provider]`), matching the same
  string-or-symbol tolerance `Config#dig` already used — consistent with
  how `settings.yaml` is parsed (`YAML.safe_load` produces string keys, but
  the code never assumes that).
- **`prompt_override?` treats a missing or non-Hash `prompt_override` node
  as `false`, not an error** — a task with no `prompt_override:` key at all
  in `settings.yaml` (or a malformed one) silently uses the shipped default
  prompt rather than raising. This is why the `PROMPTS_DIR` bug (setup
  fix #3 above) didn't surface during the smoke test only by coincidence of
  this repo's specific `settings.yaml` — a config without `prompt_override:
  system: true` would have hit the broken default path and gotten a silent
  `nil` system prompt instead of a clear error.
- **`Player` itself is a two-line subclass** (`task_name = "player"`) — all
  actual behavior lives in `Base`, matching the same "thin subclass, real
  logic in the shared parent" shape already seen in `Backends::Base` and its
  five subclasses.

### Carried-forward findings, re-verified against this iteration's copy

`context.rb`, `message.rb`, `registry.rb`, `tool.rb`, and `prompt_builder.rb`
are **byte-identical** to `03_prompt_builder`'s copies (diffed directly, zero
differences) — so every finding from the prior review still applies
unchanged:

- **`PromptBuilder#to_messages`/`#to_tools` still call each backend's
  `to_messages`/`to_tools` with the 1-argument form**, which still raises
  `ArgumentError` for `OpenAI`/`Ollama`/`OllamaCloud` (2-arg
  `to_messages(system, messages)`). `Client#call` never triggers this — it
  only calls `builder.to_api_payload`, which routes through each backend's
  own `to_payload`, which calls that backend's `to_messages` with its own
  correct arity internally. Still true in this iteration: `to_api_payload`
  is the only interface-safe entry point on `PromptBuilder` across all five
  backends.
- **`Message` still has no way to represent an assistant's own tool-call
  intent** (name + arguments + id) — only a `tool_result`'s `tool_use_id`.
  The prior review flagged this as "a gap to watch once a later iteration
  starts round-tripping real tool calls." This iteration's `example.rb`
  avoids exercising it: it sends one user turn and lets the model respond
  with `tool_use` directly, rather than building a synthetic
  assistant-called-a-tool turn and echoing a `tool_result` back. The gap is
  therefore still unaddressed, not yet hit, and still worth watching for
  `05_agent_loop`, which per the README is exactly where multi-turn tool
  round-trips start.

**README discrepancy noticed while reviewing (not fixed — flagging for
awareness, not a code bug):** the `## Run Example` section says
`./week1_baseline/bin/04_api_client`, omitting the `ruby/` path segment —
the real path in this repo is `week1_baseline/bin/ruby/04_api_client`. Same
class of stale-path note as flagged in the `02_the_registry` review.

---

## Retain — the short list

1. **`Client` has two independently-bounded retry paths** (transient
   exceptions vs. retryable HTTP status codes), both capped at
   `MAX_RETRIES = 3` with the same exponential backoff — verify which path
   a given failure takes before assuming a change to one affects the other.
2. **Every backend validates its model at construction, not at
   request-build time** — `UnsupportedModelError` fires the moment a
   `Backends::X.new(...)` is called with an unrecognized model string.
3. **`estimate_cost` distinguishes "free" (`0.0`) from "unknown" (`nil`)**
   by which value each backend's `MODELS` table carries for
   `cost_per_million` — don't conflate the two.
4. **`Tasks::Base#prompt_override?` fails closed (returns `false`), not
   loud, on a missing/malformed `prompt_override` node** — a broken
   `PROMPTS_DIR` default (or any default-prompt path) can silently return
   `nil` instead of erroring if a settings file doesn't happen to opt into
   the user-prompt override. Confirmed exactly this shape of bug in fix #3.
5. **The off-by-one `BOUKENSHA_DIR` `../` bug is now confirmed in 4 of 5
   Ruby iterations wired up so far** (`00`, `01`, `02`, `03`, now `04`) —
   still expect it, latent, in `05`–`08`.
6. **A second, independent off-by-one (`PROMPTS_DIR`, in library code this
   time, not an example script) shows the same bug *class* can appear
   anywhere a `../`-count is hand-written and copy-pasted across
   iterations** — worth grepping for `File.expand_path("../` patterns in
   each new iteration's `lib/`, not just its `examples/`, before assuming a
   smoke-test pass means every path constant is correct.
7. **`PromptBuilder#to_messages`/`#to_tools`'s arity bug (flagged in the
   `03_prompt_builder` review) is still present and still only reachable
   through those two convenience methods** — `to_api_payload` remains the
   only safe entry point across all five backends.
8. **The `Message` model still cannot represent an assistant's own tool
   call** — still not hit by this iteration's example, still worth watching
   once `05_agent_loop` starts building real multi-turn tool transcripts.
