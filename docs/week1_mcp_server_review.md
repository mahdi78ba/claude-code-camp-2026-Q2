# MCP Server — Initial Implementation Review (Part 3)

Reviews what was generated at `ruby/13_mcp_server/` against the design in
`docs/week1_mcp_architecture_design.md` (2.1/2.2/2.3) and the Part 3
checklist: does the package contain a server, a client, a dispatcher, and
tool definitions, and does it actually work end-to-end against a live MUD.

## 3.1/3.2 — Package structure generated

```
ruby/13_mcp_server/
  README.md
  bin/
    mud_mcp_server        43 lines  — executable entry point (env config -> Dispatcher -> Server#run)
  examples/
    example.rb             35 lines  — client-driven smoke test against a live CircleMUD
  lib/
    mud_mcp.rb               8 lines  — requires the four components below + version
    mud_mcp/
      version.rb            3 lines  — MudMcp::VERSION
      dispatcher.rb        61 lines  — tool catalog: register/list/call
      server.rb            99 lines  — JSON-RPC 2.0 over stdio
      client.rb            82 lines  — subprocess-driving MCP client
      tools.rb             493 lines — the ~30 MUD tool definitions, ported from Tools::Mud
```

824 lines total. No `Gemfile`/gemspec — the only external dependency
(`mud_manager`) is a locally-built gem that's already installed (`gem list
mud_manager` → `0.1.0`), and everything else used (`json`, `open3`,
`rbconfig`) is stdlib, so there was nothing for Bundler to resolve. This is
a deliberate departure from steps 09–12's Gemfile+gemspec convention,
made to *avoid* re-hitting the dependency wrinkle
`docs/week1_standard_tool_library_review.md` flagged (a `Gemfile` here would
just reproduce the same unresolvable-remote-source problem for no benefit,
since this step declares no gem of its own to publish).

## 3.3 — Component checklist

| Required | Present | Where | Notes |
|---|---|---|---|
| **MCP server** | ✅ | `lib/mud_mcp/server.rb` | Newline-delimited JSON-RPC 2.0 over `$stdin`/`$stdout`. Handles `initialize`, `notifications/initialized`, `tools/list`, `tools/call`, `ping`. Diagnostics go to `$stderr` only — verified nothing but JSON hits stdout (see smoke test below). |
| **MCP client** | ✅ | `lib/mud_mcp/client.rb` | Spawns the server via `Open3.popen2`, performs the handshake, exposes `list_tools`/`call_tool`. Synchronous — one in-flight request at a time, matching the server's own single-threaded read loop. |
| **Dispatcher** | ✅ | `lib/mud_mcp/dispatcher.rb` | `tool`/`list`/`call`. `Server` never touches `MudManager` or tool internals directly — it only calls `dispatcher.list` and `dispatcher.call`, which is the separation 2.1 asked for. |
| **Tool definitions** | ✅ | `lib/mud_mcp/tools.rb` | All 27 tools from `Boukensha::Tools::Mud` (`ruby/12_context/lib/boukensha/tools/mud.rb`), same names/descriptions/parameters/handler bodies, registered against the `Dispatcher` instead of Boukensha's `Registry`. |

All four required pieces are present and wired together
(`bin/mud_mcp_server`: env → `Tools.register(dispatcher, ...)` → `Server.new(dispatcher, session:).run`).

## Live smoke test

Ran against the CircleMUD already up on `localhost:4000` (the same instance
every other step in this repo targets), using the real `dummy`/`helloworld`
credentials from `.boukensha/settings.yaml`.

**`examples/example.rb`** (full client → subprocess-server → MUD round trip):

```
connected to mud-mcp-server v0.1.0
27 tools available: mud_connect, mud_disconnect, mud_status, look, examine,
check, move, flee, set_position, track, attack, skill_strike, consider, say,
tell, channel_say, get_item, drop_item, put_item, equip_item, consume_item,
cast_spell, use_magic_item, shop, practice, save_character, send_raw

look ->
The Temple Of Midgaard
   You are in the southern end of the temple hall in the Temple of Midgaard.
...
25H 100M 15V (news) (motd) >

check score ->
You are 20 years old.
...
```

Real room description, real character sheet — the session logged in for
real and the response text came back through the full MCP round trip
(client → subprocess stdin → server → `MudManager::Session` → CircleMUD →
back out the same path).

**Raw JSON-RPC, piped directly into `bin/mud_mcp_server`** (bypassing the
Ruby client, to check the wire format itself rather than trusting the
client's own parsing):

- `tools/list` → 27 tools; spot-checked `move`'s schema:
  ```json
  {
    "name": "move",
    "description": "Move in a compass direction or up/down.",
    "inputSchema": {
      "type": "object",
      "properties": { "direction": { "type": "string", "description": "..." } },
      "required": ["direction"]
    }
  }
  ```
  Confirms `Dispatcher#tool`'s "required-ness comes from the handler's own
  keyword arguments" design actually produces a correct schema, not just a
  plausible-looking one.
- `tools/call` with `examine` and **no** `target` argument →
  `{"content":[{"type":"text","text":"error: missing keyword: :target"}],"isError":true}`
  — a schema-boundary failure, correctly flagged `isError: true`.
- `tools/call` with an unknown tool name →
  `{"content":[{"type":"text","text":"error: unknown tool \"nonexistent_tool\""}],"isError":true}`.
- `tools/call` with `move direction: "sideways"` (a MUD-domain validation
  error, not a schema error) →
  `{"content":[{"type":"text","text":"error: invalid direction: ..."}],"isError":false}`
  — **not** flagged as an error at the protocol level, because the handler
  caught its own `ArgumentError` and returned a string, exactly as
  `Tools::Mud`'s `rescue ArgumentError => e; "error: #{e.message}"` already
  did before this port. This is intentional (see README, "Two kinds of
  error"), not a bug: it preserves the exact behavior the agent already
  relies on today (read the string, decide whether to retry), and only adds
  a signal for the boundary case that a plain string genuinely couldn't
  carry before.
- `$stderr` only ever printed `[mud_mcp] server shutting down` — confirms
  `$stdout` stayed clean JSON-RPC throughout, which any real MCP client
  parsing line-by-line depends on.

## Gaps / follow-ups (not blocking, flagged for the next step)

1. **The Ruby agent hasn't been migrated to use this server yet.**
   `Boukensha::Tools::Mud` (step 12) still registers tools in-process. Per
   the architecture design (2.1), it should become an MCP client like any
   other language, so there is exactly one live path to the MUD instead of
   two that could each believe they own the session. That migration is
   explicitly out of scope for "generate the initial implementation" but is
   the natural next step.
2. **Concurrent MCP clients against one server process is untested.**
   The design doc flagged this as an open question rather than a decision;
   this implementation doesn't add any serialization beyond what a single
   `$stdin.gets` read loop already gives it for free (one request handled
   at a time) — fine for the single-client case exercised above, unverified
   beyond that.
3. **Transport is stdio only** — no HTTP/SSE — matching the design's stated
   starting point, not an oversight.

## Retain

- **Reusing `Proc#parameters` to derive the JSON-Schema `required` array**
  instead of a hand-maintained flag in the parameters hash is worth keeping
  as the pattern for any future MCP tool surface in this repo — it makes it
  structurally impossible for the schema and the handler's actual arity to
  disagree.
- **Porting tool bodies verbatim** (same `guard`/`send_cmd` closures, same
  `rescue ArgumentError` per tool) rather than restructuring them during the
  move to MCP kept this a mechanical, low-risk port — the live smoke test
  producing byte-identical-looking MUD output on the first run is the
  evidence that nothing was lost in translation.
