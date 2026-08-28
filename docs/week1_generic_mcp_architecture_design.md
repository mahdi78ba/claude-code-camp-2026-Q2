# Generic MCP Architecture Design (MCP Part 2 — Design)

Design only, following on from `docs/week1_mcp_genericity_review.md`. No
code changes here — this fixes the target shape before implementing it,
same as `docs/week1_mcp_architecture_design.md` did for the original MCP
integration.

## Goals, restated as constraints

- **2.1** — one generic component registers tools from *any* MCP server
  Boukensha is told about, without knowing what domain that server serves.
  Today that logic exists (`Tools::Mud.register`'s body, lines 44–56 of
  `ruby/10_standard_tool_library/lib/boukensha/tools/mud.rb`) but is
  trapped inside a MUD-named method with MUD-named parameters.
- **2.2** — `host`/`port`/`name`/`password` stop being special, hardcoded
  Boukensha-level concepts. MUD's connection details become *data* — one
  entry in a list of MCP server configs — not a dedicated `mud:` keyword,
  a dedicated `mud_opts_from_config`, or dedicated `Config#mud_host` etc.
- **2.3** — adding a second MCP server (any domain) should cost zero
  Boukensha code changes: install its server executable, add one config
  entry, done.

## Component design: `Boukensha::Tools::Mcp`

A new module replacing what `Tools::Mud.register`'s body already does
generically, generalized to N servers instead of one:

```ruby
module Boukensha
  module Tools
    module Mcp
      # servers: [{name:, command: [...], env: {}}, ...]
      # Returns one MudMcp::Client per server that started successfully.
      def self.register(registry, servers:)
        servers.filter_map { |server| register_one(registry, server) }
      end

      def self.register_one(registry, server)
        client = MudMcp::Client.new(command: server[:command], env: server[:env] || {})
        client.handshake
        client.list_tools.each { |tool| register_proxy_tool(registry, server[:name], client, tool) }
        at_exit { client.close }
        client
      rescue MudMcp::Client::Error, Errno::ENOENT => e
        warn "[boukensha] MCP server #{server[:name].inspect} failed to start: #{e.message}"
        nil
      end

      def self.register_proxy_tool(registry, server_name, client, tool)
        registry.tool tool[:name],
          description: tool[:description],
          parameters: tool[:inputSchema][:properties] do |**args|
          text, = client.call_tool(tool[:name], args)
          text
        end
      end
      private_class_method :register_proxy_tool
    end
  end
end
```

Nothing in this module knows what a MUD is. `Tools::Mud` — kept as a thin
convenience wrapper so existing call sites and existing `settings.yaml`
keep working — shrinks to just building one server-config entry:

```ruby
module Boukensha
  module Tools
    module Mud
      def self.register(registry, host: "localhost", port: 4000, name:, password:)
        Mcp.register(registry, servers: [{
          name:    "mud",
          command: nil, # MudMcp::Client's own default (bin/mud_mcp_server)
          env: {
            "MUD_HOST" => host.to_s, "MUD_PORT" => port.to_s,
            "MUD_NAME" => name,     "MUD_PASSWORD" => password
          }
        }]).first
      end
    end
  end
end
```

**Deliberately reuses `MudMcp::Client` as-is**, unrenamed, in this phase.
Its behavior is already fully generic (per `docs/week1_mcp_genericity_review.md`
1.1) — only its *name* and its `DEFAULT_SERVER` default are MUD-flavored,
neither of which blocks using it against an arbitrary `command:`. Splitting
it into a separate domain-agnostic `mcp` gem (review's opportunity #2) is a
bigger, separately-scoped change — see Phasing below. This design doesn't
need that split to satisfy 2.1; `Tools::Mcp` works today by passing an
explicit `command:` per server.

## Config design: MCP servers as data, not a hardcoded case

**Target `settings.yaml` shape** — replaces the `mud:` block:

```yaml
mcp_servers:
  - name: mud
    command: ["mud_mcp_server"]
    env:
      MUD_HOST: localhost
      MUD_PORT: "4000"
      MUD_NAME: dummy
      MUD_PASSWORD: helloworld
```

Note what's *not* here: no `Config` method needs to know the string
`"MUD_HOST"` means "the MUD's hostname." That mapping lives only in
whichever server's own README documents its env contract (already true —
`ruby/13_mcp_server/README.md` documents exactly this contract today).
Config becomes a pure passthrough:

```ruby
# Config
def mcp_servers
  (dig(:mcp_servers) || []).map do |s|
    { name: s["name"], command: Array(s["command"]), env: s["env"] || {} }
  end
end
```

`Config#mud_host`/`#mud_port`/`#mud_username`/`#mud_password` are retired —
not deprecated-but-kept, actually removed — since keeping them would mean
two parallel ways to configure the same thing, which is exactly the
hardcoding 2.2 asks to eliminate.

**`boukensha.rb`** — `Boukensha.run`/`.repl` drop the `mud:` keyword in
favor of a generic one:

