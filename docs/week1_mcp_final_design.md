# Finalized Generic MCP Design (MCP Part 2 — Design Sign-off)

Closes out the design phase. Supersedes
`docs/week1_generic_mcp_architecture_design.md` where they disagree — that
document had the right shape but a real bug and a couple of gaps, all
caught and resolved in `docs/week1_mcp_refactor_plan_review.md`. This
document folds those fixes in, finishes the one piece the review left
open (`Repl`/banner + tool naming), and draws the final now-vs-deferred
line. Design only — nothing implemented yet.

## 4.1 — Remaining considerations, resolved

### Tool naming

Default: **no namespacing.** A tool registers under exactly the name its
MCP server reports (`look`, not `mud__look`). Namespacing every tool
unconditionally would change every existing tool name for the single
server that exists today, for a problem (collisions) that doesn't exist
yet with only one server configured.

Escape hatch: a server config entry may set an optional `prefix:`. When
present, every tool from that server registers as `"#{prefix}_#{name}"`
instead of the bare name — a deliberate, visible choice the person writing
`mcp_servers:` makes up front, not something the system decides for them.

```yaml
mcp_servers:
  - name: mud
    command: ["mud_mcp_server"]
    env: { MUD_HOST: localhost, MUD_PORT: "4000", MUD_NAME: dummy, MUD_PASSWORD: "$MUD_PASSWORD" }
    # prefix: mud   # optional — omitted here since there's no collision to avoid yet
```

(`"$MUD_PASSWORD"` resolving against `ENV` is the secrets fix from the
review — `Config#mcp_servers` resolves any string value starting with `$`
against `ENV`, literal otherwise, so a real credential never has to sit as
plaintext in the "safe to commit" settings file.)

### Server registration

- **Order is meaningful now.** `mcp_servers:` entries register in list
  order; the first server to claim a given tool name wins it (see 4.2). No
  hidden reordering, no priority field — the order in the YAML *is* the
  priority.
- **Return shape.** `Tools::Mcp.register(registry, servers:)` returns one
  `{name:, client:}` per server that started successfully — servers that
  failed to spawn, timed out, or errored during handshake are simply
  absent from the result (already true of the `filter_map` shape from the
  prior design; keeping it). This return value is what feeds the `Repl`
  banner below — nothing else currently needs it, so nothing more
  elaborate is warranted.
- **Isolation, finalized**: `register_one` wraps the
  spawn+handshake+list_tools sequence in both a `Timeout.timeout` and a
  `rescue StandardError` (both fixes from the review) — one misbehaving
  server (fails to start, or hangs) produces one warning and is absent
  from the result; every other configured server still registers.

### `Repl`/banner (the piece the review deferred, finished now)

`Repl.new`'s `mud:` keyword is replaced with `mcp_servers:`, taking the
`[{name:, client:}, ...]` array `Tools::Mcp.register` already returns —
not a raw config hash, not a re-probe. The banner line becomes:

```
mcp servers: mud (connected)
```

or `(not configured)` when the array is empty, or, with a second server
someday, `mud (connected), weather (connected)`. The old `probe_mud`'s raw
TCP reachability check is **deleted outright**, not generalized — it was
only ever a proxy for "did we actually connect," and now the banner has
the real answer directly (a client object in the array *means* the MCP
handshake already succeeded; there's nothing left to probe). This also
retires the old comment's concern about "probing here would cause a
double-login" — there's no separate probe left to cause one.

## 4.2 — Tool name collision handling, decided

**Warn, and keep the first registration; refuse the second.** Considered
three alternatives and rejected them:

- *Auto-rename the second tool* (e.g. `weather__look`) — adds
  registration-order-dependent naming the person configuring servers never
  asked for, for a scenario (an actual collision) that should probably just
  be fixed by them (via `prefix:`) rather than papered over silently.
- *Always namespace every tool by server* — eliminates collisions
  structurally, but changes every tool's name unconditionally, breaking the
  existing single-server naming for a problem that only exists once there
  are two-plus servers.
- *Abort the whole registration on any collision* — matches this
  codebase's existing precedent for hard *configuration* errors (e.g.
  `env_or_abort` for a missing required env var), but a name collision
  between two otherwise-valid servers isn't a broken config, it's an
  emergent conflict between two valid ones — crashing the entire
  `Boukensha.run`/`.repl` over one overlapping tool name, when every other
  tool from both servers is fine, is disproportionate.

