# MCP Architecture Design (Part 2)

Builds on the decision in `docs/week1_mcp_integration_plan.md` (MCP is the
communication layer). This document is the 2.1/2.2/2.3 deliverable: how the
pieces are separated, who owns what, and what moves behind the MCP boundary.
Still no server code — this fixes the shape before Part 3 implements it.

## Design goals, restated as constraints

- **2.1** — a language-specific agent (Ruby today, Python next, anything
  after that) must contain **zero** MUD-protocol code: no socket, no telnet
  IAC handling, no login state machine, no CircleMUD command syntax.
- **2.2** — exactly **one** component ever holds the live `MudManager::Session`
  (the open socket + logged-in character): the MCP server process. No agent,
  in any language, ever touches a MUD socket directly, ever.
- **2.3** — gameplay capabilities are visible to agents only as MCP tools
  (`tools/list` / `tools/call`), never as a library an agent links against
  and calls in-process.

## Component diagram

```
 Ruby agent (Boukensha)      Python agent (boukensha)      <future agent>
        |                            |                            |
        |  MCP client (stdio)        |  MCP client (stdio)        |
        v                            v                            v
   +----------------------------------------------------------------+
   |                    MCP Server  (Ruby process)                 |
   |                                                                |
   |  tools/list  -> the ~30 tool schemas (name, description,       |
   |                 inputSchema) — mirrors today's                 |
   |                 registry.tool blocks 1:1                       |
   |  tools/call  -> dispatches to Primitives + the one Session     |
   |                                                                |
   |   +----------------------------------------------------------+ |
   |   |  MudManager (gem, unchanged internals)                  | |
   |   |    Session      — socket, reader thread, IAC strip,     | |
   |   |                   login state machine, read_until_*     | |
   |   |    Primitives   — command builders, enum validation     | |
   |   +----------------------------------------------------------+ |
   +--------------------------------|---------------------------------+
                                    | telnet (TCP)
                                    v
                              CircleMUD server
```

Everything below the `MCP Server` box is exactly today's `mud_manager` gem,
untouched. Everything above it no longer contains a `Tools::Mud`-style
in-process registration — that module's *logic* moves into the server; each
language's agent keeps only a thin MCP client wiring.

## 2.1 — Separating session management from the agent

Today, `Boukensha::Tools::Mud.register` (`ruby/12_context/lib/boukensha/tools/mud.rb`)
does two jobs at once: it *owns* the `MudManager::Session` (creates it,
auto-connects it at startup) and it *exposes* gameplay as agent tools
(`registry.tool "look" do ... end`). The design splits those two jobs across
the MCP boundary:

| Concern | Today (in-process) | After this design |
|---|---|---|
| Owns the socket / login | `Tools::Mud.register`, inside the agent process | MCP server process, only |
| Owns command validation (`Primitives`) | same process as the agent | MCP server process, only |
| Decides *when* to call a tool | the agent's LLM loop | unchanged — still the agent |
| Knows tool names/descriptions/schemas | hardcoded in each language's registry | `tools/list` response, fetched at runtime, same for every language |
| Renders the MUD's text response | same process | passed back verbatim as the `tools/call` result; agent still just sees a string, as it does today |

The agent's job shrinks to: speak MCP, hold no MUD state, format tool
results for the model. That is true whether the agent is Ruby, Python, or
a language with no `mud_manager` port at all — which is the entire point.

**This supersedes part of the Part 1 plan.** Part 1 left open whether the
Ruby agent keeps its step-10 in-process path *alongside* an MCP path. Given
2.1's "language-specific agent must contain zero MUD-protocol code," the
Ruby agent should **not** keep a special-cased direct path — it becomes an
MCP client like every other language. Keeping two code paths (in-process for
Ruby, MCP for everyone else) would reintroduce exactly the duplication this
whole design exists to remove, and would mean two places could each believe
they own the session.

## 2.2 — MudManager as sole owner of the session

Invariant: **only the MCP server process ever calls `MudManager::Session#open`.**
Concretely:

- The server creates exactly one `MudManager::Session` at process startup
  (or lazily on the first `mud_connect` call — same auto-connect-with-warn
  behavior `Tools::Mud.register` already has today, just relocated).
- `Primitives` stays a stateless, pure module — no change needed there at
  all; it already just builds command strings.
- No MCP tool ever hands back a socket, file descriptor, or raw session
  handle to a client. The only things that cross the MCP boundary are: tool
  name, JSON arguments in, and a text result out — the same shape
  `send_cmd`/`guard` in today's `tools/mud.rb` already produce.
