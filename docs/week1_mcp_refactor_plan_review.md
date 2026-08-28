# Reviewing the Generic MCP Refactor Plan (MCP Part 2 — Review)

Self-review of `docs/week1_generic_mcp_architecture_design.md` (the plan I
produced for MCP Part 2, step 2) before anyone implements it. Read it back
adversarially instead of taking my own design at face value — found real
bugs in the sketched code and one rationale gap that matters more than the
code bugs. Structured as: what's sound, what's wrong, then a definitive
accept/modify/reject list.

## 3.1/3.2 — Walking back through the plan critically

### Bug: the `command: nil` sketch in `Tools::Mud.register` doesn't do what it says

The design's `Tools::Mud.register` passes `command: nil` to `Mcp.register`,
with a comment claiming that falls back to `MudMcp::Client`'s own default.
It doesn't. Ruby keyword defaults only apply when the keyword is *omitted*;
passing `command: nil` explicitly overrides
`command: [RbConfig.ruby, DEFAULT_SERVER]` with a literal `nil`.
`Open3.popen2(env, *nil)` — Ruby implicitly converts `*nil` to no
arguments, so this collapses to `Open3.popen2(env)` with **zero** command
arguments, which is not a valid call (it needs at least one command
element). This is exactly the kind of thing that looks fine in a design
doc's pseudo-code and breaks the moment someone types it into a file.
**Verdict: real bug, must fix before implementing** — either
`register_one` only passes `command:` when the entry has one (`server[:command] ? {command: server[:command]} : {}`, merged into the `Client.new` kwargs), or `Tools::Mud.register` builds the same default array itself instead of relying on `nil` to mean "use the default."

### Gap: per-server failure isolation doesn't actually cover "hangs," only "raises"

2.3 in the design claims "failure isolation is per-server" and points at
`register_one`'s `rescue MudMcp::Client::Error, Errno::ENOENT`. That only
catches a subprocess that fails to spawn or that exits/closes its pipe.
It does **not** catch a subprocess that spawns fine and then hangs — e.g.
a MUD server that's up but never responds to login, so the child process
never writes an `initialize` response. `Client#handshake` →
`request` → `read_until_id` loops on `@stdout.gets` with no deadline; a
hung server hangs `Tools::Mcp.register_one` forever, which hangs
`Boukensha.run`/`.repl` forever, for every server configured after it too.
That's the opposite of "one bad server doesn't take down the others."
**Verdict: real gap, needs a timeout** (`Timeout.timeout(n) { ... }` around
the handshake/list_tools portion of `register_one`, rescuing
`Timeout::Error` alongside the other two). The rescue clause should also
widen from two named exception classes to `StandardError` generally —
narrowly listing "the errors I thought of" contradicts the isolation goal
2.3 itself states; any per-server failure should degrade to a warning, not
just the two I happened to enumerate.

### Gap: the collision-handling recommendation doesn't specify what actually happens to the second tool

The design recommends "detect and warn" for name collisions across
servers, but a warning alone doesn't change behavior — `Context#register_tool`
(`@tools[tool.name] = tool`) still silently overwrites the earlier tool
with the later one. A warning that's easy to miss (stderr, during startup,
before any conversation begins) protecting nothing isn't much of a
safeguard. It also references a capability that doesn't exist yet:
`Registry` has no method to ask "is a tool already registered under this
name" — `Context#tools` exists but `Registry` never exposes it, so
"compare incoming tool names against `registry`'s existing keys" isn't
actually implementable against the current `Registry` class without adding
to it first.
**Verdict: recommendation needs sharpening, not just implementing as
written** — warn *and* keep the first registration (refuse the second),
which requires adding a small query method (e.g. `Registry#registered?(name)`
or exposing `@context.tools.key?(name)`) as part of the same change, not as
a follow-up.

### Rationale gap the design doc didn't address at all: secrets in a "safe to commit" file

`ruby/10_standard_tool_library/.boukensha/settings.yaml`'s own header
comment says it's "non-secret configuration (safe to commit)" — secrets
are supposed to live only in the gitignored `.env`
(`Config#load_env`). The design's `mcp_servers:` shape puts raw literal
values straight into `env:` inside `settings.yaml`
(`MUD_PASSWORD: helloworld`). For the throwaway `dummy`/`helloworld` test
account that's harmless and matches what's already committed today, but
the design as written gives no way for someone configuring a **real**
account/API key on a real MCP server to avoid putting that secret in a
file the project explicitly documents as commit-safe. That's a genuine
regression in the secret/non-secret separation the project already
established — not hypothetical, since the whole point of generalizing to
"any configured MCP server" is that someone *will* eventually configure a
server whose `env:` needs a real credential.
**Verdict: missing from the design, needs to be added** — the simplest fix
that doesn't require new infrastructure: values in an `mcp_servers` entry's
`env:` map that look like `"$SOME_VAR"` resolve against `ENV` (already
populated from `.env` by the time `Config` is used) instead of being taken
literally; anything else is a literal value, unchanged. One small rule in
`Config#mcp_servers`, no new file format, no new dependency.

