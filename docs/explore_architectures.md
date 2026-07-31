# Architecture Exploration — Plain Agent

## The experiment

Can a **plain agent** — Claude Code with only its normal file/shell tools and no
MUD-specific tooling — play the MUD by connecting to the server and completing a
goal on its own?

- **Location:** `week0_explore/explore_architecture/01_plain_agent`
- **Agent instructions (`CLAUDE.md`):** act as a player-journey agent; connect to
  `localhost:4000` as `dummy`/`helloworld`; keep working state in
  `data/player.md` and `data/world.md`; run the loop read → observe → act → update.
- **Goal issued:** `Find the bakery and list the menu.`
- **Models tested:** Haiku 4.5 and Sonnet, both at effort = high.
- **Expected outcome (per bootcamp):** the agent is *not* expected to cleanly
  succeed — the point is to expose the architecture's limits.

## What we actually observed (four runs)

| # | Model | Server | Character | What it did | Time |
|---|-------|--------|-----------|-------------|------|
| 1 | Haiku 4.5 | **down** | — | Couldn't connect; fell back to grep/reading world data files; reported the menu from source. Its own note: *"Not yet in game."* | — |
| 2 | Sonnet | up | — | **Cache hit:** read the state files, saw `✓ COMPLETED`, and repeated the saved answer without playing. | ~7 s |
| 3 | Sonnet | up | **immortal** (blank re-seed) | Wrote ~280 lines of throwaway client code; logged in as the Implementor; used the god command `goto 3009` to **teleport** to the bakery. | ~6.5 min |
| 4 | Haiku 4.5 | up | **mortal warrior** | Wrote **and rewrote** a connection/exploration script ~11 times; got confused by duplicate "Main Street" rooms; eventually navigated to the bakery and ran `list`. | ~5.75 min |

Run 4 (fresh memory + real mortal character) is the most honest test, and it is
worth reading closely.

### Run 4 blow-by-blow (Haiku, mortal)

- Tried `nc`, then `telnet` — neither gave it a usable interactive session.
- Wrote a **Python script** to drive the connection (58 lines), then **rewrote it
  again and again** as each new obstacle appeared: login confirmation (57) →
  character name in the login flow (70) → entering the game (76) → exploring
  (115) → world-mapping (125) → re-navigating (87, 61, 75, 79) → handling
  duplicate room names (111). That is **~11 rewrites**, each script growing.
- Mid-task it wandered off to **search the parent folder for `CHALLENGES.md`** —
  unrelated to the immediate goal.
- It **misread the world**: *"there are multiple Main Streets!"* Several rooms
  share the name "Main Street", and the agent had no reliable way to tell them
  apart.
- After ~5m 47s it reached the bakery and pulled the menu (danish 7, bread 15,
  waybread 76).

### A sharp detail: the "menu" is not a fixed fact

The live prices differed between runs — the immortal saw danish **5** / bread
**11** / waybread **56**; the mortal warrior saw **7 / 15 / 76**. CircleMUD
adjusts shop prices to the *character* (charisma/level). So the menu depends on
**who is asking** — the true answer only comes from playing as the actual
character, which is exactly what reading static files cannot give you.

## Technical observations (Task 4)

- **It struggled to connect and log in.** It cycled through `nc`, `telnet`, and
  then hand-written Python, discovering the login flow by trial and error
  (confirmation prompt, character name, entering the game).
- **It created temporary code to manage the connection and send commands** — and
  kept **regenerating** it (~11 rewrites in the Haiku run; ~280 lines in the
  Sonnet run). Almost all of the agent's effort went into building a throwaway
  client rather than into playing.
- **It lacked knowledge of the MUD's text interface,** so it could not recognize
  or cleanly recover from login problems, and it got confused by repeated room
  names ("multiple Main Streets").
- **It read files unrelated to the assigned task** (searched for `CHALLENGES.md`;
  and in the server-down run it read the world data files to get the answer
  without playing at all).
- **A stronger model did not fix the problems.** Haiku and Sonnet hit the same
  architectural wall; Sonnet only "won" by abusing immortal `goto`. The
  limitation is structural, not a matter of model intelligence.

## Why this happens — the root cause

Playing a MUD needs **one long-lived, interactive session**: open a socket, send
a command, read the reply, decide, send the next — over the *same* connection,
across many steps.

A coding harness's shell tool runs **one-shot processes**: each command starts,
runs, and exits. It cannot hold a telnet session open between the agent's
reasoning turns. So to make progress the agent writes a **batch script** that
reconnects, re-logs-in, **replays the whole path from the start**, and appends one
new action — then runs it blind, reads the output, and guesses the next script.
That is why the scripts kept growing, why the run took ~6 minutes, and why it was
so fragile: the agent cannot truly react turn-by-turn the way live play requires.

## Technical conclusions (Task 5)

- A **fixed login process should live in a reusable script**, not be regenerated
  by the model on every run.
- **Coding harnesses can drift off task** and write unnecessary code (world
  mappers, repeated client rewrites) instead of doing the job.
- A **dedicated MUD SDK / manager** would provide a reliable interface for
  connecting and sending commands, so the agent never re-implements the plumbing.
- An **MCP server** could expose that interface to a coding harness as clean
  tools (e.g. `connect`, `send`, `read`).
- **Markdown files alone may be insufficient** for complex player/world state:
  they go stale (the cache-parrot bug) and are too lossy/ambiguous for structured
  data such as the room graph (the "multiple Main Streets" confusion).

## Key takeaway

**Use coding harnesses for coding tasks.** For a specialized *operational* agent
(one that plays the game), build a **dedicated agent loop** and a **reusable
interface**: connection, login, and command I/O should be solved once by real
infrastructure, leaving the model free to focus on *decisions* — not plumbing.
