# Week 1 Review — API Client Python Port (`python/04_api_client`)

Companion to [`week1_api_client_port_plan.md`](week1_api_client_port_plan.md)
(the plan) and the Ruby-side [`week1_api_client_review.md`](week1_api_client_review.md).
This doc covers what was actually built, a real (not just smoke-test) review
pass per [[feedback_port_review_rigor]], and what to retain going forward.

---

## What was done

1. **Copied `python/03_prompt_builder` → `python/04_api_client`** verbatim
   (`.venv`/`__pycache__` excluded), same precedent as the `02 → 03` copy.
2. **Wrote the port plan** (`docs/week1_api_client_port_plan.md`) from a
   confirmed `diff -rq ruby/03_prompt_builder ruby/04_api_client`, then
   cross-checked it against the existing Python tree — both of Ruby's
   `tasks/base.rb` fixes (`.yaml` error text, an `isinstance`/`is_a?(Hash)`
   guard in `fetch`) were already present in `python/03_prompt_builder`,
   narrowing the real delta to: `errors.py` (`ApiError`), `client.py` (new),
   `__init__.py` export update, `prompts/system.md`, and the
   example/README rewrite.
3. **Implemented the port**, in dependency order: `errors.py` → `client.py`
   → `boukensha/__init__.py` export update → `prompts/system.md` →
   `examples/example.py` rewrite → `README.md`.
4. **Added the runner** `bin/python/04_api_client`, mirroring
   `bin/python/03_prompt_builder`'s "prefer lesson-local `.venv`, else
   `python3`" shape.
5. **Verified with a real, live API call** — `./bin/python/04_api_client`
   made an actual HTTPS POST to `https://api.anthropic.com/v1/messages`
   using the key already provisioned in `.boukensha/.env`. Response came
   back `stop_reason: "tool_use"` selecting `list_directory`, matching the
   Ruby runner's documented response shape and usage counts almost exactly
   (Ruby: 777 input / 53 output tokens; Python run: 777 input / 53–65
   output tokens across two runs — same input, minor output variance is
   expected model non-determinism, not a bug).
6. **Ran a real `code-review` pass** (effort: high) against the staged
   diff, not just the smoke test — see findings below. One was fixed, one
   was confirmed as an intentional, already-documented Ruby-fidelity
   choice, one was logged but not acted on (see rationale).

No new `week1_config_troubleshooting.md` entries were needed for
environment/install issues — the venv setup and dependency install were
identical to `03_prompt_builder`'s, no new problems hit. One real *code*
bug was found and fixed (below), unrelated to environment setup.

---

## Code review

### `boukensha.Client` (`boukensha/client.py`) — new this iteration

```python
class Client:
    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def call(self, *, max_output_tokens=1024):
        ...
        while True:
            attempts += 1
            try:
                with urllib.request.urlopen(request) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as e:
                ...  # retryable status codes vs. final ApiError
            except urllib.error.URLError as e:
                ...  # transient network errors vs. final ApiError
```

Line-by-line parity check against `lib/boukensha/client.rb`:

| Aspect | Ruby | Python | Match |
|---|---|---|---|
| Retryable status codes | `[408,409,429,500,502,503,504]` | `{408,409,429,500,502,503,504}` | ✓ |
| `MAX_RETRIES` / backoff formula | `3` / `0.5 * 2**(attempt-1)` | identical | ✓ |
| Default `max_output_tokens` | `1024` | `1024` | ✓ |
| Retry-threshold comparison operators | `attempts > MAX_RETRIES` (transient) / `attempts <= MAX_RETRIES` (status) | identical operators, identical branches | ✓ exact |
| Final error message pluralization | `"s" unless attempts == 1`, status path only | same, `HTTPError` path only | ✓ |
| Transient-exhausted message | always plural "attempts" | same | ✓ |
| Response body in error message | `response.body` | `e.read().decode(..., errors="replace")` | ✓ |

