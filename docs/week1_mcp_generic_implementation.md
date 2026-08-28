# Generic MCP Config: Implementation, Test, and the Startup Error Found

## Premise check (4.1)

4.1 asked to confirm the MCP server configuration had been added to
`settings.yaml`. Checked first rather than assuming: it hadn't. Every MCP
Part 2 document (`docs/week1_generic_mcp_architecture_design.md`,
`docs/week1_mcp_refactor_plan_review.md`, `docs/week1_mcp_final_design.md`)
was design-only — `settings.yaml` still had the old `mud:` block, `Config`
still had `mud_host` et al., `boukensha.rb` still had `mud:`/
`mud_opts_from_config`, and `Tools::Mud` was still the MUD-specific (if
already MCP-client-backed) wrapper from MCP Part 1.

Since the finalized design was explicitly marked implementation-ready and
this task's own 4.2/4.3 presuppose it exists, I implemented it — the 8
items from `docs/week1_mcp_final_design.md` §4.3 "implement now" — rather
than just reporting the gap and stopping.

## What was implemented

| File | Change |
|---|---|
| `lib/boukensha/registry.rb` | + `Registry#registered?(name)` |
| `lib/boukensha/config.rb` | `mud_host`/`mud_port`/`mud_username`/`mud_password` removed; + `Config#mcp_servers` (parses `mcp_servers:`, resolves `"$VAR"` env values against `ENV`) |
| `lib/boukensha/tools/mcp.rb` | **new** — generic `Tools::Mcp.register(registry, servers:)`: per-server `Timeout.timeout(10)`, broad `rescue StandardError`, collision guard (warn + keep first via `registry.registered?`), optional `prefix:` |
| `lib/boukensha/tools/mud.rb` | **deleted** — no compatibility wrapper kept (design review's reversed call) |
| `lib/boukensha.rb` | `run`/`.repl`: `mud:` → `mcp:` keyword; `Tools::Mcp.register` replaces `Tools::Mud.register`/`mud_opts_from_config`; require list updated |
| `lib/boukensha/repl.rb` | `mud:` → `mcp_servers:` (array of `{name:, client:}`); `mud_status_string`/`probe_mud` deleted; banner reports `"#{name} (connected)"` per server directly from registration results, no re-probing |
| `.boukensha/settings.yaml` | `mud:` block → `mcp_servers:` list, one `mud` entry, `command:` omitted (falls back to `MudMcp::Client`'s own default) |
| `README.md` | (unchanged by this task beyond the earlier floating-artifacts note) |

## 4.3 — the startup error, found and fixed

First launch attempt failed:

```
lib/boukensha.rb:164:in `repl': undefined local variable or method `mud' for Boukensha:Module (NameError)
    resolved_mud = mud == false ? nil : (mud || mud_opts_from_config(cfg))
```

Root cause: `Boukensha.run` and `Boukensha.repl` had near-identical but not
byte-identical `mud:`-handling blocks — `run`'s had a leading comment line,
`repl`'s didn't. My first edit pass targeted the comment+code block as one
`old_string`, which only matched `run`'s copy; `repl`'s copy (no comment
prefix) silently kept the old `mud`/`mud_opts_from_config` reference even
though its keyword argument had already been renamed to `mcp:` in the same
pass — a parameter rename with one of its two call sites not actually
updated. Fixed by editing `repl`'s block directly. Re-ran; clean boot.

## 4.2 — testing the updated configuration

**Live, via the actual `boukensha` command** (not a bypassed script),
against the real CircleMUD and the real Anthropic API:

```
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.10.0)   ║
╚══════════════════════════════════════╝
  config:      /home/mahdi/.boukensha
  provider:    anthropic (claude-haiku-4-5)  ✓ API key set
  mcp servers: mud (connected)
...
boukensha> check exits
**Current location exits:**
- **north** → By The Temple Altar
...
boukensha> [mud_mcp] server shutting down
Goodbye.
```

Real exit data, correct new banner line, clean shutdown, no orphan
`mud_mcp_server` process afterward.

**Isolation** (one misconfigured server doesn't take down the others):

```ruby
servers = [
  { name: "bad",  command: ["/no/such/executable"], env: {} },
  { name: "mud",  command: [], env: {MUD_HOST: ..., MUD_NAME: "dummy", ...} },
  { name: "mud2", command: [], env: {..., MUD_NAME: "dummy", ...}, prefix: "mud2" }
]
```
→ `bad` failed immediately (`Errno::ENOENT`, warned, skipped). `mud2` — same
underlying `MUD_NAME` as `mud`, so CircleMUD's concurrent-login handling
hung past the login prompts our regex-based login flow doesn't expect —
timed out at 10s exactly as designed, warned, skipped. `mud` alone still
registered all 27 tools and worked. (The `mud2` case is an artifact of
reusing one test character for two connections, not a bug — it's exactly
the collision `docs/week1_mcp_final_design.md` already flagged as
unresolved multi-client-per-character behavior, now empirically confirmed
to degrade the way isolation is supposed to: a timeout + warning, not a
hang or a crash of the whole registration.)

**Collision guard and `prefix:`**, tested directly since two real
distinct MUD identities weren't available:

```
[boukensha] MCP server "second": tool "look" collides with an already-registered tool — skipped
dispatch(look) => "first server look result"        # first registration survives
second_look registered? true
dispatch(second_look) => "fake result for look"      # prefix correctly disambiguates
```

**`mcp: false`**: `Boukensha.run(..., mcp: false)` — no subprocess spawned,
no crash, normal model response.

**Gem rebuilt and reinstalled** (`boukensha-0.10.0.gem`, matching the
convention already established for this step) after all of the above so
the installed artifact matches the code, not just the source tree via
`.boukensharc`. Re-ran the launch test once more post-install: clean.

## Net result

`settings.yaml`'s MCP config now genuinely exists, is genuinely tested (not
just unit-tested — the real `boukensha` command, the real model, the real
MUD), and the one real bug the process surfaced was found and fixed before
calling this done, not left for a later "review" step to catch.
