# MCP Part 3 — Reviewing the Refactor, Removing Obsolete Scaffolding

Note on scope: this reviews the MCP refactor that's actually implemented in
code — `ruby/13_mcp_server` + `ruby/10_standard_tool_library`'s
`Tools::Mud` (MCP Part 1, steps 3–4). The multi-server *generic* design
from MCP Part 2 was only ever documented (`docs/week1_mcp_final_design.md`
and friends) — nothing from that design has been implemented yet, so
there's no generic-refactor code to review here.

## 1.1 — Does the agent still contain built-in tools?

**`ruby/10_standard_tool_library`: no.** `lib/boukensha/tools/mud.rb` is
78 lines, requires only `mud_mcp/client`, and contains zero MUD-domain
logic — no `MudManager`, no telnet, no CircleMUD command strings. It
spawns an MCP server subprocess, calls `tools/list`, and proxies whatever
comes back. Confirmed again just now (re-ran the `$LOADED_FEATURES` check
from the Part 4 review, still holds) and re-verified live end-to-end
through `bundle exec` this time (see 1.3).

**Caveat this task's wording glosses over**: "the agent" isn't singular in
this repo — `ruby/11_tui` and `ruby/12_context` are separate lesson steps,
each with their own copy of the pre-MCP `Tools::Mud` (~480 lines,
`require "mud_manager"` directly, hardcoded `registry.tool` blocks per
command). Those **do** still contain built-in tools. Every prior review in
this arc (`docs/week1_mcp_standard_tool_library_integration.md`,
`docs/week1_mcp_review_and_gaps.md`, `docs/week1_mcp_genericity_review.md`)
flagged this as deliberately out of scope — each MCP Part 1 task named
"the Standard Tool Library" specifically, not the later steps. I haven't
reversed that judgment on my own here, since 1.2 (below) is about removing
things that are *already* obsolete, not performing a new migration — steps
11/12's implementations aren't obsolete, they're simply not yet migrated,
which is a different thing. **If "the agent no longer contains built-in
tools" is meant to hold across the whole Boukensha lineage, that's still
not true today** — flagging rather than either quietly ignoring it or
unilaterally rewriting two unrelated lesson steps. Say if you want that
migration done; it's the same mechanical change already proven in step 10.

## 1.2 — Obsolete scaffolding: found one real thing, fixed it

Looked for literal dead code left behind by the refactor in
`ruby/10_standard_tool_library` — there wasn't any (the tools/mud.rb
rewrite already replaced the old ~480-line implementation in place; there's
no parallel "old version" file sitting around, and `git diff` shows a
clean replacement, not an addition alongside the old code).

What I did find was **incomplete**, not obsolete, but it's exactly the kind
of refactor-era scaffolding gap this step asks to clean up:
`vendor/cache/` (git-tracked, unlike `vendor/bundle/`) still had
`mud_manager-0.1.0.gem` cached — correctly, since `mud_mcp` still depends
on it transitively — but was **missing `mud_mcp-0.1.0.gem` itself**, the
new *direct* dependency the gemspec was repointed at in Part 4. That gap is
exactly why `bundle install` has failed outright in every review since the
original step-10 review — three separate docs recorded "the same wrinkle,"
assuming it was unfixable without network access to a real gem index.

It wasn't. Copied the already-built `mud_mcp-0.1.0.gem` (from
`ruby/13_mcp_server/`) into `vendor/cache/`, then:

```
$ bundle install --local
Installing mud_mcp 0.1.0
Bundle complete! 2 Gemfile dependencies, 5 gems now installed.

$ bundle check
The Gemfile's dependencies are satisfied

$ bundle install       # works without --local too, now that the cache is complete
Bundle complete! 2 Gemfile dependencies, 5 gems now installed.
```

Bundler regenerated `Gemfile.lock` itself in the process — replacing the
hand-reconstructed version from MCP Part 1 (flagged in
`docs/week1_mcp_review_and_gaps.md` gap 3 as "a plausible reconstruction,
not something Bundler itself confirmed") with a real, tool-verified one.
That gap is now closed, not just documented as a known limitation.

Nothing else in `vendor/`, the gemspec, or the Gemfile needed removing —
everything else was already either correct or, per the mud_manager entry,
still genuinely needed.

## 1.3 — MCP client implementation, re-verified before continuing

Ran the same kind of check as the Part 4/5 reviews, but this time through
`bundle exec` — the environment the Gemfile/Gemfile.lock fix in 1.2 now
makes possible, and the more rigorous check since it uses the vendored
gems, not whatever happens to be on the system gem path:

```
$ bundle exec ruby -e '
  require "boukensha/context"; require "boukensha/registry"; require "boukensha/tools/mud"
  registry = Boukensha::Registry.new(Boukensha::Context.new(task: "..."))
  client = Boukensha::Tools::Mud.register(registry, host: "localhost", port: 4000, name: "dummy", password: "helloworld")
  puts registry.dispatch("check", kind: "exits")
  client.close
'
```

Result: 27 tools registered, real live exit data back from CircleMUD
("Obvious exits: north - By The Temple Altar…"), clean `client.close`, no
orphan `mud_mcp_server` process left behind afterward (`ps aux` checked).
The MCP client implementation is confirmed working end-to-end, through the
actual bundled dependency chain this time, not just an ad hoc script
pointed at system gems.

## What changed

```
M  ruby/10_standard_tool_library/Gemfile.lock   (regenerated by Bundler, not hand-edited)
A  ruby/10_standard_tool_library/vendor/cache/mud_mcp-0.1.0.gem
```

(`boukensha.gemspec` and `tools/mud.rb` were already changed in MCP Part 1
— unaffected by this review.) Nothing removed, because nothing obsolete
survived to be removed — the one gap found was incompleteness in the
vendor cache, now fixed.
