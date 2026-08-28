# MCP Part 4 — Reviewing Current Tool Behavior (5)

## Checked the premise before noting it as a future improvement

The instruction says to observe that the agent currently uses `send_raw`
for the `look` command. It doesn't — checked, not assumed:

**The specific session from the previous task** (`docs/week1_mcp_part4_mud_communication_test.md`,
"What is my current location in the game?") logged:
```json
{"phase":"tool_call","name":"look","args":{"target":"","preposition":""}}
```
The dedicated `look` tool, not `send_raw`.

**Every other session log in `.boukensha/sessions/`** — swept all of them,
not just the one from the last task:
```
$ grep -o '"phase":"tool_call","name":"[a-z_]*"' *.jsonl | sort | uniq -c
      1 "phase":"tool_call","name":"look"     (×3 across different sessions)
      1 "phase":"tool_call","name":"check"    (×3 across different sessions)
      1 "phase":"tool_call","name":"move"     (×1)
```
```
$ grep -o '"phase":"tool_call","name":"send_raw"' *.jsonl
(no matches — send_raw has never actually been invoked in any logged session)
```
`send_raw` appears in some log files, but only inside `phase: "prompt"`
events, where the logger records the *full list of available tool
names* on every turn — its presence there just means the tool is
registered and offered to the model, not that it was ever called.

## Conclusion

Every location/room query across every session on record used the
dedicated `look` or `check` tool. `send_raw` — the documented "escape
hatch" for when no structured tool fits — has never been reached for a
`look`-shaped request. There's no regression to log here: the dedicated
`look` tool already exists (registered by `MudManager::Mcp::Tools`,
proxied unchanged through `Boukensha::Tools::Mcp`), is already preferred
by the model over the generic escape hatch, and every test in this
session's MCP work confirms it. Not adding this as a "future improvement"
item, since it would describe a problem that isn't happening — if a real
instance of the model reaching for `send_raw` where `look` would fit
better ever turns up in a session log, that would be worth logging then,
with the actual transcript as evidence.