- **Concurrency**: if more than one MCP client (e.g. a Ruby agent and a
  Python agent) attaches to the *same* running server, tool calls must still
  be serialized against the one session, so two commands can't interleave
  mid-response. Today's `send_cmd` lambda already does
  `drain -> send_command -> read_until_prompt` as one unit inside a single
  process/thread; the server needs the equivalent guarantee across
  concurrent MCP requests (e.g. a mutex around dispatch, or simply
  processing `tools/call` requests one at a time). Whether **multiple
  simultaneous clients** is a real Part 3 requirement, or the server is
  single-client-only (one character, one agent, one MCP client connection)
  and multi-client is explicitly out of scope, is the one open question this
  design defers rather than answers speculatively — either way the
  serialization rule above holds.
- Session lifecycle (open → logged in → commands → `mud_disconnect`/process
  exit → closed) is entirely internal to the server. Restarting the server
  is the only way to force a fresh login; no MCP tool needs to expose
  socket-level lifecycle beyond the existing `mud_connect` / `mud_disconnect`
  / `mud_status` trio, which map onto the server unchanged.

## 2.3 — Gameplay exposed only through the MCP server

The ~30 tools currently registered by `Tools::Mud` (`mud_connect`, `look`,
`examine`, `check`, `move`, `flee`, `set_position`, `track`, `attack`,
`skill_strike`, `consider`, `say`, `tell`, `channel_say`, `get_item`,
`drop_item`, `put_item`, `equip_item`, `consume_item`, `cast_spell`,
`use_magic_item`, `shop`, `practice`, `save_character`, `send_raw`) become
the MCP server's `tools/list` catalog, one-for-one:

- **Name** — unchanged (`look`, `move`, `attack`, …).
- **Description** — unchanged, copied verbatim from the existing
  `description:` strings; they already read like MCP tool descriptions
  (written for a model deciding when to call them, not for a human API doc).
- **Parameters** — the existing `parameters: { target: { type: "string",
  description: "..." } }` hashes already have the shape of an MCP
  `inputSchema`'s `properties`; only wrapping (`type: "object"`, `required:
  [...]`, top-level envelope) needs adding, not redesigning.
- **Handler body** — the `guard.call` / `send_cmd.call(p.xxx(...))` /
  `rescue ArgumentError` pattern moves verbatim into the MCP tool's call
  handler. No behavioral change, only relocation.

No language ever gets its own copy of this catalog to maintain. A new
language gains full MUD gameplay by writing an MCP client and nothing else —
no `mud_manager` port, no CircleMUD protocol knowledge, no command-string
building.

## Config & secrets ownership (refines Part 1)

Part 1 assumed the agent's own `Boukensha::Config` (`mud_host`/`mud_port`/
`mud_username`/`mud_password`) would feed the MCP server. Under this design
that's backwards: since the agent no longer touches MUD state at all (2.1),
it has no reason to hold MUD credentials either. The MCP **server** owns
that config directly — read from its own environment/settings at launch
(following the precedent already set by `mud_manager`'s own
`examples/live_session_test.rb`, which reads `MUD_NAME`/`MUD_PASSWORD` from
the environment), not passed through from whichever agent happens to
connect to it.

## Call-flow walkthrough (`mud_connect` then `look`)

```
Agent                MCP client            MCP server                MudManager
  |  "call mud_connect"  |                     |                         |
  |--------------------->|--tools/call-------->|                         |
  |                      |                     |--Session#open---------->|
  |                      |                     |--Session#login--------->|
  |                      |                     |<--welcome text-----------|
  |                      |<--result: "connected to host:port\n..."--------|
  |<---------------------|                     |                         |
  |  "call look"         |                     |                         |
  |--------------------->|--tools/call-------->|                         |
  |                      |                     |--drain/send/read_until_prompt->|
  |                      |                     |<--room description------------|
  |                      |<--result: room text-|                         |
  |<---------------------|                     |                         |
```

The agent never sees telnet bytes, IAC sequences, or the login prompt
sequence — only tool names, arguments, and text results, exactly as it does
today talking to its own in-process `Registry`.

## Non-goals for Part 2

- No `.proto`/JSON-Schema files, no server code, no changes to
  `mud_manager` or `tools/mud.rb` themselves.
- No decision yet on stdio-vs-HTTP transport mechanics, exact directory
  layout (`ruby/13_mcp_server/` or elsewhere), or the Ruby MCP server
  SDK/library to use — those are Part 3 (implementation) decisions, informed
  by this shape but not blocked on it.
- Multi-client concurrency is flagged as an open question, not resolved,
  per 2.2 above.
