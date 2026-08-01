# Architecture Exploration

Week 0 asks one question in two experiments: **what does it actually take for an
AI agent to play a live MUD reliably?** Architecture 1 tries the simplest thing
(a plain agent) and watches it fail; Architecture 2 gives the agent a reusable
Skill and sees how much further it gets — and where it still breaks.

---

# Architecture 1 — Plain Agent

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

Run 4 (fresh memory + real mortal character) is the most honest test.

### Run 4 blow-by-blow (Haiku, mortal)

- Tried `nc`, then `telnet` — neither gave it a usable interactive session.
- Wrote a **Python script** to drive the connection (58 lines), then **rewrote it
  again and again** as each new obstacle appeared: login confirmation → character
  name → entering the game → exploring → world-mapping → re-navigating → handling
  duplicate room names. That is **~11 rewrites**, each script growing.
- Mid-task it wandered off to **search the parent folder for `CHALLENGES.md`** —
  unrelated to the immediate goal.
- It **misread the world**: *"there are multiple Main Streets!"* Several rooms
  share the name "Main Street", and it had no reliable way to tell them apart.
- After ~5m 47s it reached the bakery and pulled the menu.

### A sharp detail: the "menu" is not a fixed fact

The live prices differed between runs — the immortal saw danish **5** / bread
**11** / waybread **56**; the mortal warrior saw **7 / 15 / 76**. CircleMUD
adjusts shop prices to the *character* (charisma/level). The true answer only
comes from playing as the actual character — which is exactly what reading static
files cannot give you.

## Technical observations

- **It struggled to connect and log in** — cycling through `nc`, `telnet`, then
  hand-written Python, discovering the login flow by trial and error.
- **It created temporary code to manage the connection** — and kept
  **regenerating** it (~11 rewrites; ~280 lines in the Sonnet run). Almost all
  effort went into building a throwaway client rather than playing.
- **It lacked knowledge of the MUD's text interface,** so it could not recover
  cleanly from login problems and got confused by repeated room names.
- **It read files unrelated to the task** (searched for `CHALLENGES.md`; read the
  world data files to get the answer without playing).
- **A stronger model did not fix the problems.** Haiku and Sonnet hit the same
  wall; Sonnet only "won" by abusing immortal `goto`. The limit is structural.

## Why this happens — the root cause

Playing a MUD needs **one long-lived, interactive session**: open a socket, send a
command, read the reply, decide, send the next — over the *same* connection.

A coding harness's shell tool runs **one-shot processes**: each command starts,
runs, and exits. It cannot hold a session open between reasoning turns. So the
agent writes a **batch script** that reconnects, re-logs-in, **replays the whole
path**, and appends one action — then runs it blind. That is why the scripts kept
growing and why it was so fragile.

## Technical conclusions

- A **fixed login process should live in a reusable script**, not be regenerated
  every run.
- **Coding harnesses can drift off task** and write unnecessary code.
- A **dedicated MUD SDK / manager** would give a reliable connect/send/read
  interface, so the agent never re-implements the plumbing.
- An **MCP server** could expose that interface to a harness as clean tools.
- **Markdown files alone may be insufficient** for complex state — they go stale
  (cache-parrot) and are too ambiguous for structured data (the room graph).

## Key takeaway

**Use coding harnesses for coding tasks.** For a specialized *operational* agent,
build a **dedicated agent loop** and a **reusable interface**: connection, login,
and command I/O should be solved once by real infrastructure, leaving the model
free to focus on *decisions* — not plumbing.

---

# Architecture 2 — Agent Skills driven by main agent

## The experiment

Give the main agent a reusable **Agent Skill** (`play-mud`) — a script + documented
know-how + memory files — and see whether it can now connect and play, and how far
it scales from simple goals to long ones.

- **Location:** `week0_explore/explore_architecture/02_agent_skills`
- **The skill:** `.claude/skills/play-mud/` containing
  - `SKILL.md` — instructions the main agent reads: login flow, the memory loop,
    and rules.
  - `scripts/mud.py` — the connection engine.
  - `data/player.md` + `data/world.md` — persistent memory.
