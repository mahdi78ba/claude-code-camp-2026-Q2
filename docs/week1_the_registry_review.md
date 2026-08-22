# Week 1 Review — Tool Registry (`02_the_registry`)

Everything technical for this iteration in one place: the setup/fix work
done to get it running, and the code review (registration, dispatch, and how
far the registry actually separates tool management from `Context`). Builds
on the `Tool`/`Message`/`Context` structs reviewed in
[`week1_struct_skeleton_review.md`](week1_struct_skeleton_review.md). This
iteration adds the layer that registers tools and dispatches calls to them —
the piece `01_struct_skeleton` deliberately left unused (`Tool#block` was
declared but never invoked).

---

## Setup & fixes applied

What it took to get `02_the_registry` from "already checked into the repo"
to "actually runs and matches the README":

1. **Directory audit** — `week1_baseline/ruby/02_the_registry` was already
   present (part of the initial commit), fully fleshed out
   (`registry.rb`, `errors.rb`, README, example). No files needed copying
   in. Confirmed no `*Zone.Identifier` files anywhere in the repo.
2. **Fixed the off-by-one `../` bug in `examples/example.rb`** — same class
   of bug as `00_config` and `01_struct_skeleton` (logged as entries #4/#8 in
   `week1_config_troubleshooting.md`, this one as entry #10). The line
   ```ruby
   ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)
   ```
   only had 3 `../`, resolving to a nonexistent `week1_baseline/.boukensha`
   instead of `<repo-root>/.boukensha`. `settings.yaml` then loaded as `{}`,
   `config.tasks(:player)` returned `nil`, and
   `Tasks::Base.system_prompt(nil, ...)` crashed with
   `NoMethodError: undefined method '[]' for nil:NilClass`. Fixed by adding
   the missing `../`:
   ```ruby
   ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
   ```
   **Still latent, unfixed, in iterations 03–08** — same 3-`../` mistake
   confirmed via repo-wide grep; expect and fix it there too before wiring up
   their runners.
3. **Vendored gems locally** — `02_the_registry` had a `Gemfile`/`Gemfile.lock`
   (just `dotenv`) but no local bundle config yet:
   ```bash
   cd week1_baseline/ruby/02_the_registry
   bundle config set --local path 'vendor/bundle'
   bundle install
   ```
   `.bundle/` and `vendor/bundle/` are both gitignored (confirmed via
   `git check-ignore -v`), consistent with every prior iteration.
4. **Added a runner script** at `week1_baseline/bin/ruby/02_the_registry`
   (`chmod u+x`), matching the pattern from `01_struct_skeleton`:
   ```bash
   #!/usr/bin/env bash
   cd "$(dirname "$0")/../../ruby/02_the_registry"
   bundle exec ruby examples/example.rb
   ```
5. **Verified output** — `./week1_baseline/bin/ruby/02_the_registry` now runs
   clean and matches the README's `## Expected Output` section, with two
   doc-only discrepancies noted (not code bugs, not fixed):
   - README's sample shows `Context: #<Context turns=0 tools=2 budget=8192>`;
     the real `Context#to_s` (unchanged since `01_struct_skeleton`) prints
     `task=player turns=0 tools=2` — no `budget` field exists in the code
     yet.
   - README's `## Run Example` section points at
     `./week1_baseline/bin/01_the_registry` — wrong iteration number; the
     real path is `./week1_baseline/bin/ruby/02_the_registry`.

Full Problem/Fix/Why writeup of step 2 lives in `week1_config_troubleshooting.md`
(entry #10) alongside the same bug's history in earlier iterations — kept
there rather than duplicated here since that file is the standing
cross-iteration log.

---

## Code review

---

## `Boukensha::Registry` (`lib/boukensha/registry.rb`)

```ruby
require_relative "errors"

module Boukensha
  class Registry
    def initialize(context)
      @context = context
    end

    def tool(name, description:, parameters: {}, &block)
      tool = Tool.new(name.to_s, description, parameters, block)
      @context.register_tool(tool)
      tool
    end

    def dispatch(name, args = {})
      tool = @context.tools[name.to_s]
      raise UnknownToolError, "No tool registered as '#{name}'" unless tool
      tool.block.call(**args.transform_keys(&:to_sym))
    end
  end
end
```

- **The Registry holds no tool state of its own.** `initialize` stores only
  `@context` — there's no `@tools` hash on the Registry. Both `tool` and
  `dispatch` read/write through to `@context.register_tool` /
  `@context.tools[...]`. The Registry is a stateless façade over `Context`'s
  storage, not an independent store — see "separation" discussion below.
- **`tool` is a friendlier construction API than raw `Tool.new`.** Compared to
  `01_struct_skeleton`'s example (`Tool.new("move", "...", {...}, ->(direction)
  {...})`, all positional, no defaults), this method:
  - takes `description:`/`parameters:` as keywords, so args can't be silently
    transposed the way two positional strings could be;
  - defaults `parameters:` to `{}`, so a zero-argument tool needs no
    boilerplate;
  - coerces `name.to_s`, so a caller can register with a Symbol (`:move`) or
    String (`"move"`) and it's always stored as a String — matters because
    `dispatch`/`Context#register_tool` both key off `tool.name` as a String.
  - still builds a plain `Tool` struct underneath — this is a nicer front
    door onto the same shape from the previous iteration, not a replacement
    for it.
- **`tool` returns the constructed `Tool`.** Nothing in `example.rb` uses that
  return value (both calls are bare statements) — a currently-unused nicety
  that would let a caller do `t = registry.tool(...)` and inspect it
  immediately.
- **`dispatch`'s string→symbol translation is unconditional.** `args.transform_keys(&:to_sym)`
  runs on every call, whether `args` came from parsed JSON (string keys, the
  case the README's "Considerations" section calls out) or was already
  symbol-keyed Ruby (harmless no-op there, since `Symbol#to_sym` returns
  `self`). Fine either way, but worth noting `dispatch` doesn't distinguish
  "internal" calls from "wire" calls — it always assumes the normalize step is
  safe to run.
- **No validation of `args` against `tool.parameters` before calling the
  block.** `UnknownToolError` is deliberately raised for an *unregistered*
  name (the one error boundary the README calls out), but a *wrong-shaped*
  call to a *known* tool — e.g. `dispatch("move", {})` with no `direction`
  key — isn't caught by the Registry at all. It falls straight through to
  `tool.block.call(**{})`, which raises Ruby's own
  `ArgumentError: missing keyword: :direction` from inside the block
  invocation, not a `Boukensha`-specific error. So today there's exactly one
  explicit error boundary (unknown tool name), not two (unknown name +
  malformed args) — worth watching whether a later iteration validates args
  against `tool.parameters` before invoking `block`.
- **No enumeration API of its own.** `example.rb` prints the tool table via
  `ctx.tools.each_value`, reaching back into `Context` directly rather than
  asking `registry` for a list — confirms only *registration* and *dispatch*
  moved into the Registry; storage and enumeration are still `Context`'s job.

## `Boukensha::UnknownToolError` (`lib/boukensha/errors.rb`)

```ruby
module Boukensha
  class UnknownToolError < StandardError; end
end
```

- Minimal — no custom fields, message comes from the `raise Klass, "text"`
  call site in `Registry#dispatch`.
- Inherits directly from `StandardError`, not from some shared
  `Boukensha::Error` base. Fine with a single error class; if more
  `Boukensha`-specific errors get added in later iterations, introducing a
  common ancestor then would let callers `rescue Boukensha::Error` broadly —
  not needed yet with just one class.

---

## How tools are registered

Registration is a two-step handoff, always initiated through the Registry in
this iteration's example:

```ruby
registry.tool("move",
  description: "Move the player in a direction (north, south, east, west, up, down)",
  parameters: { direction: { type: "string" } }
) do |direction:|
  "You move #{direction} into a torch-lit corridor."
end
```

1. `Registry#tool` builds a `Tool` struct from the name/description/parameters
   plus the block passed via `&block` (the `do...end` here).
2. It immediately calls `@context.register_tool(tool)`, which is the *same*
   `Context` method `01_struct_skeleton` called directly
   (`@tools[tool.name] = tool`, a plain Hash write, last-write-wins on a
   duplicate name — unchanged from the earlier iteration's review).

Net effect: the Registry does not introduce new storage or a new invariant —
it introduces a **safer construction path** into storage that already
existed. Nothing stops a caller from skipping the Registry and calling
`ctx.register_tool(Tool.new(...))` directly, as `01_struct_skeleton` did —
that path still works identically and would bypass the `name.to_s` coercion
and the keyword-based defaults.

## How tool calls are dispatched

```ruby
result = registry.dispatch("shout", { "message" => "dragon spotted" })
```

1. `dispatch` looks up `@context.tools[name.to_s]` — a direct read of
   `Context`'s internal Hash, not through some `Context#find_tool` accessor.
2. Missing name → raise `UnknownToolError` immediately, before touching
   `args` at all (confirmed by `registry.dispatch("flee")` in the example,
   which passes no args and never needs to — the lookup fails first).
3. Found name → `tool.block.call(**args.transform_keys(&:to_sym))`. This is
   the line that finally exercises `Tool#block`, which `01_struct_skeleton`
   registered but never called. The `transform_keys` step is what makes
   string-keyed args (`{"message" => ...}`, matching what a real JSON tool
   call over an API would look like) compatible with a Ruby block declared
   with keyword parameters (`|message:|`) — symbol-keyed only.

The dispatch flow is intentionally simple: name lookup, one error boundary,
one key-normalization step, then a direct block call. There's no logging, no
result wrapping (`dispatch` returns whatever the block returns, raw), and no
recording of the call into `ctx.messages` — the caller (`example.rb`) just
`puts`s the result. Tool-call history (pairing a dispatched call and its
result back into the conversation via `Message#tool_use_id`, the one
`Message` field still unused since the `01_struct_skeleton` review) is not
wired up here either — still a later concern.

## "The registry separates tool management from agent context" — how far that goes

This is true, but it's a **behavioral** separation more than a **storage**
one, and worth being precise about which parts moved and which didn't:

| Responsibility | Owner before (`01_struct_skeleton`) | Owner now (`02_the_registry`) |
|---|---|---|
| Tool storage (`@tools` Hash) | `Context` | still `Context` |
| Registering a tool | caller → `ctx.register_tool(Tool.new(...))` directly | caller → `registry.tool(...)`, which internally still calls `ctx.register_tool` |
| Looking up a tool by name | caller reached into `ctx.tools[name]` itself | `Registry#dispatch` does the lookup, still via `ctx.tools[...]` |
| Invoking the tool's block | nothing did — `Tool#block` was dead code | `Registry#dispatch` calls `tool.block.call(...)` |
| Unknown-tool error handling | didn't exist | `Registry` raises `UnknownToolError` |
| Args key normalization (string→symbol) | didn't exist | `Registry#dispatch` |

So what actually separated out is **the dispatch protocol** — the rule that
"the agent never calls a tool directly, it asks the registry" (per the
README) — plus a safer registration API. What did **not** separate out is
**ownership of the tool table** — `Context` still holds the Hash, and
`Registry` still has to know its shape (`ctx.tools[name.to_s]`) to read it.

Two consequences worth flagging as things to watch in later iterations:

1. **The separation isn't enforced, only conventional.** `Context#register_tool`
   and `Context#tools` are still public and fully functional on their own —
   a caller can bypass `Registry` entirely (as `01_struct_skeleton`'s example
   did, and still could here) and nothing prevents it. The safety `Registry`
   adds (name coercion, keyword defaults, the `UnknownToolError` boundary)
   only applies to code that chooses to go through it.
2. **The coupling runs both directions.** `Context` doesn't know `Registry`
   exists (good — `Context` stays usable standalone, as confirmed by
   `01_struct_skeleton` never referencing a registry). But `Registry` has to
   know `Context` stores tools in a Hash keyed by String name to do its
   lookup (`@context.tools[name.to_s]`) — it's not going through an
   abstraction like `Context#find_tool(name)`. If `Context`'s internal
   storage ever changed shape, `Registry#dispatch` would need to change with
   it. A fuller separation would either give `Context` a lookup method that
   hides its storage, or move the Hash itself into `Registry` and have
   `Context#tools` read *from* the registry instead of the other way around.

---

## Example walkthrough (`examples/example.rb`)

The example mirrors `01_struct_skeleton`'s structure (build `Config` →
`Tasks::Player.system_prompt` → `Context`) but replaces direct
`ctx.register_tool` calls with a `Registry`, and adds three `dispatch` calls
at the end that didn't exist in the previous iteration at all.

```ruby
ctx      = Boukensha::Context.new(task: Boukensha::Tasks::Player, system: system_prompt)
registry = Boukensha::Registry.new(ctx)
```

- Same "system prompt may resolve to `nil`" caveat as the struct-skeleton
  review applies unchanged here — `system_prompt` is computed the same way,
  with no `default_prompts_dir:` passed, so it only returns non-`nil` if a
  user prompt override exists. Not new to this iteration, just still true.

```ruby
registry.tool("move", ...) do |direction:| ... end
registry.tool("shout", ...) do |message:| ... end
```

- Both tools' block keyword parameters (`direction:`, `message:`) are
  hand-kept in sync with their `parameters:` hash keys — same caveat flagged
  in the struct-skeleton review for `Tool#parameters` vs. the block's arity:
  nothing validates the two match, at registration or at dispatch time.

```ruby
puts "Dispatching 'shout' with message='dragon spotted'..."
result = registry.dispatch("shout", { "message" => "dragon spotted" })
puts "Result: #{result}"
```

- Deliberately passes a **string-keyed** hash to exercise the
  `transform_keys(&:to_sym)` gotcha described in the README. Same pattern
  repeated for `move` with `{"direction" => "north"}`.

```ruby
begin
  registry.dispatch("flee")
rescue Boukensha::UnknownToolError => e
  puts "UnknownToolError caught: #{e.message}"
end
```

- Exercises the one explicit error boundary this iteration adds. `args`
  defaults to `{}` and is never touched, since the name lookup fails first —
  confirms `dispatch("flee")` (no second arg) is a legal call, not a
  shorthand that would break.

### Summary

This iteration finally exercises `Tool#block` (dead code since
`01_struct_skeleton`) and adds the one error boundary the README calls out
(`UnknownToolError`). What it does *not* yet do: validate call args against a
tool's declared `parameters`, wrap/log a dispatch result, or record a
dispatched call and its result back into `ctx.messages` via
`Message#tool_use_id` — that field is still unused, three iterations in.
Storage of tools also hasn't moved — it's still a `Context` Hash that
`Registry` reads through rather than owns — so "the registry separates tool
management from context" is accurate for *registration/dispatch behavior*,
not for *data ownership*.
