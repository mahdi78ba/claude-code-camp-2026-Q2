# MCP Integration Plan — Part 1 (Plan Only)

No server code, gemspec, or README changes in this step. This document is the
1.1/1.2/1.3 deliverable: scope the problem, evaluate the cross-language
options, and record the decision to build on MCP. Implementation is Part 2.

## The problem

`week0_explore/mud_manager/` is the canonical Ruby gem (vendored into
`ruby/10_standard_tool_library/vendor/bundle/.../mud_manager-0.1.0/` for that
step) that owns everything CircleMUD-specific and hard to get right:

- `MudManager::Session` (`lib/mud_manager/session.rb`) — the long-lived
  telnet socket, a background reader thread, telnet IAC stripping, the
  `read_until_quiet` / `read_until_prompt` response-collection logic, and the
  multi-step CircleMUD login dance (`login`).
- `MudManager::Primitives` (`lib/mud_manager/primitives.rb`) — ~50
  stateless builder methods (`move`, `attack`, `look`, `cast`, `shop`, …) that
  validate enum arguments and produce the exact command string CircleMUD
  expects.

Today the only consumer is `Boukensha::Tools::Mud.register`
(`ruby/12_context/lib/boukensha/tools/mud.rb`), which creates **one**
`MudManager::Session`, closes over it, and registers ~30 tools
(`mud_connect`, `look`, `move`, `attack`, `cast_spell`, `shop`, …) against the
Ruby agent's in-process `Registry`. This only works because the Ruby agent
and `MudManager` live in the same process and the same language.

The Python port (`python/`) currently stops at `08_the_repl_loop` — it has no
MUD tools at all, and there is no `mud_manager` equivalent in Python. Porting
`Tools::Mud` the way every other step so far has been ported (translate the
Ruby line-by-line into Python) would mean **reimplementing the telnet
session, the IAC stripper, and the CircleMUD login state machine a second
time**, in a different language, and a third time for the next language
after that. That duplication is exactly the failure mode
`docs/explore_architectures.md` already flagged during the Week 0 plain-agent
experiments:

> A dedicated MUD SDK / manager would give a reliable connect/send/read
> interface, so the agent never re-implements the plumbing. **An MCP server
> could expose that interface to a harness as clean tools.**

Part 1 exists to actually evaluate that suggestion before committing to it.

## 1.1 Technical exploration plan

1. **Spike a minimal MCP server in Ruby** wrapping just 2–3 tools
   (`mud_connect`, `look`, `move`) from the existing `mud_manager` gem, using
   stdio transport. Confirm a generic MCP client (official Python MCP SDK, or
   Claude Code itself via `.mcp.json`) can `tools/list` and `tools/call`
   against a live local CircleMUD (`localhost:4000`, per
   `.boukensha/settings.yaml`).
2. **Resolve the session-lifecycle question**: `MudManager::Session` is one
   stateful telnet socket tied to one logged-in character — there is no
   multi-session support today (`docs/week1_standard_tool_library_review.md`
   flags the same closure-over-one-`session` limitation in the current
   in-process design). Decide whether one MCP server process = one character
   session (mirrors current behavior) and whether concurrent MCP clients
   against that one process are in scope for Part 2 or explicitly deferred.
3. **Port the full tool surface 1:1.** Every `registry.tool "name",
   description:, parameters: {...} do |...| end` block in
   `lib/boukensha/tools/mud.rb` becomes one MCP tool definition. This should
   be close to mechanical — the hand-written `parameters:` hashes already
   look like a JSON Schema `properties` map (`type`, `description` per
   field), and `send_cmd`/`guard` become the MCP tool handler body.
4. **Prove cross-language consumption**: point a Python client (a bare MCP
   client script, or eventually `python/08_the_repl_loop`'s agent once it
   gains tool-calling) at the server and run the same commands the Ruby
   agent runs today (`mud_connect` → `look` → `move north` → `attack`).
5. **Reuse existing config, don't invent new config**: the MCP server's
   host/port/character/password should come from the same
   `Boukensha::Config#mud_host/#mud_port/#mud_username/#mud_password`
   accessors already in `lib/boukensha/config.rb`, so behavior matches the
   in-process path exactly.
6. **Decide packaging**: does `Boukensha::Tools::Mud.register` grow an
   `mcp:` mode that runs the existing logic as a standalone server process
   (`bin/mud_mcp_server`), while the in-process Ruby path from step 10 keeps
   working unchanged for the Ruby agent? Both call the same
   `mud_manager` gem either way — the fork is only in how tool calls reach
   it (direct Ruby method call vs. MCP `tools/call`).
7. **Also resolve the pre-existing dependency wrinkle** noted in the step-10
   review before shipping any of the above: `boukensha.gemspec` declares
   `mud_manager` as a normal RubyGems dependency, but it only exists locally
   at `week0_explore/mud_manager/`. An MCP server gem/executable will need a
   real path/git dependency, not an implicit "it happens to be installed
   locally" assumption.

## 1.2 Cross-language communication approaches evaluated