### Underspecified: `Repl.new`'s `mud:` keyword and banner wiring

The design correctly flags that `probe_mud`'s raw TCP check can't survive
generalization unchanged, but stops at "here's the idea" rather than
specifying the actual `Repl.new` keyword rename (`mud:` → something that
carries a list, e.g. `mcp_servers:` or the array of `[name, client]`
pairs `Tools::Mcp.register` returns) or what the banner line looks like
with N servers instead of one. Not wrong, just incomplete — implementing
this step will need to make that call, and it should be made deliberately
rather than improvised mid-implementation.
**Verdict: not a bug, but needs one more design pass focused specifically
on `Repl`/banner before (not during) implementation** — small enough not
to block starting the rest, but shouldn't be left to whoever's typing the
code to decide unreviewed.

### Judgment call worth revisiting: keeping `Tools::Mud` as a compatibility wrapper

The design keeps `Tools::Mud.register(host:, port:, name:, password:)` as
a thin wrapper over `Tools::Mcp.register`, reasoning that existing call
sites (including my own earlier test script from
`docs/week1_mcp_standard_tool_library_integration.md`) keep working. But
the design *also* accepts breaking `settings.yaml`'s `mud:` block outright
(no dual-format support) — so the migration is already not
backward-compatible end-to-end. Keeping a Ruby-level compatibility shim
while breaking the config-level format is a half-measure: it leaves two
ways to configure MUD gameplay (call `Tools::Mud.register` directly, or go
through the generic `mcp_servers:` path) permanently coexisting, which is
the exact per-domain duplication 2.2 exists to remove. It also cuts against
this project's own standing rule against backward-compatibility shims when
the code can just change.
**Verdict: reconsidered — drop `Tools::Mud` as a wrapper.** Update
`boukensha.rb`'s call site and the one existing caller (my own smoke-test
script, not committed code) directly to the generic `Tools::Mcp` +
`mcp_servers:` shape instead. If a later step wants a MUD-specific
convenience method again, it should be added deliberately when there's a
real reason, not preserved reflexively because it happened to exist.

### What held up fine on review

- **`Tools::Mcp.register(registry, servers:)` as the shape of the generic
  bridge** — correct level of generality, matches the existing
  `Tools::FileSystem`/`Tools::Shell` naming convention, no changes needed.
- **Reusing `MudMcp::Client` unrenamed in Phase A**, deferring the
  `mcp`/`mud_mcp` gem split to Phase B — still the right call. It does mean
  `Boukensha::Tools::Mcp` (a supposedly domain-agnostic module) literally
  `require`s a class named `MudMcp::Client`, which reads a little
  contradictory — worth a one-line comment acknowledging that's a known,
  temporary seam, not fixing it now.
- **Per-entry `name:` field** in the server config — earns its keep
  immediately (warnings, and now the banner) even before namespacing is
  addressed.
- **The three-way `mcp: nil | [...] | false` convention** mirroring
  `working_dir:` — consistent with the file's existing style, no changes.

## 3.3 — What actually gets incorporated

| # | Item | Verdict | What changes |
|---|---|---|---|
| 1 | `command: nil` fallback bug | **Fix required** | `register_one` only sets `command:` when the server entry provides one; never pass a literal `nil` over the keyword. |
| 2 | Handshake can hang forever, no timeout | **Fix required** | Wrap `register_one`'s handshake/`list_tools` in `Timeout.timeout` |
| 3 | Rescue only 2 exception classes | **Fix required** | Widen to `rescue StandardError` in `register_one`, consistent with the "per-server isolation" goal already stated |
| 4 | Collision handling: warn-only | **Modify** | Warn **and** refuse the second registration (keep the first); add the small `Registry` query method this needs |
| 5 | Secrets in `mcp_servers:` `env:` | **Add — was missing** | Support `"$VAR"` values resolving against `ENV` in `Config#mcp_servers`; literal strings otherwise |
| 6 | `Repl`/banner generalization | **Defer, scope explicitly** | Not implemented yet; do a short, focused design pass on `Repl.new`'s new keyword and the multi-server banner line before writing that code, rather than improvising it inline |
| 7 | Keep `Tools::Mud` as a wrapper | **Reject** | Drop it; migrate the one Ruby call site (`boukensha.rb`) and the one existing test script straight to `Tools::Mcp` + `mcp_servers:` |
| 8 | `Tools::Mcp` shape, naming, `mcp:` keyword convention | **Accept as-is** | No changes |
| 9 | Reuse `MudMcp::Client` unrenamed in Phase A | **Accept as-is** | No changes; add a one-line comment noting the naming seam is temporary |
| 10 | Phasing (A now, gem split deferred to B) | **Accept as-is** | No changes |

Items 1–5 and 7 are corrections to make before implementation starts, not
after — 1–3 are outright bugs in the sketch, 4–5 are real rationale gaps,
and 7 is a design decision I'm reversing on review. Item 6 is scoped out
deliberately rather than left ambiguous. Items 8–10 are confirmed as-is.
