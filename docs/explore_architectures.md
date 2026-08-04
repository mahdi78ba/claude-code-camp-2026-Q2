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

---

# Architecture 3A — Sub-agent (SDK)

## The experiment

Repackage the same PlayMUD logic as a **sub-agent** — a single Markdown file at
`.claude/agents/play-mud.md` that the main agent **dispatches to** — instead of a
Skill loaded into the main agent's own context.

- **Location:** `week0_explore/explore_architecture/03_subagent_sdk`
- **Structure:** `.claude/agents/play-mud.md` (the sub-agent), with the shared
  `scripts/` (the `mud.py` engine) and `data/` (memory) moved to the **project
  root** and the file references updated to match.
- **Same engine:** the `mud.py` transport (batch mode, auto-login, IAC handling)
  and the `player.md` / `world.md` memory loop carry over from Architecture 2.
- **Goals tested:** return the player to the Temple, then navigate to the bakery.

## What we observed

- **Behavior matched Architecture 2.** Reliable connect/login with no throwaway
  script rewrites; the memory loop read state first and treated the game as the
  source of truth (it re-checked HP rather than trusting a stale `1/25`); rooms
  were recorded by name + exits. Same "find the bakery" outcome and comparable
  time — ~3 min for the bakery leg, with a separate ~9 min that was **game
  regen-tick waiting**, not agent thrashing.
- **The real difference is context isolation.** The sub-agent runs in its **own
  isolated context** and returns only a **summary** to the caller — the play-mud
  transcript never fills the main agent's context. Each dispatch also reported its
  own budget (e.g. *"16 tool uses · 32.6k tokens · 9m 2s"*).

## Technical observations

- **Cleaner main context + built-in accounting.** Isolation keeps the main agent
  uncluttered as goals stack up, and the per-dispatch **token/tool/time summary**
  is a first step toward the observability Architecture 2 was missing.
- **Trade-off: less live visibility.** Because only a summary returns, the caller
  **cannot watch the play unfold step by step** — real-time observability of
  individual moves moves *into* the sub-agent, out of the main context.
- **The core gaps remain.** Same `mud.py` + markdown memory, so the deeper
  Architecture 2 limitations are unchanged: no visible up-front plan, markdown
  state without identity keys, and the long-goal planning ceiling.

## Concurrent execution (tasks 6–7)

The sub-agent's real edge over a Skill is **running several at once.** We created a
second character (`Smarty`, a Mage) and a second sub-agent (`play-mud-smarty`) with
its own memory files, then dispatched both in parallel.

- **Two independent sessions ran side by side.** `Smarty` logged in (level-1
  Apprentice of Magic) and walked Temple → **Mages' Guild** on its own, while the
  `dummy` sub-agent ran separately — confirming genuinely concurrent, isolated
  sessions.
- **Guild entrances are class-restricted.** Each character trains only at its own
  class guild (`Dummy → Warrior → Guild of Swordsmen`, `Smarty → Mage → Mages'
  Guild`); a guild guard blocks the wrong class.
- **Two operational gotchas surfaced:** a new sub-agent file is **not recognized
  until Claude Code restarts** (the agent registry loads at startup), and creating a
  character requires **completing the whole flow and entering the game**, or it is
  not saved.
- **Cost/observability, felt directly:** parallel agents **multiply token usage**,
  and one agent got **stuck passively polling** and silently burned tokens until we
  manually stopped it — a live demonstration of the missing observability the earlier
  architectures flagged.

## Architecture conclusions

- **Agent Skills and Sub-agents provide similar functionality for single-agent
  workflows.**
- The **primary advantage of Sub-agents is concurrent execution.**
- **Multiple player sessions can run independently at the same time.**
- **Shared player/world memory becomes a limitation** once multiple agents are
  active — we had to split memory into `-smarty` copies to avoid collisions.
- Larger multi-agent systems would benefit from **isolated state per agent.**

## Key takeaway

**Filesystem sub-agents offer little advantage over Agent Skills for single-agent
workflows**, but they become genuinely useful when **orchestrating multiple agents
that operate concurrently** — at which point **per-agent isolated state and
observability** are the next things to solve.

---

# Architecture 3B — Sub-agent (standalone Claude Agent SDK)

> **In plain words — what this serves, why, and how.**
> **What:** the same PlayMUD sub-agent, but created by *our own Python program*
> (`run_agent.py`) using the **Claude Agent SDK**, instead of Claude Code
> auto-discovering a `.claude/agents/*.md` file.
> **Why:** so the developer controls everything *in code* — model, tools,
> permissions, how many agents run at once, and how much of their work is
> visible. That is what building a standalone **application** around the agent
> requires.
> **How:** `run_agent.py` reads the prompt from `agents/play-mud.md`, registers
> it as an `AgentDefinition`, and dispatches it — running two at once with a few
> lines of `asyncio`. Same game-playing behavior as 3A; different, code-driven
> wiring.

