# Week 1 Review — Core Data Structures (`01_struct_skeleton`)

Review of `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/{tool,message,context}.rb`.
This iteration defines the three shapes that get passed around the agent loop
for the rest of the codebase.

---

## `Boukensha::Tool` (`lib/boukensha/tool.rb`)

```ruby
Tool = Struct.new(:name, :description, :parameters, :block) do
  def to_s
    "#<Tool name=#{name} description=#{description.to_s[0..40]} params=#{parameters.keys}>"
  end
end
```

- Plain `Struct`, positional (not `keyword_init: true`) — construction order
  matters: `Tool.new(name, description, parameters, block)`, as seen in
  `examples/example.rb`. No keyword form exists yet, so a caller can silently
  swap `description`/`parameters` if they get the order wrong.
- `parameters` holds a JSON-Schema-shaped `Hash` per argument
  (`{ direction: { type: "string", description: "..." } }`) — this is the
  shape an LLM tool-use API expects, so the field is already forward-looking
  even though nothing consumes it yet.
- `block` stores the callable (`->(direction) { ... }`) that runs when the
  tool is invoked, but **nothing in this iteration calls `tool.block`** — the
  struct only defines the shape; dispatch is deferred to a later iteration
  (likely the registry/agent-loop steps).
- Custom `#to_s` overrides Struct's verbose default inspect output and
  truncates `description` to 41 chars — deliberately readable in logs at the
  cost of losing full text. `parameters.keys` is printed rather than the full
  hash, which matches the README's example output (`params=[:direction]`).

## `Boukensha::Message` (`lib/boukensha/message.rb`)

```ruby
Message = Struct.new(:role, :content, :tool_use_id) do
  def to_s
    id_tag = tool_use_id ? " [#{tool_use_id}]" : ""
    "#<Message role=#{role}#{id_tag} content=#{content.to_s[0..60]}...>"
  end
end
```

- `role` is untyped — `example.rb` passes symbols (`:user`, `:assistant`);
  nothing enforces that it's one of `user` / `assistant` / `tool_result`. A
  typo (`:asistant`) would pass silently.
- `tool_use_id` is optional (defaults to `nil` via Struct) and only shown in
  `#to_s` when present — this is the field that pairs a `tool_result` message
  back to the tool call that produced it, per the README, but **no code path
  in this iteration exercises the `tool_result` role** — `example.rb` only
  ever creates `:user`/`:assistant` messages, so the pairing behavior is
  documented but not yet demonstrated or tested.
- Content truncation (`[0..60]`) always appends `"..."`, even for strings
  shorter than 61 chars (e.g. `"You move north..."` in the README sample) —
  cosmetic, but means the ellipsis isn't a reliable "was truncated" signal.

## `Boukensha::Context` (`lib/boukensha/context.rb`)

```ruby
class Context
  attr_reader :task, :system, :messages, :tools

  def initialize(task:, system: nil)
    @task, @system, @messages, @tools = task, system, [], {}
  end

  def register_tool(tool) = @tools[tool.name] = tool
  def add_message(role, content, tool_use_id: nil) = @messages << Message.new(role, content, tool_use_id)
  def tool_count = @tools.size
  def turn_count = @messages.size
end
```
*(bodies condensed here for the summary; see the file for the literal form)*

- **Not a Struct** — unlike `Tool`/`Message`, `Context` is a regular class.
  That's the right call: it's a mutable container with behavior
  (`register_tool`, `add_message`, counters), not a pure data record, so a
  Struct would have bought nothing. Worth calling out explicitly since the
  task framing ("Ruby uses lightweight Structs...") could read as if all
  three were Structs.
- `task:` is a **required** keyword arg holding a *class* (`Boukensha::Tasks::Player`,
  not an instance — tasks are stateless class-method objects per
  `tasks/base.rb`), while `system:` is optional. `task&.task_name` is used
  when rendering, defensively guarding against `task` being `nil` even though
  the initializer marks it required — inconsistent strictness.
