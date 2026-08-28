# MCP Part 2 — Review: How Generic Is the Current MCP Integration?

Review only, no code changes. Looks at what Part 3/4 actually built
(`ruby/13_mcp_server/`, `ruby/10_standard_tool_library/lib/boukensha/tools/mud.rb`)
through a different lens than the earlier reviews: not "does it work" (it
does — see `docs/week1_mcp_review_and_gaps.md`) but "how much of this is
MCP-the-protocol versus MUD-the-domain, and how cleanly are those two
separated."

## 1.1 — How the integration fits together today

```
Boukensha::Tools::Mud.register(registry, host:, port:, name:, password:)
  ↓ builds env {"MUD_HOST"=>.., "MUD_NAME"=>.., ...}, spawns:
MudMcp::Client                                    (generic MCP client)
  ↓ Open3.popen2 → subprocess
bin/mud_mcp_server                                (MUD-specific launcher)
  ↓ reads MUD_HOST/MUD_PORT/MUD_NAME/MUD_PASSWORD from ENV
MudMcp::Tools.register(dispatcher, host:, port:, name:, password:)  (MUD-specific)
  ↓ registers 27 tools against:
MudMcp::Dispatcher                                (generic tool catalog)
  ↓ served over stdio by:
MudMcp::Server                                    (generic JSON-RPC/MCP wire protocol)
  ↓ each tool handler calls into:
MudManager::Session / Primitives                  (MUD-specific — telnet, CircleMUD)
```

Three of the six links in that chain are already protocol-generic and
don't know what a MUD is: **`Dispatcher`** (`ruby/13_mcp_server/lib/mud_mcp/dispatcher.rb`)
just maps names to schemas and handlers; **`Server`** (`server.rb`) just
speaks JSON-RPC 2.0 over stdio and calls `dispatcher.list`/`dispatcher.call`;
**`Client`** (`client.rb`) just spawns a command and does
handshake/list_tools/call_tool. None of those three files mention `mud`,
`MudManager`, `CircleMUD`, or telnet anywhere in their logic. That's a real,
working separation — `docs/week1_mcp_architecture_design.md`'s 2.1/2.2 goals
are met at the protocol layer.

The other three links — `bin/mud_mcp_server`, `MudMcp::Tools`, and
`Boukensha::Tools::Mud` — are where MUD-specific knowledge actually lives,
which is expected for `Tools`/`bin/mud_mcp_server` (their whole job) but,
per 1.2 below, leaks further than that into places that don't need it.

## 1.2 — Where it's still tightly coupled to MUD Manager

| Where | What's coupled | Why it's a problem for genericity |
|---|---|---|
| `ruby/13_mcp_server/mud_mcp.gemspec` + `lib/mud_mcp.rb` | The gem bundles the three generic files (`dispatcher.rb`, `server.rb`, `client.rb`) into the **same package and namespace** as the fully MUD-specific `tools.rb`, and declares `mud_manager` as a hard dependency of the whole gem. | Anything that wants just "an MCP server/client pair in Ruby" — a future non-MUD tool domain — has to depend on `mud_mcp`, which drags in `mud_manager` whether or not it's ever used. There's no way to get `Dispatcher`/`Server`/`Client` without also getting the MUD gem. |
| `ruby/13_mcp_server/lib/mud_mcp/client.rb:17` | `DEFAULT_SERVER = File.expand_path("../../bin/mud_mcp_server", __dir__)` | The generic `Client` class's *default* is "spawn the MUD server." A caller can override `command:`, but the class's own behavior, without arguments, assumes you're talking to MUD specifically — a generic client shouldn't have a domain-specific default baked in. |
| `bin/mud_mcp_server:30-41` | Reads `MUD_HOST`/`MUD_PORT`/`MUD_NAME`/`MUD_PASSWORD` directly in the executable, via `env_or_abort` | Expected for a MUD-specific launcher, but there's no generic "run any Dispatcher as an MCP-over-stdio server" entry point separate from this one — `Server#run` is generic, but nothing exposes *just* that without also going through this MUD-flavored `ENV.fetch` block. |
| `ruby/10_standard_tool_library/lib/boukensha/tools/mud.rb:43-56` | `Tools::Mud.register`'s signature (`host:, port:, name:, password:`) and its `env` hash (`"MUD_HOST"`, `"MUD_NAME"`, …) | The method *body* below the env-building (`client.handshake`; `client.list_tools.each { register_proxy_tool(...) }`; `at_exit { client.close }`) is 100% generic — it would work against **any** MCP server, not just this one. But it's trapped inside a MUD-named module with MUD-named parameters, so nothing else in Boukensha can reuse "proxy an MCP server's tools into my registry" without copy-pasting this method and swapping the env keys. |
| `ruby/10_standard_tool_library/lib/boukensha/tools/mud.rb:67-75` | `register_proxy_tool` — also fully generic (forwards any `{name, description, inputSchema}` into `registry.tool`) | `private_class_method`, scoped to `Tools::Mud` only. The one piece of code that actually bridges "MCP tool schema" → "Boukensha tool" isn't reusable outside this file. |
| `boukensha.rb`'s `mud_opts_from_config` (step 10, `lib/boukensha.rb`) | Builds `{host:, port:, name:, password:}` specifically from `cfg.mud_host` etc. | Correctly scoped to MUD (it's reading MUD settings), but it's the only config-resolution path `Boukensha.run`/`.repl` has for *any* MCP-backed tool set — adding a second MCP tool domain would mean writing a second, differently-named `..._opts_from_config` and a second `mud: nil` / `Tools::Whatever.register(...) if resolved` block in `boukensha.rb` itself, rather than one generic "list of MCP servers to proxy" option. |

