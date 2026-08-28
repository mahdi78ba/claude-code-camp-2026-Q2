# Review: Current MCP Implementation, Gaps, and Integration Status (Part 5)

## 5.2 first, because it changes how to read 5.1

The checklist item asks to **confirm** the current implementation is only a
standalone example and hasn't been integrated into the Standard Tool
Library yet. Checked it directly rather than taking that as given — it's
**no longer true**, and I have stronger evidence for that than what Part 4
originally shipped with.

- **Right after Part 3**, the claim was accurate — I wrote it myself, as
  gap 1 in `docs/week1_mcp_server_review.md`: "The Ruby agent hasn't been
  migrated to use this server yet... `Boukensha::Tools::Mud` still
  registers tools in-process."
- **Part 4 closed that gap** — `ruby/10_standard_tool_library`'s
  `Tools::Mud.register` was rewritten as an MCP client proxy. But the
  verification I ran for Part 4 only proved the mechanism, not the
  integration surface: a hand-rolled script calling `registry.dispatch`
  directly, skipping `Boukensha.run`, `Config`, `RunDSL`, and the real
  `Agent`/`Client`/model loop entirely. That's a fair thing to call
  "still basically a standalone example" — it exercised the same objects a
  real user path uses, but not through the real user path.
- **For this review, I ran the actual documented entry point** —
  `Boukensha.run`, the same call `examples/example.rb` makes, with the real
  configured Anthropic API key, against the live CircleMUD:

  ```ruby
  Boukensha.run(
    task: "Connect to the MUD, look at your surroundings, check your score, " \
          "then look at the available exits and tell me what you see.",
    working_dir: false
  )
  ```

  Result (Claude Haiku 4.5, via the real `Agent` loop, calling tools that
  round-tripped through the spawned `mud_mcp_server` subprocess to the live
  MUD and back):

  > **Location:** Temple Of Midgaard (southern temple hall)
  > **Current Status:** HP: 25/25 · Mana: 100/100 · Movement: 15/84 ·
  > Level 1 Swordpupil · Gold: 0 · hungry and thirsty
  > **Available Exits:** North → By The Temple Altar · East → The Midgaard
  > Donation Room · South → The Temple Square · West → The Reading Room ·
  > Down → The Temple Square

  Every fact in that summary is real, live MUD state (matches the `look`
  and `check score` output already captured in
  `docs/week1_mcp_standard_tool_library_integration.md`) — not fabricated,
  not cached. The model actually called `look`, `check`, and `look`-with-a-
  direction through the MCP-proxied tools, got real text back, and wrote a
  coherent answer from it.

**Conclusion: as of this review, the integration is real and works
end-to-end through the Standard Tool Library's actual entry point, not
just through a standalone example.** `examples/example.rb` itself doesn't
print the agent's answer (that's a pre-existing trait of that file, unrelated
to this work — confirmed by diff, it's untouched), which is why this needed
a one-off script to actually see the result; that's a documentation/demo gap
(see below), not an integration gap.

## 5.1 — Gaps found

Real ones, not the one 5.2 asked about (already resolved above):

1. **`ruby/11_tui` and `ruby/12_context` are unmigrated.** Both carry their
   own copy of the pre-MCP `Tools::Mud`, requiring `mud_manager` directly
   and holding their own in-process `MudManager::Session`. Only step 10 —
   the one this task named — was migrated. Anyone running the TUI or the
   Context-management step still gets the old path, with its own
   independent MUD login, potentially colliding with a step-10 run against
   the same character.

2. **`examples/example.rb` doesn't surface its own result.** `Boukensha.run`
   returns the agent's final answer as a string; the example script
   discards it. This predates this work (confirmed via `git diff` — the
   file is untouched) but it means the documented demo currently *looks*
   like it does nothing when run, which is exactly the kind of thing that
   makes "is this actually integrated?" hard to answer by inspection alone
   — worth a `puts result` fix independent of MCP.

3. **`Gemfile.lock` was hand-edited, not Bundler-verified.** I updated the
   `PATH`/`GEM` stanzas to say `mud_mcp` instead of `mud_manager` by hand,
   because `bundle install` fails outright for this dependency (confirmed:
   `Could not find compatible versions... mud_mcp ~> 0.1 could not be
   found in rubygems repository... cached gems or installed locally`) —
   the same pre-existing wrinkle already flagged for `mud_manager` in
   `docs/week1_standard_tool_library_review.md`, now inherited by `mud_mcp`
   too. The lock file is a plausible reconstruction of what a working
   `bundle install` would produce, not something Bundler itself confirmed.
   `bundle`-based workflows for this step remain broken; only direct
   `ruby`/`require` invocation (what every README already documents) works.

4. **Registering MUD tools now costs a whole extra process, every time.**
   Before: `Tools::Mud.register` opened one socket in the calling process.
   Now: it spawns a full second Ruby interpreter (`mud_mcp_server`) via
   `Open3.popen2`, then does the MCP handshake, *then* that subprocess opens
   the socket and logs in. Same end state, measurably more startup latency
   and memory per `Boukensha.run`/`.repl` call. Not broken, just a real cost
   the architecture design didn't quantify.

5. **No committed automated test for this integration.** Every check in
   this review and in Part 4 (the `$LOADED_FEATURES` assertion, the tool
   count, the live `Boukensha.run` call) was run ad hoc from the shell, not
   as a test file in the repo. Nothing would catch a future regression here
   automatically.

6. **Multi-client/concurrent-session semantics remain unresolved** — flagged
   as an open question in `docs/week1_mcp_architecture_design.md` (2.2) and
   still open. Two `Boukensha.run` calls (or a step-10 run alongside an
   unmigrated step-12 run) against the same MUD character would each spawn
   their own session and log in independently; CircleMUD's own "reconnecting"
   handling is the only thing standing between that and a kicked session.
   This isn't new — it's the same limitation the pre-MCP design had — but
   MCP was partly motivated by enabling multiple language clients, and that
   scenario specifically hasn't been tested.

7. **`ruby/13_mcp_server/examples/example.rb` is a separate, intentionally
   standalone demo** of the MCP client/server pair on its own (no Boukensha
   involved at all). Worth calling out explicitly so it isn't mistaken for
   evidence about step 10's integration status one way or the other — it
   never was that evidence; the `Boukensha.run` test above is.
