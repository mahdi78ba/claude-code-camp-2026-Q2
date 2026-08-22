"""Boukensha Step 2: Tool Registry — Python port smoke test."""

import os
import sys
from pathlib import Path

# Make the package importable when run directly (examples/ is a sibling of
# the boukensha/ package inside this lesson folder).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boukensha import Config, Context, Registry, UnknownToolError  # noqa: E402
from boukensha.tasks import Player  # noqa: E402

# Override the config directory so the example works from the repo.
# In real usage a user's ~/.boukensha is picked up automatically.
repo_root = Path(__file__).resolve().parents[4]
os.environ.setdefault("BOUKENSHA_DIR", str(repo_root / ".boukensha"))

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings, user_prompts_dir=config.user_prompts_dir
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

# Notice that we now register the tools through the registry instead of
# directly on the context, as the previous step did. They will still be
# attached to context, which is why we pass it into the registry when we
# construct it.
registry.tool(
    "move",
    description="Move the player in a direction (north, south, east, west, up, down)",
    parameters={"direction": {"type": "string"}},
    block=lambda direction: f"You move {direction} into a torch-lit corridor.",
)

registry.tool(
    "shout",
    description="Shout a message so everyone in the zone can hear it",
    parameters={"message": {"type": "string"}},
    block=lambda message: message.upper(),
)

print("=== Boukensha Step 2: Tool Registry ===")
print()
print(f"Config:  {config}")
print(f"Context: {ctx}")
print("Tools:")
for t in ctx.tools.values():
    print(f"  {t}")
print()

# Here we are mimicking what the agent would do when it needs to call a
# tool from the registry. We are still missing the actual code that would
# decide when to call the registry for a tool.
print("Dispatching 'shout' with message='dragon spotted'...")
result = registry.dispatch("shout", {"message": "dragon spotted"})
print(f"Result: {result}")
print()

print("Dispatching 'move' with direction='north'...")
result = registry.dispatch("move", {"direction": "north"})
print(f"Result: {result}")
print()

try:
    registry.dispatch("flee")
except UnknownToolError as e:
    print(f"UnknownToolError caught: {e}")
