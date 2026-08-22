# Python Port Plan — API Client (`04_api_client`)

Plan only — no `boukensha/` code has been written yet, beyond copying
`python/03_prompt_builder` verbatim into `python/04_api_client` as the
starting point (`.venv/` and `__pycache__/` excluded from the copy, same
precedent as the `01→02` and `02→03` ports). This document scopes exactly
what to change next, and just as importantly, what to leave alone.

## What actually changed in Ruby (03 → 04)

Confirmed with `diff -rq ruby/03_prompt_builder ruby/04_api_client`
(vendor/bundle noise stripped):

```
Only in 04_api_client/lib/boukensha: client.rb
Files 03_prompt_builder/lib/boukensha/config.rb and 04_api_client/lib/boukensha/config.rb differ
Files 03_prompt_builder/lib/boukensha/errors.rb and 04_api_client/lib/boukensha/errors.rb differ
Files 03_prompt_builder/lib/boukensha/tasks/base.rb and 04_api_client/lib/boukensha/tasks/base.rb differ
Files 03_prompt_builder/lib/boukensha.rb and 04_api_client/lib/boukensha.rb differ
Files 03_prompt_builder/examples/example.rb and 04_api_client/examples/example.rb differ
Files 03_prompt_builder/prompts/system.md and 04_api_client/prompts/system.md differ
```

`backends/*.rb` (all five providers plus `base.rb`) are **byte-identical**
between the two Ruby iterations — no backend logic changed in this step.

Of the files marked "differ," most of the delta is small:

- `config.rb` — comment wording only (`"shipped alongside the
  gem/library code"` → `"shipped alongside this step"`) plus a blank line.
  No behavior change; `PROMPTS_DIR`'s value is identical in both.
- `errors.rb` — adds one class, `ApiError < StandardError`.
- `tasks/base.rb` — two defensive fixes: error message text
  `settings.yml` → `settings.yaml`, and a `return nil unless
  settings.is_a?(Hash)` guard added to `fetch`.
- `lib/boukensha.rb` — drops the standalone `require_relative
  "boukensha/backends/base"` line (each backend file already requires it
  itself) and adds `require_relative "boukensha/client"`.
- `prompts/system.md` — new system prompt text ("autonomous player
  exploring a CircleMUD world" instead of "MUD player assistant").

The real, behavior-carrying delta is: one new class (`Boukensha::Client`,
~80 lines, retry/backoff + HTTP POST via stdlib `net/http`), one new error
class (`ApiError`), and a rewritten example that swaps the toy `look`/`move`
tools for real filesystem tools (`read_file`, `list_directory`) and adds a
live `client.call` + raw-response print.

**Important cross-check against the current Python tree:** both of the
`tasks/base.rb` fixes are **already present** in `python/03_prompt_builder`:

- `tasks/base.py`'s `provider`/`model` error messages already say
  `"...required in settings.yaml"` (not `.yml`).
- `tasks/base.py`'s `_fetch` already has `if not isinstance(settings,
  dict): return None`.

So, unlike the Ruby side, **no change is needed in `tasks/base.py` for this
port** — the Python port had already anticipated both fixes. This mirrors
the `03_prompt_builder` port plan's finding that `tasks/base.py` and
`config.py` were "ported ahead of schedule."

`config.py`'s `PROMPTS_DIR` is computed dynamically
(`Path(__file__).resolve().parent.parent / "prompts"`), not via a
hand-written `../`-count string. This sidesteps the entire bug class
documented in `week1_config_troubleshooting.md` entries #4/#8/#10/#11/#12/#13
(the Ruby `BOUKENSHA_DIR`/`PROMPTS_DIR` off-by-one `../` bugs) — nothing to
audit or fix here, by construction, on either the config or example side
(`example.py` already resolves the repo root via `Path(__file__).resolve()
.parents[4]`, not a hand-counted string).

## Files to add / change in Python

### 1. `boukensha/errors.py` — add `ApiError`

```python
class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with a model it doesn't support."""


class ApiError(Exception):
    """Raised when an HTTP request to a provider's API fails."""
