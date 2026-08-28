"""Boukensha configuration loader.

Python port of the Ruby reference (week1_baseline/ruby/00_config).

The .boukensha config directory is resolved in this order:
  1. BOUKENSHA_DIR environment variable (set before loading .env)
  2. .boukensha in the current working directory
  3. ~/.boukensha  (default location for a real install)
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


class Config:
    # Default location for a real install.
    DEFAULT_DIR = str(Path.home() / ".boukensha")

    # Default prompts shipped alongside the library code.
    # This file lives at <lesson>/boukensha/config.py, so the shipped
    # prompts directory is <lesson>/prompts.
    PROMPTS_DIR = str(Path(__file__).resolve().parent.parent / "prompts")

    def __init__(self) -> None:
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings = self._load_settings()

    # ---------- tasks -----------------------------------------------------

    def tasks(self, name=None):
        """No argument: the full tasks dict from settings.yaml.

        With a name: that task's settings dict, e.g. tasks("player").
        """
        all_tasks = self.dig("tasks") or {}
        if name is None:
            return all_tasks
        return all_tasks.get(str(name))

    @property
    def user_prompts_dir(self) -> str:
        """The user's prompts directory for task prompt overrides."""
        return str(Path(self.dir) / "prompts")

    # ---------- MCP servers -------------------------------------------------

    def mcp_servers(self):
        """[{name, command, env, prefix}, ...] from settings.yaml's
        mcp_servers: list. An env value of the literal form "$VAR" resolves
        against os.environ (already populated from .env by _load_env)
        instead of being taken as a literal string — settings.yaml is
        commit-safe, so a real credential should never have to sit in it as
        plaintext just because this is the only place to configure an MCP
        server's connection details.
        """
        entries = self.dig("mcp_servers") or []
        return [
            {
                "name": entry.get("name"),
                "command": entry.get("command") or [],
                "env": self._resolve_env(entry.get("env") or {}),
                "prefix": entry.get("prefix"),
            }
            for entry in entries
        ]

    # ---------- low-level helpers -----------------------------------------

    def dig(self, *keys):
        """Fetch a nested key path from settings, e.g. dig("mud", "host")."""
        node = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(str(key))
            else:
                return None
        return node

    def __str__(self) -> str:
        return (
            f"#<Boukensha::Config dir={self.dir} "
            f"tasks={','.join(self.tasks().keys())}>"
        )

    __repr__ = __str__

    # ---------- private ---------------------------------------------------

    def _resolve_dir(self) -> str:
        # 1. Explicit override
        env_dir = os.environ.get("BOUKENSHA_DIR")
        if env_dir:
            return str(Path(env_dir).expanduser().resolve())

        # 2. .boukensha in the current working directory
        cwd_dir = Path.cwd() / ".boukensha"
        if cwd_dir.is_dir():
            return str(cwd_dir)

        # 3. ~/.boukensha default
        return str(Path(self.DEFAULT_DIR).expanduser().resolve())

    def _load_env(self) -> None:
        env_file = Path(self.dir) / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self) -> dict:
        settings_file = Path(self.dir) / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}

    def _resolve_env(self, raw: dict) -> dict:
        return {
            k: (os.environ.get(v[1:]) if isinstance(v, str) and v.startswith("$") else v)
            for k, v in raw.items()
        }
