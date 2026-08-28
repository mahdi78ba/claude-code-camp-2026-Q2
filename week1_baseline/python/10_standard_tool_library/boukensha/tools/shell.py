"""Command-execution tools, sandboxed to a single working directory.

Python port of Boukensha::Tools::Shell.

Tools registered: run_command.
"""

from __future__ import annotations

import subprocess


def register(registry, *, working_dir, timeout=30, allowed_commands=None):
    root = str(working_dir)
    allowed_note = (
        f" Allowed executables: {', '.join(str(c) for c in allowed_commands)}."
        if allowed_commands else ""
    )

    def oops(msg):
        return f"error: {msg}"

    def run_command(command):
        if allowed_commands is not None:
            executable = command.strip().split()[0] if command.strip() else ""
            allowed = [str(c) for c in allowed_commands]
            if executable not in allowed:
                return oops(
                    f"'{executable}' is not in the allowed-commands list ({', '.join(allowed)})"
                )

        try:
            result = subprocess.run(
                command, shell=True, cwd=root, timeout=timeout,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
        except subprocess.TimeoutExpired:
            return oops(f"command timed out after {timeout}s: {command}")
        except OSError as e:
            return oops(str(e))

        output = result.stdout.decode(errors="replace").strip()
        exit_note = "" if result.returncode == 0 else f"\n[exit {result.returncode}]"
        return f"{output}{exit_note}" if output else f"(no output){exit_note}"

    registry.tool(
        "run_command",
        description=(
            f"Run a shell command inside the working directory and return its combined "
            f"stdout+stderr output. Commands run with a {timeout}-second timeout.{allowed_note}"
        ),
        parameters={
            "command": {
                "type": "string",
                "description": "The shell command to execute (e.g. 'python script.py', 'ls -la', 'git status')",
            }
        },
        block=run_command,
    )
