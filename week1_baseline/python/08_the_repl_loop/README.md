# Step 8 — The REPL Loop

Python port of `ruby/08_the_repl_loop`.

## What this step adds

| | Step 7 | Step 8 |
|---|---|---|
| Entry point | `boukensha.run(task="…")` | `boukensha.repl()` |
| Turns | one | many |
| History | discarded | accumulates across turns |
| User interaction | none | stdin prompt |

## New primitives

### `boukensha.Repl`

The interactive session loop. Built-in commands:

| Command | Effect |
|---|---|
| `/quiet` | Suppress logging output |
| `/loud` | Re-enable logging output |
| `/clear` | Wipe conversation history (tools stay registered) |
| `/help` | Print the command list |
| `/exit` / `/quit` | Leave the REPL |
| Ctrl-D | EOF — leave the REPL |
| Ctrl-C | Interrupt — leave the REPL gracefully |

Ctrl-D is detected differently than in Ruby: Python's `input()` raises
`EOFError` on end-of-input rather than returning a `None`/`nil` sentinel, so
`Repl.start()` wraps the read in `try/except EOFError` instead of checking
the return value.

### `boukensha.repl()`

Same keyword arguments as `boukensha.run()`, minus `task`. Pass a
`configure` callable to register tools; then the REPL loop takes over.

```python
def configure(dsl):
    dsl.tool(
        "read_file",
        description="Read a file from disk",
        parameters={"path": {"type": "string", "description": "File path"}},
        block=lambda path: Path(path).read_text(),
    )

boukensha.repl(model="claude-haiku-4-5", configure=configure)
```

## Changes from step 7

### `Context.clear_messages()`
Empties `self.messages` while keeping `self.tools` registered. Used by the
REPL's `/clear` command.

### `Agent.run()` / `Agent._wrap_up()` — persist the final reply
Before step 8, the agent returned its final text without adding it to the
context (harmless for a one-shot `boukensha.run()`, since the context is
discarded afterward). A REPL needs the full transcript so subsequent turns
see the prior exchange — all three return points now append an
`"assistant"` message before returning:

```python
# step 7 — final text returned but NOT added to context
return text

# step 8 — final text added to context, then returned
self.context.add_message("assistant", text)
return text
```

This applies to the normal completion path in `run()` **and** both paths
inside `_wrap_up()` (the wind-down success case and its `ApiError`
fallback) — three call sites, not one.

### `Config._resolve_dir()` — a new middle tier
`BOUKENSHA_DIR` resolution now checks a `.boukensha/` directory in the
current working directory before falling back to `~/.boukensha`:

```
1. BOUKENSHA_DIR environment variable
2. .boukensha/ in the current working directory   ← new
3. ~/.boukensha (default)
```

### `Client.call()` — a clearer 401 message
A `401` response now raises `ApiError("authentication failed (401) — check
your API key")` instead of the generic attempt-count message — the failure
mode a REPL user is most likely to hit interactively (a bad or missing key)
now says so directly.

## Running it

```sh
./week1_baseline/bin/python/08_the_repl_loop
```

```
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.8.0)   ║
╚══════════════════════════════════════╝

boukensha> list the files in the lib directory
…
boukensha> now read boukensha/agent.py and explain the loop
…
boukensha> /quiet
(logging suppressed — type /loud to re-enable)
boukensha> what was the first file I asked you about?
…
boukensha> /exit
Goodbye.
```

The last question demonstrates persistent history: the agent answers from
the accumulated transcript, not just the last message.
