# MCP Servers & the Agent's Components — What We Have, How to Add Any Server, and What Makes This Agent *This* Agent

Two questions, answered together because they're the same mechanism seen
from two sides: **how many MCP servers does `boukensha` actually run**, and
**what, structurally, is "the agent"** — the specific set of components
that make it work, and why an MCP server plugs into that set without any
of them changing. Grounded in the current code
(`ruby/12_context`/`python/12_context`) and the real config this repo runs.

If you haven't read it yet, [`week1_agent_loop_explained.md`](week1_agent_loop_explained.md)
covers the loop itself (registering a tool, dispatching it, stop
conditions) — this doc assumes that mechanism and focuses on **where tools
come from**, MCP being one source of them.

---

## The short answers, up front

| Question | Answer |
|---|---|
| How many MCP servers are implemented (i.e. the *bridge* code that can talk MCP)? | **One bridge, usable for any number of servers** — `Tools::Mcp` (Ruby) / `boukensha.tools.mcp` (Python). It's generic; it doesn't ship bundled with any particular server's logic. |
| How many MCP servers are actually **configured and running** in this repo? | **One** — `mud`, in `.boukensha/settings.yaml`'s `mcp_servers:` list, spawning `mud_manager --mcp` and exposing **27 tools** (`mud_connect`, `look`, `move`, `attack`, `cast_spell`, `shop`, ... — see §4). |
| Do we have an `mcp_filesystem` server? | **No.** Filesystem access here (`pwd`/`read_file`/`write_file`/`delete_file`) is a **native, hand-written tool set** (`Tools::FileSystem`), registered directly on the `Registry` — not an MCP server at all. Nothing stops you from *also* configuring the standard `@modelcontextprotocol/server-filesystem` MCP server (or any other MCP server) — see §6 for exactly how, with zero code changes. |
| How do I add a new MCP server? | Add one entry to `mcp_servers:` in `settings.yaml`. That's it — no Ruby/Python code to write. See §5–§6. |

---

## 1. What an MCP server actually is, in plain terms

MCP (Model Context Protocol) is a small, provider-neutral wire format for
"here is a list of tools, here's how to call one, here's the result" — the
same *shape* of information a Boukensha `Tool` already carries
(`name`, `description`, a parameters schema, a way to call it), just
spoken over a process boundary instead of an in-process Ruby/Python block.
An **MCP server** is any program that:

1. Is started as a subprocess.
2. Speaks JSON-RPC 2.0, one message per line, over its own stdin/stdout.
3. Answers three requests: `initialize` (handshake), `tools/list` (what
   can you do?), `tools/call` (do it, here are the arguments).

That's the entire contract. It doesn't matter what language the server is
written in, or what it actually does behind that interface — a MUD client,
a filesystem sandbox, a database, a web browser. Anything that speaks this
contract is "an MCP server," and anything that can spawn a process and
follow that contract is "an MCP client."

---

## 2. The schema — one config entry per server

Every MCP server this app knows about is one entry in `settings.yaml`'s
`mcp_servers:` list. This is the **entire configuration surface** — nothing
else needs editing to add a server:

```yaml
mcp_servers:
  - name: mud                        # required — used as a log label and for
                                      # collision warnings; also the default
                                      # tool-name prefix if you ever want one
    command: ["mud_manager", "--mcp"]  # required (Python) / optional (Ruby,
                                        # falls back to this exact default)
    env:                              # optional — merged into the subprocess's
      MUD_HOST: localhost             # environment, additively (PATH etc.
      MUD_PORT: "4000"                # from the parent process still work)
      MUD_NAME: dummy
      MUD_PASSWORD: helloworld
    # prefix: "mud"                   # optional — see §6, only needed to
                                       # resolve a tool-name collision
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | A label for logs/warnings — not sent to the model |
| `command` | array of strings | The subprocess argv to spawn, e.g. `["npx", "-y", "some-mcp-server"]` |
| `env` | map | Extra environment variables for that one subprocess. A value written as `"$SOME_VAR"` is resolved against the real environment (loaded from `.env`) rather than taken literally — so a real secret never has to sit in `settings.yaml` in plaintext |
| `prefix` | string, optional | Prepended to every tool name from this server (`"look"` → `"mud_look"`) — an opt-in escape hatch for when two servers (or a server and a native tool) expose the same tool name |

The **currently live config in this repo** has exactly one entry — `mud` —
which is why the answer to "how many MCP servers do we have" is 1, not the
number of tools it exposes (27) and not the number of *backends* (5,
unrelated concept — see §7).

---

## 3. The generic bridge — one piece of code, any server

`Tools::Mcp.register` (Ruby: `ruby/12_context/lib/boukensha/tools/mcp.rb`;
Python: `python/12_context/boukensha/tools/mcp.py`) is the **only** code
that knows how to talk MCP. It is deliberately domain-blind — it has never
heard of a MUD, a filesystem, or anything else a server might do:

```ruby
# Called once, at startup, with the whole mcp_servers: list:
Boukensha::Tools::Mcp.register(registry, servers: [
  { name: "mud", command: ["mud_manager", "--mcp"], env: {...} },
  # ...any number of additional server hashes go here, same shape
])
```

For **each** server in the list, it does exactly four things:

```
1. spawn the subprocess (server[:command], server[:env])
2. handshake  ── MCP's "initialize" request, 10-second timeout
3. tools/list ── ask the server what tools it has
4. for each tool the server reports:
      registry.tool(name, description: tool.description,
                     parameters: tool.inputSchema.properties) do |**args|
        client.call_tool(tool.name, args)   # forward the call over MCP, return the text
      end
