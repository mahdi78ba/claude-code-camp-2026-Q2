# Python Port Plan — Tools and MCP: A Standard Tool Library (`10_standard_tool_library`)

Baseline for this port is `python/08_the_repl_loop`, copied verbatim into
`python/10_standard_tool_library` (`__pycache__/`, `.venv/` excluded —
machine-local, regenerated on install). **Step 09 (`09_global_executable`)
is deliberately skipped as a Python step** — see "Why 09 is skipped"
below — so this plan's delta is the *cumulative* Ruby diff
`ruby/08_the_repl_loop` → `ruby/10_standard_tool_library`, as currently
committed on `main` (which already includes the later "replace in-process
MUD tool calls with MCP" refactor — commit `77370ae` — on top of the
original "Complete Standard Tool Library" commit `e22c6bf`; there is no
separate pre-MCP milestone to port through, only the final state).

## Why 09 is skipped

`ruby/08_the_repl_loop` → `ruby/09_global_executable` is **100% Ruby
packaging**: a `boukensha.gemspec`, a `bin/boukensha` executable, a new
`lib/boukensha_loader.rb` that resolves *which step's `lib/` to load* via
`BOUKENSHA_PATH`/`~/.boukensharc`, and `Gemfile`/`vendor/bundle` churn to
vendor `bundler` itself. Confirmed by `diff -rq ruby/08_the_repl_loop
ruby/09_global_executable`: every changed/added path is `Gemfile*`,
`bin/`, `*.gemspec`, `vendor/`, or `lib/boukensha_loader.rb`; the only
change inside `lib/boukensha/` proper is a version-string bump
(`0.8.0` → `0.9.0`) and a doc-comment reword in `boukensha.rb` with no
behavior change. Python already has its own per-step launcher mechanism
(`bin/python/<step>`, one script per step, no shared "which step do I
load" indirection) and no gem-equivalent packaging concern, so there is
nothing in `09` for a Python port to do. `docs/plans/python_port/` has no
`09_global_executable.md` for the same reason.

One more file to dispense with before the real diff: `lib/boukensha_loader.rb`
(the gem loader's own module, entirely a `09` artifact) also changed
between `09` and `10` — it gained a legacy-env-var convenience path
(`MUD_NAME`/`MUD_HOST`/`MUD_PORT`/`MUD_PASSWORD` build one `mcp:` entry
for `Boukensha.repl` when invoking the packaged `boukensha` executable
directly). This is still 100% packaging/CLI-invocation convenience with
no `lib/boukensha/` counterpart — it exists only to let someone running
the *installed gem* skip writing a `settings.yaml`. Python has no
installed-executable equivalent to attach this convenience to, so it's
skipped for the same reason `09` itself is skipped, not overlooked.

## What actually changed in Ruby (08 → 10, cumulative)

```
$ diff -rq ruby/08_the_repl_loop ruby/10_standard_tool_library
(packaging-only, same as the 08→09 diff above, plus:)
Files 09_global_executable/lib/boukensha/client.rb and 10_standard_tool_library/lib/boukensha/client.rb differ
Files 09_global_executable/lib/boukensha/config.rb and 10_standard_tool_library/lib/boukensha/config.rb differ
Files 09_global_executable/lib/boukensha/context.rb and 10_standard_tool_library/lib/boukensha/context.rb differ
Files 09_global_executable/lib/boukensha/logger.rb and 10_standard_tool_library/lib/boukensha/logger.rb differ
Files 09_global_executable/lib/boukensha/registry.rb and 10_standard_tool_library/lib/boukensha/registry.rb differ
Files 09_global_executable/lib/boukensha/repl.rb and 10_standard_tool_library/lib/boukensha/repl.rb differ
Only in 10_standard_tool_library/lib/boukensha: tools/
Files 09_global_executable/lib/boukensha.rb and 10_standard_tool_library/lib/boukensha.rb differ
```

1. **New `lib/boukensha/tools/file_system.rb`** — `Boukensha::Tools::FileSystem`,
   a module whose single class method `.register(registry, working_dir:)`
   registers six tools, all sandboxed to `working_dir` (every agent-supplied
   path is resolved with `File.expand_path(path, root)` and rejected with an
   `"error: path '...' escapes the working directory"` string, never an
   exception, if it lands outside `root`):
   `pwd`, `list_directory`, `read_file`, `write_file` (creates missing parent
   dirs), `delete_file`, and `search_files` (grep a regex across the tree,
   `path:line:content` format, one `oops`-wrapped error per unreadable file
   rather than aborting the whole search).

2. **New `lib/boukensha/tools/shell.rb`** — `Boukensha::Tools::Shell`,
   `.register(registry, working_dir:, timeout: 30, allowed_commands: nil)`
   registers one tool, `run_command`: runs the string through
   `Open3.capture2e` inside `working_dir` under `Timeout.timeout(timeout)`,
   returns combined stdout+stderr (trimmed) plus a `"\n[exit N]"` suffix on
   failure, or `"(no output)"` if empty. `allowed_commands`, when set, checks
   only the first whitespace-split token against the list before running
   anything.

3. **New `lib/boukensha/tools/mcp.rb`** — `Boukensha::Tools::Mcp`, the generic
   bridge from the registry to *any number* of configured MCP servers
   (replacing an earlier, now-removed MUD-specific `Tools::Mud` — not part of
   this diff, already gone by the time this repo's `10_standard_tool_library`
   was committed). `.register(registry, servers:)` calls `register_one` per
   server entry (`{name:, command:, env:, prefix:}`); each spawns
   `MudManager::Mcp::Client` (from the separate `mud_manager` gem — see
   "MCP client: no `mud_manager` gem in Python" below), performs the MCP
   handshake + `tools/list` under a 10s `Timeout.timeout`, and registers one
   Boukensha tool per MCP tool returned — the handler just forwards the call
   over MCP (`client.call_tool(tool_name, args)`) and returns the text
   (`isError` is ignored: the dispatcher already prefixes error text with
   `"error: "`, same convention every other tool here uses). A server that
   raises anywhere in that sequence is `warn`ed about and dropped — silently
   absent from the registry, not a fatal error for the whole process. Tool
   name collisions across servers are rejected (warn + skip) unless the
   server config sets `prefix:`.

4. **`lib/boukensha/registry.rb`** — one new method, `registered?(name)`
   (checks `@context.tools.key?`), used by `Tools::Mcp`'s collision check.

5. **`lib/boukensha/context.rb`** — `initialize` gains `working_dir: nil`,
   stored as `@working_dir = working_dir ? File.expand_path(working_dir) : nil`
   with a new `attr_reader`. **Confirmed dead in this diff**: nothing reads
   `context.working_dir` anywhere in `lib/` or `examples/` (grepped) —
   `Tools::FileSystem`/`Tools::Shell` both take `working_dir:` as their own
   explicit registration argument, independent of `Context`. Port it exactly
   as-is (a faithful 1:1 port, not a place to "fix" unused Ruby state).

6. **`lib/boukensha.rb`** — `Boukensha.run`/`Boukensha.repl` both gain four
   new keyword args: `working_dir: Dir.pwd`, `allowed_commands: nil`,
   `shell_timeout: 30`, `mcp: nil`. After building `ctx`/`registry`:
   ```ruby
   if working_dir
     Tools::FileSystem.register(registry, working_dir: working_dir)
     Tools::Shell.register(registry, working_dir: working_dir,
                           timeout: shell_timeout, allowed_commands: allowed_commands)
   end

   resolved_mcp = mcp == false ? [] : (mcp || cfg.mcp_servers)
   mcp_clients  = resolved_mcp.any? ? Tools::Mcp.register(registry, servers: resolved_mcp) : []
   ```
   `working_dir: false` opts out of the filesystem/shell tools entirely (used
   by the MUD example, which needs neither). `mcp: nil` (the default) means
   "use `config.mcp_servers` (`settings.yaml`'s `mcp_servers:` list)";
   `mcp: false` or `mcp: []` means "register none". `repl` additionally
   threads `mcp_clients` into `Repl.new(..., mcp_servers: mcp_clients)` so the
   banner can report which servers actually connected.

## MCP client: no `mud_manager` gem in Python

Ruby's `Tools::Mcp` doesn't implement the MCP wire protocol itself — it
`require`s `mud_manager/mcp/client`, a class from the separate `mud_manager`
gem (`week0_explore/mud_manager/lib/mud_manager/mcp/client.rb`). That class
is a **minimal, hand-rolled MCP client**: `Open3.popen2` to spawn the server
command, then newline-delimited JSON-RPC 2.0 over its stdin/stdout —
`initialize` request → `notifications/initialized` notification →
`tools/list` → `tools/call` per invocation → close. No MCP SDK, no
dependency beyond stdlib (`json`, `open3`, `timeout`). The MCP *server* side
(`mud_manager --mcp`, also in that same gem) is unchanged by this port —
it's a separate OS process either language's client can spawn and speak
line-delimited JSON-RPC to; **nothing about the server needs porting**.

Python has no equivalent `mud_manager` package to import a client class
from, and this repo doesn't currently depend on the `mcp` PyPI SDK. Per
`requirements.txt` (`PyYAML`, `python-dotenv` only), every prior Python
port has stayed stdlib-only wherever Ruby stayed stdlib-only-plus-one
teaching gem — the same call applies here (see "Judgment calls" #1).

## Cross-check against the current Python tree

- **No `Tools` package/module exists in Python at all yet** (`08` has no
  `boukensha/tools/` directory) — everything in this plan's items 1–3
  above is wholly new work, not a delta against existing Python code.
- **`Registry.registered?` doesn't exist** (`registry.py`'s `Registry` has
  only `tool`/`dispatch`) — needs adding (item #4).
- **`Context` has no `working_dir`** — needs adding (item #5), as a
  faithful, equally-unused port (see item #5 above).
- **Three things in this Ruby diff are *regressions* already fixed in
  Python — do not port them backward:**
  1. `config.rb`'s `resolve_dir` **reverted from 3 tiers back to 2**
     (dropped the `.boukensha`-in-cwd tier added in Ruby's own `08`) at
     some point before `10_standard_tool_library` was first committed —
     confirmed by diffing `e22c6bf`'s `config.rb` (the very first
     "Complete Standard Tool Library" commit, pre-MCP) against `08`'s: it's
     already 2-tier there, i.e. this happened when `10`'s working tree was
     first scaffolded, not as part of the MCP refactor. Python's
     `config.py::_resolve_dir` still has the 3-tier version from the `08`
     port (confirmed by reading the current file) — **leave it alone**.
  2. `client.rb`'s 401-specific `ApiError` message (added in Ruby's own
     `08`) is **gone** from `10`'s `client.rb` — confirmed by reading the
     file directly (`unless response.is_a?(Net::HTTPSuccess)` has only the
     generic message now). Python's `client.py` still has the 401-specific
     branch from the `08` port — **leave it alone**.
  3. `logger.rb`'s OpenAI `provider_name` special case (`return "openai" if
     backend.is_a?(Backends::OpenAI)`, ported to Python back in `06`/`07`)
     is **gone** from `10`'s `logger.rb` — confirmed by reading the file.
     Python's `logger.py` still has it — **leave it alone**.

     None of these three are re-introduced by the later MCP-integration
     commit (`77370ae`) either — all three files it touches
     (`config.rb`/`client.rb`/`registry.rb`/`repl.rb`/`boukensha.rb`) were
     already in this reverted state in the first `10_standard_tool_library`
     commit. Flagging this explicitly rather than silently "fixing Ruby"
     as part of this port — the fix is simply *not porting the regression*,
     Python's existing code is already correct.
- **`Boukensha::Agent`, `PromptBuilder`, `Message`, `Tool`,
  `Tasks::Base`/`Tasks::Player`, all five backends, `Repl`'s turn-handling
  logic (only its banner changes — see item below), `Client`'s retry
  logic** are otherwise unchanged in this diff — nothing else to touch.

## Files to add / change in Python

### 1. `boukensha/tools/__init__.py` — new

```python
"""Boukensha's standard tool library.

Python port of Boukensha::Tools. Three independent registration modules —
file_system, shell, mcp — each exposing a module-level register(registry, ...)
function, mirroring Ruby's Tools::FileSystem/.Shell/.Mcp module namespaces
(each a bare namespace holding one class method, not a stateful object — a
plain function per file is the direct equivalent, not a class with one
method).
"""

from . import file_system, shell, mcp

__all__ = ["file_system", "shell", "mcp"]
```

Call sites read `tools.file_system.register(...)` /
`tools.shell.register(...)` / `tools.mcp.register(...)` — same shape as
Ruby's `Tools::FileSystem.register(...)` etc., just a module attribute
instead of a class method.

### 2. `boukensha/tools/file_system.py` — new, ported from `tools/file_system.rb`

```python
"""Standard file-oriented tools, sandboxed to a single root directory.

Python port of Boukensha::Tools::FileSystem. Every path argument the agent
supplies is resolved relative to `working_dir`; a resolved path that would
escape that root (path traversal) produces an "error: ..." string instead
of raising, so the agent sees it and can try something else.
"""

from __future__ import annotations

import re
from pathlib import Path


def register(registry, *, working_dir):
    root = Path(working_dir).resolve()

    def resolve(path):
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
        entries = sorted(p.name for p in target.iterdir())
        entries = [f"{name}/" if (target / name).is_dir() else name for name in entries]
        return "\n".join(entries) if entries else "(empty)"

    registry.tool(
        "list_directory",
        description="List files and subdirectories at a path relative to the working directory. Defaults to the working directory itself.",
        parameters={"path": {"type": "string", "description": "Relative path to list (default '.')"}},
        block=list_directory,
    )

    def read_file(path):
        target = resolve(path)
        if isinstance(target, str):
            return target
        if not target.is_file():
            return oops(f"'{path}' is not a file")
        try:
            return target.read_text()
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

        search_root = target.parent if target.is_file() else target
        files = [target] if target.is_file() else sorted(search_root.rglob(glob))

        matches = []
        for file in files:
            if not file.is_file():
                continue
            rel = file.relative_to(root)
            try:
                with open(file, errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if regex.search(line):
                            matches.append(f"{rel}:{lineno}:{line.rstrip(chr(10))}")
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
```

Translation notes, not just renames:

- **`registry.tool(...) do |...| ... end` becomes `registry.tool(...,
  block=fn)`** — `Registry.tool` in Python already takes `block` as a
  keyword (see `registry.py`), consistent with every prior tool
  registration in this codebase (e.g. `RunDSL`).
- **Path traversal check**: Ruby's `absolute == root ||
  absolute.start_with?("#{root}/")` becomes `absolute == root or root in
  absolute.parents` — `Path.parents` is the idiomatic pathlib way to ask
  "is `root` an ancestor of this path," equivalent to the string-prefix
  check without the subtle bug class of a manual `startswith` (e.g. root
  `/a/b` wrongly matching `/a/bc`) that Ruby's explicit `"#{root}/"`
  suffix was already careful to avoid — same safety property, idiomatic
  Python spelling.
- **`Dir.entries` + reject `.`/`..` becomes `Path.iterdir()`** — `iterdir`
  never yields `.`/`..` in the first place, so there's nothing to filter
  (no Python equivalent bug to reintroduce).
- **`File.foreach(file).with_index(1)` becomes `enumerate(fh, start=1)`** —
  direct translation; `errors="replace"` on `open()` mirrors Ruby's
  default external encoding behavior closely enough for a search tool
  (neither language aborts the whole search over one binary/non-UTF-8
  file — Ruby's `rescue => e` around the per-file loop and Python's
  `except OSError` both keep going).
- **`Dir.glob(File.join(target, "**", glob))` becomes
  `search_root.rglob(glob)`** — pathlib's recursive glob is the direct
  equivalent; both include files at the top level of `search_root`, not
  just nested ones.
- **`content.bytesize` becomes `len(content.encode())`** — byte count of
  the UTF-8-encoded string, not `len(content)` (character count), matching
  Ruby's byte-oriented `bytesize`.

### 3. `boukensha/tools/shell.py` — new, ported from `tools/shell.rb`

```python
"""Command-execution tools, sandboxed to a single working directory.

Python port of Boukensha::Tools::Shell.
"""

from __future__ import annotations

import subprocess


def register(registry, *, working_dir, timeout=30, allowed_commands=None):
    root = str(working_dir)

    def oops(msg):
        return f"error: {msg}"

    allowed_note = (
        f" Allowed executables: {', '.join(allowed_commands)}." if allowed_commands else ""
    )

    def run_command(command):
        if allowed_commands is not None:
            executable = command.strip().split()[0] if command.strip() else ""
            if executable not in [str(c) for c in allowed_commands]:
                allowed_list = ", ".join(allowed_commands)
                return oops(f"'{executable}' is not in the allowed-commands list ({allowed_list})")

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
        parameters={"command": {"type": "string", "description": "The shell command to execute (e.g. 'python script.py', 'ls -la', 'git status')"}},
        block=run_command,
    )
```

Translation notes:

- **`Open3.capture2e(command, chdir:)` becomes `subprocess.run(command,
  shell=True, cwd=root, stdout=PIPE, stderr=STDOUT)`** — `shell=True` with
  a single string is the direct match for Ruby's `Open3` given a bare
  command string (which Ruby's own `Process.spawn` semantics route through
  `/bin/sh -c` whenever the string contains shell metacharacters, and
  sometimes execs directly otherwise). Always using `shell=True` in
  Python — rather than trying to replicate Ruby's metacharacter-sniffing
  heuristic for when to invoke a shell — is the simpler, more predictable
  choice, and it's what the "Known limitations" section of the Ruby
  README already documents as the *de facto* behavior anyway (`echo hi;
  rm -rf /` already goes through a shell in Ruby too, since `;` is a
  metacharacter).
- **A real behavior difference worth flagging, not fixing**: Ruby's
  `Errno::ENOENT` rescue only fires when Ruby execs the command directly
  (no shell metacharacters) and the executable isn't found — e.g. `next
  oops.call("command not found: ...")`. Once Python always uses
  `shell=True`, an unknown command is instead reported by the *shell*
  itself (`sh: 1: badcmd: not found`, exit code 127) via the normal
  output/exit-code path, not a raised `OSError` — so the `except OSError`
  branch above will essentially only fire if `/bin/sh` itself is missing
  (never, in practice). This means the Python tool's error text for "you
  typo'd the command name" looks like `"sh: 1: badcmd: not found\n[exit
  127]"` rather than Ruby's `"error: command not found: ..."` — different
  wording, same net effect (a clear failure signal reaches the agent).
  Not a regression to chase further; see Judgment call #2.
- **The known, documented-in-Ruby-README timeout limitation carries
  over, but is slightly better in Python, not worse**: Ruby's
  `Timeout.timeout` only interrupts the Ruby thread waiting on the
  subprocess — the spawned process (e.g. `sleep 20`) keeps running in the
  background after the tool "returns." Python's `subprocess.run(...,
  timeout=...)` — via `Popen.communicate(timeout=...)` — actually calls
  `.kill()` on the *immediate* child process (the `sh -c ...` shell) when
  the timeout fires. This is a natural consequence of using the stdlib's
  built-in timeout, not extra scope: it does **not** attempt to kill an
  entire process *group* (a background `&`-ed grandchild spawned by that
  shell can still survive, same residual gap Ruby's README documents for
  its own worse case) — full process-group cleanup remains out of scope
  for this port, matching Ruby's own "known limitation, not fixed in this
  iteration" framing.
- **`allowed_commands.map(&:to_s).include?(executable)` becomes
  `[str(c) for c in allowed_commands]` inline** — same defensive
  stringification (handles a caller passing symbols/non-strings in Ruby;
  in Python, guards a caller passing e.g. `Path` objects), preserved for
  parity even though every realistic caller already passes a list of
  plain strings.

### 4. `boukensha/tools/mcp.py` — new, ported from `tools/mcp.rb`

```python
"""The generic bridge between Boukensha's Registry and any number of
configured MCP servers.

Python port of Boukensha::Tools::Mcp. Doesn't know what any server's tools
actually do — MUD gameplay is just one entry in `servers`, not a special
case.

No `mud_manager` package exists for Python to import an MCP client from
(see docs/plans/python_port/10_standard_tool_library.md, "MCP client: no
mud_manager gem in Python"), so this module carries its own minimal
client: spawn a command, speak newline-delimited JSON-RPC 2.0 over its
stdin/stdout. Mirrors MudManager::Mcp::Client
(week0_explore/mud_manager/lib/mud_manager/mcp/client.rb) line-for-line —
same four calls (handshake, list_tools, call_tool, close), same wire
format, talking to the exact same `mud_manager --mcp` server process
(unchanged by this port; the server is not reimplemented here).
"""

from __future__ import annotations

import json
import subprocess

HANDSHAKE_TIMEOUT = 10  # seconds

_CLIENT_INFO = {"name": "boukensha-mcp-client", "version": "1.0"}
_PROTOCOL_VERSION = "2024-11-05"


class _McpError(Exception):
    pass


class _McpClient:
    """Minimal MCP client: spawn, handshake, tools/list, tools/call, close."""

    def __init__(self, *, command, env=None):
        import os
        full_env = {**os.environ, **(env or {})}
        self._proc = subprocess.Popen(
            command, env=full_env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self._next_id = 0

    def handshake(self):
        result = self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        })
        self._notify("notifications/initialized")
        return result.get("serverInfo")

    def list_tools(self):
        return self._request("tools/list")["tools"]

    def call_tool(self, name, arguments=None):
        result = self._request("tools/call", {"name": str(name), "arguments": arguments or {}})
        content = result.get("content") or []
        text = content[0].get("text", "") if content else ""
        return text, result.get("isError") is True

    def close(self):
        if self._proc.stdin and not self._proc.stdin.closed:
            self._proc.stdin.close()
        if self._proc.stdout and not self._proc.stdout.closed:
            self._proc.stdout.close()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()

    # ---------- private -----------------------------------------------

    def _request(self, method, params=None):
        self._next_id += 1
        request_id = self._next_id
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        response = self._read_until_id(request_id)
        if "error" in response:
            err = response["error"]
            raise _McpError(f"{err['message']} (code {err['code']})")
        return response["result"]

    def _notify(self, method, params=None):
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _write(self, payload):
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

    def _read_until_id(self, request_id):
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise _McpError("server closed the connection")
            message = json.loads(line)
            if message.get("id") == request_id:
                return message


def register(registry, *, servers):
    return [r for r in (_register_one(registry, server) for server in servers) if r is not None]


def _register_one(registry, server):
    import signal
    import warnings

    command = server.get("command") or None
    client = _McpClient(command=command, env=server.get("env") or {}) if command else None
    if client is None:
        raise ValueError(f"MCP server {server.get('name')!r} needs a command (no default, unlike Ruby's mud_manager fallback)")

    try:
        _with_timeout(HANDSHAKE_TIMEOUT, lambda: _do_handshake(registry, server, client))
        return {"name": server.get("name"), "client": client}
    except Exception as e:
        print(f"[boukensha] MCP server {server.get('name')!r} failed to start: {type(e).__name__}: {e}")
        return None


def _do_handshake(registry, server, client):
    client.handshake()
    for tool in client.list_tools():
        _register_proxy_tool(registry, server.get("name"), client, tool, server.get("prefix"))


def _register_proxy_tool(registry, server_name, client, tool, prefix):
    name = f"{prefix}_{tool['name']}" if prefix else tool["name"]

    if registry.registered(name):
        print(
            f"[boukensha] MCP server {server_name!r}: tool {name!r} collides with an "
            f"already-registered tool — skipped (use prefix: on this server's config "
            f"entry to disambiguate)"
        )
        return

    def call(**kwargs):
        text, _is_error = client.call_tool(tool["name"], kwargs)
        return text

    registry.tool(
        name,
        description=tool.get("description"),
        parameters=tool["inputSchema"]["properties"],
        block=call,
    )
```

Translation notes, not just renames:

- **`Open3.popen2` becomes `subprocess.Popen(..., stdin=PIPE,
  stdout=PIPE, text=True, bufsize=1)`** — `text=True` gives line-buffered
  str I/O directly (Ruby's `$stdin`/`$stdout` on the pipe are also
  text-mode by default), `bufsize=1` matches Ruby's per-line
  `puts`/`gets` flushing behavior so no message sits unflushed in a
  buffer.
- **`env` merging**: Ruby's `Open3.popen2(env, *command)` passes `env` as
  *additions* to the current environment (`Open3`/`Process.spawn`'s `env`
  hash is merged over the parent's, not a replacement) — Python's
  `subprocess.Popen(env=...)`, by contrast, **replaces** the entire
  environment if `env` is not `None`. The port above merges explicitly
  (`{**os.environ, **(env or {})}`) to match Ruby's actual behavior — a
  literal `env={"MUD_HOST": "localhost"}` in Python without this merge
  would silently drop `PATH` and break spawning `mud_manager` by bare name
  in `command: ["mud_manager", "--mcp"]`. This is the one place in this
  file where a naive line-for-line translation would introduce a real bug
  (worth a dedicated regression test — see Verification plan).
- **`at_exit { client.close }` has no direct Python equivalent inside a
  function** (Ruby's `at_exit` registers a process-wide hook from
  anywhere) — closest idiomatic equivalent is `atexit.register(client.close)`
  from the stdlib `atexit` module; the plan's sketch above omits it for
  brevity but the actual port should add `import atexit;
  atexit.register(client.close)` right after a successful handshake,
  mirroring Ruby's guarantee that a spawned MCP server subprocess is
  cleaned up even if the caller never explicitly closes it.
- **`Timeout.timeout(HANDSHAKE_TIMEOUT) { ... }` has no single stdlib
  one-liner in Python** — `signal.alarm` (POSIX-only, main-thread-only) is
  the closest analog to Ruby's `Timeout` (which also has known caveats,
  documented in Ruby's own stdlib, about interrupting arbitrary blocking
  calls); alternatively run the handshake in a helper thread and
  `join(timeout=...)`. **Flagged as Judgment call #3** — the sketch above
  calls a placeholder `_with_timeout` helper rather than picking one
  silently, since the two options have different portability/threading
  trade-offs worth a deliberate choice, not a default.
- **`servers.filter_map { |server| register_one(...) }` becomes the
  explicit generator-with-`None`-filter list comprehension shown** —
  `filter_map` has no single built-in Python equivalent; this is the
  standard idiom for "map then drop falsy/None," not a design choice
  specific to this file.
- **`warn` (Ruby, writes to `$stderr`) becomes `print(..., file=sys.stderr)`
  in the real port** — the sketch above uses a bare `print` for brevity;
  match every other warning path in this codebase (grep for existing
  `sys.stderr` usage in `logger.py`/`client.py` and follow that
  convention) rather than introducing a new "print to stdout" precedent
  for what should be operational noise.
- **`tool[:inputSchema][:properties]` stays a plain dict key lookup** — an
  MCP `tools/list` response's `inputSchema.properties` is already the
  exact shape `Registry.tool`'s `parameters` expects in both languages
  (both Ruby's `Tool` and Python's `Tool` just pass this dict straight
  through into the API payload's tool schema) — no reshaping needed.
- **Command validation is stricter than Ruby's, deliberately, per the
  actual `settings.yaml` in this repo**: Ruby's client has a `DEFAULT_COMMAND
  = ["mud_manager", "--mcp"]` fallback baked into `MudManager::Mcp::Client`
  itself (used when `command:` is blank), because that class lives inside
  the `mud_manager` gem and can reasonably default to its own executable.
  Python's client has no such gem-specific default to fall back to, so an
  empty `command:` is a hard error here rather than a silent
  MUD-flavored default — **and this repo's own `settings.yaml` always sets
  `command: ["mud_manager", "--mcp"]` explicitly anyway** (see the config
  file itself), so this stricter behavior doesn't affect the one server
  this codebase actually configures. Flagged for the implementer under
  Judgment calls in case a future config omits `command:` expecting the
  old implicit default.

### 5. `boukensha/registry.py` — add `registered`

```python
def registered(self, name) -> bool:
    return str(name) in self.context.tools
```

Direct translation of `Registry#registered?` — the trailing `?` is
dropped per this codebase's established Ruby-bang/question-mark-to-plain-name
convention (same treatment `clear_messages!` got in the `08` port).

### 6. `boukensha/context.py` — add `working_dir`

```python
def __init__(self, *, task, system=None, working_dir=None) -> None:
    self.task = task
    self.system = system
    self.working_dir = str(Path(working_dir).resolve()) if working_dir else None
    self.messages: list[Message] = []
    self.tools: dict[str, Tool] = {}
```

(`from pathlib import Path` added to the existing imports.) Ported as a
faithful no-op field, matching Ruby's own currently-unused
`attr_reader :working_dir` (see "Cross-check" item #5 above) — not an
invitation to also wire it into `FileSystem`/`Shell`'s own `working_dir:`
resolution, which stays independent exactly as it is in Ruby.

### 7. `boukensha/__init__.py` — new keyword args on `run()`/`repl()`

Both functions gain `working_dir=None, allowed_commands=None,
shell_timeout=30, mcp=None`, and both need this block after `registry =
Registry(ctx)` (before the `configure(...)` call, matching Ruby's
ordering — tools registered by the standard library first, so a
user-supplied `configure` block can still see/override them):

```python
if working_dir:
    tools.file_system.register(registry, working_dir=working_dir)
    tools.shell.register(registry, working_dir=working_dir,
                          timeout=shell_timeout, allowed_commands=allowed_commands)

resolved_mcp = [] if mcp is False else (mcp or cfg.mcp_servers)
mcp_clients = tools.mcp.register(registry, servers=resolved_mcp) if resolved_mcp else []
```

`from . import tools` added near the top alongside the other `from .
xxx import`s. Note the **default value divergence, deliberate**: Ruby
defaults `working_dir: Dir.pwd` (always-on unless explicitly passed
`false`); this plan's Python signature defaults `working_dir=None`
(effectively "off unless the caller opts in"). This is flagged explicitly
under Judgment calls (#4) rather than silently picked, since it changes
whether every existing Python caller of `run()`/`repl()` (all the earlier
steps' examples, if ever re-run against this step's code) starts getting
filesystem/shell tools registered for free.

`repl()` additionally passes `mcp_servers=mcp_clients` into the `Repl(...)`
construction call (see item #9).

Add `"tools"` to `__all__`.

### 8. `boukensha/config.py` — replace `mud_host`/`mud_port`/etc. with `mcp_servers`

```python
# ---------- MCP servers -------------------------------------------------

def mcp_servers(self):
    """[{name, command, env, prefix}, ...] from settings.yaml's mcp_servers:
    list. An env value of the literal form "$VAR" resolves against
    os.environ (already populated from .env by _load_env) instead of being
    taken as a literal string — settings.yaml is commit-safe, so a real
    credential should never have to sit in it as plaintext.
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

def _resolve_env(self, raw):
    return {
        k: (os.environ.get(v[1:]) if isinstance(v, str) and v.startswith("$") else v)
        for k, v in raw.items()
    }
```

Remove the `mud_host`/`mud_port`/`mud_username`/`mud_password` properties
— Ruby's diff removes the equivalent `dig(:mud, ...)` methods entirely
(replaced, not kept alongside), and nothing in the `10` Ruby tree
references `config.mud_host` etc. anymore (confirmed by grep — only
`mcp_servers` is called from `boukensha.rb`). Also update the module
docstring's `# ---------- MUD connection` section header/comment the same
way Ruby's did (`# ---------- MCP servers`).

**Do not** touch `_resolve_dir` (see "Cross-check" item — Python's 3-tier
version is correct; Ruby's 2-tier version in this file is the regression
to *not* replicate).

### 9. `boukensha/repl.py` — banner gains an MCP status line

```python
def __init__(self, *, context, registry, builder, client, logger,
             config_dir=None, provider=None, model=None, version=None,
             api_key=None, mcp_servers=None, task_settings=None,
             max_iterations=None, max_output_tokens=None):
    ...
    self.mcp_servers = mcp_servers or []
    ...

def _banner(self):
    ...
    mcp_status = self._mcp_status_string()
    return (
        "\n"
        "╔══════════════════════════════════════╗\n"
        f"║  BOUKENSHA MUD Assistant (v{ver}){pad}║\n"
        "╚══════════════════════════════════════╝\n"
        f"  config:      {config_line}\n"
        f"  provider:    {provider_line}\n"
        f"  mcp servers: {mcp_status}\n"
        "\n"
        "  /quiet or /loud   toggle logging\n"
        "  /clear           reset conversation history\n"
        "  /exit or /quit    leave the REPL\n"
    )

def _mcp_status_string(self):
    if not self.mcp_servers:
        return "(not configured)"
    return ", ".join(f"{s['name']} (connected)" for s in self.mcp_servers)
```

Note the **realignment of the `config:`/`provider:` label padding**
(`config:` → `config:  ` becomes `config:    ` etc., all now padded to
line up with the wider `mcp servers:` label) — a cosmetic-but-exact match
of Ruby's `10` banner, not just an addition; get the column alignment
from the Ruby heredoc literally, don't eyeball it.

### 10. `boukensha/__init__.py`, `repl()` — thread `mcp_clients` into `Repl`

Continuing item #7: `repl()`'s `Repl(...)` construction call gains
`mcp_servers=mcp_clients`.

### 11. `examples/example.py` — new MUD demo, mirroring `examples/example.rb`

```python
"""Boukensha Step 10: Tools and MCP — a standard tool library, MUD demo."""

import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boukensha  # noqa: E402

os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parents[4] / ".boukensha"))

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
```

Direct translation of `ruby/10_standard_tool_library/examples/example.rb`.
`working_dir=False` matches this plan's item #7 default divergence
regardless of which way Judgment call #4 is resolved — this example is
explicit either way, so it's unaffected by that choice.

### 12. `README.md` — full rewrite, not a port

Same treatment as every prior step: translate
`ruby/10_standard_tool_library/README.md` into the Python-flavored
equivalent (`Boukensha::Tools::FileSystem`/`.Shell`/`.Mcp` →
`boukensha.tools.file_system`/`.shell`/`.mcp`, `ruby examples/demo.rb` →
`./bin/python/10_standard_tool_library`). Carry forward, translated, the
Ruby README's **"Known limitations (not fixed in this iteration)"**
section nearly verbatim — it documents real, still-present behavior in
both languages (`run_command`'s incomplete process-tree cleanup on
timeout, `allowed_commands` being a first-token filter and not a shell
sandbox, malformed tool calls raising `TypeError`/`KeyError` instead of
returning an `"error: ..."` string the same way path/file errors do, MCP
tool registration paying its connection cost eagerly during setup rather
than lazily on first use) — and its **"Technical observations"** section
should note the Python-specific equivalents surfaced by this plan (the
`shell=True`-vs-`Errno::ENOENT` wording difference from item #3's plan
above; that Python needs no local-gem `vendor/cache` workaround since it
has no `mud_manager`-equivalent packaging problem — it just spawns the
already-installed `mud_manager --mcp` executable Ruby's own setup
requires anyway, see Verification plan).

### 13. `bin/python/10_standard_tool_library` — new runner

Mirror `bin/python/08_the_repl_loop` verbatim, path bumped (continuing
Python's own per-step launcher convention — see "Why 09 is skipped"; this
is *not* modeled on Ruby's `BOUKENSHA_PATH=... boukensha` indirection):

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../python/10_standard_tool_library"

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

exec "$PY" examples/example.py
```

## Judgment calls (flag for the implementer, don't silently decide)

1. **Hand-roll the MCP client (as sketched in file #4) vs. add the `mcp`
   PyPI SDK as a new dependency?** Recommendation: **hand-roll**, matching
   Ruby's own choice to hand-roll a ~90-line client rather than depend on
   an official MCP SDK gem, and matching this Python port's existing
   stdlib-first posture (`requirements.txt` has exactly two entries,
   neither of which is network-protocol machinery). The wire protocol is
   simple enough (newline-delimited JSON-RPC 2.0, four request types) that
   a faithful line-for-line port of `MudManager::Mcp::Client` is both
   less code and less new-dependency risk than pulling in a full SDK for
   one teaching exercise.
2. **Chase the `Errno::ENOENT`-vs-shell-message divergence in
   `tools/shell.py` (item #3) further, e.g. by pre-checking
   `shutil.which(executable)` before invoking the shell, to recover
   Ruby's exact `"error: command not found: ..."` wording?**
   Recommendation: **no** — Ruby's own README already documents
   `run_command`'s error-shape inconsistency as a known, not-fixed
   limitation of this exact tool (see file #12's carried-forward "Known
   limitations" section), and the Python version's behavior is already at
   least as informative (the shell's own "not found" message plus a
   nonzero exit code, both visible to the agent) — adding a
   `shutil.which` pre-check to manufacture Ruby's specific wording would
   be scope creep this step's Ruby original doesn't do either.
3. **How to implement the MCP handshake's 10-second timeout — `signal.alarm`
   or a helper thread with `join(timeout=...)`?** Recommendation:
   **a helper thread** — `signal.alarm` only works on the main thread and
   only on POSIX, and this codebase's Windows-compatibility posture is
   otherwise not signal-reliant anywhere else in the Python port; a thread
   with a timeout-bounded `join()` (falling back to treating the server as
   failed-to-start if the thread is still alive past the deadline, then
   discarding/closing the subprocess) works cross-platform and mirrors
   Ruby's `Timeout.timeout` more closely in spirit (interrupt the *caller's*
   wait, not the callee) than an alarm signal would.
4. **`run()`/`repl()`'s new `working_dir` default: `None` (opt-in, as
   sketched in file #7) or `Path.cwd()` (opt-out, matching Ruby's
   `Dir.pwd` default exactly)?** Recommendation: **match Ruby —
   default to the current working directory (`Path.cwd()`), opt-out via
   `working_dir=False`** — the whole point of "a standard tool library"
   is that a caller gets a working filesystem/shell out of the box
   without asking for it, same as Ruby; defaulting to `None`/off would
   silently make Python's `run()`/`repl()` behave differently from every
   Ruby example and from this same step's own README the moment either is
   called without `working_dir=` at all. Flagged as a judgment call
   rather than silently applied because it changes the zero-config
   behavior of `run()`/`repl()` for any caller (including every earlier
   Python step's example, if ever pointed at this step's code) that
   doesn't pass `working_dir=` explicitly.
5. **Prefix `_McpClient`/`_register_one`/`_register_proxy_tool` with a
   leading underscore (module-private, as sketched) or leave them
   public?** Recommendation: **underscore-private**, matching Ruby's own
   `private_class_method :register_proxy_tool` — `register` is the only
   name external callers (`boukensha/__init__.py`) need, same public
   surface as Ruby's `Tools::Mcp.register` (a single public entry point).

## Unchanged — carry forward as-is

`boukensha/agent.py`, `boukensha/prompt_builder.py`, `boukensha/message.py`,
`boukensha/tool.py`, `boukensha/tasks/*.py`, `boukensha/backends/*.py`,
`boukensha/logger.py` (**except**: do not remove its OpenAI
`_provider_name` special case — see Cross-check), `boukensha/client.py`
(**except**: do not remove its 401-specific `ApiError` message — see
Cross-check), `boukensha/version.py`'s *shape* (only its value changes —
see Judgment call below), `requirements.txt` (no new pip dependency; see
Judgment call #1). None of these have any Python-relevant change in the
Ruby `08`→`10` diff.

One more version-numbering judgment call, kept separate from the list
above since it's purely cosmetic: **`VERSION` should read `"0.10.0"`**,
matching Ruby's step-10 value, even though Python never had its own
`"0.9.0"` release for the skipped step 09 — the version string tracks
"which Ruby step's features are present," not "how many Python releases
have happened," consistent with every version bump in this series so far
tracking the Ruby step number 1:1.

## Verification plan

Same two-layer approach as every prior port in this series, with an
extra MCP-specific layer given this step's added subprocess/IPC surface:

1. **Offline**, no live API, no live MCP server:
   - Construct a temp directory tree, register `Tools::FileSystem`
     against it, and drive each of the six tools directly: a path
     traversal attempt (`../../../etc/passwd`) returns the `"error: ...
     escapes"` string rather than raising or reading outside the sandbox;
     `write_file` creates missing parent directories; `search_files`
     finds a known pattern and reports correct `path:line:content`
     triples; `delete_file`/`read_file` on a nonexistent path each return
     their respective `oops` strings, not exceptions.
   - Register `Tools::Shell` with `allowed_commands=["true"]` and confirm
     a disallowed command (`"false"`) is rejected *before* executing
     (verifiable by asserting no subprocess side effect occurred, e.g. a
     sentinel file the command would have written is absent); confirm a
     genuinely allowed command's combined stdout+stderr and non-zero exit
     code both surface correctly; confirm a command exceeding `timeout=`
     is reported as timed out.
   - Construct a fake/stub MCP server script (any short Python script
     that speaks the four-message JSON-RPC handshake over stdin/stdout —
     no real `mud_manager` needed) and drive `_McpClient` against it
     directly: handshake succeeds, `list_tools` returns the stub's
     canned tool list, `call_tool` round-trips arguments and gets back
     the stub's canned text. This is the direct regression test for the
     `env`-merging fix called out in file #4's translation notes — assert
     the spawned stub process still has `PATH` (and can therefore itself
     spawn something, or just assert `os.environ["PATH"]` is visible
     inside it) when `Tools::Mcp.register` is called with a non-empty
     `env:` override, proving Python's `env={**os.environ, **env}`
     merge (not a bare `env=env` replacement) took effect.
   - Register two servers (real or stub) whose tool lists both include a
     tool of the same bare name, one with `prefix:` set and one without;
     confirm the unprefixed collision is warned-and-skipped (registry
     ends up with only one of the two), matching
     `Registry#registered?`'s role in `register_proxy_tool`.
   - Assert `Context(...).working_dir` round-trips an expanded absolute
     path when passed a relative one, and is `None` when omitted — the
     direct unit check for item #6, even though (as documented) nothing
     downstream currently reads it.
   - Re-run the three specific regression checks from the `08` port
     plan's own verification section (three-tier `_resolve_dir`,
     401-specific `ApiError` message, OpenAI `_provider_name` special
     case) against `python/10_standard_tool_library`'s copied-forward
     files — confirming the copy-then-diff process for this step didn't
     accidentally carry Ruby's three reverted-in-`10` behaviors backward
     into the new step's tree the way Ruby's own history did.
2. **Live smoke test against the real `mud_manager --mcp` server**: with
   `mud_manager` gem-installed and reachable on `$PATH` exactly as Ruby's
   own `10_standard_tool_library` setup requires (see that step's
   README's "Technical observations" about vendoring it locally — that
   vendoring is a Bundler/RubyGems concern only; the *installed
   executable* it produces is what Python's client spawns, no separate
   Python-side packaging needed), run `./bin/python/10_standard_tool_library`
   for real against the Anthropic backend and a running CircleMUD
   instance, and compare the resulting `.boukensha/sessions/<id>.jsonl`
   against the real `ruby/10_standard_tool_library` session already
   verified for this iteration (`docs/week1_standard_tool_library_review.md`
   / `docs/week1_mcp_part4_verification.md`) — same MCP tool names
   surfacing in `tool_result` log entries (`mud_connect`, `look`, `check`,
   etc.), same overall `turn_end reason: completed` shape, values
   naturally differing (session id, timestamps, token counts).
3. Confirm `log_viz` can list and render the Python-generated session
   exactly like the Ruby one — no `log_viz` changes expected.
