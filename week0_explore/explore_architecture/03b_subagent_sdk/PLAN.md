# PLAN — Architecture 3B: Sub-agent via Claude Agent SDK

## Goal

Replace the **filesystem sub-agent** used in Architecture 3A — a Markdown file
under `.claude/agents/` that Claude Code auto-discovers at startup and
dispatches to via its own Agent tool — with an equivalent implemented as a
**standalone program using the Claude Agent SDK** (`claude-agent-sdk`, Python).
The program defines the agent's system prompt, tools, and orchestration in
code and drives it via `query()`, independent of Claude Code's own subagent
discovery/dispatch mechanism.

This directory (`03b_subagent_sdk`) currently starts as an exact copy of
`03a_subagent_sdk`. This plan converts it into the SDK-based version while
`03a_subagent_sdk` remains untouched as the baseline for comparison.

## What stays the same

- `scripts/mud.py` — the telnet engine (batch mode, auto-login, IAC
  negotiation handling). Unchanged.
- `data/player.md`, `data/world.md`, `data/player-smarty.md`,
  `data/world-smarty.md` — the persistent memory files. Unchanged, same
  contract (read before acting, update before ending the turn).
- The **content** of the current sub-agent instructions (login table,
  connection quirks, the read → observe → act → update loop, "the game is the
  source of truth" rules) — carried over verbatim into a system prompt built
  in code, not lost in the migration.
- Two independent characters/personas: `dummy` (Warrior) and `Smarty` (Mage),
  each with their own memory files — same isolation model as 3A.

## What changes

1. **Remove** `.claude/agents/play-mud.md` and
   `.claude/agents/play-mud-smarty.md` — no longer discovered or dispatched by
   Claude Code.
2. **Remove** `.claude/settings.json` — its `allow` list exists to pre-approve
   Claude Code's own permission prompts; the SDK program instead sets
   `allowed_tools` / `permission_mode` directly in code, so this file has no
   remaining purpose here.
3. **Add** `pyproject.toml` (managed with `uv`) declaring the
   `claude-agent-sdk` dependency (requires Python ≥3.10; this repo has 3.13).
4. **Add** `agents/play_mud_agent.py` — the new standalone program.

## New program design (`agents/play_mud_agent.py`)

- A small `CHARACTERS` table mirroring the two existing sub-agent files:

  | key      | name     | password     | player file             | world file              |
  |----------|----------|--------------|--------------------------|--------------------------|
  | `dummy`  | dummy    | helloworld   | `data/player.md`         | `data/world.md`          |
  | `smarty` | Smarty   | helloworld   | `data/player-smarty.md`  | `data/world-smarty.md`   |

- `build_system_prompt(character)` — reproduces the login flow, connection
  quirks, memory loop, and rules from the current `.md` sub-agent bodies,
  parameterized per character so one function serves both.
- `run_character(character, goal) -> str`, using `claude_agent_sdk.query()`:
  - `system_prompt` = the built prompt
  - `allowed_tools=["Bash", "Read", "Edit"]` (matches the existing
    `tools:` frontmatter)
  - `permission_mode="acceptEdits"` (non-interactive batch use)
  - `cwd` = the `03b_subagent_sdk` project root, so relative paths
    (`scripts/mud.py`, `data/*.md`) resolve exactly as they do today
  - `model="sonnet"`
  - Streams every `AssistantMessage`/`TextBlock`/`ToolUseBlock` to stdout as
    it happens, and captures `ResultMessage.result` as the returned summary.
    This directly addresses the observability gap noted in Architecture 3A
    ("only a summary returns... cannot watch the play unfold step by step") —
    since we own the loop here, we get live visibility for free.
- `main()` — CLI via `argparse`: `--character {dummy,smarty,both}` and
  `--goal "..."`. `--character both` runs
  `asyncio.gather(run_character(dummy_cfg, goal), run_character(smarty_cfg, goal))`
  for genuine concurrent play — replacing 3A's approach of manually invoking
  two separate Task-tool dispatches from the main agent.

## Verification steps

1. `uv sync` in `03b_subagent_sdk/` to install `claude-agent-sdk`.
2. Confirm the MUD server is reachable at `localhost:4000` (already confirmed
   up as of this writing).
3. Single-character dry run, e.g.:
   `uv run agents/play_mud_agent.py --character dummy --goal "Check your current status and location, then report back."`
   — verify login succeeds, `mud.py` is invoked via Bash exactly as before,
   and `data/player.md` / `data/world.md` get updated.
4. Concurrency run:
   `uv run agents/play_mud_agent.py --character both --goal "..."`
   — verify both sessions run side by side without cross-touching the other
   character's data files (same isolation guarantee 3A demonstrated, now via
   `asyncio.gather` instead of two Task dispatches).

## Out of scope

- `03a_subagent_sdk` and the other architecture folders are not touched —
  this migration is scoped to `03b_subagent_sdk` only.
- Updating `docs/explore_architectures.md` with an "Architecture 3B"
  write-up is **not** included in this plan by default — that doc records
  *observed* behavior from real runs (per its existing pattern for 1, 2, and
  3A), so I'll propose that as a follow-up after step 3/4 produce real output,
  rather than writing it speculatively now.
