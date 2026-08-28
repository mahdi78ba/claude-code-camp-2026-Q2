# Mud Manager MCP Merge — Executed and Verified (5.2–5.4)

Plan: `docs/week1_mud_manager_mcp_merge_plan.md`. This records what
actually happened and what verified it.

## 5.2 — Executed

- Moved `MudMcp::{Dispatcher,Server,Client,Tools}` from
  `ruby/13_mcp_server/lib/mud_mcp/*` into
  `week0_explore/mud_manager/lib/mud_manager/mcp/*`, renamed to the nested
  `MudManager::Mcp::*` namespace (a real merge, not a same-named module
  relocated into a differently-named gem).
- `mud_manager.gemspec`: `0.1.0` → `0.2.0`, gained
  `bin/mud_manager_mcp_server` (was `bin/mud_mcp_server`), description
  updated. Still zero external dependencies (json/open3/rbconfig/socket/
  thread all stdlib).
- `require "mud_manager"` still doesn't auto-load the MCP layer — same
  discipline as before, a client-only consumer requires
  `mud_manager/mcp/client` specifically.
- Updated the one real consumer, `ruby/10_standard_tool_library`:
  `boukensha.gemspec` (`mud_mcp ~> 0.1` → `mud_manager ~> 0.2`),
  `lib/boukensha/tools/mcp.rb` (`require "mud_mcp/client"` →
  `require "mud_manager/mcp/client"`, `MudMcp::Client` →
  `MudManager::Mcp::Client`).
- Rebuilt `vendor/cache`/`Gemfile.lock` the same way as the two prior fixes
  in this arc: copied the new `.gem` in, `bundle install --local`,
  `bundle clean` to drop the now-unused `mud_mcp-0.1.0`/`mud_manager-0.1.0`
  installs from `vendor/bundle`.
- Confirmed nothing outside `ruby/13_mcp_server` itself depended on it
  (only prose mentions of "mud_mcp" in comments/descriptions turned up),
  then deleted the directory and uninstalled the standalone `mud_mcp` gem
  from the local gem environment — not before rebuilding, reinstalling,
  and re-verifying the merged version end-to-end (see 5.3/5.4), so there
  was always a working fallback until the new location was proven.

## 5.3 — Built and installed

```
$ gem build mud_manager.gemspec        # -> mud_manager-0.2.0.gem
$ gem install --user-install ./mud_manager-0.2.0.gem
$ gem list mud_manager -a
mud_manager (0.2.0, 0.1.0)             # 0.2.0 resolves as default
```

## 5.4 — Verified the merged server exposes the expected tools

**Standalone, from a neutral directory** (`/tmp`, gem-installed path only,
no source-tree `$LOAD_PATH` tricks):

```
handshake: {:name=>"mud-manager-mcp-server", :version=>"0.1.0"}
tool count: 27
tool names: attack, cast_spell, channel_say, check, consider, consume_item,
drop_item, equip_item, examine, flee, get_item, look, move, mud_connect,
mud_disconnect, mud_status, practice, put_item, save_character, say,
send_raw, set_position, shop, skill_strike, tell, track, use_magic_item
```
— the exact same 27 tools the pre-merge `mud_mcp` gem exposed, plus a real
`look` call returning live CircleMUD output.

**Through the real consumer**, twice — once via `bundle exec` directly
against the registry, once via the actual installed `boukensha` command
(rebuilt against the new dependency), against the real live MUD and the
real Anthropic API:

```
mcp servers: mud (connected)
boukensha> check score
**Status Summary:**
- Health: 25/25 HP
...
boukensha> [mud_manager/mcp] server shutting down
Goodbye.
```

**Post-cleanup regression check**: after deleting `ruby/13_mcp_server` and
running `gem uninstall mud_mcp -a`, re-ran the `boukensha` launch once
more to confirm nothing was silently still relying on the retired gem —
clean boot, same result, no orphan process.
