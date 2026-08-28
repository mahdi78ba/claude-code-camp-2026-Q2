# Step 10 — Tools and MCP: A Standard Tool Library

Python port of `ruby/10_standard_tool_library`. Boukensha now ships three
built-in tool modules under `boukensha.tools`. Instead of manually
registering tools, a real coding harness gives the agent a standard
library of capabilities — and a generic bridge to any MCP server — out
of the box.

Step 9 (`ruby/09_global_executable`) has no Python counterpart — it's
100% Ruby gem-packaging (a `boukensha.gemspec`, a `bin/boukensha`
executable, a `BOUKENSHA_PATH`/`~/.boukensharc` loader). Python already
has its own per-step launcher (`bin/python/<step>`), so this port picks
up directly where `08_the_repl_loop` left off — see
`docs/plans/python_port/10_standard_tool_library.md` for the full
rationale.

## What's new

### `boukensha.tools.file_system`

The evolution of a plain `read_file`/`list_directory` `configure` block —
same five tools plus one new one. Registers automatically when
`working_dir=` is set (the default):

| Tool | Description |
|------|-------------|
| `pwd` | Return the working directory |
| `list_directory` | List files at a path (default `.`) |
| `read_file` | Read a file's contents |
| `write_file` | Write (or create) a file |
| `delete_file` | Delete a file |
| `search_files` | **New** — grep for a regex pattern across the working tree, returns `path:line:content` matches |

All paths are **relative to the working directory**. Absolute paths and
`..` traversals that escape the root are rejected with an error string,
not an exception.

### `boukensha.tools.shell`

New module. Registers automatically when `working_dir=` is set:

| Tool | Description |
|------|-------------|
| `run_command` | Run a shell command inside the working directory |

Commands run with a configurable timeout and an optional allow-list of
permitted executables.

### `boukensha.tools.mcp`

New module — the standard tool library's bridge to **MCP (Model Context
Protocol)** servers. Rather than a MUD-specific tool set, `Boukensha` now
speaks the same generic MCP client protocol Ruby's `mud_manager` gem
implements: spawn a configured server command, perform the MCP handshake
over stdio, and register one Boukensha tool per MCP tool the server
reports. MUD gameplay is just one configured server (`settings.yaml`'s
`mcp_servers:` list) — this module has no MUD-specific code in it at all.

```python
boukensha.tools.mcp.register(registry, servers=[
    {"name": "mud", "command": ["mud_manager", "--mcp"], "env": {...}}
])
```

Registers automatically from `config.mcp_servers()` (`settings.yaml`'s
`mcp_servers:` list) unless overridden via the `mcp=` keyword. A server
that fails to spawn, hangs past its 10-second handshake timeout, or
errors is warned about (to stderr) and simply absent from the registry —
one bad server doesn't take any other configured server down with it.
Two servers exposing a tool of the same bare name collide; the second
one registered is skipped with a warning unless its config sets
`prefix:` to disambiguate (e.g. `mud_look`).

