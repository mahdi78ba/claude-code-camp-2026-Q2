# Integrating MCP into the Standard Tool Library (Part 4)

Wires the MCP server generated in Part 3 (`ruby/13_mcp_server/`) into
`ruby/10_standard_tool_library` — the step named "the Standard Tool
Library." This is the migration flagged as follow-up work in
`docs/week1_mcp_server_review.md` (gap 1): the Ruby agent stops registering
MUD tools in-process and becomes an MCP client like the architecture design
(`docs/week1_mcp_architecture_design.md`, 2.1) said it should.

## 4.1 — Moving the MCP package into the Week 1 project structure

"Moving it in" concretely meant making `mud_mcp` a real, installable
dependency the same way `mud_manager` already is — not just files sitting
in a step-13 folder nothing else references yet:

1. Added `ruby/13_mcp_server/mud_mcp.gemspec` (mirrors
   `week0_explore/mud_manager/mud_manager.gemspec`: `spec.files`, a `bin/`
   executable, `spec.add_dependency "mud_manager", "~> 0.1"` since
   `lib/mud_mcp/tools.rb` is the one file that still needs it).
2. Built and installed it exactly like `mud_manager` was:
   `gem build mud_mcp.gemspec && gem install mud_mcp-0.1.0.gem`. (Landed in
   the user gem path, not the system one `mud_manager` used, only because
   this environment has no passwordless `sudo` — functionally identical:
   `require "mud_mcp"` resolves from any directory, confirmed by running it
   from `/tmp` before touching step 10 at all.)
3. Fixed two latent bugs this surfaced: `client.rb` and `server.rb` both
   referenced the top-level `VERSION` constant without requiring
   `version.rb` themselves — harmless while everything only ever loaded
   through the `mud_mcp.rb` aggregator (which requires every file in a
   fixed order), but a real `NameError` once something required
   `mud_mcp/client` on its own. Fixed by giving each file its own
   `require_relative "version"`.

`ruby/10_standard_tool_library/boukensha.gemspec`'s dependency changed from
`mud_manager` to `mud_mcp` (comment updated to say why: the server, not
Boukensha, is the one that still talks to `mud_manager`/CircleMUD).
`Gemfile.lock` was hand-updated to match (`mud_mcp (~> 0.1)`, pulling in
`mud_manager` transitively) — `bundle install` itself still can't resolve
either gem from rubygems.org, exactly the pre-existing wrinkle
`docs/week1_standard_tool_library_review.md` already flagged for
`mud_manager`; this doesn't fix that, it just carries the same known
limitation forward under the new dependency name. Nothing in this repo's
documented workflow runs through Bundler anyway (`ruby examples/example.rb`
directly, per every step's README).

## 4.2 — Standard Tool Library talks to MudManager through the MCP client

`ruby/10_standard_tool_library/lib/boukensha/tools/mud.rb` no longer
hardcodes ~30 tool definitions or requires `mud_manager`/`mud_mcp` in full —
it requires only `mud_mcp/client`, and `Tools::Mud.register` shrank to a
generic MCP-to-Registry bridge:

```ruby
def self.register(registry, host: "localhost", port: 4000, name:, password:)
  client = MudMcp::Client.new(env: {
    "MUD_HOST" => host.to_s, "MUD_PORT" => port.to_s,
    "MUD_NAME" => name, "MUD_PASSWORD" => password
  })
  client.handshake
  client.list_tools.each { |tool| register_proxy_tool(registry, client, tool) }
  at_exit { client.close }
  client
end
```

Each proxied tool forwards straight through: same name, same description,
same parameters (an MCP `inputSchema`'s `properties` is already exactly the
shape `registry.tool`'s `parameters:` expects), handler body is just
`client.call_tool(tool[:name], args)`. Discovering the catalog via
`tools/list` at runtime — instead of hardcoding tool names — means this file
no longer needs to know what MUD gameplay even consists of; a tool added to
`ruby/13_mcp_server/lib/mud_mcp/tools.rb` reaches this agent with zero
changes here.

## 4.3 — Verifying MudManager still owns the session, MCP only exposes tools

Ran a direct integration check (bypassing the LLM/Agent loop — no API key
needed — by calling `registry.dispatch` directly, the exact seam
`Tools::Mud` registers against) against the live CircleMUD on
`localhost:4000`:

```
registered 27 tools: attack, cast_spell, channel_say, check, consider,
consume_item, drop_item, equip_item, examine, flee, get_item, look, move,
mud_connect, mud_disconnect, mud_status, practice, put_item,
save_character, say, send_raw, set_position, shop, skill_strike, tell,
track, use_magic_item

look ->
The Temple Of Midgaard
   You are in the southern end of the temple hall in the Temple of Midgaard.
...
25H 100M 15V (news) (motd) >

move (invalid direction) ->
error: invalid direction: "sideways" (expected one of north, east, south, west, up, down)

check score ->
You are 20 years old.
...
25H 100M 15V (news) (motd) >

closed client cleanly.
confirmed: mud_manager was never loaded in this process.
```

That last line is the load-bearing check for 4.3, not just a nice-to-have:
the test script asserts `$LOADED_FEATURES.none? { |f| f.include?("mud_manager") }`
both before and after exercising every tool. It passes — `mud_manager` is
never `require`d into the Boukensha agent process at all, let alone called
from it. The socket, the CircleMUD login state machine, and the command
builders exist only inside the spawned `mud_mcp_server` subprocess; this
process only ever sent JSON tool calls and got text back. `ps aux` after
`client.close` shows no leftover `mud_mcp_server` process — the `at_exit`
hook (and the explicit `client.close` in the test) tears the subprocess
down cleanly, so the session's lifecycle stays tied to the server process
exactly as designed, not leaked into the agent's.

This is the concrete confirmation of the ownership split
`docs/week1_mcp_architecture_design.md` (2.2) called for: exactly one
component (the MCP server, via `mud_mcp`'s bundled `MudManager::Session`)
ever holds the live connection; the agent process holds a client handle and
nothing else.

## What did NOT change

- `ruby/11_tui` and `ruby/12_context` still register `Tools::Mud`
  in-process, unchanged. The task named "the Standard Tool Library"
  specifically (step 10); migrating the later steps that carry their own
  copy of `tools/mud.rb` forward is the same kind of follow-up work
  `docs/week1_mcp_server_review.md` already flagged, not done here to avoid
  scope creep across three step directories the task didn't name.
- `ruby/13_mcp_server` itself is unchanged in behavior — only two files
  (`client.rb`, `server.rb`) gained a missing `require_relative "version"`,
  and the package gained a gemspec so it could be installed.
