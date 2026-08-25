# Step 10 — A Standard Tool Library

Boukensha now ships two built-in tool modules. Instead of manually registering tools, a real coding harness gives the agent a standard library of capabilities out of the box.

## What's new

### `Boukensha::Tools::FileSystem`

The evolution of step 9's `WorkingDirectory` — same five tools plus one new one. Registers automatically when `working_dir:` is set:

| Tool | Description |
|------|-------------|
| `pwd` | Return the working directory |
| `list_directory` | List files at a path (default `.`) |
| `read_file` | Read a file's contents |
| `write_file` | Write (or create) a file |
| `delete_file` | Delete a file |
| `search_files` | **New** — grep for a regex pattern across the working tree, returns `path:line:content` matches |

All paths are **relative to the working directory**. Absolute paths and `..` traversals that escape the root are rejected with an error string.

### `Boukensha::Tools::Shell`

New module. Registers automatically when `working_dir:` is set:

| Tool | Description |
|------|-------------|
| `run_command` | Run a shell command inside the working directory |

Commands run with a configurable timeout and an optional allow-list of permitted executables.

### New `Boukensha.run` / `Boukensha.repl` keyword arguments

```ruby
Boukensha.run(
  task:             "...",
  working_dir:      "/my/project",
  allowed_commands: ["ruby", "git", "bundle"],  # nil = allow all (default)
  shell_timeout:    30                           # seconds, default 30
)
```

`allowed_commands: nil` permits any executable. Pass an explicit list to lock the agent down:

```ruby
# Only allow ruby and git — rm, curl, etc. will be rejected
Boukensha.run(task: "...", allowed_commands: ["ruby", "git"])
```

### Direct registration

Both modules can be registered manually if you need finer control:

```ruby
Boukensha::Tools::FileSystem.register(registry, working_dir: "/my/project")
Boukensha::Tools::Shell.register(registry, working_dir: "/my/project",
                              timeout: 10, allowed_commands: ["ruby"])
```

## Run the demo

```sh
ruby examples/demo.rb

# or via the global executable pointed at this step:
BOUKENSHA_PATH=~/Sites/boukensha/10_standard_tool_library boukensha
```

## Technical observations (from testing this step)

- **`mud_manager` isn't on rubygems.org.** `boukensha.gemspec` declares
  `add_dependency "mud_manager", "~> 0.1"` as if it were a published gem, but
  it's a local teaching gem built from `week0_explore/mud_manager/`. A plain
  `bundle install` fails with "that version can no longer be found in that
  source." Fix used here: `gem build` the local gemspec, copy the resulting
  `.gem` into this step's `vendor/cache/`, then `bundle install` — Bundler
  prefers a matching cached gem over the remote source.
- **`examples/example.rb` had an off-by-one in `BOUKENSHA_DIR` resolution**,
  now fixed: it used three `../` (`File.expand_path("../../../.boukensha",
  __dir__)`), landing on the nonexistent `week1_baseline/.boukensha` instead
  of the repo-root `.boukensha` where `settings.yaml`/`.env` actually live.
  Steps `00`–`08` all use four `../`. With the wrong path, `Boukensha.config`
  silently loads with empty task settings and no API key
  (`tasks.player.model is required in settings.yaml`) rather than erroring
  about the missing directory itself — worth knowing if this ever recurs.
- **Confirmed working end-to-end** after the two fixes above: the demo
  connects to a local CircleMUD (`mud_connect`), looks at the room (`look`),
  checks score (`check kind: score`), and checks exits (`check kind: exits`),
  matching the task prompt, and completes in 3 iterations
  (`turn_end reason: completed`) — verified via the `.boukensha/sessions/*.jsonl`
  log, not just stdout (the demo prints nothing itself beyond the config/API-key
  banner; the actual transcript only shows up in the session log or
  `log_viz`).

See
[`docs/week1_standard_tool_library_review.md`](../../../docs/week1_standard_tool_library_review.md)
for the full code-level review this was drawn from.

## Known limitations (not fixed in this iteration)

- **`run_command`'s timeout doesn't kill the child process.** `Timeout.timeout`
  only interrupts the Ruby thread waiting on `Open3.capture2e` — the spawned
  `sh -c ...` process (and whatever it started) keeps running to completion
  in the background. Reproduced with `timeout: 1, command: "sleep 20"`: the
  tool correctly returns `"command timed out after 1s"`, but `ps` still shows
  the `sleep 20` process alive afterward. Every timeout also prints an
  unrescued `Thread ... terminated with exception ... IOError` warning to
  stderr (cosmetic — the returned result is unaffected).
- **`allowed_commands` is a first-token name filter, not a shell-aware
  sandbox.** `echo hi; rm -rf /` passes the allow-list check (first token is
  `echo`) and then both commands execute, since the full string is still
  handed to a shell. Fine for keeping an agent from typing `rm` by name; not
  a boundary against command chaining/injection.
- **Malformed tool calls raise instead of returning an error string, breaking
  the module's own stated contract.** `Registry#dispatch` calls
  `tool.block.call(**args)` outside of any tool's own `rescue`, so a missing
  required keyword (e.g. `write_file` without `content:`) or an unexpected
  extra keyword raises `ArgumentError` there rather than producing the
  `"error: ..."` string style used for e.g. path-escape or file-not-found
  failures. Not fatal — `Agent#handle_tool_calls` rescues `StandardError` and
  turns it into an `"ERROR: ArgumentError: ..."` tool result — but the error
  *shape* differs from every other failure mode these tools produce.
- **`Tools::Mud.register` has a side effect the other two modules don't**: it
  opens a real socket and logs in during registration (agent setup), before
  the first model call, rather than lazily on first tool use like
  `FileSystem`/`Shell`. Failure degrades gracefully (rescued + `warn`,
  `mud_connect` still available manually), but every `Boukensha.run`/`.repl`
  with a configured `mud_host` pays that connection cost up front.