```

That fourth step is the entire idea: **every tool an MCP server reports
becomes a completely normal Boukensha `Tool`**, registered on the exact
same `Registry` a hand-written tool would use (§3a of
[`week1_agent_loop_explained.md`](week1_agent_loop_explained.md)). Its
"block" just happens to forward the call across a process boundary instead
of running Ruby/Python directly — the `Agent` and `Registry` cannot tell
the difference, and never try to. This is *why* adding a new MCP server
never requires touching `agent.rb`/`agent.py`, `registry.rb`/`registry.py`,
or anything backend-related: the bridge is the only thing that ever learns
a new server exists, and it already knows how to handle one generically.

**Failure isolation:** a server that fails to spawn, times out its
handshake, or errors while listing tools is warned about on stderr and
simply *absent* from the result — `register` returns `[{name:, client:},
...]` only for the servers that actually started. One misconfigured server
(bad command, MUD not reachable, wrong password) does not prevent any
other configured server, or the app itself, from starting.

---

## 4. What's actually running right now: the `mud` server, 27 tools

`week0_explore/mud_manager` (the same gem week 0 built to speak CircleMUD)
ships its own MCP server executable, `mud_manager --mcp`, wrapping every
MUD action as one MCP tool:

```
mud_connect · mud_disconnect · mud_status · look · examine · check · move ·
flee · set_position · track · attack · skill_strike · consider · say ·
tell · channel_say · get_item · drop_item · put_item · equip_item ·
consume_item · cast_spell · use_magic_item · shop · practice ·
save_character · send_raw
```

Boukensha's own agent contains **zero** MUD-specific code — no `move`
method, no telnet handling, nothing. All of that lives inside
`mud_manager`; Boukensha only ever sees "the `mud` server reported 27
tools with these names/descriptions/schemas," exactly the same way it
would see any other server. This was a whole multi-part design effort
during the week (design → self-review caught a bug in the plan itself →
implement → verify against a real MUD → generalize) — the full story is in
[`week1_journal.md`](week1_journal.md#the-mcp-integration-arc--five-parts-one-running-story).

---

## 5. What's *not* an MCP server: native tools

Two other tool sources exist, and it's worth being precise that neither is
MCP, because this is exactly where the `mcp_filesystem` question lands:

| Tool set | How it's built | Registered by |
|---|---|---|
| `Tools::FileSystem` (`pwd`, `read_file`, `write_file`, `delete_file`) | Plain Ruby/Python code in this repo, in-process | `Tools::FileSystem.register(registry, working_dir: ...)` |
| `Tools::Shell` (`run_command`) | Plain Ruby/Python code, in-process | `Tools::Shell.register(registry, working_dir:, allowed_commands:)` |
| `Tools::Mcp` (any server's tools, e.g. `mud`'s 27) | Proxied over a subprocess, MCP wire format | `Tools::Mcp.register(registry, servers: cfg.mcp_servers)` |

All three land in the exact same place — `Context#tools`, a flat
`{name => Tool}` hash — and are indistinguishable to `Agent`/`Registry`
once registered (see §7). `working_dir:` (default: the current directory)
turns on the first two automatically when you call `Boukensha.run`/`.repl`;
`mcp:` (default: whatever `settings.yaml`'s `mcp_servers:` says) turns on
the third. Both can be disabled explicitly (`working_dir: false`,
`mcp: false`).

**So: do we have `mcp_filesystem`? No — our filesystem access predates
this app treating MCP as the tool boundary, and was never rebuilt as an
MCP server, because it didn't need to be** (unlike MUD gameplay, which
specifically needed to be shared, protocol-correct code reachable from
*both* Ruby and Python — see §4's linked doc for why that mattered enough
to justify the MCP arc). Nothing architecturally prevents adding the
official filesystem MCP server anyway — walked through next.