Nothing here is broken — this is the same distinction the earlier reviews
already drew for other reasons (e.g. `docs/week1_mcp_server_review.md`'s
"Two kinds of error," `docs/week1_mcp_architecture_design.md`'s ownership
split). The pattern across all six rows: **the generic MCP mechanism and
the MUD-specific content are logically separate already (different
methods, mostly different files) but not yet packaged/named/exposed as
separate, independently reusable things.**

## 1.3 — Opportunities to make the integration more generic

In rough order of how much they'd actually buy, cheapest first:

1. **Extract the proxy loop in `Tools::Mud.register` into a small, generic
   helper** — something like `Boukensha::Tools::McpBridge.register(registry,
   command:, env: {})`, doing exactly what lines 44–55 of `tools/mud.rb` do
   today minus the MUD-specific env-building. `Tools::Mud.register` would
   shrink to building the `env` hash and calling
   `McpBridge.register(registry, command: [...], env: {...})`. This is the
   highest-leverage change: it's the one piece of code every *future*
   MCP-backed tool domain would otherwise have to copy-paste, and
   extracting it doesn't require touching the wire protocol or the gem
   boundary at all.

2. **Split the `mud_mcp` gem in two**: a domain-agnostic `mcp` gem
   (`Dispatcher`, `Server`, `Client` — no `mud_manager` dependency, no
   MUD-shaped defaults) and a `mud_mcp` gem that depends on `mcp` +
   `mud_manager` and contributes only `Tools` + a thin `bin/mud_mcp_server`.
   `MudMcp::Client::DEFAULT_SERVER` would either move to the MUD-specific
   gem (as, say, `MudMcp::DEFAULT_COMMAND`) or be dropped in favor of always
   requiring an explicit `command:`. This is the change that actually lets
   a second, unrelated tool domain reuse the protocol layer without taking
   on `mud_manager` — right now it can't, full stop.

3. **Generalize `boukensha.rb`'s MCP wiring** from a single hardcoded
   `mud:` option to something like `mcp_servers: [{command:, env:}, ...]`,
   with `mud_opts_from_config` becoming one entry-builder among possibly
   several. Lower priority than 1–2 since it only matters once a *second*
   MCP tool domain actually exists — right now there's exactly one, so this
   would be generalizing against a hypothetical rather than a real second
   caller.

4. **Let one server process expose more than one tool source** — today
   `bin/mud_mcp_server` wires exactly `MudMcp::Tools` into one `Dispatcher`.
   A generic launcher taking a list of tool-registrar modules would let,
   e.g., MUD tools and some other tool source share one process/session —
   speculative, and not obviously useful while there's only one tool
   source, so lowest priority of the four.

**Caveat worth stating plainly**: this is a teaching repo with exactly one
MCP-backed tool domain (MUD gameplay) so far. Generalizing before a second,
real consumer exists risks building abstraction for its own sake — #1 pays
for itself immediately (it's less code, not more), but #2–#4 are
"opportunities," not "gaps that are currently costing anything." Worth
doing #1 regardless; worth doing #2+ only if/when a second MCP tool domain
is actually on the table.
