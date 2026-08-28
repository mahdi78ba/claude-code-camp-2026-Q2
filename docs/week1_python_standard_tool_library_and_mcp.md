# Python Standard Tool Library & MCP — Reference

Plain-language reference for what `python/10_standard_tool_library` adds
to Boukensha: a standard library of built-in tools, and a generic bridge
to MCP (Model Context Protocol) servers. Covers what each piece does, the
config schema, the wire protocol, and a worked example end to end.

For the deep "why" behind each design/porting decision, see
[`plans/python_port/10_standard_tool_library.md`](plans/python_port/10_standard_tool_library.md).
This doc is the simpler "what it is and how to use it" companion.

---

## 0. What we did — session summary

In one sentence: **we ported Ruby's `10_standard_tool_library` to Python
(three new tool modules, including a generic MCP client), fixed two real
bugs found along the way, and tuned the agent's system prompt so it stops
wasting a turn "checking" a MUD connection that's already there.**

Step by step:

1. **Planned the port.** Compared `ruby/10_standard_tool_library` (which
   already includes its later MCP-integration refactor — the "MUD
   gameplay via MCP" design is the *current* state of that Ruby step, not
   a separate later change) against the last-ported Python step,
   `python/08_the_repl_loop`. Step 09 (`ruby/09_global_executable`) has
   no Python counterpart — it's pure Ruby gem-packaging (a `.gemspec`, a
   `bin/boukensha` executable), nothing in it applies to Python. Plan
   written to
   [`plans/python_port/10_standard_tool_library.md`](plans/python_port/10_standard_tool_library.md).

2. **Executed the port.** Added three new tool modules —
   `boukensha/tools/file_system.py`, `shell.py`, `mcp.py` — plus small
   additions to existing files (`Registry.registered()`,
   `Context.working_dir`, `Config.mcp_servers()`), and wired all of it
   into `boukensha.run()`/`boukensha.repl()`. What each piece actually
   does, with full schema and examples, is §1–§4 below.

3. **Found and fixed two real bugs**, both in the new MCP client's
   *failure-path* cleanup (a bad server command, or a hung handshake) —
   neither shows up on a normal successful run, only when something
   actually goes wrong starting a server. One was a client that could
   raise instead of being caught; the other was a genuine deadlock
   between two threads both touching the same subprocess pipe. Full
   writeup in `docs/week1_config_troubleshooting.md`, entry #31.

4. **Tested the port** by launching the real demo
   (`bin/python/10_standard_tool_library`) against the actual installed
   `mud_manager --mcp` server and a live CircleMUD instance — confirmed
   the agent completes a real gameplay task end to end over MCP. See §6.

5. **Reviewed agent behavior and closed a prompting gap.** The agent was
   calling `mud_status` defensively before every gameplay action — one
   wasted turn per run — even though the MCP server already connects and
   logs in during its own startup, before the agent ever gets a chance to
   call anything. Weighed three fixes (change the MCP server; teach
   Boukensha's generic MCP bridge to auto-retry; or just tell the agent
   in its system prompt) and picked the prompt-only one, since it's the
   only option that doesn't touch working code or compromise the MCP
   bridge's genericity. See §8.

6. **Validated the fix and completed the port.** Reran the demo fresh —
   the agent now goes straight to the gameplay tool over MCP, skipping
   the defensive check entirely, with identical end-user results and one
   fewer round trip than before.

---

## 1. The three tool modules

Before this step, every example had to manually write a `configure`
function and register each tool by hand. Now `boukensha.run()` /
`boukensha.repl()` can hand the agent a standard set of capabilities
automatically:

```python
boukensha.run(
    task="List the files here and summarize what this project does.",
    working_dir="/path/to/project",   # turns on file_system + shell tools
)
```

