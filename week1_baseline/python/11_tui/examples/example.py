"""Boukensha Step 10: Tools and MCP — a standard tool library, MUD demo.

Demonstrates boukensha.tools.mcp, which registers gameplay tools by
proxying an MCP server (the mud_manager gem's bundled one, by default).
Connection details come from ~/.boukensha/settings.yaml's mcp_servers:
list by default. Set BOUKENSHA_DIR to point at a different config
directory.
"""

import os
import sys
from pathlib import Path

# Make the package importable when run directly (examples/ is a sibling of
# the boukensha/ package inside this lesson folder).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boukensha  # noqa: E402

# Config is loaded automatically inside boukensha.run() — system prompt,
# model, API key, and mcp_servers all come from ~/.boukensha (or
# BOUKENSHA_DIR) by default.
repo_root = Path(__file__).resolve().parents[4]
os.environ.setdefault("BOUKENSHA_DIR", str(repo_root / ".boukensha"))

cfg = boukensha.get_config()
print(f"Config: {cfg}")
print(f"API key set? {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
print()

boukensha.run(
    task=(
        "Connect to the MUD, look at your surroundings, check your score, "
        "then look at the available exits and tell me what you see."
    ),
    # system/model/api_key all come from config automatically
    working_dir=False,  # no filesystem tools needed for MUD play
    # mcp: comes from config (settings.yaml mcp_servers: list) automatically
)
