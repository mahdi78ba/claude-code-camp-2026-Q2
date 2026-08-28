# MCP Part 4 — Verifying the MCP Integration (3)

Verifies the three specific claims: Boukensha launches with the MCP
server starting successfully, Boukensha works from outside the repository
root, and the configured MCP server(s) load successfully. Follows the
`--mcp` executable rename and `settings.yaml` update from
`docs/week1_mcp_server_config_update.md`.

## Setup at time of verification

```
$ gem list boukensha mud_manager -a
boukensha (0.10.0, 0.9.0)
mud_manager (0.3.0, 0.2.0, 0.1.0)

$ which boukensha
/home/mahdi/.local/share/gem/ruby/3.2.0/bin/boukensha

$ which mud_manager
/home/mahdi/.local/share/gem/ruby/3.2.0/bin/mud_manager

$ cat ~/.boukensharc
/home/mahdi/claude-code-camp-2026-Q2/week1_baseline/ruby/10_standard_tool_library
```

Both executables resolve from `~/.local/share/gem/ruby/3.2.0/bin` (the
`--user-install` location — this environment has no passwordless `sudo`
for a system-wide install), which is now on `$PATH` via the export added
to `~/.bashrc` in the prior step.

`.boukensha/settings.yaml`'s relevant section at time of test:

```yaml
mcp_servers:
  - name: mud
    command: ["mud_manager", "--mcp"]
    env:
      MUD_HOST: localhost
      MUD_PORT: "4000"
      MUD_NAME: dummy
      MUD_PASSWORD: helloworld
```

## Test 1 — Launch from outside the repository root

```
$ cd /tmp && boukensha
```

`/tmp` is not inside `claude-code-camp-2026-Q2` at all — not just a
different subdirectory of the repo, an entirely separate filesystem
location with no relationship to the checkout. Confirms `command:
["mud_manager", "--mcp"]` resolves purely via `$PATH`, with no repo- or
gem-install-path-relative assumption left over from the old
`[RbConfig.ruby, <path to the .rb file>]` default.

Full transcript:

```
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.10.0)   ║
╚══════════════════════════════════════╝
  config:      /home/mahdi/.boukensha
  provider:    anthropic (claude-haiku-4-5)  ✓ API key set
  mcp servers: mud (connected)

  /quiet or /loud   toggle logging
  /clear           reset conversation history
  /exit or /quit    leave the REPL

boukensha> [mud_manager/mcp] server shutting down
Goodbye.
```

**Result: pass.** No error, no traceback, clean banner, clean `/exit`.

## Test 2 — MCP server starts successfully

Two independent pieces of evidence from the same run, not just one:

1. **The banner's `mcp servers: mud (connected)` line.** This isn't a
   guess or a static string — it's built in `Repl#mcp_status_string`
   directly from what `Tools::Mcp.register` returned. `register_one`
   only returns a `{name:, client:}` entry after `client.handshake`
   inside a `Timeout.timeout` block actually completes — i.e. the MCP
   `initialize` round trip over the spawned subprocess's stdio genuinely
   succeeded. If the subprocess had failed to spawn, hung, or errored,
   this line would read `(not configured)` instead (empty array) and a
   `warn` would have printed to stderr — neither happened.
2. **The shutdown line.** `[mud_manager/mcp] server shutting down` comes
   from inside the spawned server subprocess itself
   (`MudManager::Mcp::Server#shutdown`), printed to its own stderr and
   visible in the combined transcript above. Its presence means a real
   second process existed, ran, and tore down cleanly on `/exit` —
   consistent with `client.close` in `Tools::Mcp`'s `at_exit` hook (or the
   REPL's own teardown) actually reaching the subprocess.

**Result: pass.**

## Test 3 — Configured MCP servers load successfully

`.boukensha/settings.yaml` configures exactly one server, named `mud`.
The banner reports exactly `mud (connected)` — one entry, matching the one
configured entry, by name. (`Repl#mcp_status_string` would render
multiple as a comma-separated list if more than one were configured and
connected — not exercised here since there's only one server in this
project's config, but the code path is shared with the multi-server
generic design from MCP Part 2.)

**Result: pass.**

## Post-test cleanup check

```
$ ps aux | grep -iE "mud_manager|boukensha" | grep -v grep
(no output)
```

No orphaned `mud_manager --mcp` subprocess or leftover `boukensha` process
after the REPL exited — the subprocess lifecycle is fully scoped to the
parent's run, not leaked.

## Technical observations

- **This is the first time `mcp_servers:`'s `command:` field has been
  exercised with a real value.** Every prior test in this MCP arc either
  omitted `command:` (falling back to `MudManager::Mcp::Client`'s
  in-code default) or drove the client directly from a script. This is
  the first end-to-end pass where `settings.yaml` itself supplies the
  exact argv array (`["mud_manager", "--mcp"]`) that gets handed to
  `Open3.popen2` — confirms the YAML → `Config#mcp_servers` →
  `Tools::Mcp.register` → `Client.new(command:)` chain carries an array
  value through intact (not, say, silently stringified or split on
  whitespace somewhere in between).
- **The `~/.bashrc` `$PATH` fix is doing real, load-bearing work here.**
  Without it, this exact test would fail — not with a Boukensha-level
  error, but with `Errno::ENOENT` from `Open3.popen2` failing to find
  `mud_manager` on `$PATH`, caught by `Tools::Mcp.register_one`'s
  `rescue StandardError`, surfacing only as a quiet `warn` to stderr and
  `mcp servers: (not configured)` in the banner — i.e. a silent
  degradation, not a crash, which is worth knowing before assuming a
  clean-looking banner on some *other* machine means the fix is
  unnecessary there.
- **The REPL banner is sufficient to answer "did MCP start" without
  reading logs.** No need to grep `.boukensha/sessions/*.jsonl` or add
  `-v`/debug output for this particular question — the existing banner
  line was designed (per `docs/week1_mcp_final_design.md`, §4.1) to
  report exactly this, from real registration results rather than a
  reachability probe, and it does.
- **Two installed versions each of `boukensha` (0.9.0/0.10.0) and
  `mud_manager` (0.1.0/0.2.0/0.3.0) remain side by side** — RubyGems
  resolves the executables to the latest by default, which is what both
  `which` calls above confirm, but this is the same latent multi-version
  situation flagged in `docs/week1_mcp_validation.md` (7.2, item 3),
  unchanged by this verification.