- **Built with** the official Skill Creator.
- **Goals tested:** simple (bakery menu), two-step (guild + practice kick), and a
  long multi-stage goal (defeat the Massive Minotaur).

## What the skill contains / what we built

- **`SKILL.md`** — makes the main agent auto-discover the skill; documents the exact
  login flow (`dummy` → `helloworld` → *PRESS RETURN* → menu `1`), the
  read → observe → act → update loop, and rules (the game is the source of truth;
  disambiguate duplicate room names by their exits; keep memory terse).
- **`scripts/mud.py`** — began as an interactive REPL the agent *couldn't* drive, so
  it kept writing throwaway scripts. We upgraded it to **batch execution**
  (`python3 scripts/mud.py --cmds "look;score;n"`) with **auto-login**, **telnet
  negotiation handling** (answering the *"Attempting to Detect Client"* IAC
  sequence), and a read loop that **waits through the ~20s first-input delay**.
- **`data/*.md`** — structured memory: identity/stats/equipment/goals, and rooms by
  name + exits, routes as command strings, unexplored leads, and survival notes.

## What we observed (run history)

| Goal | Model | Outcome | Notes |
|---|---|---|---|
| Bakery menu | Sonnet | ✅ clean | connected, navigated, listed the menu; ~5 min, ~1 script |
| Guild + practice (immortal) | Haiku | ❌ | Docker re-seed → immortal character; **31 min, 10 scripts**; misread it as "the server seeds immortals" |
| Guild + practice (real `dummy`) | Haiku | ⚠️ partial | connected as the real warrior but **described** the task instead of doing it (info shortcut) |
| Walk to guild, practice kick | Haiku | ✅ but heavy | actually practiced (*"You practice for a while…"*); **7 scripts**, ~3 min |
| Re-ask (same session) | Haiku | ❌ parrot | 9-second cached summary — stale answer lived in the **session**, not just the files |
| Re-ask after `/clear` | Haiku | ✅ target hit | fresh session forced a real check → **"kick already learned, 0 practice sessions"** |
| Defeat the Minotaur (long goal) | Sonnet | ❌ *by design* | backtracked in the sewers, fixated on the target room, then **asked the user what to do** instead of adapting |

## Technical observations

- **The skill reliably connects and plays** — once the transport was real (batch
  mode + auto-login + telnet handling), simple goals complete, even with Haiku.
- **The transport had to be genuine.** As a REPL, the agent couldn't drive it and
  wrote 6–10 throwaway scripts per run; batch execution removed most of that.
- **Caching lives in two places.** Stale answers came from the markdown files
  *and* the agent's session memory — clearing the files wasn't enough; a `/clear`
  (fresh session) was required for an honest run.
- **Markdown lacks identity.** Duplicate room names (two "Watery Sewers", three
  "Dark Passageways") silently corrupt a name-keyed map. We now key by name +
  exits, but a **vnum / DB key** is the real fix, and the routes table grows
  quadratically as the map expands.
- **Long goals expose the ceiling.** On the Minotaur goal the agent backtracked
  repeatedly, fixated on the final room, gave little visibility into
  movement/cost/reasoning, updated memory in bursts (hard to watch live), and
  ultimately **punted the decision to the user** — its reasoning was sound (dying
  is a free reset for a naked level-1), but it would not **commit autonomously**.
- **Weak vs. strong model:** with a not-fully-turnkey skill, Haiku thrashed far
  more than Sonnet. A good interface **narrows** the model gap; a rough one
  **widens** it.

## Technical conclusions

- Agent Skills can **reliably connect to and play** the MUD.
- **Simple goals** can be completed using **Haiku 4.5**.
- **More complex state, world, and player management is still required** (identity
  keys / a real store, not just markdown).
- The agent needs **better observability** — token usage and its current journey
  (route, cost, position, reasoning).
- A **custom agentic loop** would provide more control over execution, planning,
  and memory.
- The agent should use a **configurable player persona** — including risk and
  exploration preferences.
- **Goals should be decomposed into a visible plan** before execution.

## Key takeaway

**Agent Skills improve connection reliability, but a custom agent loop is still
needed** for adaptive planning, scalable memory, observability, and long-running
gameplay.