- **The one genuine adaptation, not a literal translation**: Ruby's
  `Net::HTTP#request` never raises for a non-2xx response — the caller
  checks `response.is_a?(Net::HTTPSuccess)` after the retry loop. Python's
  `urllib.request.urlopen` raises `urllib.error.HTTPError` for any status
  ≥ 400 and wraps lower-level connection/timeout/SSL failures in
  `urllib.error.URLError`. Catching the raw Python exception types a
  mechanical translation might reach for (`socket.timeout`,
  `ConnectionError`, `ssl.SSLError`) would silently never match, since
  `urlopen` always wraps them in `URLError` first — confirmed this is
  necessary by checking `urllib.error`'s wrapping behavior, not assumed.
  `HTTPError` is caught before `URLError` because `HTTPError` **is a**
  `URLError` subclass — reversing the order would misroute every non-2xx
  response into the transient-retry path.
- **SSL needs no manual configuration**, unlike Ruby's commented-out
  `OpenSSL::X509::DEFAULT_CERT_FILE` workaround (that constant resolves to
  a macOS-only path that doesn't exist on Linux/WSL2). Python's `ssl`
  module picks up the OS default trust store automatically — verified by
  the live HTTPS call succeeding with zero SSL configuration in
  `client.py`. Documented in the README as the Python port genuinely being
  simpler here, not silently different.

### `examples/example.py` — rewrite, matches `example.rb`'s new shape

- Tools swapped from `look`/`move` to `read_file`/`list_directory`,
  matching `File.read`/`Dir.entries` with `Path(path).read_text()` and a
  sorted, dotfile-filtered directory listing.
- Three hand-seeded messages replaced with one real user turn — matches.
- Same provider/model resolution and `if/elif/else` backend-construction
  chain as `03_prompt_builder`'s example — carried forward unchanged in
  shape, per that port's established precedent of matching Ruby's control
  flow 1:1 over a "more Pythonic" dispatch table.
- `client.call()` + `json.dumps(response, indent=2)` — matches Ruby's
  `client.call` + `JSON.pretty_generate(response)`.

### Findings from the `code-review` pass (effort: high)

1. **`Config.mud_host`/`mud_port` used Python's `or` for defaulting —
   fixed.** Ruby's `dig(:mud, :port) || 4000` only falls back on `nil`/
   `false`; Ruby's `0` and `""` are truthy and get returned as-is. The
   Python port's `self.dig("mud", "port") or 4000` treats `0` as falsy, so
   a legitimately-configured `mud.port: 0` (or `mud.host: ""`) silently
   became `4000`/`"localhost"` instead. **Fixed** by switching both
   properties to explicit `is None` checks:
   ```python
   @property
   def mud_port(self):
       value = self.dig("mud", "port")
       return 4000 if value is None else value
   ```
   Re-verified interactively both ways: `{"mud": {"port": 0, "host": ""}}`
   now returns `0`/`""` unchanged, and no `mud` config still returns the
   correct defaults (`"localhost"`/`4000`). This bug predates this port —
   it was carried over unchanged from `02_the_registry`/`03_prompt_builder`
   — but since it surfaced during this iteration's review and the fix is
   self-contained, it was fixed here rather than only noted. `02_the_registry`
   and `03_prompt_builder`'s copies of `config.py` still have the
   unfixed version; not touched, per "fix on sight in the copy you're
   reviewing" precedent (mirrors how the Ruby `../`-count bugs were handled
   one iteration at a time, not retroactively across all of them).
   `_resolve_dir`'s analogous `os.environ.get("BOUKENSHA_DIR") or
   self.DEFAULT_DIR"` has the same theoretical gap (an explicitly-set empty
   `BOUKENSHA_DIR=""` would fall back to `DEFAULT_DIR` in Python but resolve
   to the current working directory in Ruby) — **left as-is**: nobody
   sets `BOUKENSHA_DIR` to an empty string on purpose, and Python's
   behavior (fall back to a sane default) is arguably more correct than
   Ruby's own quirk here, not less.

2. **`PromptBuilder.to_messages()`'s arity mismatch for 3 of 5 backends —
   confirmed intentional, no action needed.** Flagged again by the
   reviewer as a "live footgun," but this is the exact, previously-known
   Ruby-reference bug already documented at length in this port's own
   README (`03_prompt_builder`'s README carried it forward, and this
   iteration's README repeats it with an added note that `Client.call`
   never triggers it). Confirmed once more: `Client.call` only ever
   invokes `builder.to_api_payload()`, which routes through each backend's
   own `to_payload`/`to_messages` with the correct arity internally — the
   gap is real but unreachable from this iteration's actual code path.
   Not "fixed" deliberately, matching the Ruby review's own treatment
   ("treat `to_api_payload()` as the only currently-safe entry point").