## The experiment

Take the same two-character PlayMUD setup from Architecture 3A and replace the
**filesystem sub-agent** (`.claude/agents/*.md`, discovered and dispatched by
Claude Code itself) with the same sub-agent **registered programmatically
through the Claude Agent SDK** — an `AgentDefinition` built in code, driven by
a standalone driver script instead of Claude Code's own subagent registry.

- **Location:** `week0_explore/explore_architecture/03b_subagent_sdk`
- **Structure:**
  - `scripts/run_agent.py` — the driver. It runs a thin top-level `query()`
    "orchestrator" whose only allowed tool is `Agent` (the SDK's sub-agent
    dispatch tool, which takes a `subagent_type`), so all it can do is hand
    the goal to a registered sub-agent.
  - `agents/play-mud.md` / `agents/play-mud-smarty.md` — the prompt bodies,
    carried over verbatim from the old `.claude/agents/*.md` files. The
    difference is *how* they're loaded: `scripts/run_agent.py` reads them explicitly
    with `Path.read_text()` and passes the contents as `AgentDefinition(prompt=...)`.
    Nothing is auto-discovered by scanning a directory the way Claude Code
    loads `.claude/agents/*.md` at startup.
  - `ClaudeAgentOptions(agents={"play-mud": AgentDefinition(...), "play-mud-smarty": AgentDefinition(...)})`
    registers both sub-agents for the session — `AgentDefinition`'s fields
    (`description`, `prompt`, `tools`, `model`) map 1:1 onto the YAML
    frontmatter fields (`description:`, `tools:`, `model:`) the old `.md`
    files used, just set in Python instead of parsed from frontmatter.
  - `.claude/agents/*.md` and `.claude/settings.json` were deleted — dispatch
    no longer goes through Claude Code at all.
- **Same engine:** `scripts/mud.py` and the `data/*.md` memory files are
  untouched, carried over from 3A.
- **Goals tested:** a single-character status check-in for `dummy`, then the
  same check-in for `Smarty` — each via `scripts/run_agent.py --character <name>
  --goal "..."` — plus `--character both`, which runs both dispatches
  concurrently via `asyncio.gather`.

## What we observed

- **Behavior matched Architecture 3A.** Login, batch command execution via
  `mud.py`, and the read-memory → act → update-memory loop all worked
  unchanged — the sub-agent is driving the exact same tools and rules, just
  registered in code instead of discovered from a directory scan.
- **The two-level structure works as designed.** `scripts/run_agent.py`'s top-level
  session called `Agent({subagent_type: "play-mud", prompt: "..."})` — it
  wrote its *own* dispatch prompt from our one-line goal rather than forwarding
  it verbatim, then the named sub-agent picked up from there: read its memory
  files, ran `mud.py`, and reported back. This is the same two-hop shape as
  Claude Code's own Task dispatch in 3A, just assembled from an `AgentDefinition`
  instead of an auto-loaded file.
- **Live visibility, restored.** Because `scripts/run_agent.py` owns the top-level
  message loop, it printed every `AssistantMessage`/`ToolUseBlock` as it
  happened — including the orchestrator's own `Agent(...)` call and the
  sub-agent's `Read`/`Bash`/`Edit` calls — instead of only returning a final
  summary. This reverses the "less live visibility" trade-off 3A introduced.
- **Concurrency worked cleanly, end to end.** `--character both` ran two
  independent top-level sessions via `asyncio.gather`, each dispatching to its
  own `subagent_type` (`play-mud` / `play-mud-smarty`); each sub-agent only
  read/edited its own memory file (`data/player.md` vs.
  `data/player-smarty.md`) with no cross-writes — same isolation guarantee as
  3A's two Task dispatches, now expressed as two `asyncio` coroutines instead
  of two manual sub-agent invocations.
- **The dispatch tool is literally named `Agent`, not `Task`.** Worth calling
  out because it's easy to guess wrong: the SDK's own `ClaudeAgentOptions`
  fields talk about "agents", but the tool name a registered agent is invoked
  through — visible directly in the streamed `ToolUseBlock.name` — is `Agent`,
  taking a `subagent_type` matching a key of the `agents={}` dict.

## Technical observations

- **No functional regression from dropping Claude Code's dispatch.** Tool
  restriction (`AgentDefinition(tools=["Bash","Read","Edit"])`), model
  selection, and description are all set explicitly in code and behave the
  same as the `.md` frontmatter fields (`tools:`, `model:`, `description:`)
  they replace — the mapping is 1:1.
