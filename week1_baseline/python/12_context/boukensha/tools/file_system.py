"""Standard file-oriented tools, sandboxed to a single root directory.

Python port of Boukensha::Tools::FileSystem. Every path argument the agent
supplies is resolved relative to `working_dir`; a resolved path that would
escape that root (path traversal) produces an "error: ..." string instead
of raising, so the agent sees it and can try something else.

Tools registered: pwd, list_directory, read_file, write_file, delete_file,
search_files.
"""

from __future__ import annotations

import re
from pathlib import Path


def register(registry, *, working_dir):
    root = Path(working_dir).expanduser().resolve()

    def resolve(path):
        """Resolve an agent-supplied path inside root.

        Returns the resolved Path on success, or an "error: ..." string.
        """
        absolute = (root / path).resolve()
        if absolute == root or root in absolute.parents:
            return absolute
        return f"error: path '{path}' escapes the working directory"

    def oops(msg):
        return f"error: {msg}"

    registry.tool(
        "pwd",
        description="Return the working directory — the root that all file paths are relative to.",
        parameters={},
        block=lambda: str(root),
    )

    def list_directory(path="."):
        target = resolve(path)
        if isinstance(target, str):
            return target
        if not target.is_dir():
            return oops(f"'{path}' is not a directory")

        names = sorted(p.name for p in target.iterdir())
        entries = [f"{name}/" if (target / name).is_dir() else name for name in names]
        return "\n".join(entries) if entries else "(empty)"

    registry.tool(
        "list_directory",
        description="List files and subdirectories at a path relative to the working directory. Defaults to the working directory itself.",
        parameters={
            "path": {"type": "string", "description": "Relative path to list (default '.')"}
        },
        block=list_directory,
    )

    def read_file(path):
        target = resolve(path)
        if isinstance(target, str):
            return target
        if not target.is_file():
            return oops(f"'{path}' is not a file")
        try:
            return target.read_text(errors="replace")
        except OSError as e:
            return oops(str(e))

    registry.tool(
        "read_file",
        description="Read and return the full contents of a file. Path is relative to the working directory.",
        parameters={"path": {"type": "string", "description": "Relative path to the file"}},
        block=read_file,
    )

    def write_file(path, content):
        target = resolve(path)
        if isinstance(target, str):
            return target
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            rel = target.relative_to(root)
            return f"ok: wrote {len(content.encode())} bytes to {rel}"
        except OSError as e:
            return oops(str(e))

    registry.tool(
        "write_file",
        description="Write content to a file, creating it (and any missing parent directories) if needed, overwriting if it exists. Path is relative to the working directory.",
        parameters={
            "path": {"type": "string", "description": "Relative path to the file"},
            "content": {"type": "string", "description": "Text content to write"},
        },
        block=write_file,
    )

    def delete_file(path):
        target = resolve(path)
        if isinstance(target, str):
            return target
        if not target.is_file():
            return oops(f"'{path}' is not a file")
        try:
            target.unlink()
            return f"ok: deleted {path}"
        except OSError as e:
            return oops(str(e))

    registry.tool(
        "delete_file",
        description="Delete a file. Directories are not deleted. Path is relative to the working directory.",
        parameters={"path": {"type": "string", "description": "Relative path to the file to delete"}},
        block=delete_file,
    )

    def search_files(pattern, path=".", glob="*"):
        target = resolve(path)
        if isinstance(target, str):
            return target

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return oops(f"invalid pattern: {e}")

        if target.is_file():
            files = [target]
        else:
            files = sorted(target.rglob(glob))

        matches = []
        for file in files:
            if not file.is_file():
                continue
            rel = file.relative_to(root)
            try:
                with open(file, errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if regex.search(line):
                            matches.append(f"{rel}:{lineno}:{line.rstrip(chr(13) + chr(10))}")
            except OSError as e:
                matches.append(f"{rel}: error reading file: {e}")

        return "\n".join(matches) if matches else "no matches"

    registry.tool(
        "search_files",
        description="Search for a text pattern (literal string or regex) across all files in the working directory tree. Returns matching lines in 'path:line_number:content' format.",
        parameters={
            "pattern": {"type": "string", "description": "The text or regex pattern to search for"},
            "path": {"type": "string", "description": "Subdirectory or file to search within (default '.' = entire working directory)"},
            "glob": {"type": "string", "description": "File glob to restrict which files are searched, e.g. '*.py' (default '*')"},
        },
        block=search_files,
    )