```ruby
def self.run(..., mcp: nil, ...)
  resolved_mcp = mcp == false ? [] : (mcp || cfg.mcp_servers)
  Tools::Mcp.register(registry, servers: resolved_mcp) if resolved_mcp.any?
  ...
end
```

`mcp: nil` (default) → use `settings.yaml`'s `mcp_servers:` list.
`mcp: [...]` → explicit override, same shape as the config list.
`mcp: false` → opt out entirely. This is the same three-way convention
`working_dir:`/`mud:` already use elsewhere in this file — no new pattern
introduced, just applied one level more generically.

**Migration note**: existing `settings.yaml` files with a `mud:` block
would need a one-time edit to the `mcp_servers:` shape above. That's a
real, visible breaking change for anyone with the old config — worth
calling out explicitly rather than silently supporting both shapes forever
(which would just be a second hardcoded special case, undermining the
point of this design).

**`repl.rb`'s banner** (`mud_status_string`/`probe_mud`) needs to change
too, and can't just be renamed: `probe_mud` does a raw TCP reachability
check against `host:port`, which assumes every MCP server is "a thing with
a host and port" — not true in general (a server could be a pure local
subprocess with no network dependency at all). Generalizing this means
either (a) dropping the reachability probe and showing configured server
names only ("mcp servers: mud, weather"), or (b) tracking each server's
*actual* handshake success/failure from `Tools::Mcp.register`'s return
value (the `filter_map`/`rescue` above already produces exactly that
signal) and displaying that instead of a speculative socket probe. (b) is
strictly better information and doesn't need a new mechanism — it reuses
data `Tools::Mcp.register` already has.

## 2.3 — Supporting additional MCP servers under this architecture

**Onboarding checklist for a second server** (any domain), under this
design:

1. Build and install its MCP server (own gem, own `bin/`, own env
   contract) — no dependency on `mud_mcp` or `mud_manager` unless it
   happens to need them.
2. Add one entry to `mcp_servers:` in `settings.yaml` (or pass one via the
   `mcp:` keyword directly).
3. Nothing else. `Tools::Mcp.register` iterates the list; `boukensha.rb`
   doesn't grow a second `weather_opts_from_config`/`Tools::Weather.register`
   pair the way it would under the current hardcoded-per-domain pattern.

**Real risk this surfaces that the single-server case never had: tool name
collisions.** `Context#register_tool` (`context.rb`) is a flat
`@tools[tool.name] = tool` — if a second server also exposes a tool called
`look` or `status`, its registration would silently overwrite the first
server's tool with the same name, and the model would only ever be able to
call one of them. This needs an explicit decision, not silence:

- **Detect and warn/raise at registration time** (cheapest: compare
  incoming tool names against `registry`'s existing keys before
  registering, one server at a time, in `Tools::Mcp.register_one`) — fails
  loudly instead of silently losing a tool.
- **Namespace tool names by server** (e.g. `"mud__look"`) — fully
  eliminates collisions, but changes what name the model sees and calls,
  and would need the description to still read naturally to the model.
- **Leave uncollided by convention** (author discipline, no code) — fine
  while there's one server, not a real answer once there are two.

Recommendation: detect-and-warn now (cheap, non-breaking, catches the
mistake immediately); revisit namespacing only if/when a real collision
between two actual servers shows up, rather than pre-namespacing
speculatively.

**Startup cost scales with server count.** Each configured server is one
more subprocess spawned and one more handshake awaited, synchronously,
during `Tools::Mcp.register` — N servers means N times the per-server
startup cost `docs/week1_mcp_review_and_gaps.md` (gap 4) already flagged
for the single-MUD-server case. Not a blocker, just linear, and worth
knowing before configuring a long list of servers for something
latency-sensitive.

**Failure isolation is per-server**, not all-or-nothing:
`Tools::Mcp.register_one`'s `rescue` (shown above) means one misconfigured
or unreachable server produces a warning and zero tools from it, while
every other configured server still registers normally and
`Boukensha.run`/`.repl` still boots. This matches the existing "fail open"
philosophy `Tools::Mud`'s own auto-connect already uses (a MUD that's down
doesn't crash the agent, just leaves MUD tools erroring until reconnected)
— generalized from "the one server might be down" to "any subset of
configured servers might be down."

## Phasing (this design intentionally stops here)

- **Phase A** (what this design specifies): `Tools::Mcp` generic bridge +
  `mcp_servers:` config, built on the *existing* `MudMcp::Client` class
  unchanged. Delivers 2.1/2.2/2.3 without touching the gem boundary.
- **Phase B** (deferred, `docs/week1_mcp_genericity_review.md` opportunity
  #2): split `mud_mcp` into a domain-agnostic `mcp` gem (`Dispatcher`,
  `Server`, `Client`) plus a `mud_mcp` gem (just `Tools`, the executable,
  the `mud_manager` dependency) on top of it. Not required for Phase A to
  work — only becomes worth doing once a second real MCP server exists and
  would otherwise have to depend on `mud_mcp` (and thus `mud_manager`) just
  to get a generic client.

No implementation in this step — Phase A is scoped tightly enough that the
next step could build it directly from this document.