---

## 6. Adding *any* MCP server — worked example (the official filesystem server)

This is the generic recipe — the same four steps for literally any MCP
server that exists, demonstrated with `@modelcontextprotocol/server-filesystem`
(the standard, widely-used reference filesystem server, run via `npx`):

**Step 1 — find out how to run it.** Every MCP server documents its own
launch command and arguments; this one takes the allowed root directory as
an argv argument.

**Step 2 — add one entry to `settings.yaml`:**

```yaml
mcp_servers:
  - name: mud
    command: ["mud_manager", "--mcp"]
    env: { MUD_HOST: localhost, MUD_PORT: "4000", ... }

  - name: fs                                             # ← new
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/home/you/project"]
    prefix: "mcpfs"                                      # ← see step 3
```

**Step 3 — resolve the name collision.** The official filesystem server
also exposes tools named `read_file`/`write_file` — the *exact* names our
own native `Tools::FileSystem` already registered. Without `prefix:`, the
bridge's collision check (§3, and `week1_mcp_journal`'s coverage of this
same guard) would print a warning and **skip** the MCP server's
conflicting tools rather than silently shadowing the native ones:

```
[boukensha] MCP server "fs": tool "read_file" collides with an
already-registered tool — skipped (use prefix: on this server's config
entry to disambiguate)
```

`prefix: "mcpfs"` turns that server's tools into `mcpfs_read_file`,
`mcpfs_write_file`, etc. — both tool sets now coexist, and the model sees
both `read_file` (native, sandboxed to `working_dir`) and
`mcpfs_read_file` (proxied through the external server, sandboxed to
whatever root you passed it in step 2) as distinct, separately-described
options.

**Step 4 — nothing else.** Run `Boukensha.run`/`.repl` (or the REPL/TUI)
as normal. On startup, `Tools::Mcp.register` spawns both configured
servers, handshakes with each, and registers whatever tools each reports —
your new server's tools are now callable by the model exactly like every
other tool, with no Ruby/Python code written for this step at all.

**The general recipe, stripped of the filesystem example:** *any* command
that can be spawned as a subprocess and speaks MCP over stdio can be added
this way — a database server, a web-search server, a browser-automation
server, one you write yourself. One `mcp_servers:` entry, `prefix:` only if
a name collides with something already registered, done.

---

## 7. What makes *this* agent this agent — the component schema

Zooming out from "how tools get in": the specific, load-bearing design
decisions that define `Boukensha::Agent` as an object, and why an MCP
server (or any tool source) can plug in without any of them changing.

```
                     ┌─────────────────────────────────────────┐
                     │              Context                    │
                     │  system prompt · messages[] · tools{}    │
                     │  ← the ONLY object that survives a turn  │
                     └───────────────┬───────────────────────────┘
                                     │ read/write by all of:
        ┌────────────┬──────────────┼──────────────┬────────────┐
        ▼            ▼              ▼              ▼            ▼
    Registry     Backend (1 of 5)  PromptBuilder  Client      Agent
  name→Tool      Anthropic/OpenAI/  pure          HTTP POST   the loop:
  lookup +       Gemini/Ollama/     delegation     + retry     call → branch
  dispatch       OllamaCloud                                   on stop_reason
        ▲
        │ tools registered here come from THREE interchangeable sources:
        │   Tools::FileSystem.register(...)   — native
        │   Tools::Shell.register(...)        — native
        │   Tools::Mcp.register(...)          — one proxy Tool per MCP tool
        │  Registry/Agent cannot tell which source a given Tool came from.
```

### `Agent`'s own constructor — its actual, literal dependency list

```ruby
Agent.new(
  context:,                          # required — the shared state (§ above)
  registry:,                         # required — tool lookup + dispatch
  builder:,                          # required — talks to whichever Backend
  client:,                           # required — HTTP transport
  logger:            Logger.new,     # optional — structured .jsonl events
  max_iterations:     25,            # optional — action-count ceiling
  max_turn_tokens:    nil,           # optional — spend ceiling (0/nil = off)
  max_output_tokens:  nil            # optional — per-call reply-length cap
)
```

That's the complete list. Notice what's **absent**: no `provider:`
argument, no `mcp:` argument, no knowledge of MCP at all. `Agent` only ever
calls `@registry.dispatch(name, args)` — it has no idea, and no way to
find out, whether the tool that runs is a block of local Ruby/Python code
or a proxy that shells out to a subprocess over JSON-RPC. That indifference
is the specific, deliberate property that makes §6's four-step recipe work
without touching this class.

