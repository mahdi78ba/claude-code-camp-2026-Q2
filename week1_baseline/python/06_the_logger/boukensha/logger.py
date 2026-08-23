"""Records each agent run as structured JSON Lines.

Python port of Boukensha::Logger. A file logger, not user-facing display
output: one JSONL file per session under `.boukensha/sessions/`, one JSON
object per line (`session_id`, `at`, `phase`, plus phase-specific data).
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from . import backends
from . import get_config, is_debug

DEFAULT_SESSION_DIR = "sessions"


class Logger:
    def __init__(self, *, session_id=None, dir=None, log=None, snapshot=None):
        self.session_id = session_id or self._generate_session_id()
        self.path = Path(log) if log else Path(dir or self._default_dir()) / f"{self.session_id}.jsonl"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._log_io = open(self.path, "a", encoding="utf-8")
        self._write_log({"phase": "session_start", **(snapshot or {})})

    def iteration(self, *, n, max):
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, *, kind, n, max):
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, *, reason, iterations, tokens=None):
        self._write_log(
            {"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens}
        )

    def prompt(self, *, messages, tools):
        self._write_log(
            {
                "phase": "prompt",
                "message_count": len(messages),
                "messages": [self._serialize_message(m) for m in messages],
                "tool_count": len(tools),
                "tools": list(tools.keys()),
            }
        )

    def tool_call(self, *, name, args):
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, *, name, result, ok=True, error=None):
        self._write_log(
            {"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error}
        )

    def response(self, *, text, usage=None, stop_reason=None, task=None, backend=None):
        event = {
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        }
        event.update(self._execution_metadata(task=task, backend=backend, usage=usage))
        self._write_log(event)

    def raw(self, *, data):
        if not is_debug():
            return

        self._write_log({"phase": "raw", "data": data})

    def close(self):
        if self._log_io:
            self._log_io.close()

    # ---------- private -----------------------------------------------

    def _default_dir(self):
        return Path(get_config().dir) / DEFAULT_SESSION_DIR

    def _write_log(self, event):
        line = {**event, "session_id": self.session_id, "at": self._now_iso()}
        self._log_io.write(json.dumps(line) + "\n")
        self._log_io.flush()

    @staticmethod
    def _now_iso():
        return datetime.now().astimezone().isoformat()

    @staticmethod
    def _generate_session_id():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}-{secrets.token_hex(4)}"

    @staticmethod
    def _serialize_message(msg):
        return {"role": msg.role, "content": msg.content}

    def _execution_metadata(self, *, task, backend, usage):
        if not (task or backend or usage):
            return {}

        tokens = self._usage_tokens(usage)
        metadata = {
            "task": self._task_name(task),
            "provider": self._provider_name(backend),
            "model": getattr(backend, "model", None) if backend else None,
            "usage_unit": getattr(backend, "usage_unit", None) if backend else None,
            "usage_level": getattr(backend, "usage_level", None) if backend else None,
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _task_name(task):
        if task is None:
            return None
        if hasattr(task, "task_name"):
            return task.task_name()
        return str(task)

    @staticmethod
    def _provider_name(backend):
        if backend is None:
            return None
        # OpenAI's trailing acronym doesn't snake_case cleanly (the generic
        # regex below would yield "open_ai"), so special-case it to match
        # the "openai" provider string used in settings.yaml / config.py.
        if isinstance(backend, backends.OpenAI):
            return "openai"

        name = type(backend).__name__
        result = []
        for i, ch in enumerate(name):
            if i > 0 and ch.isupper() and name[i - 1].islower():
                result.append("_")
            result.append(ch)
        return "".join(result).lower()

    @staticmethod
    def _usage_tokens(usage):
        usage = usage or {}
        return {
            "input": Logger._first_integer(
                usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"
            ),
            "output": Logger._first_integer(
                usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"
            ),
        }

    @staticmethod
    def _first_integer(data, *keys):
        for key in keys:
            value = data.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _estimate_cost(backend, tokens):
        if backend is None or not hasattr(backend, "estimate_cost"):
            return None
        if tokens["input"] is None or tokens["output"] is None:
            return None

        return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])