- **README/code mismatch on the schema.** The README's field table for
  `Context` lists `system`, `messages`, `tools`, `token_budget` (and shows
  `#<Context turns=2 tools=1 budget=8192>` / `used=7800` in examples), but the
  actual class:
  - has no `token_budget` attribute or constructor param at all — budget
    tracking isn't implemented yet, only documented as intent.
  - exposes `task` (not mentioned in the README's field table) instead.
  - `#to_s` in the code is `"#<Context task=#{task&.task_name} turns=#{turn_count} tools=#{tool_count}>"`
    — no `budget=`/`used=` segment, so the README's sample output doesn't
    match what running `examples/example.rb` actually prints.
  - This is expected for a skeleton iteration (budget enforcement is called
    out in `tasks/base.rb`'s sibling doc as a later concern), but it means
    the README is describing the *target* shape a couple of iterations
    ahead of the code, not the current state.
- `tools` is keyed by `tool.name` (a `Hash`, not an `Array`) — so registering
  two tools with the same name silently overwrites the first; no error, no
  merge.
- `tool_count`/`turn_count` use Ruby 3.0+ endless method syntax
  (`def tool_count = @tools.size`) — consistent with `Tasks::Player.task_name`
  and `Tool`/`Message`'s single-expression helpers, matching this codebase's
  established style rather than a one-off.

---

## Cross-cutting observations

1. **Structs are used only where the value is a pure, order-stable tuple**
   (`Tool`, `Message`); anything with behavior or required invariants
   (`Context`) is a plain class. That's a reasonable and consistent line to
   draw, not an inconsistency.
2. **Nothing is validated at construction.** `Tool#parameters` isn't checked
   against a schema shape, `Message#role` isn't checked against an allowed
   set, and `Context#task` accepts anything responding (or not) to
   `.task_name`. Fine for a skeleton step whose goal is just "define the
   shapes," but worth tracking if a later iteration doesn't add guards before
   wiring in a real LLM backend, where a malformed `Tool`/`Message` would
   only fail at the API boundary.
3. **The README is aspirational in one place**: the `Context` section
   documents a `token_budget` field and `budget=`/`used=` output that doesn't
   exist in this iteration's code yet. Not a bug, but worth confirming this
   is intentional (documenting where `Context` is headed) rather than a
   README that was copied from a later iteration by mistake.
4. **Tool dispatch and tool-result messages are both declared but unused**
   in this iteration — `Tool#block` is never called, and `Message` never
   gets constructed with `role: :tool_result`. Confirms this step is purely
   about the data shapes; the registry/execution loop that exercises them
   comes later.

---

## Example walkthrough (`examples/example.rb`)

The example (35 lines) is a single linear script — create a `Context`,
register a `Tool`, append two `Message`s, print everything — that shows the
three structs used together. It builds on the previous (`00_config`)
iteration's `Config`/`Tasks::Player` rather than being a clean-room demo of
just the new structs.

### 1. Creating the `Context` (lines 4–14)

```ruby
config = Boukensha::Config.new
player_settings = config.tasks(:player)
system_prompt = Boukensha::Tasks::Player.system_prompt(
  player_settings,
  user_prompts_dir: config.user_prompts_dir
)

ctx = Boukensha::Context.new(
  task: Boukensha::Tasks::Player,
  system: system_prompt
)
```

- `task:` receives the **class** `Boukensha::Tasks::Player`, not an instance
  — consistent with `Tasks::Base` being an abstract, stateless,
  class-method-only object (see the earlier struct review).
- **The system prompt likely resolves to `nil` on a stock checkout.** The
  call to `system_prompt` omits `default_prompts_dir:`. Tracing into
  `tasks/base.rb`:
  ```ruby
  def self.prompt(settings, name = :system, user_prompts_dir: nil, default_prompts_dir: nil)
    if prompt_override?(settings, name) && (text = read_user_prompt(name, user_prompts_dir: user_prompts_dir))
      return text
    end
    read_default_prompt(name, default_prompts_dir: default_prompts_dir)
  end
  # ...
  def read_default_prompt(prompt_name, default_prompts_dir: nil)
    return nil unless default_prompts_dir
    read_file(File.join(default_prompts_dir, "#{prompt_name}.md"))
  end
  ```
  With `default_prompts_dir` unset it defaults to `nil`, so
  `read_default_prompt` short-circuits to `nil`. This lines up with the rest
  of the iteration: `01_struct_skeleton/lib/boukensha/config.rb` no longer
  defines a `PROMPTS_DIR` constant, and the iteration doesn't ship a
  `prompts/system.md` at all (both existed in `00_config`, confirmed by
  diffing the two directories). So unless you've manually created
  `.boukensha/prompts/player/system.md` **and** set
  `prompt_override.system: true` in `settings.yaml`, `system_prompt` returns
  `nil`, and `ctx.system` is `nil` for the whole run. Not a bug — this
  iteration simply doesn't carry a default-prompt fallback forward — but it
  means the example silently runs with an empty system prompt out of the
  box, and nothing in the printed output calls that out (`Context#to_s`
  doesn't print `system` at all).

### 2. Registering the tool (lines 16–23)

```ruby
ctx.register_tool(
  Boukensha::Tool.new(
    "move",
    "Move the player in a direction (north, south, east, west, up, down)",
    { direction: { type: "string", description: "The direction to move" } },
    ->(direction) { "You move #{direction} into a torch-lit corridor." }
  )
)
```

- Built with the **positional** `Tool.new(name, description, parameters,
  block)` form — order-dependent, as flagged in the struct review above; get
  two args swapped and it fails silently rather than raising.
- `parameters` is the JSON-Schema-shaped hash `Tool` is designed to carry;
  `block` is a lambda whose arity (`direction`) matches that schema's one
  key. The two are hand-kept in sync by the author — nothing checks that the
  lambda's parameters actually match the `parameters` hash's keys.
- Only the **shape** is exercised: `register_tool` just does
  `@tools["move"] = tool`. The lambda in `block` is never invoked anywhere in
  this script — there's no simulated tool call, so `Tool#block` stays
  dead code for this iteration. Confirms execution/dispatch is deferred to a
  later step (the registry).
- Only one tool is registered, so `Context#register_tool`'s
  overwrite-on-duplicate-name behavior (hash keyed by `tool.name`, noted
  above) isn't exercised one way or the other here.

### 3. Adding messages to history (lines 25–26)

```ruby
ctx.add_message(:user, "Explore north and tell me what you find.")
ctx.add_message(:assistant, "Sure, let me head north and take a look.")
```

- A bare two-turn `:user`/`:assistant` exchange. `add_message` just does
  `@messages << Message.new(role, content, tool_use_id)` — a plain append,
  so ordering/alternation is entirely the caller's responsibility; `Context`
  doesn't validate turn structure.
- **The tool that was just registered is never actually "called" in the
  conversation.** Despite registering `move` immediately above, the example
  never adds a `role: :tool_result` message (with a `tool_use_id` pairing it
  back to a call) — so the one piece of `Message` designed specifically for
  tool interactions (`tool_use_id`) is declared in the struct but still has
  no working example anywhere in this iteration. A learner reading only this
  script would not see how a tool call and its result are supposed to be
  threaded through the transcript.

### 4. Printing the result (lines 28–34)

```ruby
puts "Tool:     #{ctx.tools['move']}"
```

- Hardcodes the string key `'move'` to look the tool back up. This works
  only because `Tool.new`'s first positional arg (`"move"`) was a `String`,
  matching how `register_tool` keys `@tools` by `tool.name`. It's a magic
  string tying this line to the specific tool registered above — if the tool
  were renamed, `ctx.tools['move']` would quietly return `nil`, and
  `"Tool:     #{nil}"` prints as `"Tool:     "` with no error, which would be
  a confusing silent failure to debug for a learner tweaking the example.
- The `Context:` line comes from `Context#to_s`; per the struct review, this
  won't print a `budget=`/`used=` segment the way the README's sample output
  does, so a learner running this script and comparing output to the README
  line-for-line will see a mismatch there too.

### Summary

The example proves the happy path — construct, register, append, print —
for all three structs, but two things it *doesn't* demonstrate are exactly
the two things flagged as "declared but unused" in the struct review:
tool invocation (`Tool#block`) and tool-result pairing
(`Message#tool_use_id` with `role: :tool_result`). Both are shapes waiting
for a consumer that arrives in a later iteration.