### The four properties that define this agent specifically

1. **One `Agent` class, five interchangeable providers.** Swapping
   `Backends::Anthropic` for `Backends::Gemini` changes zero lines in
   `agent.rb`/`agent.py` — every backend normalizes its provider's wire
   format into the same `{stop_reason, content}` shape before `Agent` ever
   sees a response (full comparison table in
   [`week1_agent_loop_explained.md`](week1_agent_loop_explained.md#2-the-schema--the-shapes-involved)).
2. **`Context` is the only stateful object.** `Agent`, `Client`, `Backend`
   are all cheap/disposable/reconstructible; only `Context#messages` and
   `Context#tools` persist across a turn (and across turns, in a REPL).
   Full treatment in
   [`week1_context_management_explained.md`](week1_context_management_explained.md).
3. **Tools are a single flat namespace, source-blind.** `Context#tools` is
   one `{name => Tool}` hash whether a `Tool` came from a hand-written
   block, `Tools::FileSystem`, or an MCP proxy — this doc's §3–§6 is the
   direct consequence of that design choice, not a special case bolted on
   for MCP.
4. **Limits are triggers, not exceptions.** `max_iterations`/
   `max_turn_tokens` reaching zero never raises — it swaps to one
   tools-disabled wind-down call so a turn always ends in a real reply
   (detailed in
   [`week1_agent_loop_explained.md`](week1_agent_loop_explained.md#6-max_iterations-max_turn_tokens-and-what-stop-really-means)).

### Seeing an MCP-backed tool call — indistinguishable in the log, on purpose

Because §3's bridge produces a completely normal `Tool`, an MCP-proxied
tool call looks **identical** in the session log to a native one — same
`tool_call`/`tool_result` event shape covered in
[`week1_agent_loop_explained.md`](week1_agent_loop_explained.md#b-the-session-log--one-json-object-per-line-forever),
no `"via": "mcp"` marker anywhere:

```jsonc
{"phase":"tool_call","name":"look","args":{}, ...}
{"phase":"tool_result","name":"look",
 "result":"You are standing in the town square...","ok":true,"error":null, ...}
```

`look` here is one of the `mud` server's 27 MCP tools — nothing in this
line reveals that its `tool.block` shelled out over a subprocess rather
than running local code. That invisibility is intentional: it's the same
"the agent doesn't know or care where a tool's implementation lives"
property from §7 above, visible end-to-end in the one place a human
actually inspects a run.

---

## 8. Cheat sheet

```
how many MCP servers configured right now →  1 ("mud", .boukensha/settings.yaml)
how many tools that one server exposes    →  27 (mud_connect, look, move, attack, ...)
do we have an MCP filesystem server       →  no — filesystem access is native (Tools::FileSystem),
                                              not MCP; adding one is possible, see §6
add a new MCP server                      →  one entry under mcp_servers: in settings.yaml — no code
resolve a tool-name collision             →  prefix: "something" on that server's config entry
the bridge code (all servers share it)    →  Tools::Mcp.register / boukensha.tools.mcp.register
what Agent knows about MCP                →  nothing — it only ever calls Registry#dispatch
what Agent's constructor needs            →  context, registry, builder, client (+ optional logger/limits)
a bad/unreachable server                  →  warned on stderr, skipped — doesn't take the app down
```

---

## Go deeper

- [`week1_agent_loop_explained.md`](week1_agent_loop_explained.md) — tool
  registration, dispatch, stop conditions; this doc's direct companion.
- [`week1_journal.md`](week1_journal.md#the-mcp-integration-arc--five-parts-one-running-story) —
  the full narrative of *why* MCP was chosen as the tool boundary and how
  the design/implementation/merge arc actually went, across ~20 docs.
- [`week1_mcp_generic_implementation.md`](week1_mcp_generic_implementation.md),
  [`week1_mcp_genericity_review.md`](week1_mcp_genericity_review.md) — the
  audit pass that specifically checked this bridge for MUD-specific
  leakage before calling it "generic."
- [`week1_mcp_server_config_update.md`](week1_mcp_server_config_update.md) —
  when `settings.yaml` moved from a MUD-specific `mud:` block to the
  generic `mcp_servers:` list this doc's schema describes.
- [`week1_python_standard_tool_library_and_mcp.md`](week1_python_standard_tool_library_and_mcp.md) —
  plain-language reference for the Python port of everything in §3–§5.
- [`week1_context_management_explained.md`](week1_context_management_explained.md) —
  the other half of "what makes this agent specific": how `Context` is the
  one piece of state everything else is built around.
