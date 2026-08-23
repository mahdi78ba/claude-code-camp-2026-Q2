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

    # ---------- MUD connection ---------------------------------------------

    @property
    def mud_host(self):
        value = self.dig("mud", "host")
        return "localhost" if value is None else value

    @property
    def mud_port(self):
        value = self.dig("mud", "port")
        return 4000 if value is None else value

    @property
    def mud_username(self):
        return self.dig("mud", "username")

    @property
    def mud_password(self):
        return self.dig("mud", "password")

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
