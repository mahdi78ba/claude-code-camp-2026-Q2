# Debugging the MCP Startup Issue (MCP Part 4, 1)

## Checked first: does Boukensha currently fail to start?

No. Fresh test, right now, before assuming the premise:

```
$ boukensha
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.10.0)   ║
╚══════════════════════════════════════╝
  mcp servers: mud (connected)
boukensha> /exit
[mud_manager/mcp] server shutting down
Goodbye.
```
Exit code `0`. And the installed gem is byte-identical to source right now
(`diff -rq` on both `boukensha`'s and `mud_manager`'s installed `lib/`+`bin/`
against their source directories — zero differences either way).

## 1.1/1.2 — What this describes did happen, and was already root-caused

This is the exact failure already found and fixed while reviewing MCP
startup configuration (`docs/week1_mcp_startup_config_review.md`, item 1),
not a new one. Recapping the investigation, since that's what 1.1/1.2 ask
for:

**Symptom**, first reproduced with the legacy `MUD_NAME` env-var path:
```
$ MUD_NAME=dummy MUD_PASSWORD=helloworld boukensha
lib/boukensha.rb:128:in `repl': unknown keyword: :mud (ArgumentError)
```

**Root cause (1.2, confirmed)**: the *installed gem* was carrying an
outdated MCP configuration shape. `boukensha_loader.rb` — bundled inside
the gem, not something a caller edits — still built
`repl_opts[:mud] = {host:, port:, name:, password:}` and passed it to
`Boukensha.repl(**repl_opts)`. That was correct before the generic MCP
refactor (MCP Part 3, item 4), which renamed `Boukensha.repl`'s keyword
from `mud:` to `mcp:` and changed its expected shape to
`[{name:, command:, env:}]`. The refactor updated `boukensha.rb` and
`repl.rb`, but the edit that renamed the keyword in the *loader's*
legacy-override branch didn't happen in the same pass — so the gem kept
shipping a caller (`boukensha_loader.rb`) still speaking the pre-refactor
shape to a method that no longer accepted it. `require`-time success masked
it: the file `require`s cleanly (no syntax error), and the mismatch only
surfaces when that specific branch actually executes (`MUD_NAME` set).

**Fix**: `boukensha_loader.rb`'s `repl_opts[:mud] = {...}` →
`repl_opts[:mcp] = [{name: "mud", env: {...}}]`, matching what
`Tools::Mcp.register` actually expects now.

## 1.3 — Rebuild and reinstall, and reconfirmation it's still current

Already done as part of the same fix:
```
$ gem build boukensha.gemspec        # -> boukensha-0.10.0.gem
$ gem install --user-install --force ./boukensha-0.10.0.gem
```
Re-verified just now (this task) that the installed gem is still in that
fixed state, not stale again — the `diff -rq` above against current
source came back empty. Both the legacy `MUD_NAME` path and the normal
`settings.yaml`-driven path were re-tested live in
`docs/week1_mcp_startup_config_review.md` and once more in
`docs/week1_mcp_validation.md`; nothing has changed since.

## Net finding

There is no open startup failure right now. If this checkpoint is meant
to catch the specific "renamed a keyword in one file, forgot the other
caller, shipped a stale gem" mistake, it already happened once this
session and was already caught, root-caused, and fixed — this doc is the
paper trail for that, not a new fix.
