# Step 7 — The `boukensha.run()` DSL

Python port of `ruby/07_the_run_dsl`.

## What this step adds

A single top-level entry point: `boukensha.run()`.

Every previous step required you to manually create and wire together a
`Context`, `Registry`, a `Backend`, `PromptBuilder`, `Client`, `Logger`, and
`Agent`. Step 7 hides all of that behind one function call.

## The new primitive

### `boukensha.RunDSL`

A tiny host object passed to the `configure` callback given to
`boukensha.run()`. It exposes exactly one method: `tool`. This keeps the
DSL surface intentionally small and prevents callers from reaching internal
state (`Context`, `Client`, etc.).

Ruby's version instead takes a block and `instance_eval`s it against a
`RunDSL` instance, so a bare `tool` call inside the block resolves as
`self.tool`. Python has no equivalent to `instance_eval` — there's no way
to make a bare `tool(...)` call inside a function silently resolve against
an arbitrary receiver. The Pythonic equivalent is an explicit `configure`
callable: `boukensha.run()` invokes it as `configure(dsl)`, and the caller
writes `dsl.tool(...)` instead of a bare `tool`. This preserves the design
intent exactly — a single, narrow method surface for registering tools —
only the syntax for reaching that surface changes.

### `boukensha.run()`

Accepts keyword arguments that describe *what* to do. All plumbing is
handled internally.

| Option | Default | Description |
|---|---|---|
| `task` | *(required)* | The user message handed to the agent |
| `system` | task's configured/default system prompt | System prompt |
| `model` | task's configured model | Model name |
| `backend` | task's configured provider | `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, or `"ollama_cloud"` |
| `api_key` | matching `*_API_KEY` env var | API key for the chosen backend |
| `ollama_host` | `"http://localhost:11434"` | Ollama base URL |
| `log` | `None` | Optional path override; by default logs go to `.boukensha/sessions/<session-id>.jsonl` |
| `max_output_tokens` | task's configured value (`1024` by default) | Max tokens per API response |
| `configure` | `None` | Callable invoked as `configure(dsl)` to register tools via `dsl.tool(...)` |

## Before and after

**Step 6 — manual plumbing:**

```python
config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)
ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)
backend = backends.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=Player.model(player_settings))
builder = PromptBuilder(ctx, backend)
client = Client(builder)
logger = Logger()
agent = Agent(context=ctx, registry=registry, builder=builder, client=client,
              logger=logger, task_settings=player_settings)

registry.tool(
    "read_file", description="Read a file",
    parameters={"path": {"type": "string"}},
    block=lambda path: Path(path).read_text(),
)

ctx.add_message("user", "Read lib/boukensha.rb")
agent.run()
```

**Step 7 — just describe what you want:**

```python
def configure(dsl):
    dsl.tool(
        "read_file", description="Read a file",
        parameters={"path": {"type": "string"}},
        block=lambda path: Path(path).read_text(),
    )

result = boukensha.run(task="Read lib/boukensha.rb", configure=configure)
```

## Run Example

```sh
./week1_baseline/bin/python/07_the_run_dsl
```

The example registers two tools (`read_file`, `list_directory`) and asks
the agent to list the directory then read `README.md`. `Logger` is a file
logger, not display output — it writes a session JSONL file under
`.boukensha/sessions`.