3. **`to_tools()`/`to_messages()` duplicated near-verbatim across
   `openai.py`/`ollama.py`/`ollama_cloud.py` — noted, not refactored.**
   A real simplification opportunity (a shared `Base` helper could
   de-duplicate the OpenAI-style function-calling schema), but these three
   files are direct, faithful ports of Ruby backends that have the exact
   same duplication on the Ruby side (`backends/*.rb` were not touched in
   this Ruby iteration and were confirmed byte-identical to
   `03_prompt_builder`'s copies). Introducing a shared abstraction here
   would diverge from the Ruby reference for its own sake, which is out of
   scope for a port whose job is fidelity, not redesign — consistent with
   this project's standing precedent of flagging cross-cutting Ruby design
   choices in review docs rather than silently "improving" them mid-port.

---

## Verification performed

1. **Byte-diff against `03_prompt_builder`** (`diff -rq`, `.venv`/
   `__pycache__` excluded) — confirmed `config.py` (pre-fix),
   `context.py`, `message.py`, `registry.py`, `tool.py`, `prompt_builder.py`,
   `tasks/*`, and `backends/*.py` are **untouched**, exactly matching the
   plan's scope guard. Only `errors.py`, `__init__.py`, `client.py` (new),
   `prompts/system.md`, `examples/example.py`, and `README.md` differ.
2. **Runner smoke test, twice** (before and after the `config.py` fix):
   `./bin/python/04_api_client` exits `0` both times and completes a real
   HTTPS round trip, returning `stop_reason: "tool_use"` /
   `list_directory` — matches the Ruby runner's documented live-call
   output shape.
3. **`mud_host`/`mud_port` zero/empty-string regression check** — see
   finding #1 above; confirmed both the bug (pre-fix) and the fix
   (post-fix) interactively, not just from reading the diff.
4. **`Client` retry/backoff logic traced by hand** against `client.rb`,
   operator-for-operator (see the parity table above) — not just "looks
   similar," every threshold comparison and message string was checked to
   produce identical behavior for identical inputs.

---

## Retain — the short list

1. **`Client.call()` is the only interface-safe entry point on
   `PromptBuilder`/`Client` for `OpenAI`/`Ollama`/`OllamaCloud`** — same
   caveat carried forward from `03_prompt_builder`, now re-confirmed as
   still true and still unreachable from `Client`.
2. **`urllib.error.HTTPError` must be caught before `URLError`** in any
   future `urlopen`-based code in this codebase — `HTTPError` is a
   `URLError` subclass, and reversing the catch order silently misroutes
   every non-2xx response into the transient-retry path instead of the
   status-code-based one.
3. **Python's `or`-for-defaulting is not a safe stand-in for Ruby's
   `||`** whenever the configured value could legitimately be `0`,
   `""`, or `[]`/`{}` — Ruby's falsy set is `nil`/`false` only; Python's is
   much bigger. `estimate_cost`'s explicit `is None` checks already got
   this right; `Config.mud_host`/`mud_port` didn't, until this review.
   **Grep for bare `or <default>` / `... or {}` patterns reading
   `settings.yaml`-sourced values in any future port** — this is a bug
   *class* in exactly the same sense the Ruby `../`-count bugs were, just
   on the Python side.
4. **Backend-level duplication (`to_tools`/`to_messages` across
   OpenAI-style backends) is a faithfully-ported Ruby trait, not a Python
   regression** — don't refactor it away independently of the Ruby
   reference; note it in review docs instead, the same way the `03`
   review flagged the `to_messages` arity asymmetry without "fixing" it.
5. **Going forward**: `05_agent_loop` is where multi-turn tool round-trips
   start exercising `Message`'s current inability to represent an
   assistant's own tool-call intent (name + arguments + id) — flagged by
   the Ruby review as a gap to watch, still unaddressed on both sides,
   still not hit by any example through `04_api_client`.
