"""Boukensha Step 7: The Run DSL — Python port smoke test."""

import os
import sys
from pathlib import Path

# Make the package importable when run directly (examples/ is a sibling of
# the boukensha/ package inside this lesson folder).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boukensha  # noqa: E402

# Config is loaded automatically inside boukensha.run() — system prompt,
# model, and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by
# default. You can still override any of them as keyword arguments if you
# want.
# Override the config directory so the example works from the repo.
# In real usage a user's ~/.boukensha is picked up automatically.
repo_root = Path(__file__).resolve().parents[4]
os.environ.setdefault("BOUKENSHA_DIR", str(repo_root / ".boukensha"))

print("=== Boukensha Step 7: The Run DSL ===")
print()
print(f"Config: {boukensha.get_config()}")
print()

base_dir = Path(__file__).resolve().parent.parent


def configure(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
        block=lambda path: (base_dir / path).read_text(),
    )

    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
        block=lambda path: ", ".join(
            f.name for f in (base_dir / path).iterdir() if not f.name.startswith(".")
        ),
    )


result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    configure=configure,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
