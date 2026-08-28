"""Boukensha Step 11: A Terminal UI — interactive launcher.

Launches the interactive REPL: a Textual TUI by default (see
boukensha/tui.py), or the plain print()/input() REPL from step 10 with
--no-tui. Connection details come from ~/.boukensha/settings.yaml's
mcp_servers: list by default. Set BOUKENSHA_DIR to point at a different
config directory.

examples/example.py (the step-10 MUD one-shot demo, using boukensha.run())
is unchanged and still lives alongside this file — this is a separate,
new entry point for the interactive REPL/TUI, not a replacement for it.

    ./bin/python/11_tui              # Textual TUI (default)
    ./bin/python/11_tui --no-tui     # plain REPL
"""

import os
import sys
from pathlib import Path

# Make the package importable when run directly (examples/ is a sibling of
# the boukensha/ package inside this lesson folder).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boukensha  # noqa: E402

# Config is loaded automatically inside boukensha.repl() — system prompt,
# model, API key, and mcp_servers all come from ~/.boukensha (or
# BOUKENSHA_DIR) by default.
repo_root = Path(__file__).resolve().parents[4]
os.environ.setdefault("BOUKENSHA_DIR", str(repo_root / ".boukensha"))

no_tui = "--no-tui" in sys.argv

boukensha.repl(
    tui=not no_tui,
    # system/model/api_key/mcp all come from config automatically
    working_dir=False,  # no filesystem tools needed for MUD play
)
