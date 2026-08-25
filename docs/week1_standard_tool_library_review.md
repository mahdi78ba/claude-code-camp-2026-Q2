# `10_standard_tool_library` — Reviewing the Standard Tool Library

Scope: `lib/boukensha/tool.rb`, `registry.rb`, `context.rb`, `run_dsl.rb`, and
the three modules under `lib/boukensha/tools/` (`file_system.rb`, `shell.rb`,
`mud.rb`), plus how `Boukensha.run` / `.repl` wire them up. Findings below
marked **confirmed live** were reproduced with a standalone probe script
against the real code (no mocks); findings marked **from source** are static
reads only — `Tools::Mud` needs a running CircleMUD instance I didn't stand
up for this pass.

## Simple explanation: how a "tool" becomes something the agent can call

Four pieces, each with exactly one job:

- **`Tool`** (`tool.rb`) — a plain `Struct(name, description, parameters, block)`.
  Just data plus the callable.
- **`Registry`** (`registry.rb`) — owns registration and dispatch:
  `tool(name, description:, parameters:, &block)` builds a `Tool` and hands it
  to the `Context`; `dispatch(name, args)` looks the tool up by name and calls
  `tool.block.call(**args.transform_keys(&:to_sym))`.
- **`Context`** (`context.rb`) — the actual storage (`@tools = {}`), plus
  conversation `@messages`. `Registry` is a thin façade in front of it;
  `Context#register_tool` is a one-line hash insert (`@tools[tool.name] = tool`),
  so re-registering the same name silently replaces the old tool — no
  duplicate-registration guard.
- **`RunDSL`** (`run_dsl.rb`) — the `self` inside a `Boukensha.run { tool "x", ... }`
  block. It exposes exactly one method, `tool`, which just forwards to
  `registry.tool`. Deliberately narrow surface — you can't reach `@context` or
  anything else from inside that block.

The three `Tools::*` modules never touch `Registry`/`Context` internals — they
only ever call `registry.tool(...)`, the same public API `RunDSL` uses. That's
the "standard library" idea from the README: `FileSystem`/`Shell`/`Mud` are
just pre-written callers of the same `registry.tool` primitive every custom
tool in earlier steps used, bundled so you don't have to hand-write them.

### Where auto-registration actually happens

`boukensha.rb`'s `run`/`repl` (identical logic, duplicated in both methods):

```ruby
if working_dir
  Tools::FileSystem.register(registry, working_dir: working_dir)
  Tools::Shell.register(registry, working_dir: working_dir,
                        timeout: shell_timeout, allowed_commands: allowed_commands)
end

resolved_mud = mud == false ? nil : (mud || mud_opts_from_config(cfg))
Tools::Mud.register(registry, **resolved_mud) if resolved_mud

RunDSL.new(registry).instance_eval(&block) if block
```

Order matters here in one subtle way: the `&block` (custom `tool "..."` calls)
runs **after** the standard-library registration, so a custom block can
silently override a standard tool by reusing its name (e.g. redefining
`read_file`) — there's no protection either way, per the no-guard behavior in
`Context#register_tool` above. Not necessarily wrong, but worth knowing: it's
last-write-wins, not first-write-wins.

