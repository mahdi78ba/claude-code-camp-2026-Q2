# `08_the_repl_loop` — Reviewing `repl.rb`

Companion to [`week1_repl_loop_overview.md`](week1_repl_loop_overview.md) (which
covers the whole iteration: `Boukensha.repl`, `Context#clear_messages!`, the
`Agent#run` history fix). This doc is scoped to exactly
`lib/boukensha/repl.rb` itself — the class the README calls "the interactive
session loop."

## Simple explanation

`Repl#start` is a `loop do ... end` with one job: print a prompt, read one
line of input, and decide what to do with it.

- If it's a built-in command (`/exit`, `/clear`, …), handle it directly and
  go straight back to the prompt — the agent never sees it.
- Otherwise, hand the line to the agent as a new message, print whatever the
  agent says back, and go back to the prompt.

It keeps doing this — reading, deciding, running, printing — until the user
types `/exit`/`/quit` or presses Ctrl-D. Because the same conversation object
is reused on every pass through the loop, each new question is answered with
the *whole conversation so far* in view, not just the latest line.

## 2.1 — Walking through `repl.rb`

`Boukensha::Repl` (`lib/boukensha/repl.rb`) is a plain object, not a subclass
of anything — no threads, no event loop library, just Ruby's own `loop`.
`initialize` (lines 30–45) does no work beyond storing what `Boukensha.repl`
already built for it: the shared `@context`, `@registry`, `@builder`,
`@client`, `@logger`, plus display-only extras (`@provider`, `@model`,
`@version`, `@api_key`, `@config_dir`) used only by `banner`. A `@turn`
counter starts at `0`.

`start` (lines 47–84) is the whole loop:

```ruby
def start
  puts banner
  loop do
    print PROMPT
    $stdout.flush
    input = $stdin.gets
    break unless input           # EOF / Ctrl-D
    input = input.chomp.strip
    next if input.empty?
    case input
    when "/exit", "/quit" then puts "Goodbye."; break
    when "/help"  then puts HELP; next
    when "/quiet" then Boukensha.quiet!; puts "..."; next
    when "/loud"  then Boukensha.loud!;  puts "..."; next
    when "/clear" then @context.clear_messages!; @turn = 0; puts "..."; next
    end
    run_turn(input)
  end
end
```

The `$stdout.flush` after `print PROMPT` matters: without it, the prompt can
sit in an unflushed buffer while `$stdin.gets` blocks, so the user would see
no prompt at all until the terminal's own buffering happened to flush it.

`run_turn` (lines 110–136) is the only path that talks to the model:

```ruby
def run_turn(input)
  @turn += 1
  @logger.turn(n: @turn)
  @context.add_message(:user, input)
  agent  = Agent.new(context: @context, registry: @registry, builder: @builder,
                      client: @client, logger: @logger, task_settings: @task_settings,
                      max_iterations: @max_iterations, max_output_tokens: @max_output_tokens)
  result = agent.run
  puts; puts result
rescue LoopError => e
  puts "\n[error] #{e.message}"
rescue ApiError => e
  puts "\n[error] API call failed: #{e.message}"
end
```

A **new `Agent` is built for every turn** rather than one long-lived `Agent`
reused across the session. This is cheap and correct here: `Agent` holds no
state of its own beyond `@iteration` (reset to `0` in its own `initialize`)
and the objects it's handed — `Context`, `Registry`, `Client`, `Logger` — are
the same shared instances every time, so nothing about the conversation is
lost by discarding the `Agent` wrapper at the end of each turn. It also means
`max_iterations` (the tool-call ceiling from `Agent::MAX_ITERATIONS` / task
settings) is correctly a **per-turn** budget, not a session-wide one — typing
a second question always gets a fresh allowance of tool calls, even if the
first question used all 25.

## 2.2 — The accept/forward loop, specifically

The mechanism the task asked to note, traced end to end:

1. `$stdin.gets` blocks until the user presses Enter (or sends EOF)
   — one line in, one line out; there's no partial-input or multi-line
   handling.
2. The raw line is `chomp.strip`ped before anything else looks at it, so
   trailing newline and surrounding whitespace never reach either the
   command matcher or the agent.
3. If it's not a recognized `/command`, it's forwarded verbatim to
   `@context.add_message(:user, input)` — this is the actual "forward to the
   agent" step. Nothing is rewritten, wrapped, or annotated first.
4. A brand-new `Agent` is constructed around the same shared context and run
   once (`agent.run`), which internally loops on *tool calls* (a completely
   separate, inner loop — see `Agent#run` in `lib/boukensha/agent.rb`) until
   the model returns plain text.