```

Same flatness precedent as `UnsupportedModelError` in the prior port —
mirrors `Boukensha::ApiError < StandardError` as a plain `Exception`
subclass.

### 2. `boukensha/client.py` — new, ported from `lib/boukensha/client.rb`

Ruby's `Client` uses `net/http` (stdlib, "no gems" is explicitly the point
per the Ruby README's "No Dependencies" section). The Python port uses
`urllib.request` (stdlib) for the same reason — no new entry in
`requirements.txt`.

Structural differences from a literal translation, driven by how the two
standard libraries actually surface errors:

- **Ruby's `Net::HTTP` does not raise on a non-2xx response** — it returns
  a response object, and the code checks `response.is_a?(Net::HTTPSuccess)`
  after the retry loop. **Python's `urllib.request.urlopen` raises
  `urllib.error.HTTPError`** (a subclass of `OSError`) for any status
  ≥ 400. So the retryable-status-code check and the "raise `ApiError`"
  logic both move into an `except urllib.error.HTTPError` clause instead of
  an `if` after the loop.
- **Ruby's transient-error list is explicit Net::HTTP/OpenSSL exception
  classes** (`EOFError`, `Errno::ECONNRESET`, `Errno::ECONNREFUSED`,
  `Net::OpenTimeout`, `Net::ReadTimeout`, `OpenSSL::SSL::SSLError`,
  `SocketError`, `Timeout::Error`). **`urlopen` wraps the low-level
  `OSError`/`socket.timeout`/`ssl.SSLError` that actually occurs inside its
  own `urllib.error.URLError`** (`URLError.reason` holds the original
  exception) — catching the raw exception types directly (as a literal
  translation would) would silently never match, since they never propagate
  unwrapped. Catch `urllib.error.URLError` instead (checked in a second
  `except` clause, after `HTTPError`, since `HTTPError` is itself a
  subclass of `URLError` and must be caught first).
- **HTTPError instances carry the failed response body** — `e.read()`
  before the error object goes out of scope, mirroring Ruby's
  `response.body` in the final `ApiError` message.
- Retry bookkeeping (`RETRYABLE_STATUS_CODES`, `MAX_RETRIES = 3`,
  `BASE_RETRY_DELAY = 0.5`, `attempt * 2` exponential backoff via
  `time.sleep`) ports 1:1 — same constants, same formula
  (`BASE_RETRY_DELAY * (2 ** (attempt - 1))`).
- `call(self, *, max_output_tokens=1024)` matches the existing Python
  convention (keyword-only args) already used by `to_api_payload`.

```python
class Client:
    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def __init__(self, builder):
        self.builder = builder

    def call(self, *, max_output_tokens=1024):
        body = json.dumps(
            self.builder.to_api_payload(max_output_tokens=max_output_tokens)
        ).encode("utf-8")
        request = urllib.request.Request(
            self.builder.url, data=body, headers=self.builder.headers, method="POST"
        )

        attempts = 0
        while True:
            attempts += 1
            try:
                with urllib.request.urlopen(request) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as e:
                if self._retryable_status(e.code) and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue
                body_text = e.read().decode("utf-8", errors="replace")
                suffix = "s" if attempts != 1 else ""
                raise ApiError(
                    f"API request failed after {attempts} attempt{suffix} "
                    f"({e.code}): {body_text}"
                ) from e
            except urllib.error.URLError as e:
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: "
                        f"{type(e.reason).__name__}: {e.reason}"
                    ) from e
                time.sleep(self._retry_delay(attempts))
```

### 3. `boukensha/__init__.py` — export `Client`, `ApiError`

```python
from .client import Client
from .errors import UnknownToolError, UnsupportedModelError, ApiError
```

mirroring `lib/boukensha.rb`'s new `require_relative "boukensha/client"`
line, added to `__all__`.

### 4. `boukensha/config.py` — no change

`PROMPTS_DIR` is already correct and already computed dynamically (see
above). The Ruby diff here is comment-only. Verify, don't touch.

### 5. `boukensha/tasks/base.py` — no change

Both Ruby fixes in this step (`.yaml` message text, `isinstance` guard)
are already present. Verify, don't touch.

### 6. `examples/example.py` — rewrite to match Ruby's new `example.rb`

- Replace the `look`/`move` toy tools with `read_file` (reads a file from
  disk given `path`) and `list_directory` (lists non-dotfile entries in a
  directory given `path`), matching Ruby's `File.read`/`Dir.entries`
  1:1 with `Path(path).read_text()` / real directory listing.
- Drop the three hand-seeded `ctx.add_message(...)` calls (`user`,
  `assistant`, `tool_result`) — this step sends a single real user turn:
  `"What files are in the current directory?"`.
- Keep the same provider/model resolution and backend-construction
  branch structure as `03_prompt_builder`'s example (`if/elif/else`
  chain reading `os.environ`) — Ruby's `case` didn't change its branches'
  bodies, only added multi-line formatting, which is a Ruby style choice,
  not a behavior change worth porting for its own sake.
- Construct `client = Client(builder)`, print
  `f"Sending request to {builder.url}..."`, call `response =
  client.call()`, and print the parsed response with
  `json.dumps(response, indent=2)` (Ruby's `JSON.pretty_generate`).
- Update the banner string to `"=== Boukensha Step 4: API Client ==="`
  (matching this port's established `Step N` capitalization convention
  from `03_prompt_builder`'s `example.py`, not Ruby's literal
  `BOUKENSHA`/`Step 4` casing).

### 7. `prompts/system.md` — update text

Port the new system prompt verbatim:

```
You are Boukensha, an autonomous player exploring a CircleMUD world.