`working_dir` defaults to `Dir.pwd`, so **`FileSystem` and `Shell` are opt-out,
not opt-in** — every `Boukensha.run`/`.repl` call gets a live shell (with no
command allow-list by default: `allowed_commands: nil` means "permit
everything") unless you explicitly pass `working_dir: false`. `Mud` is the
opposite: opt-in unless `.boukensha/settings.yaml` already has `mud.host` set,
in which case it's silently auto-enabled too via `mud_opts_from_config`.

## `Boukensha::Tools::FileSystem` — sandboxed file access

The sandbox is one closure, reused by all six tools:

```ruby
resolve = lambda do |path|
  absolute = File.expand_path(path.to_s, root)
  if absolute == root || absolute.start_with?("#{root}/")
    absolute
  else
    "error: path '#{path}' escapes the working directory"
  end
end
```

**Confirmed live** — this holds up against the traversal shapes I tried:

| Input | Result |
|---|---|
| `../../etc/passwd` | rejected (`escapes the working directory`) |
| `/etc/passwd` (absolute, outside root) | rejected |
| `../<root-dirname>-evil/secret.txt` (sibling dir whose name has the root's dirname as a *prefix*, targeting the classic `start_with?` bug where `/tmp/foo-evil` incorrectly passes a naive `start_with?("/tmp/foo")` check) | rejected |

The third case is the one worth calling out: a naive `start_with?(root)`
(without the trailing `/`) would have let `/tmp/foo-evil/secret.txt` through
because it literally starts with the string `/tmp/foo`. This code guards
against exactly that by requiring the `/` separator (`start_with?("#{root}/")`)
*and* by resolving `..` via `File.expand_path` before the check ever runs —
so there's no window where an unresolved `..` could be compared against the
prefix. Good defensive pattern, confirmed rather than assumed.

**Confirmed live — a real gap**: this sandboxing only covers the `path:`
argument. It does **not** cover malformed tool *invocations*. Two ways to
trigger an uncaught exception that never reaches a tool's own `rescue`:

```ruby
registry.dispatch("write_file", path: "x.txt")
# => ArgumentError: missing keyword: :content

registry.dispatch("list_directory", path: ".", extra_bogus_arg: "x")
# => ArgumentError: unknown keyword: :extra_bogus_arg
```

Both happen at `tool.block.call(**args)` in `Registry#dispatch` — i.e.
*before* the block body (and its own `rescue => e`) ever runs. This directly
contradicts the module's own doc comment: "the tool returns an error string
rather than raising — so the agent sees it and can try something sensible
instead." That promise holds for path-escape errors but not for
missing/extra-keyword errors. It's not fatal — `Agent#handle_tool_calls`
wraps every `dispatch` call in `rescue StandardError => e` and turns it into
a `"ERROR: ArgumentError: ..."` tool-result string the model still sees — but
the *shape* of that error differs (raw exception class + message vs. the
tool's own crafted `"error: ..."` string), and it's exactly the failure mode
you'd expect an LLM to hit occasionally (forgetting a required arg, or
passing one extra field a backend's JSON schema didn't strip). A generic
`rescue ArgumentError` wrapper in `Registry#dispatch` itself — not per-tool —
would close this for every current and future tool at once.

`delete_file` on a directory: confirmed it returns `"error: 'notes' is not a
file"` rather than raising `Errno::EISDIR` — the `File.file?` guard ahead of
the `File.delete` call earns its keep here.

## `Boukensha::Tools::Shell` — `run_command`

Allow-list check is a plain first-token match against `allowed_commands`,
done *before* execution:

```ruby
executable = command.to_s.strip.split(/\s+/).first.to_s
unless allowed_commands.map(&:to_s).include?(executable)
  next oops.call(...)
end
```

**Confirmed live**: `rm -rf /` is rejected up front when `allowed_commands:
["ruby", "echo"]`; `echo hello` runs and returns `"hello"`. Note this is a
literal first-token check, not a shell-syntax-aware one — `echo hi; rm -rf /`
would pass the guard (first token `echo`) and then execute *both* commands,
since the whole string still goes to `Open3.capture2e(command, ...)`, which
runs it through `/bin/sh -c` when the string contains shell metacharacters.
The allow-list is a name filter, not a sandbox against command chaining.
Worth documenting as a known limitation if this is ever used with a
non-trusted-sounding allow-list.

**Confirmed live — a real bug**: the timeout does not stop the child process.

```ruby
Timeout.timeout(timeout) do
  stdout_err, status = Open3.capture2e(command, chdir: root)
end
rescue Timeout::Error
  next oops.call("command timed out after #{timeout}s: #{command}")
```

`Timeout.timeout` only interrupts the *Ruby thread* waiting on
`Open3.capture2e` — it never signals the spawned OS process. Reproduced with
`timeout: 1, command: "sleep 20 && touch <marker>"`:

```
$ ps -eo pid,ppid,stat,cmd | grep sleep
2828  2825  S  sh -c sleep 20 && touch /tmp/.../marker
2831  2828  S  sleep 20
dispatch returned: "error: command timed out after 1s: sleep 20 && touch ..."
```

The tool call returns in ~1s as documented, but the `sh -c ...` and `sleep 20`
processes are still alive afterward, running to completion regardless of what
the agent does next — a resource leak on every timeout, and a real gap in the
safety story if `shell_timeout:` is being relied on as a hard ceiling (e.g. to
bound a runaway build command). It also prints an unrescued warning to
stderr on every timeout, because `Open3.capture2e` spawns its own internal
reader thread that gets interrupted mid-read:

```
#<Thread:0x... open3.rb:404 run> terminated with exception (report_on_exception is true):
open3.rb:404:in `read': stream closed in another thread (IOError)
```

This is cosmetic (doesn't corrupt the returned result — confirmed the
`"command timed out..."` string still comes back correctly) but it's visible
noise on every timeout and a sign the interrupt is happening somewhere it
wasn't fully accounted for. Fixing the leak (e.g. tracking the child pid via
`Open3.popen2e` and explicitly killing the process group on `Timeout::Error`)
would likely also quiet this warning, since there'd be no thread left mid-read
to interrupt.

`command not found`: confirmed a nonexistent executable raises
`Errno::ENOENT`, which *is* rescued in-block and returns a clean
`"error: command not found: ..."` string — this path (unlike the two
`ArgumentError` cases above) matches the module's stated contract.

## `Boukensha::Tools::Mud` — from source (not live-tested)

Far larger than the other two (~30 tools across connection, perception,
movement, combat, communication, inventory, magic, and a `send_raw` escape
hatch) and structurally different in one important way: it isn't a pure set
of closures until first use. `register` itself has a side effect:

```ruby
def self.register(registry, host: "localhost", port: 4000, name:, password:)
  session = MudManager::Session.new(host: host, port: port)
  ...
  # Auto-connect at startup so the session is ready immediately...
  begin
    session.open
    session.login(name, password)
  rescue MudManager::Session::Error => e
    warn "[boukensha] MUD auto-connect failed: #{e.message} — call mud_connect manually"
  end
end
```

`FileSystem.register` and `Shell.register` only build closures — no I/O
happens until the agent actually calls a tool. `Mud.register` opens a real
socket and logs in **during agent setup**, before the first model call. If
the MUD host is unreachable, this degrades gracefully (rescued, logged via
`warn`, and `mud_connect` remains available as a manual retry) — but it does
mean every `Boukensha.run`/`.repl` invocation with a configured `mud_host`
pays a network round-trip (and, per the repo's `.boukensha/settings.yaml`,
targets `localhost:4000` — i.e. every run expects a local CircleMUD server
already up) before the agent loop even starts. Also notable: all ~30 tools
close over the **same** `session` — there's no multi-session support, which
is fine for a single-player teaching harness but would need rethinking for
anything concurrent.

One dependency wrinkle worth flagging for whoever runs this step next:
`boukensha.gemspec` declares `spec.add_dependency "mud_manager", "~> 0.1"` as
if it were a published RubyGems package, but it isn't on rubygems.org — its
source lives locally at `week0_explore/mud_manager/` (a `.gem` built there,
`mud_manager-0.1.0.gem`). A plain `bundle install` in this step's directory
will fail to resolve it; unlike steps `00`–`09`, this step has no
`vendor/bundle/` yet, so that hasn't been exercised here. Whoever does the
Python port (or first `bundle install`) for this step will need to point
Bundler at that local `.gem`/path, not fetch from rubygems.org.

### A documentation gap

`README.md` for this step describes `FileSystem` and `Shell` in full
(including a table per tool) but **never mentions `Tools::Mud` at all** —
despite it being ~480 of the ~1,000 new lines in this step and the module
most directly relevant to "playing the MUD" (the stated end goal of the whole
`boukensha` project). The `examples/example.rb` demo is MUD-only
(`working_dir: false`, connects and looks around), which only makes sense
once you already know `Tools::Mud` exists — the README doesn't get you there.

## Retain — the short list

1. **Resolve-then-prefix-check with the trailing separator** in `FileSystem`
   is the right pattern for path-sandboxing and is worth reusing verbatim in
   future tools that touch the filesystem — confirmed it defeats both `..`
   traversal and the "sibling directory with a matching string prefix" trap
   that a bare `start_with?(root)` (no `/`) would fall into.
2. **Tools return error strings instead of raising, on the happy-invalid-input
   path** (bad path, missing file, `ENOENT`) — this is what lets the agent
   see a failure and retry sensibly instead of the whole turn blowing up. The
   gap is only at the dispatch boundary (missing/extra keywords) — the
   in-block error-string discipline itself is worth keeping.
3. **Fail-open on registration, not on first use** (`Mud`'s auto-connect
   rescues and warns rather than raising) is a reasonable choice for a
   teaching harness — but note it's genuinely different from `FileSystem`
   /`Shell`'s fully-lazy registration, and that difference isn't visible from
   the `Boukensha.run` call site.