| Approach | How it would work here | Pros | Cons |
|---|---|---|---|
| **Reimplement per language** (status quo path) | Hand-port `mud_manager`'s `Session` + `Primitives` into Python, then Go, etc., same as every other step so far | No new infrastructure; consistent with how the course has ported everything else | Telnet/IAC-stripping/login state machine gets rewritten and re-debugged per language; the two implementations *will* drift (e.g. a CircleMUD login-flow edge case fixed in Ruby silently stays broken in Python) |
| **Raw TCP proxy** | A small Ruby process holds the real `MudManager::Session` and forwards raw bytes or line-delimited commands over a second, simpler TCP socket to any language | Cross-language via plain sockets, no framework dependency | Only solves the *transport*, not the *interface* — every client still has to know the ~30 command shapes, argument validation, and enum rules that `Primitives` currently owns; no standard tool-discovery, so each client also hardcodes tool names/params by hand |
| **REST/HTTP JSON API** | Wrap `Session`/`Primitives` in an HTTP server (project already has Sinatra experience via `ruby/log_viz`) with one endpoint per tool | Any language has an HTTP client; human-debuggable with `curl` | No standard schema for "these are the callable tools and their argument shapes" — would need a hand-rolled OpenAPI doc kept in sync by hand; no shared concept of a tool call built for LLM agents specifically, so each new agent language reinvents the request/response mapping |
| **gRPC** | Define a `.proto` for the ~30 commands, generate Ruby server + Python/Go/etc. clients | Strong typing, codegen, efficient | Protobuf/codegen toolchain is heavy for a teaching project this size; still no LLM-tool-schema semantics — every consuming agent has to hand-adapt generated RPC stubs into whatever its own tool-calling format expects |
| **Message queue** (Redis pub/sub, NATS, etc.) | Agent publishes a command message, a Ruby worker holding the session executes it and publishes the result | Decouples caller and session lifetime; multiple consumers possible | Adds a whole infrastructure dependency (broker) for a single-player teaching harness; still no standard tool-schema layer; request/response correlation and timeouts become extra work |
| **MCP (Model Context Protocol)** | Ruby MCP server wraps `mud_manager`, exposing the *existing* ~30 `registry.tool` definitions as MCP tools over stdio (or HTTP/SSE later) | Purpose-built for exactly this: "give an LLM agent a discoverable set of named tools with JSON-schema parameters." Tool discovery (`tools/list`) and invocation (`tools/call`) are already standardized, so any MCP-capable client — Python, Claude Code itself, a future TUI — gets the full MUD tool surface with zero protocol reimplementation. Maps almost 1:1 onto the tool DSL already used in `tools/mud.rb` | Newer/smaller ecosystem than HTTP or gRPC; Ruby-side server SDK support is less mature than Python/TypeScript (may need a thin hand-rolled JSON-RPC-over-stdio layer); single-session model still needs the same concurrency decision as every other option |

The first five options all solve *transport* (getting bytes from a Python
process to a Ruby process) but leave the *tool contract* — names,
descriptions, argument schemas, discovery — to be reinvented per client.
That contract is exactly what `registry.tool` already models inside
Boukensha, and exactly what MCP standardizes.

## 1.3 Decision: use MCP as the communication layer

**Chosen approach: MCP.** Rationale:

- **It matches the shape of the code that already exists.** Every tool in
  `lib/boukensha/tools/mud.rb` is already `name + description + parameters
  (JSON-schema-shaped) + handler`. That is MCP's tool model. Moving to MCP is
  a wrapper around the existing `Primitives`/`Session` calls, not a rewrite
  of them.
- **The hard part stays solved exactly once.** Telnet IAC handling, the
  CircleMUD login state machine, and the `read_until_prompt` response
  framing stay in Ruby, inside `mud_manager`, used by exactly one process.
  Every other language only needs an MCP client, not a MUD client.
- **Discovery is standardized.** A Python (or any) agent calls `tools/list`
  and gets the full, current tool set with descriptions and argument
  shapes — no hand-maintained OpenAPI doc, no generated stubs to keep in
  sync by hand.
- **It's the option the project's own prior research already pointed at**
  (`docs/explore_architectures.md`), so this decision closes the loop on a
  root cause identified back in Week 0 rather than introducing a new,
  unvalidated idea.

**What this commits Part 2 to, concretely:**

1. A new Ruby MCP server (likely a new step directory, e.g.
   `ruby/13_mcp_server/`, or a mode inside the existing gem — TBD in Part 2)
   that `require`s `mud_manager` and re-registers the same ~30 tools against
   an MCP tool registry instead of (or alongside) Boukensha's own
   `Registry`.
2. Transport: start with **stdio** (simplest, matches "one process, one
   logged-in character, one trusted local client") — revisit HTTP/SSE only
   if a remote or multi-client scenario is actually needed.
3. Config sourced from the existing `Boukensha::Config` MUD accessors, not a
   parallel config file.
4. The dependency wrinkle on `mud_manager` (declared as a RubyGems
   dependency but only available locally) gets fixed as part of this work,
   since the MCP server is a second consumer that will hit the same
   `bundle install` failure the step-10 review already flagged.

**Explicitly out of scope for Part 1:** writing the server, changing any
`.gemspec`, touching `tools/mud.rb`, or picking Part 2's exact directory
layout. Those are Part 2.
