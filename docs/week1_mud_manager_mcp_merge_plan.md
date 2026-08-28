# Plan: Merge the MCP Server into the `mud_manager` Gem (5.1)

## Current state (two gems, one depending on the other)

```
week0_explore/mud_manager/        mud_manager gem — Session + Primitives only
week1_baseline/ruby/13_mcp_server/  mud_mcp gem — Dispatcher/Server/Client/Tools,
                                     depends on mud_manager
```

`ruby/10_standard_tool_library` depends on `mud_mcp` (which transitively
pulls `mud_manager`), and requires only `mud_mcp/client`.

## Target state (one gem)

```
week0_explore/mud_manager/
  mud_manager.gemspec              # version 0.1.0 -> 0.2.0; adds bin/mud_manager_mcp_server
  lib/
    mud_manager.rb                 # unchanged — Session/Primitives only, no auto MCP load
    mud_manager/
      session.rb, primitives.rb    # unchanged
      mcp.rb                       # new aggregator (was mud_mcp.rb): requires the 4 files below
      mcp/
        version.rb, dispatcher.rb, server.rb, client.rb, tools.rb   # moved, renamed
  bin/
    mud_manager_mcp_server         # was bin/mud_mcp_server
  examples/
    mcp_client_demo.rb             # was ruby/13_mcp_server/examples/example.rb
```

Module names move from `MudMcp::*` to the nested `MudManager::Mcp::*` — a
real merge, not just a file relocation that leaves a same-named module
awkwardly living inside a differently-named gem.

**`require "mud_manager"` still does NOT auto-load the MCP layer.** Same
discipline as before (MCP Part 1/4): a client-only consumer requires
`mud_manager/mcp/client` specifically, so `MudManager::Session`/
`Primitives` never load into an agent process that only wants to talk MCP.
Only `mud_manager/mcp` (the full aggregator, used by the server executable
itself) pulls in `tools.rb`, which is the one file that still needs
`Session`/`Primitives`.

## What has to change in the one real consumer

`ruby/10_standard_tool_library`:
- `boukensha.gemspec`: dependency `mud_mcp ~> 0.1` → `mud_manager ~> 0.2`
- `lib/boukensha/tools/mcp.rb`: `require "mud_mcp/client"` →
  `require "mud_manager/mcp/client"`; `MudMcp::Client` →
  `MudManager::Mcp::Client`
- `vendor/cache`/`Gemfile.lock`: rebuilt against the new gem (same
  `gem build` → copy into `vendor/cache` → `bundle install --local`
  sequence already used twice in this arc)

Not asked for by 5.1–5.4 directly, but doing it is what makes 5.4's
verification ("does the MCP server expose the expected tools") mean
something beyond a throwaway script — every prior verification in this arc
went through the real consumer, and leaving `boukensha` depending on a
gem (`mud_mcp`) that's about to stop being maintained separately would
just recreate the exact "obsolete scaffolding" problem MCP Part 3 already
cleaned up once.

## Disposition of `ruby/13_mcp_server`

Removed once the new location is built, installed, and verified working —
not before. It was entirely generated in this session (MCP Part 1),
nothing outside this repo depends on it, and keeping a second, now-inert
copy of the same code around would be exactly the kind of dead weight this
merge exists to eliminate. Ordering matters: prove the new location works
first, so there's always a working fallback until it does.
