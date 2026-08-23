# `08_the_repl_loop` — `Boukensha.repl` Overview

## 1. Simple explanation

`Boukensha.run` (step 6/7) sends exactly one task and returns. `Boukensha.repl`
keeps the same `Context`/`Registry`/`Client`/`Logger` alive across many turns:
it prints a `boukensha> ` prompt, reads a line from stdin, runs the agent, prints
the reply, and loops — until `/exit`, `/quit`, or EOF (Ctrl-D).

```ruby
Boukensha.repl(model: "claude-haiku-4-5") do
  tool "read_file",
    description: "Read a file from disk",
    parameters:  { path: { type: "string", description: "File path" } } do |path:|
    File.read(path)
  end
end
```

Because the same `Context` is reused for every turn, the agent sees the full
conversation transcript on turn 2, 3, etc. — not just the latest message.

## 2. Technical explanation

### `Boukensha.repl` (`lib/boukensha.rb`)

Mirrors `Boukensha.run`'s setup exactly (config load, task/model/backend/api_key
resolution, `Context`/`Registry` construction, `RunDSL` block eval, backend
instantiation) but instead of building one `Agent` and calling it once, it
constructs a `Boukensha::Repl` and calls `.start`. `rescue Interrupt` at this
level turns a Ctrl-C into a graceful `"Interrupted."` message instead of a
stack trace.

### `Boukensha::Repl` (`lib/boukensha/repl.rb`)

The loop itself:

1. Prints a banner (version, config dir, provider/model, API-key presence).
2. Reads a line; `nil` (EOF) breaks the loop.
3. Built-in commands (`/exit`, `/quit`, `/help`, `/quiet`, `/loud`, `/clear`)
   are intercepted before reaching the agent.
4. Anything else becomes `run_turn(input)`: increments a turn counter, appends
   the input as a user message on the **shared** `@context`, builds a **new**
   `Agent` per turn (cheap — it's a thin wrapper around the same context/
   registry/client/logger), and prints `agent.run`'s return value.
5. `LoopError`/`ApiError` are caught per-turn so one bad turn doesn't kill the
   session.

### `Context#clear_messages!` (`lib/boukensha/context.rb`)

New method backing `/clear`: resets `@messages` to `[]` but leaves `@tools`
and `@system` untouched, so registered tools survive a history wipe.

### `Agent#run` now persists its own final reply

Before this step, `Agent#run`'s final branch returned `text` without adding
it to the context (harmless for a one-shot `Boukensha.run`, since the context
is discarded after). For the REPL, that omission would silently drop half of
every turn from history — the next turn's prompt would include the user's
questions but not the agent's answers. `lib/boukensha/agent.rb` now does:

```ruby
@context.add_message(:assistant, text)
return text
```

before returning, so turn 2 onward sees the full back-and-forth.

### `examples/example.rb` — the Run DSL entry point, `BOUKENSHA_DIR` moved out

`Boukensha.repl do ... tool "..." do |...| ... end end` (line ~14) is the
same Run DSL block syntax as `Boukensha.run`, minus `task:` — `tool` calls
inside the block register on the shared `Registry` via `RunDSL#tool` before
the REPL loop takes over; nothing about starting the REPL differs from
starting a one-shot run except which `Boukensha.*` method is called.

`examples/example.rb` no longer sets `ENV["BOUKENSHA_DIR"]` itself. That
line has moved into `bin/ruby/08_the_repl_loop` (the launcher exports it
before invoking `bundle exec ruby examples/example.rb`), so the example
script now relies on whatever's already in the environment — matching its
own comment ("`~/.boukensha` (or `BOUKENSHA_DIR`) by default"). Running the
script directly, bypassing the launcher, correctly falls through to
`~/.boukensha`, which doesn't exist in this environment — `Config` raises a
clear `ArgumentError` (`tasks.player.model is required in settings.yaml`)
rather than silently misconfiguring, confirming the fallback path is loud,
not silent.

## 3. Objective assessment

**What it adds:** a genuinely new interaction mode (many turns, accumulating
history, live commands) built entirely from step-7 primitives — no new
backend/client/protocol code, just a loop plus one context method plus one
missing `add_message` call in the agent.

**What it costs:** a new `Agent` is constructed on every turn (line ~116 of
`repl.rb`). This is cheap here (no state to migrate — `Context`/`Registry`/
`Client`/`Logger` are all passed in by reference) but it does mean
`@iteration` resets to 0 each turn, which is correct (`max_iterations` is a
per-turn ceiling, not a per-session one).

**README accuracy note:** the README documents `Logger#turn` as printing a
`╔══ turn N ══╗` header "at the start of each REPL turn." The shipped
`Logger#turn` (`lib/boukensha/logger.rb`) only calls `write_log`, which writes
JSON to the session file and never touches `$stdout` — consistent with
`Logger`'s design since step 6 ("a file logger, not user-facing display
output"), but it means no visible turn header actually appears on screen, and
`/quiet`/`/loud` currently toggle a `Boukensha.quiet?` flag that nothing reads.
Flagging as a doc/behavior mismatch rather than "fixing" it, since adding new
`$stdout` output isn't part of this step's shipped feature set.

**Verified behavior** (`./bin/ruby/08_the_repl_loop`, live Anthropic call,
piped stdin):

- Banner prints correct config dir, provider (`anthropic`), model
  (`claude-haiku-4-5`), and `✓ API key set`.
- Turn 1 (`list the files in the lib directory`) dispatches `list_directory`
  and returns a correct two-entry listing.
- `/quiet` prints its confirmation and suppresses nothing further (see note
  above).
- Turn 2 (`what did I just ask you?`) is answered correctly from the shared
  `Context` — direct confirmation that `Agent#run`'s new `add_message` call
  and the REPL's turn-scoped `Agent.new` are wired correctly.
- `/clear` followed by `what number did I mention?` gets "I don't have any
  record of you mentioning a number" — confirms history actually resets.
- `/exit` prints `Goodbye.` and exits cleanly.
- The session's `.jsonl` log shows two `turn` entries, each starting its own
  `iteration` count back at 1, confirming the per-turn `Agent` is fresh each
  time.

This confirms `Boukensha.repl` is what the README claims for interaction
(prompt/read/run/print, persistent history, live commands), modulo the
turn-header display gap noted above.