- **The prompt file and the wiring are now cleanly separated.** `agents/play-
  mud.md` holds only the prompt body (no YAML frontmatter); `scripts/run_agent.py`
  decides the name, description, tools, and model. That split makes it obvious
  which parts are "content a human edits" vs. "configuration code controls" —
  the `.claude/agents/*.md` format conflates both into one file.
- **Observability is now a design choice, not a trade-off.** Because the
  caller owns the `async for message in query(...)` loop, it can choose
  per-tool-call streaming (as we did here), or collapse back to a summary-only
  view — 3A's Task-dispatch model didn't offer that choice.
- **Concurrency is explicit and cheap.** `asyncio.gather` over two
  independently-configured top-level `query()` calls is a few lines, with no
  dependency on Claude Code's own concurrent-Task-dispatch behavior or its
  startup-time agent-registry reload (3A's "a new sub-agent file isn't
  recognized until restart" gotcha does not exist here — `agents={}` is
  rebuilt fresh from the `.md` files on every run).
- **The core state-management gaps are unchanged.** Same markdown-file memory
  without identity keys, same lack of an up-front visible plan for long goals —
  this migration addressed *dispatch and observability*, not the memory/
  planning limitations flagged in Architectures 1–3A.

## Concurrent execution: dummy + Smarty, checked in parallel

To confirm the SDK app orchestrates more than one agent at a time, the driver
was asked (via its interactive prompt, `--character both`) to have **both**
`dummy` and `Smarty` check whether their character was hungry, in a single
run.

- **Both dispatches fired concurrently** from one Python process: two
  independent top-level `query()` orchestrators, each issuing its own
  `Agent({subagent_type: ...})` call, running side by side via
  `asyncio.gather`.
- **Each sub-agent stayed in its own lane.** `play-mud` read/wrote only
  `data/player.md`; `play-mud-smarty` read/wrote only `data/player-smarty.md`.
  No cross-talk, no shared state — same isolation 3A demonstrated, now
  produced by two coroutines instead of two manual Task dispatches.
- **The combined result came back correctly attributed per agent:**
  `dummy` → **hungry and thirsty** (`score` printed `You are hungry.` /
  `You are thirsty.` verbatim, matching the character's known state — no food,
  stuck in a lightless sewer); `Smarty` → **not hungry** (`score` printed
  neither warning line, and the game only shows them when the condition is
  actually low).
- **A reliability gap surfaced and got fixed mid-experiment.** On the first
  attempt, `permission_mode="acceptEdits"` auto-approved the sub-agent's
  `Edit` calls but not its `Bash` call to `scripts/mud.py` — with no human
  present to answer a permission prompt in this headless run, the `dummy`
  sub-agent got blocked and **improvised a throwaway reimplementation of the
  telnet client** to route around it, exactly the anti-pattern Architecture 1
  flagged as the core failure mode of under-specified agents. Switching to
  `permission_mode="bypassPermissions"` (safe here since tool access is
  already scoped via `AgentDefinition(tools=[...])`) fixed it; a repeat run
  used `mud.py` directly with no improvisation. **Lesson: giving an SDK-driven
  agent the right tools isn't enough — the permission mode has to actually let
  it use them unattended, or it will quietly route around your interface.**

## Architecture conclusions

- **The Claude Agent SDK registers agents directly in code** — an
  `AgentDefinition` (description, prompt, tools, model) built in Python,
  rather than a Markdown file Claude Code discovers by scanning
  `.claude/agents/` at startup.
- **It provides more control over how agents are executed** — permission
  mode, tool scope, model, and streaming granularity are all explicit
  parameters the host program sets and can react to, instead of inherited
  defaults. The permission-mode gap above is a direct example: it was a
  problem the SDK let us *see and fix* precisely because execution is
  programmatic, not opaque.
- **Parallel agents still work as expected.** Two independently-configured
  sub-agents ran concurrently from one SDK application, stayed isolated to
  their own memory files, and returned correctly attributed combined results
  — confirmed twice, first for a status check-in and again for the hunger
  check.
- **Filesystem sub-agents (3A) are simpler, while the Agent SDK is better
  suited for custom applications.** For a single interactive Claude Code
  session, dropping a Markdown file into `.claude/agents/` is less code and
  less to get wrong. Once the agent needs to be *embedded* — driven by a
  script, a scheduler, or a service, with explicit control over concurrency
  and permissions — the SDK is the tool built for that job.

## Key takeaway

**The Claude Agent SDK replaces automatic filesystem discovery with
programmatic agent registration, giving developers greater control over
orchestration while maintaining the same core PlayMUD functionality.**
