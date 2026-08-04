#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["claude-agent-sdk"]
# ///
"""
Architecture 3B: PlayMUD registered as a Claude Agent SDK sub-agent.

Unlike Architecture 3A, the sub-agent is not a Markdown file under
`.claude/agents/` that Claude Code discovers on the filesystem at startup.
Here it is registered programmatically via `ClaudeAgentOptions.agents`, using
an `AgentDefinition` built in code. The prompt text itself still lives in a
Markdown file (`agents/play-mud.md` / `agents/play-mud-smarty.md`) for
readability, but this driver reads it explicitly — nothing is auto-discovered.

The top-level `query()` call is a thin orchestrator: it is only allowed the
`Agent` tool (the CLI's sub-agent dispatch tool, which takes a
`subagent_type` matching a key of `ClaudeAgentOptions.agents`), so the only
thing it can do is dispatch to the registered `play-mud` / `play-mud-smarty`
sub-agent, which is where `Bash`/`Read`/`Edit` actually run.

Usage:
    ./scripts/run_agent.py                                    # interactive prompt
    ./scripts/run_agent.py --character smarty                 # interactive, as Smarty
    ./scripts/run_agent.py --goal "Find the bakery and list the menu."
    ./scripts/run_agent.py --character both --goal "Report your current status and location."
"""

import argparse
import asyncio
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import AgentDefinition, AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

PROJECT_ROOT = Path(__file__).parent.parent
PROMPT_DIR = PROJECT_ROOT / "agents"

AGENT_SPECS = {
    "play-mud": {
        "prompt_file": "play-mud.md",
        "description": (
            "Play the CircleMUD/tbaMUD server as dummy, the mortal Warrior, "
            "keeping persistent memory in data/player.md and data/world.md."
        ),
    },
    "play-mud-smarty": {
        "prompt_file": "play-mud-smarty.md",
        "description": (
            "Play the CircleMUD/tbaMUD server as Smarty, the mortal Mage, "
            "keeping persistent memory in data/player-smarty.md and data/world-smarty.md."
        ),
    },
}

CHARACTER_TO_AGENT = {"dummy": "play-mud", "smarty": "play-mud-smarty"}


def load_agent_definitions() -> dict[str, AgentDefinition]:
    """Build AgentDefinitions from prompt files under agents/ — read explicitly,
    not discovered by scanning a directory the way Claude Code loads .claude/agents/*.md."""
    definitions = {}
    for agent_name, spec in AGENT_SPECS.items():
        prompt_text = (PROMPT_DIR / spec["prompt_file"]).read_text()
        definitions[agent_name] = AgentDefinition(
            description=spec["description"],
            prompt=prompt_text,
            tools=["Bash", "Read", "Edit"],
            model="sonnet",
        )
    return definitions


async def dispatch(agent_name: str, goal: str) -> str:
    options = ClaudeAgentOptions(
        agents=load_agent_definitions(),
        allowed_tools=["Agent"],
        permission_mode="bypassPermissions",
        cwd=str(PROJECT_ROOT),
        model="sonnet",
    )

    orchestrator_prompt = f"Use the `{agent_name}` sub-agent to accomplish this goal: {goal}"

    prefix = f"[{agent_name}]"
    summary = ""

    async for message in query(prompt=orchestrator_prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"{prefix} {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"{prefix} -> {block.name}({block.input})")
        elif isinstance(message, ResultMessage):
            summary = message.result or ""
            print(f"{prefix} === done ({message.subtype}) ===")

    return summary


async def run_goal(character_key: str, goal: str) -> None:
    if character_key == "both":
        results = await asyncio.gather(
            dispatch("play-mud", goal),
            dispatch("play-mud-smarty", goal),
        )
        for agent_name, summary in zip(("play-mud", "play-mud-smarty"), results):
            print(f"\n--- Summary [{agent_name}] ---\n{summary}")
    else:
        agent_name = CHARACTER_TO_AGENT[character_key]
        summary = await dispatch(agent_name, goal)
        print(f"\n--- Summary [{agent_name}] ---\n{summary}")


async def interactive_loop(character_key: str) -> None:
    agent_label = "play-mud + play-mud-smarty" if character_key == "both" else CHARACTER_TO_AGENT[character_key]
    print("PlayMUD Agent Driver (Claude Agent SDK)")
    print(f"Character: {character_key}  |  Sub-agent: {agent_label}")
    print("Type a goal for the agent, or 'quit' to exit.\n")

    while True:
        try:
            goal = input("> ").strip()
        except EOFError:
            print()
            break

        if not goal:
            continue
        if goal.lower() in ("quit", "exit"):
            break

        await run_goal(character_key, goal)
        print()

    print("Goodbye.")


def main() -> None:
    parser = argparse.ArgumentParser(description="PlayMUD sub-agent, registered via the Claude Agent SDK")
    parser.add_argument("--character", choices=["dummy", "smarty", "both"], default="dummy")
    parser.add_argument(
        "--goal",
        help="Single-shot goal to give the agent. Omit to start an interactive prompt instead.",
    )
    args = parser.parse_args()

    if args.goal:
        asyncio.run(run_goal(args.character, args.goal))
    else:
        asyncio.run(interactive_loop(args.character))


if __name__ == "__main__":
    main()
