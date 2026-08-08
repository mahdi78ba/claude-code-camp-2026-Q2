# Week 0 Journal — Getting an AI Agent to Play a MUD

## Technical Goal
Get an AI agent to actually *play* a text game (a MUD) on its own — connect, log
in, move around, remember what it learns — and figure out which setup makes that
reliable. The long-term target: beat the Massive Minotaur in the Newbie Zone.

## Technical Uncertainty (before I started)
- Can a plain AI agent even hold a live game connection?
- Where should the agent's memory live — is markdown enough?
- Would a smarter model just solve everything?
- How do you run more than one agent at the same time?

## Technical Hypotheses (my guesses)
- The agent would connect fine, and the hard part would be the game logic.
- A stronger model (Sonnet) would clearly beat a weaker one (Haiku).
- Markdown memory files would be good enough.

*(Spoiler: mostly wrong on all three.)*

## Technical Observations

**What worked**
- Giving the agent a reusable script/skill (`mud.py`) so it stops rebuilding a
  client every run. Once the connection was solid, simple goals just worked —
  even on Haiku.
- Two sub-agents in parallel: `dummy` (Warrior) and `Smarty` (Mage) played at the
  same time, each with its own memory. Genuinely cool to watch.
- The Agent SDK version — same behavior, but now I control it in code and can see
  every step.

**What didn't**
- The plain agent couldn't hold a connection at all — it rewrote a telnet client
  ~11 times in one run. Painful.
- Markdown memory went stale and even "parroted" old answers. Clearing the files
  wasn't enough; I had to `/clear` the whole session to force a real run.
- Long goals (the Minotaur) fell apart — the agent backtracked, got stuck, and
  asked *me* what to do instead of just deciding.

**Unexpected**
- The world kept re-seeding **blank** after Docker restarts and "wiping" my
  character (it was actually safe on disk). Took a while to diagnose; fixed by
  removing auto-restart.
- A character got created as an immortal god once (first char on a blank world) —
  and the agent confidently misread that as "the server makes everyone immortal."
- Shop prices changed depending on *who* was asking. "The menu" isn't even a
  fixed fact.
- Two parallel agents multiplied token cost, and one got stuck silently burning
  tokens until I noticed and stopped it.
- In the SDK run, the agent had the right tools but the wrong permission mode
  blocked one — so it started reinventing the client again. The exact day-one
  failure, back for an encore.

## Technical Conclusions
- **A smarter model doesn't fix a wrong architecture.** The bottleneck was tooling,
  not brains.
- Agents need a real **interface** (connect / send / read), not to re-invent one
  every run.
- Memory needs **structure and identity** — plain markdown corrupts maps on
  duplicate room names and goes stale.
- Sub-agents ≈ Skills for one agent; sub-agents win for running **many at once**,
  and the SDK gives real control for building an actual app.
- Everything points at the same next step: a **custom agent loop** with planning,
  per-agent memory, and observability.

**Still open (for later)**
- Store the world with real room IDs (SQLite?) instead of markdown.
- Make the agent write a visible plan *before* acting.
- Get it to decide on its own instead of asking me.
- Actually beat the Minotaur — `dummy` is still a level-1 stuck in the sewers.

*Full write-up: `docs/explore_architectures.md`.*
