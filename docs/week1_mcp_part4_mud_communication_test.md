# MCP Part 4 — Testing Communication with the MUD (4)

Verifies the agent actually retrieves live MUD state through the MCP
server when asked a natural-language question, and uses LogViz to observe
the resulting MCP tool call rather than trusting the answer at face value.

## Setup

Launched via the installed `boukensha` command (see
`docs/week1_mcp_part4_verification.md` for the executable/config state),
default working directory, so `Boukensha::Logger` writes its session
`.jsonl` to the default location — `.boukensha/sessions/` (`Boukensha
.config.dir` + `sessions`).

## 1 — Asked the agent for its current location

```
$ boukensha
...
boukensha> What is my current location in the game?

You are currently in **The Temple of Midgaard**, a large marble temple
hall in the southern section. There's an ATM installed here, and you have
exits to the north, east, south, west, and down. The Reading Room is to
the west, and a donation room is to the east.

Your current health is low (25H/100M). You should consider resting to
recover HP before exploring further.
boukensha> [mud_manager/mcp] server shutting down
Goodbye.
```

## 2 — Verifying the answer came from the MUD, not the model guessing

Didn't just trust a plausible-sounding answer — pulled the raw session
log (`.boukensha/sessions/20260828T095305Z-059b6a68.jsonl`) and checked
the actual `tool_call`/`tool_result` events `Boukensha::Logger` wrote
during that turn:

```json
{"phase":"tool_call","name":"look","args":{"target":"","preposition":""}}
{"phase":"tool_result","name":"look","result":"[0;33mThe Temple Of Midgaard[0m\r\n   You are in the southern end of the temple hall in the Temple of Midgaard.\r\n...\r\nTo the west, you see the Reading Room.  The donation room is in a small\r\nalcove to your east.\r\n[0;36m[ Exits: n e s w d ][0m\r\n...","ok":true,"error":null}
```

**Result: pass, and the mechanism is confirmed, not just the outcome.**
The model chose to call `look` (an MCP-proxied tool — this Boukensha
process never talks to `MudManager`/CircleMUD directly, only to the
spawned `mud_manager --mcp` subprocess over stdio), got back the exact
live room text (matches CircleMUD's real output, room name, exits, and
the "Reading Room"/"donation room" detail the model then paraphrased
correctly), and only then answered. `turn_end` recorded `iterations: 2` —
one iteration to decide to call the tool, one to answer from its result —
consistent with a real tool round trip, not a zero-iteration guess.

## 3 — Observing the tool call through LogViz

Ran the actual app rather than just re-reading the raw JSON a second way:

```
$ cd ruby/log_viz && bundle exec ruby bin/log_viz
== Sinatra (v4.2.1) has taken the stage on 4567 for development
```

`GET /` listed the session by timestamp/id; `GET
/sessions/20260828T095305Z-059b6a68` rendered the full transcript. The
relevant excerpt LogViz produced:

```html
<div class="msg msg-assistant">
  ...
  <div class="msg-body">I'll check your current location by looking at the room you're in.</div>
</div>

<div class="tool-call">
  <div class="tool-name">
    &#9881; look(target: "", preposition: "")
  </div>
  <pre class="tool-result"><span class="ansi-fg-yellow">The Temple Of Midgaard</span>
   You are in the southern end of the temple hall in the Temple of Midgaard.
...
<span class="ansi-fg-cyan">[ Exits: n e s w d ]</span>
<span class="ansi-fg-green">An automatic teller machine has been installed in the wall here.
</span>
25H 100M 19V (news) (motd) &gt; </pre>
</div>
```

LogViz correctly: shows the assistant's own stated reasoning before the
call ("I'll check your current location by looking at the room you're
in."), renders the tool call with its actual arguments
(`look(target: "", preposition: "")` — both empty, meaning "describe the
current room," per that tool's own MCP description), and converts the raw
ANSI-coded MUD output into styled HTML (`ansi-fg-yellow` for the room
title, `ansi-fg-cyan` for the exits line, `ansi-fg-green` for the ATM
notice) — the same color-coding that terminal output would show, per
`lib/log_viz/ansi.rb`.

Stopped the LogViz process afterward (`ps aux` confirmed no leftover
process).

## Technical observations

- **LogViz needed no changes or special configuration to show MCP tool
  calls.** It renders whatever `Boukensha::Logger` wrote for `tool_call`/
  `tool_result` events, and those events are logged identically whether
  the tool was one of the old in-process handlers or, as here, an
  MCP-proxied one from `Tools::Mcp`. The refactor changed *how* `look`
  gets its answer (spawn a subprocess, speak JSON-RPC) but not *what*
  gets logged (`name`, `args`, `result`, `ok`) — LogViz was built against
  that logging contract, not against any particular tool implementation,
  so it kept working across the MCP migration with zero changes.
- **The tool name and argument shape in the log are exactly the MCP
  schema**, not some Boukensha-internal translation — `look(target: "",
  preposition: "")` is the same `look` tool with the same two parameters
  `ruby/13_mcp_server`'s (now `mud_manager/mcp/tools.rb`'s) `dispatcher.tool
  "look", parameters: {target:, preposition:}` declares. Confirms the
  proxying in `Tools::Mcp.register_proxy_tool` really does pass the MCP
  tool's own name and schema straight through into the Boukensha registry
  and the log, rather than renaming or reshaping anything along the way.
- **The empty-string arguments (`target: "", preposition: ""`) are the
  model's choice, not a bug.** The tool's own MCP description says "Call
  with NO arguments to describe the current room" — Anthropic's tool-use
  schema always sends every declared property (per the pre-existing
  Boukensha quirk noted in earlier reviews: every parameter is marked
  `required` in the schema sent to the model, regardless of the handler's
  actual optionality), so the model satisfies that by sending empty
  strings rather than omitting the keys — and `MudManager::Primitives.look`
  already normalizes an empty string to "absent" (`target = nil if
  target.to_s.strip.empty?`), so this produces exactly the intended
  "look at the current room" behavior.
