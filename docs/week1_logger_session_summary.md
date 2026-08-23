# Session Summary — Building "The Logger" (Simple Version)

This is a plain-language recap of what we did in this session, with small
examples. No deep jargon — just what happened and why it mattered.

## What we were building

Step 6 of the Boukensha project: a **Logger**. Every time the AI agent does
something (thinks, calls a tool, gets a reply), the Logger writes one line
to a file. Later, a small web page (`log_viz`) reads that file and shows it
as a readable chat transcript instead of raw text.

We built this twice: once in **Ruby** (the original), then **ported** it to
**Python** (rewrote the same behavior in a different language).

## The main idea: one event = one line of JSON

Every time something happens, the Logger appends one line like this to a
file:

```json
{"phase":"tool_call","name":"read_file","args":{"path":"README.md"},"session_id":"abc123","at":"2026-08-23T12:24:46+00:00"}
```

This format is called **JSONL** ("JSON Lines") — just a text file where
every single line is its own valid JSON object. It's simple on purpose:
- Easy to read one line at a time (no need to load the whole file).
- Easy to search with basic tools like `grep`.
- Easy for another program (like `log_viz`) to turn into something
  human-friendly.

Example of what one full session file contains, phase by phase:

```
session_start   → "a run just began"
iteration       → "starting loop pass #1"
prompt          → "here's what we're about to send the AI"
tool_call       → "the AI asked to run a tool"
tool_result     → "here's what that tool returned"
response        → "the AI's reply, plus cost/tokens used"
turn_end        → "the run finished, and why"
```

## Bugs we found (and what they teach)

### 1. The "off-by-one folder" bug

Several files needed to find a folder like `.boukensha/` by counting
`../` (meaning "go up one folder") a fixed number of times, e.g.:

```ruby
File.expand_path("../../../.boukensha", __dir__)
```

This is fragile — if you count wrong, you silently land in the *wrong*
folder instead of getting an error. We found this same mistake **repeated
across almost every step of the project** (7+ times!) because each new
step copied the previous one's file, including its bug.

**Lesson:** counting folder levels by hand is error-prone and the mistakes
don't shout at you — they just quietly point somewhere empty. Ruby needed
this fix every time; **Python never had this bug at all**, because the
Python code computes the path automatically from the file's own location
instead of manually typing `../../..`.

### 2. The "OpenAI" spelling bug

The Logger needed to write which AI provider was used, like `"anthropic"`
or `"openai"`. It did this by taking the code's class name (like
`OpenAI`) and converting it automatically to lowercase with underscores.

The automatic conversion is simple: *whenever a lowercase letter is
followed by an uppercase letter, insert an underscore.* That works for
most names:

```
OllamaCloud  → ollama_cloud   ✅ correct
```

But it breaks for `OpenAI`, because the letters `A` and `I` are *both*
uppercase, right next to each other — the "simple rule" still splits it:

```
OpenAI       → open_ai        ❌ wrong! should be "openai"
```

**Lesson:** "automatic" text conversions look right until you test the one
input that breaks the pattern. We fixed it by special-casing `OpenAI` and
returning `"openai"` directly, in **both** languages, and proved it by
testing all 5 provider names side by side.

### 3. The "no compiler here" problem

To view the logs in a browser, we needed to install a small web server
(`puma`). It failed to install because it needs to compile some C code,
and this environment has no compiler and no working `sudo` password.

**What we did:** swapped `puma` for `webrick` — a different web server
that's plain, pre-built Ruby code with nothing to compile. Same result
(a working web page), no compiler needed.

**Lesson:** when a tool needs something your environment doesn't have,
look for a simpler alternative that does the same job before trying to
force the original to work.

### 4. A Python-specific trap while porting

While copying the Ruby code's idea of a single global "settings" object
into Python, we almost named a function `config()`. That would have quietly
broken things, because Python already uses the name `config` internally
for the file `config.py`. Overwriting it would make other code that expects
to find that file secretly get our new function instead — a bug that
wouldn't show an error, it would just misbehave later.

**Lesson:** we caught this by literally testing it in a throwaway example
before writing the real code, and renamed it to `get_config()` instead.
Testing small assumptions early is cheaper than debugging them later.

## What we actually ran (in order)

1. **Ran the Ruby example** → it made a real call to the Anthropic API and
   created a log file:
   ```
   ./bin/ruby/06_the_logger
   ```
2. **Started the log viewer** (a small local website) and opened it to
   confirm the log displayed correctly:
   ```
   bundle exec ruby bin/log_viz
   → http://localhost:4567
   ```
3. **Copied the Ruby version's plan into a written port plan** (a markdown
   file describing exactly what needs to change to recreate this in
   Python) — so nothing gets rewritten from guesswork.
4. **Wrote the Python version** of the Logger, following that plan.
5. **Ran the Python example** the same way:
   ```
   ./bin/python/06_the_logger
   ```
   It also called the real API and created its own log file.
6. **Checked the log viewer again** with the *Python*-generated log file —
   it displayed exactly the same way as the Ruby one, with no changes
   needed to the viewer. This confirmed the file format really is
   language-independent.

## Observations

- **Copy-paste carries bugs forward.** Every new project step started as a
  copy of the previous one, so any unfixed bug traveled forward with it.
  Fixing it once didn't fix the copies — each had to be caught and fixed
  individually.
- **A clean run doesn't prove the code is bug-free** — it only proves the
  *one path* that run happened to take. The OpenAI bug was invisible in
  every test run because those runs used Anthropic, not OpenAI. We only
  found it by deliberately testing all 5 options side by side, offline,
  without needing real API access to each one.
- **Two languages, same rules, different traps.** Porting isn't just
  translating syntax — Ruby and Python are "falsy" about different things
  (e.g., is `0` treated as empty or not?), and each language has its own
  hidden footguns (like Python's module name collision above). Matching
  behavior exactly requires checking both sides carefully, not assuming
  a line-by-line rewrite is automatically correct.
- **Keeping a running troubleshooting log paid off.** Because every past
  fix (like the folder-counting bug) was written down with *why* it
  happened, later steps could predict "this will probably show up again"
  instead of rediscovering it from scratch each time.
