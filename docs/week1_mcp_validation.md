# Validating the Current State (7)

Terminology used below matches the task: **Boukensha** is the agent
application; **boukensha** is the CLI executable; **`.boukensharc`** is the
CLI configuration file (which step boukensha loads); **`.boukensha/`** is
the agent's own configuration directory (`settings.yaml`, prompts,
sessions, `.env`).

## 7.1 — Running the updated implementation

`.boukensharc` correctly points at `ruby/10_standard_tool_library` (set
during MCP Part 3's launch test, per
`docs/plans/floating_artifacts/boukensharc.md`). Ran boukensha by its full
installed path (not the bare command — see 7.2, item 1) with three real
turns, no `/exit` shortcut, to exercise repeated MCP round-trips in one
session rather than just a boot-and-quit:

```
$ ~/.local/share/gem/ruby/3.2.0/bin/boukensha
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.10.0)   ║
╚══════════════════════════════════════╝
  config:      /home/mahdi/.boukensha
  provider:    anthropic (claude-haiku-4-5)  ✓ API key set
  mcp servers: mud (connected)

boukensha> look
You're in the Temple of Midgaard...
boukensha> move north
You're now at the Temple Altar...
boukensha> check score
**Character Status:** Level 1 (Dummy the Swordpupil), 25/25 HP...
boukensha> /exit
[mud_manager/mcp] server shutting down
Goodbye.
```

All three real Anthropic API calls, all three MCP tool round-trips
(`look`, `move`, `check`) through the merged `mud_manager` gem's MCP
server, correct and consistent results (moving north from the Temple hall
actually landed at the Temple Altar, matching the exit list `look` had
already reported). Clean shutdown, no orphaned `mud_manager_mcp_server`
process afterward (`ps aux` checked).

Also re-confirmed, since the MCP merge changed a gem every other step in
this repo shares: **`mud_manager` 0.1.0 → 0.2.0 didn't break the two steps
that still use it directly.** `ruby/11_tui` and `ruby/12_context` (not
migrated to MCP — deliberately out of scope, per every prior review)
`require "mud_manager"` and get `MudManager::Session`/`Primitives` exactly
as before; those two files weren't touched by the merge, only the new
`mcp/` subtree was added. Confirmed by loading each step's own copy of
`mud_manager` and checking `MudManager::Session`/`Primitives` still
resolve — they do.

## 7.2 — Remaining startup issues, for the next lesson

Not fixed now — noted so they aren't rediscovered from scratch:

1. **boukensha isn't on `$PATH` by default.**
   `~/.local/share/gem/ruby/3.2.0/bin` (where `--user-install` puts gem
   executables, since this environment has no passwordless `sudo` for a
   system-wide install) isn't in the shell's `$PATH` — confirmed against
   `~/.bashrc`/`~/.profile` directly, not just this session's own shell.
   Every invocation in this session's validation work either exported
   `$PATH` inline or called the executable by its full path. A fresh
   terminal, with no manual workaround, cannot run bare `boukensha` at
   all. Needs either a `$PATH` update in the user's shell rc, or a
   documented "add this to your PATH" step somewhere a first-time reader
   would see it (currently nowhere).

2. **`mud_manager` now has a version split its own dependents haven't
   caught up to.** `ruby/11_tui` and `ruby/12_context` both declare
   `spec.add_dependency "mud_manager", "~> 0.1"` — a constraint `0.2.0`
   (now the gem's default-resolved version) technically violates. Neither
   step enforces the constraint at runtime (they `require "mud_manager"`
   directly, not through `Bundler.require`), so this is currently
   harmless — `Session`/`Primitives` are byte-identical between 0.1.0 and
   0.2.0 — but it's a real, latent inconsistency between what those
   gemspecs declare and what actually loads. Resolving it means either
   migrating 11/12 to the MCP path too (already flagged as deferred,
   out-of-scope work in multiple prior reviews) or at least bumping their
   gemspecs to `~> 0.2` to stop the constraint from being silently wrong.

3. **Two versions of both `mud_manager` (0.1.0, 0.2.0) and `boukensha`
   (0.9.0, 0.10.0) are installed side by side** — `0.1.0`/`0.9.0` at the
   system gem path (`/var/lib/gems`, presumably from initial environment
   setup, root-owned — not writable this session), the newer versions at
   the user path. Harmless today since RubyGems resolves to the latest
   by default, but worth knowing before assuming "the gem" means one
   specific install location.

None of these block anything working today — 7.1 ran clean end to end —
but all three are environment/dependency-hygiene items a later lesson
should pick up rather than leaving implicit.