**No `mud_manager` Python package exists** — this module carries its own
minimal, hand-rolled MCP client (newline-delimited JSON-RPC 2.0 over a
subprocess's stdio), rather than depending on an MCP SDK. It spawns and
speaks to the exact same `mud_manager --mcp` server process Ruby's setup
already requires; only the client is reimplemented, not the server.

### New `boukensha.run()` / `boukensha.repl()` keyword arguments

```python
boukensha.run(
    task="...",
    working_dir="/my/project",
    allowed_commands=["python", "git"],  # None = allow all (default)
    shell_timeout=30,                     # seconds, default 30
)
```

`allowed_commands=None` permits any executable. Pass an explicit list to
lock the agent down:

```python
# Only allow python and git — rm, curl, etc. will be rejected
boukensha.run(task="...", allowed_commands=["python", "git"])
```

`working_dir=False` opts out of the filesystem/shell tools entirely (used
by this step's own MUD demo, which needs neither). `mcp=False` (or
`mcp=[]`) opts out of MCP tool registration entirely; `mcp=None` (the
default) uses `config.mcp_servers()`.

### Direct registration

All three modules can be registered manually if you need finer control:

```python
boukensha.tools.file_system.register(registry, working_dir="/my/project")
boukensha.tools.shell.register(registry, working_dir="/my/project",
                                timeout=10, allowed_commands=["python"])
boukensha.tools.mcp.register(registry, servers=[...])
```

## Changes from step 8

- **`Registry.registered(name)`** — checks whether a tool name is already
  taken; backs `tools.mcp`'s collision check.
- **`Context(working_dir=...)`** — stored as an expanded absolute path.
  Ported as a faithful 1:1 field even though nothing currently reads it
  (same in Ruby — `FileSystem`/`Shell` take their own `working_dir=`
  argument independently of `Context`).
- **`Config.mcp_servers()`** replaces the old `mud_host`/`mud_port`/
  `mud_username`/`mud_password` properties. An `env:` value written as
  `"$VAR"` resolves against `os.environ` (already populated from `.env`)
  instead of being taken literally, so a real credential never has to sit
  in `settings.yaml` as plaintext.
- **`Repl`'s banner** gains an `mcp servers:` line reporting which
  configured servers actually connected.

## Running it

```sh
./week1_baseline/bin/python/10_standard_tool_library
```

The demo connects to the configured MUD server via MCP, looks around,
checks its score, and reports the exits — same task as
`ruby/10_standard_tool_library/examples/example.rb`. Requires
`mud_manager --mcp` to be reachable on `$PATH` (installed the same way
Ruby's own setup requires — see that step's README) and a running
CircleMUD instance, plus `settings.yaml`'s `mcp_servers:` entry pointing
at it.

## Known limitations (carried over from the Ruby original, not fixed here)

These are documented, not-fixed limitations of the design itself — both
language ports share them:

- **`run_command`'s timeout doesn't fully clean up the child process
  tree.** Python's `subprocess.run(..., timeout=...)` does kill the
  immediate shell process on timeout (slightly better than Ruby's
  `Timeout.timeout`, which only abandons the waiting thread and leaves
  the real OS process running) — but a background `&`-ed grandchild
  spawned by that shell can still survive. Full process-group cleanup is
  out of scope for this iteration, matching Ruby's own framing.
- **`allowed_commands` is a first-token name filter, not a shell-aware
  sandbox.** `"echo hi; rm -rf /"` passes the allow-list check (first
  token is `echo`) and then both commands execute, since the full string
  is still handed to a shell. Fine for keeping an agent from typing `rm`
  by name; not a boundary against command chaining/injection.
- **A missing/mismatched argument to a tool call raises instead of
  returning an error string.** `Registry.dispatch` calls
  `tool.block(**args)` outside of any tool's own try/except, so a missing
  required keyword (e.g. `write_file` without `content=`) raises a
  `TypeError` there rather than producing an `"error: ..."` string.
  Not fatal — `Agent._handle_tool_calls` already catches `Exception`
  broadly and turns it into an `"ERROR: TypeError: ..."` tool result —
  but the error *shape* differs from every other failure mode these
  tools produce. Same architectural gap as Ruby's `ArgumentError` case.
- **MCP tool registration has a side effect the other two modules don't**:
  it spawns a subprocess and performs a live handshake during
  registration (agent setup), before the first model call, rather than
  lazily on first tool use like `file_system`/`shell`. A failed server
  degrades gracefully (caught, warned, simply absent), but every
  `boukensha.run()`/`.repl()` with a configured MCP server pays that
  connection cost up front.
- **Unlike Ruby's `MudManager::Mcp::Client`, an empty/missing `command:`
  is a hard error, not a silent default.** Ruby's client lives inside the
  `mud_manager` gem and can reasonably default to its own bundled
  executable when `command:` is blank; this module has no
  gem-equivalent package to default to. This repo's own `settings.yaml`
  always sets `command:` explicitly, so it's unaffected in practice.