Warn-and-keep-first matches the codebase's existing precedent for
*degraded-but-recoverable* situations instead (the same pattern
`Tools::Mud`'s old auto-connect used: MUD unreachable → warn, keep running,
just without that capability) — narrowed to the one colliding tool instead
of the whole server.

Mechanism (small, concrete, needed regardless of implementation timing):

```ruby
# Registry — one new method
def registered?(name)
  @context.tools.key?(name.to_s)
end
```

```ruby
# Tools::Mcp
def self.register_proxy_tool(registry, server_name, client, tool)
  if registry.registered?(tool[:name])
    warn "[boukensha] MCP server #{server_name.inspect}: tool #{tool[:name].inspect} " \
         "collides with an already-registered tool — skipped (use prefix: to disambiguate)"
    return
  end
  registry.tool tool[:name], description: tool[:description],
    parameters: tool[:inputSchema][:properties] do |**args|
    text, = client.call_tool(tool[:name], args)
    text
  end
end
```

The warning names both the offending server and the tool, and points at
the fix (`prefix:`) directly, rather than just reporting that something
happened.

## 4.3 — Now vs. deferred

**Implement now:**

1. `Registry#registered?(name)` — one method, `registry.rb`.
2. `Boukensha::Tools::Mcp` — `register`/`register_one`/`register_proxy_tool`,
   with the review's three code-level fixes folded in from the start (no
   `command: nil` footgun, `Timeout.timeout` around handshake, broad
   `rescue StandardError`) plus the collision guard above and optional
   `prefix:` support.
3. `Config#mcp_servers` — generic accessor, `"$VAR"` → `ENV` resolution;
   `mud_host`/`mud_port`/`mud_username`/`mud_password` removed (not kept
   alongside).
4. `.boukensha/settings.yaml` — `mud:` block replaced with `mcp_servers:`
   (one entry, for MUD) — a real, visible breaking change, not silently
   dual-supported.
5. `boukensha.rb` — `run`/`.repl` gain `mcp:` (nil/list/false, same
   convention as `working_dir:`), lose `mud:` and `mud_opts_from_config`;
   `require_relative "boukensha/tools/mud"` replaced with
   `require_relative "boukensha/tools/mcp"`.
6. `ruby/10_standard_tool_library/lib/boukensha/tools/mud.rb` — **removed**,
   not kept as a wrapper (reversed from the original design during
   review — the config break is already accepted, so a Ruby-level shim on
   top would just leave two permanent ways to configure the same thing).
7. `Repl` — `mud:` keyword → `mcp_servers:`, banner rewritten as specified
   above, `probe_mud`/`mud_status_string` deleted.
8. `MudMcp::Client` reused unrenamed, with a one-line comment in
   `Tools::Mcp` acknowledging a domain-agnostic bridge naming a
   `MudMcp`-namespaced class is a known, temporary seam.

**Deferred, explicitly:**

1. Splitting `mud_mcp` into a domain-agnostic `mcp` gem + a `mud_mcp` gem —
   still no second real MCP server to justify the split; revisit when one
   exists.
2. Namespacing/auto-renaming on collision — rejected as the default (4.2);
   `prefix:` is the manual escape hatch, not automatic.
3. Migrating `ruby/11_tui` / `ruby/12_context` to this generic path — out
   of scope, same as every prior review already flagged; those steps keep
   whatever MUD-integration shape they currently have.
4. Anything inside `ruby/13_mcp_server` itself — unchanged by this whole
   Part 2 arc, which only touches the Boukensha/Standard-Tool-Library side.
5. An automated test for this integration — still verified ad hoc (shell
   commands, one-off scripts), same gap flagged in
   `docs/week1_mcp_review_and_gaps.md`, still open.

This is the complete, implementation-ready spec — the next step should be
able to build directly from items 1–8 above without further design
decisions.
