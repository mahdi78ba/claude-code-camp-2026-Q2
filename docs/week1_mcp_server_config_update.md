# Updating the MCP Server Configuration (MCP Part 4, 2)

## What actually changed

`.boukensha/settings.yaml`'s `mud` entry gained an explicit `command:`:

```yaml
mcp_servers:
  - name: mud
    command: ["mud_manager", "--mcp"]
    env: { ... }
```

Getting there required more than editing YAML, since the thing being
pointed at (2.1's "installed mud-manager executable") didn't fully exist
in the form this implies yet:

- **`bin/mud_manager_mcp_server` → `bin/mud_manager`, gained `--mcp`.** A
  dedicated single-purpose executable has no reason to check a flag before
  doing its one job; a general `mud_manager` executable does, since
  `--mcp` is what selects "run as an MCP server" as opposed to whatever
  else this entry point might do later. Renamed and added the check:
  `ARGV.include?("--mcp")` or `abort` with a usage message.
- **`mud_manager.gemspec`**: `executables`/`files` updated for the rename;
  version `0.2.0` → `0.3.0` (the executable's own interface changed, not
  just its name).
- **`MudManager::Mcp::Client`**: `DEFAULT_COMMAND` replaced
  `DEFAULT_SERVER` — `["mud_manager", "--mcp"]` (the installed command) in
  place of `[RbConfig.ruby, <path to the .rb file inside wherever this gem
  happens to be installed>]`. That old default was exactly the
  "repository/gem-relative Ruby command" 2.1 asks to move away from — it
  bypassed the whole point of `gem install` having put a proper executable
  stub on `$PATH`, going straight at the underlying script file instead.
  Dropped the now-unneeded `require "rbconfig"`.
- **2.2 — the `--mcp` argument**: didn't exist anywhere before this task
  (checked: `grep -rn -- "--mcp"` across the repo came back empty). Its
  purpose only makes sense with the executable rename above — "preserve
  it" meant making sure it survives as its own separate array element
  (`["mud_manager", "--mcp"]`, two argv entries) once `command:` became
  explicit, not merging it into a single string or dropping it when
  switching away from the old invocation style.
- **2.3 — comments**: `settings.yaml`'s `mcp_servers:` comment rewritten to
  describe the explicit installed-executable-plus-flag setup instead of
  the old omit-and-let-the-client-default-decide behavior it used to
  document.

## The prerequisite this surfaced: `$PATH`

`command: ["mud_manager", "--mcp"]` only resolves if `mud_manager` is
actually findable on `$PATH` when Boukensha (not `bundle exec`, which sets
its own `$PATH` via the bundle's `vendor/bundle/.../bin`) spawns the
subprocess directly. Checked against the user's actual `~/.bashrc`/
`~/.profile` (not just this session's shell) — the gem executables
directory (`~/.local/share/gem/ruby/3.2.0/bin`, `--user-install`'s
location, since this environment has no passwordless `sudo` for a
system-wide install) wasn't on it. This is exactly
`docs/week1_mcp_validation.md`'s 7.2 item 1, deferred there — this task's
own instructions can't actually work without it, so fixed it now rather
than defer it twice: appended a `$PATH` export to `~/.bashrc`.

Verified two ways: `bash -ic 'which mud_manager'` (a genuinely interactive
shell, matching what the user's real terminal does) resolves correctly;
`bash -c`/`bash -lc` (non-interactive) still don't, because `~/.bashrc`'s
own standard Debian guard (`case $- in *i*) ;; *) return;; esac`) skips
everything past that line for non-interactive shells — expected, not a
sign the fix is wrong, just a reminder that this sandbox's own Bash tool
calls aren't interactive shells either, so this session kept testing via
explicit inline `PATH` exports (as it has throughout) even after the real
fix landed.

## Rebuilt, reinstalled, and verified end-to-end

`mud_manager` 0.3.0 built and installed; `boukensha.gemspec`'s dependency
bumped `~> 0.2` → `~> 0.3` (the *library* default changed, not just the
executable, so the old constraint would've been misleadingly loose);
`vendor/cache`/`Gemfile.lock` refreshed the same way as every prior gem
bump in this arc; `boukensha` rebuilt and reinstalled.

Live, through the real `boukensha` command, real Anthropic API, real MUD:

```
mcp servers: mud (connected)
boukensha> check exits
You have two exits available:
- north to Behind The Temple Altar
- south to The Temple Of Midgaard
boukensha> [mud_manager/mcp] server shutting down
Goodbye.
```

No orphan process afterward. Also separately confirmed the whole chain
through `bundle exec` (which resolved `mud_manager` via its own bundled
`vendor/bundle/.../bin`, independent of the `~/.bashrc` fix) — two
independent paths to the same working result.
