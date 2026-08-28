# Reviewing MCP Startup Configuration (6)

## 6.1 — How the MCP server is actually launched by the agent

Two paths, traced through the current code:

**Primary path** (no `MUD_NAME` env var set): `Boukensha.run`/`.repl`
(`lib/boukensha.rb`) → `mcp: nil` → `cfg.mcp_servers` (parses
`settings.yaml`'s `mcp_servers:` list, resolving any `"$VAR"` env value
against `ENV`) → `Tools::Mcp.register(registry, servers: resolved_mcp)` →
for the `mud` entry, `command:` is absent, so
`MudManager::Mcp::Client.new(env: {...})` falls back to its own default
(`[RbConfig.ruby, DEFAULT_SERVER]`, resolved relative to wherever the
`mud_manager` gem is actually installed — no reliance on `$PATH`) →
`Open3.popen2` spawns `bin/mud_manager_mcp_server` → `client.handshake`
performs the MCP `initialize` round trip over that subprocess's stdio.

**Legacy override path** (`MUD_NAME` env var set): `boukensha_loader.rb`'s
`load_and_start_repl` builds a `repl_opts[:mcp]` entry from
`MUD_HOST`/`MUD_PORT`/`MUD_NAME`/`MUD_PASSWORD` env vars directly and calls
`Boukensha.repl(**repl_opts)` — bypassing `settings.yaml` entirely, by
design (this predates the whole MCP arc; it's the same env-var escape
hatch step 9 already documented, just needing to build the new `mcp:`
shape instead of the old `mud:` one).

**This second path was broken** until this review — see 6.3.

## 6.2 — Is `settings.yaml` the primary source?

Yes, for the case that actually matters day to day: `mcp: nil` (the
default `Boukensha.run`/`.repl` argument) reads `cfg.mcp_servers`, i.e.
`settings.yaml`'s `mcp_servers:` list. That's what every launch in this
whole MCP arc has gone through, `MUD_NAME`-env-var testing aside.

The one caveat worth stating plainly rather than glossing over: the
legacy `MUD_NAME` env var path takes priority *over* `settings.yaml` when
set (`ENV.fetch` values, not `cfg.mcp_servers`) — so "primary" means
"default when no override is present," not "the only path, full stop."
That's intentional, predates this session, and is the same precedence
`docs/plans/floating_artifacts/boukensharc.md`-adjacent env-var overrides
already use elsewhere in this loader (`BOUKENSHA_PATH` over
`~/.boukensharc` over the bundled default) — env vars winning over config
files is the loader's consistent convention, not something introduced by
the MCP work.

## 6.3 — What needed reverting or fixing

No literal "undo this experimental hack" material turned up — nothing in
`settings.yaml`, `.env`, or `~/.boukensharc` is leftover troubleshooting
residue; every persisted change across this arc was a deliberate, already-
documented part of the design. What 6.1's trace *did* surface were loose
ends from the two rounds of renaming this session did (`mud:` → `mcp:` in
MCP Part 3, then the `mud_mcp` → `mud_manager` merge in Part 5) that
weren't fully propagated everywhere — inconsistent leftovers, not
unnecessary changes, but worth fixing rather than leaving as known-broken
for a future task to rediscover:

1. **`boukensha_loader.rb`'s legacy `MUD_NAME` path was genuinely broken.**
   Confirmed by actually running it:
   ```
   $ MUD_NAME=dummy MUD_PASSWORD=helloworld boukensha
   lib/boukensha.rb:128:in `repl': unknown keyword: :mud (ArgumentError)
   ```
   It still built `repl_opts[:mud] = {...}` — a keyword `Boukensha.repl`
   stopped accepting back in MCP Part 3 (renamed to `mcp:`). Fixed to
   build `repl_opts[:mcp] = [{name: "mud", env: {...}}]`, the shape
   `Tools::Mcp.register` actually expects. Re-tested with `MUD_NAME` set:
   clean boot, `mcp servers: mud (connected)`, clean shutdown. Also
   re-tested *without* `MUD_NAME` set, to confirm the fix didn't disturb
   the primary path: unaffected.
2. **Stale comments, now corrected**: `boukensha_loader.rb`'s header
   ("MUD connection details come from settings.yaml (mud: block)"),
   `settings.yaml`'s own comment (still named `MudMcp::Client`/"the
   mud_mcp gem", both retired in the Part 5 merge), and
   `examples/example.rb`'s header (referenced the removed
   `Boukensha::Tools::Mud` and the old `mud:` config key) — all updated to
   describe what's actually there now.
3. **Left alone, deliberately**: `README.md`'s "Known limitations"
   section still describes `Tools::Mud.register`'s old auto-connect
   behavior. That's a dated historical review (from before this session,
   predating the whole MCP arc), not troubleshooting residue from this
   work — rewriting it would blur a historical record rather than clean
   up anything I actually left behind, so it stays as-is.

Rebuilt and reinstalled the `boukensha` gem after the `boukensha_loader.rb`
fix (it ships inside the gem) and re-verified both launch paths live
against the real MUD and real Anthropic API. No orphan processes after
either.