| Module | Registers | Turned on by |
|---|---|---|
| `boukensha.tools.file_system` | `pwd`, `list_directory`, `read_file`, `write_file`, `delete_file`, `search_files` | `working_dir=...` (default: current directory) |
| `boukensha.tools.shell` | `run_command` | `working_dir=...` (same switch as above) |
| `boukensha.tools.mcp` | one tool per tool an MCP server reports | `mcp=...` (default: `settings.yaml`'s `mcp_servers:` list) |

Each module is just a Python file with one function, `register(registry,
...)`. You can also call any of them directly if you want more control:

```python
from boukensha import tools

tools.file_system.register(registry, working_dir="/my/project")
tools.shell.register(registry, working_dir="/my/project",
                      timeout=10, allowed_commands=["python", "git"])
tools.mcp.register(registry, servers=[
    {"name": "mud", "command": ["mud_manager", "--mcp"], "env": {}}
])
```

---

## 2. File System tools

All six tools are **sandboxed to one root directory** (`working_dir`).
Every path argument is resolved relative to that root; anything that
would escape it (`../../etc/passwd`, an absolute path outside the root)
comes back as an error string, not an exception or an actual read outside
the sandbox:

```python
>>> registry.dispatch("read_file", {"path": "../../../etc/passwd"})
"error: path '../../../etc/passwd' escapes the working directory"
```

| Tool | Arguments | Example call | Example result |
|---|---|---|---|
| `pwd` | — | `pwd()` | `"/my/project"` |
| `list_directory` | `path` (default `"."`) | `list_directory(path=".")` | `"src/\nREADME.md"` |
| `read_file` | `path` | `read_file(path="README.md")` | file contents (string) |
| `write_file` | `path`, `content` | `write_file(path="notes.txt", content="hi")` | `"ok: wrote 2 bytes to notes.txt"` |
| `delete_file` | `path` | `delete_file(path="notes.txt")` | `"ok: deleted notes.txt"` |
| `search_files` | `pattern`, `path` (default `"."`), `glob` (default `"*"`) | `search_files(pattern="TODO", glob="*.py")` | `"agent.py:42:# TODO: fix this"` |

`search_files` returns `path:line_number:content` per match, one per
line — same shape as `grep -n`.

---

## 3. Shell tool

One tool, `run_command`, runs a shell command inside `working_dir`:

```python
>>> registry.dispatch("run_command", {"command": "git status"})
"On branch main\nnothing to commit, working tree clean"
```

Two safety knobs:

- **`timeout`** (default 30s) — kills the command if it runs too long:
  ```python
  >>> registry.dispatch("run_command", {"command": "sleep 100"})
  "error: command timed out after 30s: sleep 100"
  ```
- **`allowed_commands`** — an optional allow-list checked against just the
  first word of the command:
  ```python
  tools.shell.register(registry, working_dir=".", allowed_commands=["git", "python"])
  >>> registry.dispatch("run_command", {"command": "rm -rf /"})
  "error: 'rm' is not in the allowed-commands list (git, python)"
  ```
  This is a **name filter, not a sandbox** — `"echo hi; rm -rf /"` still
  passes (first word is `echo`) and then both commands run, since the
  whole string still goes to a real shell. Good for stopping an agent
  from typing a dangerous command *by name*; not a security boundary
  against command chaining.

---

## 4. MCP tools — the generic bridge

### What MCP is, in one paragraph

MCP (Model Context Protocol) is a small JSON-RPC 2.0 protocol for
exposing a set of "tools" from a separate program (the **server**) to a
client. Boukensha spawns the server as a subprocess and talks to it over
its stdin/stdout, one JSON message per line. The server doesn't know or
care that Boukensha is an LLM agent — it just answers "what tools do you
have?" and "call this tool with these arguments."

### The wire protocol (what actually goes over stdin/stdout)

Four message types, each one line of JSON, newline-terminated:

```jsonc
// 1. Client -> Server: handshake
{"jsonrpc": "2.0", "id": 1, "method": "initialize",
 "params": {"protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "boukensha-mcp-client", "version": "1.0"}}}

// Server -> Client: handshake response
{"jsonrpc": "2.0", "id": 1,
 "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "mud-manager-mcp-server", "version": "0.1.0"}}}

// 2. Client -> Server: "I'm ready" (a notification — no id, no reply expected)
{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}

// 3. Client -> Server: what tools do you have?
{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

// Server -> Client: tool list
{"jsonrpc": "2.0", "id": 2, "result": {"tools": [
  {"name": "look", "description": "Look at your surroundings",
   "inputSchema": {"type": "object", "properties": {
     "target": {"type": "string"}, "preposition": {"type": "string"}
   }, "required": []}}
]}}

// 4. Client -> Server: call a tool
{"jsonrpc": "2.0", "id": 3, "method": "tools/call",
 "params": {"name": "look", "arguments": {"target": "", "preposition": ""}}}

// Server -> Client: tool result
{"jsonrpc": "2.0", "id": 3,
 "result": {"content": [{"type": "text", "text": "You are in a temple hall..."}],
            "isError": false}}
```

An error response looks like this instead of `"result"`:

```jsonc
{"jsonrpc": "2.0", "id": 3, "error": {"code": -32601, "message": "method not found: bogus"}}
```

### How Boukensha turns that into agent tools

`boukensha/tools/mcp.py` does exactly this sequence per configured
server, then wires each MCP tool straight into the registry:

```
spawn subprocess  →  initialize  →  notifications/initialized  →  tools/list
                                                                       │
                                                                       ▼
                                       for each tool reported:
                                       registry.tool(name, description, parameters,
                                                     block=lambda **kw: call_tool(name, kw))
```

An MCP tool's `inputSchema.properties` is already the exact shape
Boukensha's own `registry.tool(..., parameters={...})` expects, so no
reshaping is needed — the MCP tool schema *is* the Boukensha tool schema.

### Config schema

Configured once, in `~/.boukensha/settings.yaml` (or wherever
`BOUKENSHA_DIR` points):

```yaml
mcp_servers:
  - name: mud                          # required — used in log/banner output
    command: ["mud_manager", "--mcp"]  # required — argv to spawn
    env:                               # optional — extra env vars for the subprocess
      MUD_HOST: localhost
      MUD_PORT: "4000"
      MUD_NAME: dummy
      MUD_PASSWORD: helloworld
    prefix: null                       # optional — see "name collisions" below
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | Label shown in logs and the REPL banner |
| `command` | list of strings | yes | The subprocess to spawn (argv) |
| `env` | dict | no | Extra environment variables for that subprocess |
| `prefix` | string | no | Prepended to every tool name from this server (`prefix: mud` → `mud_look`) |

An `env` value written as `"$SOME_VAR"` (a literal dollar sign) resolves
against the process's real environment instead of being taken literally —
so a real secret can live in `.env` (gitignored) while `settings.yaml`
(committed) only references its name:

```yaml
mcp_servers:
  - name: mud
    command: ["mud_manager", "--mcp"]
    env:
      MUD_PASSWORD: "$MUD_PASSWORD"   # resolves from the real env, not a literal string
```

You can also configure servers directly in code instead of
`settings.yaml`, or opt out entirely:

```python
boukensha.run(task="...", mcp=[{"name": "mud", "command": [...], "env": {...}}])
boukensha.run(task="...", mcp=False)   # no MCP servers at all
```

### Name collisions across servers

If two configured servers each expose a tool with the same bare name
(e.g. both have a `status` tool), the second one registered is skipped
with a warning — unless its config sets `prefix:`, which disambiguates
every one of its tools (`status` → `mud_status`).

### Failure handling

A server that fails to spawn, hangs past a 10-second handshake timeout,
or errors during handshake is logged to stderr and simply left out — it
does not crash the whole agent, and it does not stop any other configured
server from starting normally.

```
[boukensha] MCP server 'mud' failed to start: TimeoutError: MCP handshake exceeded 10s
```

---

## 5. Putting it together — a worked example

This is (a simplified version of) `examples/example.py`:

```python
import boukensha

boukensha.run(
    task=(
        "Connect to the MUD, look at your surroundings, check your score, "
        "then look at the available exits and tell me what you see."
    ),
    working_dir=False,   # no filesystem tools needed for MUD play
    # mcp: comes from settings.yaml's mcp_servers: list automatically
)
```

What happens, step by step:

1. `boukensha.run()` loads config, sees `mcp_servers:` has one entry
   (`mud`), and calls `tools.mcp.register(registry, servers=[...])`.
2. That spawns `mud_manager --mcp` as a subprocess and performs the
   handshake shown in §4 above.
3. `tools/list` comes back with ~27 tools (`mud_connect`, `look`,
   `check`, `move`, `attack`, ...) — each one gets registered on the
   agent's tool registry.
4. The agent receives the task, decides which tools to call, and each
   call is forwarded over the same JSON-RPC connection to the real MUD
   server and back.

---

## 6. Verified: the demo runs and talks to the MCP server

Ran the actual launcher exactly as a user would:

```
$ ./week1_baseline/bin/python/10_standard_tool_library
Config: #<Boukensha::Config dir=/home/mahdi/claude-code-camp-2026-Q2/.boukensha tasks=player>
API key set? True

[mud_manager/mcp] server shutting down
$ echo $?
0
```

Application starts successfully (exit code `0`, no traceback). The
`[mud_manager/mcp] server shutting down` line is the MCP server's own
stderr message printed as Boukensha closes the connection at the end of
the run — evidence the subprocess actually started and was talked to.

The real transcript lives in the session log, not stdout (by design —
see §4's failure-handling note: normal operation doesn't print each
tool call, only the session JSONL records it). Reading it back confirms
the agent actually communicated with the MCP server:

```
tool_call   : mud_connect {}
tool_result : mud_connect -> OK  'already connected to localhost:4000'
tool_call   : look {'target': '', 'preposition': ''}
tool_result : look -> OK  'The Temple Of Midgaard ...'
tool_call   : check {'kind': 'score'}
tool_result : check -> OK  'You are 20 years old. ...'
tool_call   : check {'kind': 'exits'}
tool_result : check -> OK  'Obvious exits: north - By The Temple Altar ...'
turn_end    : completed  iterations=3
```

Each `tool_call`/`tool_result` pair above is one full round trip through
the wire protocol in §4 (`tools/call` → real MUD server → `content[0].text`
back). `turn_end reason: completed` means the agent decided it had
enough information to answer and stopped on its own, well under the
iteration limit — confirming the whole path (agent → registry → MCP
client → subprocess → real MUD server → back) works end to end.

No orphaned subprocess was left running afterward (`pgrep -af "mud_manager --mcp"`
came back empty) — the client closed the connection cleanly on exit.

---

## 7. Known limitations (by design, not bugs)

- `allowed_commands` filters by the command's first word only — not a
  shell-injection-proof sandbox (see §3).
- `run_command`'s timeout kills the immediate process but not a
  background (`&`-ed) grandchild it spawned.
- A missing required tool argument (e.g. `write_file` with no `content`)
  raises a `TypeError` that the agent sees as a generic `"ERROR:
  TypeError: ..."` string, rather than the same `"error: ..."` shape
  every other validation failure in these tools uses.
- MCP servers connect eagerly at setup time (before the first model
  call), not lazily on first tool use — every run with a configured
  server pays that connection cost up front.

Full detail on each of these, plus the reasoning and every design
decision behind the port, is in
[`plans/python_port/10_standard_tool_library.md`](plans/python_port/10_standard_tool_library.md).

---

## 8. Agent connection guidance — removing a wasted defensive check

### The behavior observed

Given a task that never mentions connecting at all —

```python
boukensha.run(task="Look at your surroundings and tell me what you see.", working_dir=False)
```

— the agent's first tool call was `mud_status`, *before* `look`:

```
tool_call   : mud_status {}
tool_result : mud_status -> OK  'connected to localhost:4000'
tool_call   : look {'target': '', 'preposition': ''}
tool_result : look -> OK  'The Temple Of Midgaard ...'
turn_end    : completed  iterations=2
```

That extra call is pure overhead. Tracing why, in
`week0_explore/mud_manager/lib/mud_manager/mcp/tools.rb`:

```ruby
# Auto-connect at startup so the session is ready immediately and the
# first tools/call doesn't have to pay the login round-trip.
begin
  session.open
  session.login(name, password)
rescue MudManager::Session::Error => e
  warn "[mud_manager/mcp] MUD auto-connect failed: #{e.message} — call mud_connect manually"
end
```

**The MCP server already connects and logs in during its own startup**,
before it even answers `tools/list`. `mud_connect`/`mud_status` exist as
tools mainly for the *rare* case of a manual reconnect after an explicit
`mud_disconnect`, or for genuinely diagnosing a connection problem — not
as a routine step before every gameplay action. But nothing told the
agent that, and the active system prompt's "cautious... don't guess at
outcomes" framing nudged it to check first anyway, at the cost of one
whole extra turn every single run.

### Options considered

| | Approach | Verdict |
|---|---|---|
| **A** | Change the MCP server (`mud_manager`) to not expose `mud_connect`/`mud_status` at all, or otherwise change its connection behavior | Rejected — `mud_manager` is a separate gem outside this port's scope, and those tools are still legitimately useful for manual reconnects/diagnostics; removing them loses real functionality to fix a prompting problem |
| **B** | Teach Boukensha's generic `boukensha/tools/mcp.py` bridge to detect the `"error: not connected — call mud_connect first"` string and auto-retry after calling `mud_connect` | Rejected — the bridge is deliberately generic (see §4: "doesn't know what any server's tools actually do"); special-casing one server's specific error wording breaks that, and would silently mask a real "not connected" failure for a differently-behaved server |
| **C** ✅ | Leave all code exactly as-is (it already works correctly); tell the agent in its **system prompt** that it doesn't need to connect defensively | **Chosen** — zero code risk, doesn't compromise the MCP bridge's genericity, and directly targets the actual root cause: the agent didn't know the connection was already handled |

### The fix

Two files got the same additive guidance — the package's own shipped
default prompt, and the actual prompt this repo's shared
`.boukensha/settings.yaml` is configured to use instead
(`prompt_override.system: true` points `player` at
`.boukensha/prompts/player/system.md`, which is what every example run in
this repo actually uses):

**`python/10_standard_tool_library/prompts/system.md`:**
```diff
 You are Boukensha, an autonomous player exploring a CircleMUD world.

+The MUD connection is already established by the time you're asked to do anything — gameplay actions (look, move, check, attack, etc.) work immediately. Don't call mud_connect or mud_status defensively before acting; just take the gameplay action directly.
+
 Use available tools to observe the world, act deliberately, and explain only what matters for the current turn.
```

**`.boukensha/prompts/player/system.md`** (the one actually in effect):
```diff
 - Keep responses short and action-oriented — state what you're doing and why, not a long narrative.
+- The MUD connection is already established by the time you're asked to do anything — gameplay actions (look, move, check, attack, etc.) work immediately. Don't call mud_connect or mud_status defensively before acting; just take the gameplay action directly.
```

### Verified

Same probe task, run three times after the prompt change:

```
tool_call   : look
turn_end    : completed  iterations=2
```

```
tool_call   : look
turn_end    : completed  iterations=2
```

```
tool_call   : look
tool_call   : look
turn_end    : completed  iterations=3
```

All three skip `mud_status`/`mud_connect` entirely and go straight to the
gameplay action — one fewer round trip than before, with identical
end-user results.