Use available tools to observe the world, act deliberately, and explain only what matters for the current turn.
```

### 8. `requirements.txt` — no change

`Client` uses only `urllib.request`/`json`/`time` from the standard
library — same "no new dependency" outcome as the Ruby side's stdlib-only
`net/http` choice.

### 9. `README.md` — rewrite

Port the structure of Ruby's new `04_api_client/README.md` (intro, New
Files / Updated Files tables, architecture diagram, `Client` method table,
Task Configuration section, "No Dependencies" section, example raw-response
JSON shapes for Anthropic and Ollama, Considerations). Adapt
provider-specific/library-specific details to Python:

- Replace the `net/http`/`OpenSSL::X509::DEFAULT_CERT_FILE` considerations
  with the Python-equivalent note: `urllib.request` picks up the system's
  default CA trust store automatically via the `ssl` module with no
  extra configuration needed on Linux, so there's no Python analogue of
  the Ruby README's "you will need to update the code based on your
  machine's requirements" OpenSSL caveat — call this out explicitly as a
  place where the Python port is *simpler* than the Ruby reference, not
  silently different.
- Carry forward the existing "Design considerations (porting notes)"
  section from `03_prompt_builder`'s README (the `to_messages` arity
  asymmetry, `MODELS` as a class attribute, no String/Symbol branching,
  properties vs. methods, subpackage exports) since none of those Ruby
  behaviors changed in this step — add one new bullet documenting the
  `HTTPError`/`URLError` exception-wrapping difference from item 2 above.

## Explicitly NOT touched (scope guard)

Per "port only the new Ruby changes," these stay exactly as copied from
`03_prompt_builder`, untouched:

- `boukensha/tool.py`, `boukensha/message.py`, `boukensha/context.py`,
  `boukensha/registry.py`, `boukensha/prompt_builder.py`,
  `boukensha/tasks/player.py` — byte-identical on the Ruby side between
  `03` and `04`.
- `boukensha/backends/*.py` (all five providers plus `base.py`) — Ruby's
  backends are byte-identical between `03` and `04`; no backend logic
  changed in this step.
- `boukensha/config.py`, `boukensha/tasks/base.py` — see items 4/5 above;
  the one real Ruby change (`tasks/base.rb`'s two fixes) was already
  ported ahead of time.

## Order of implementation (for the follow-up "do the port" step)

1. `boukensha/errors.py` — add `ApiError`
2. `boukensha/client.py` — new
3. `boukensha/__init__.py` — export `Client`, `ApiError`
4. `prompts/system.md` — new text
5. `examples/example.py` — rewrite
6. `README.md` — rewrite
7. `week1_baseline/bin/python/04_api_client` — new runner, matching the
   `bin/python/03_prompt_builder` pattern
8. Run `.venv/bin/python examples/example.py` (after `python3 -m venv
   .venv && .venv/bin/pip install -r requirements.txt`, since
   `04_api_client` is copied without its own `.venv`) against the real
   `ANTHROPIC_API_KEY` already provisioned in `.boukensha/.env` (per
   `week1_api_client_review.md`, the Ruby side already made a live call
   with this same key), and compare the response shape against the Ruby
   run's documented output for structural parity.
9. Per `[[feedback_port_review_rigor]]`, run an actual review pass (the
   `code-review` skill against the new/changed files, not just "the
   example ran without raising") before staging/committing, and write
   findings to `docs/week1_api_client_python_review.md` — the same
   treatment the Ruby side got in `week1_api_client_review.md` and the
   `03_prompt_builder` Python port got in
   `week1_prompt_builder_python_review.md`.