5. That final text is `puts`, and — critically, per the fix documented in the
   overview doc — is also appended to `@context` as an `:assistant` message
   by `Agent#run` itself before it returns. This is what makes the *next*
   pass through `Repl#start`'s loop able to see this turn's answer, not just
   its question.
6. Control returns to `start`'s `loop`, which prints the prompt again and
   blocks on `$stdin.gets` for the next line.

Net effect, verified live (see `docs/week1_config_troubleshooting.md` entry
#25): asking "what did I just ask you?" on turn 2 gets answered correctly
from `@context`'s accumulated messages — direct confirmation that steps 3–5
actually wire history through, not just in theory.

## 2.3 — Built-in commands

| Command | What happens | Notes |
|---|---|---|
| `/exit`, `/quit` | `puts "Goodbye."`, `break` | Only path that prints an explicit goodbye. |
| Ctrl-D (EOF) | `$stdin.gets` returns `nil` → `break unless input` | Leaves the loop silently — no "Goodbye.", unlike `/exit`. A cosmetic asymmetry, not a bug. |
| Ctrl-C (Interrupt) | **Not handled inside `Repl` at all.** `Repl#start` has no `rescue Interrupt`; the `Interrupt` propagates out of `.start` and is caught one level up, in `Boukensha.repl`'s own `rescue Interrupt → puts "\nInterrupted."` (`lib/boukensha.rb:166-167`). | Worth knowing precisely where this is caught if `Repl` is ever reused outside `Boukensha.repl` — it currently relies on its caller for Ctrl-C safety. |
| `/help` | `puts HELP` (a static heredoc), `next` | Command list only; doesn't reflect any config actually in effect. |
| `/quiet` | `Boukensha.quiet!` (sets a module-level `@quiet` flag), prints a confirmation | See caveat below — the flag is set but nothing in this codebase reads it. |
| `/loud` | `Boukensha.loud!`, prints a confirmation | Same caveat, inverse direction. |
| `/clear` | `@context.clear_messages!` (empties `@messages`, keeps `@tools`/`@system`), `@turn = 0`, prints a confirmation | Verified live: a follow-up "what number did I mention?" after `/clear` correctly gets "no record" — history really is gone, not just visually hidden. |

**Caveat confirmed on `/quiet`/`/loud`:** `Boukensha.quiet?` is defined
(`lib/boukensha.rb`) and set by these two commands, but grepping the whole
`lib/` tree shows nothing else ever calls `Boukensha.quiet?` — no output path
is conditioned on it. Combined with `Logger` being file-only (see the
overview doc's README-accuracy note), `/quiet` and `/loud` currently only
print their own one-line confirmation; there is no other terminal output for
them to actually suppress or restore yet.

**Observation on `/clear` resetting `@turn`:** since `@turn` (the REPL's own
counter, used only for `@logger.turn(n: @turn)`) is reset to `0` alongside
the message history, the *next* real turn after a `/clear` logs as `turn` `n:
1` again — verified directly against a session `.jsonl`:

```
{"phase":"turn","n":1, ...}      # first message
{"phase":"turn_end", ...}
{"phase":"turn","n":1, ...}      # second message, AFTER /clear — also n:1
{"phase":"turn_end", ...}
```

This is consistent (a cleared conversation restarting its turn count at 1 is
the intuitive behavior), but it does mean a single session log file can
contain more than one `{"phase":"turn","n":1}` entry — anything that greps a
`.jsonl` log by `n:` alone (rather than by position, or by pairing each
`turn` with the `turn_end` immediately following it) needs to be aware `n`
is not a session-unique counter once `/clear` has been used.

## Retain — the short list

1. **One `Agent` per turn, sharing one long-lived `Context`/`Registry`/
   `Client`/`Logger`** — cheap, correct, and what makes `max_iterations` a
   sane per-turn (not per-session) tool-call budget.
2. **The forward path is direct and unfiltered:** whatever the user types
   (once command-matched and `strip`ped) becomes the literal `:user` message
   content — no preprocessing to account for downstream.
3. **Ctrl-C is not handled inside `Repl`** — it relies on `Boukensha.repl`'s
   `rescue Interrupt` one level up. Reusing `Repl` directly (bypassing
   `Boukensha.repl`) would lose that safety net.
4. **`/quiet`/`/loud` are currently inert beyond their own confirmation
   text** — `Boukensha.quiet?` has no reader anywhere in `lib/`.
5. **`/clear` resets the REPL's own turn counter, not just message
   history** — a session log can contain repeated `{"phase":"turn","n":1}`
   entries after a `/clear`; don't assume `n` is unique within a session file.
