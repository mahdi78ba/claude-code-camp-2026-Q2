# 00 · Configuration (Python port)

Python port of `week1_baseline/ruby/00_config`. All configuration is managed
from an external directory (`~/.boukensha/` by default), loaded by a dedicated
`boukensha.Config` class. Defaults may be hardcoded; configurable values are
not.

Configuration is organised by **task** — a role in the agentic loop bound to
its own LLM. week1_baseline only drives a single `player` task (the main loop);
a more advanced loop will assign different LLMs to different tasks.

## Design considerations

Prefer the standard library. The only two dependencies are the config parser
and dotenv (Python has no YAML in the stdlib, unlike Ruby), pinned in
`requirements.txt` the same way the Ruby reference pins `dotenv` in its
`Gemfile.lock`:

- `PyYAML` — parse `settings.yaml`
- `python-dotenv` — load `.env` credentials

The "from scratch" rule is about the **agent loop** (no Agent SDK), not about
avoiding small utility libraries — the Ruby reference likewise uses the
`dotenv` gem.

## Code layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `boukensha.Config` class |
| `boukensha/tasks/base.py` | abstract `Base` (provider/model + prompt resolution) |
| `boukensha/tasks/player.py` | concrete `Player` (the main loop) |
| `boukensha/__init__.py` | top-level exports |
| `prompts/system.md` | default system prompt shipped with the library |
| `examples/example.py` | runnable smoke-test |

## Config directory resolution

Looked up in this order:

1. **`BOUKENSHA_DIR` env var** — point it at any directory you like.
2. **`~/.boukensha`** — the default location for a real install.

The example sets `BOUKENSHA_DIR` to the repo-root `.boukensha/` so it runs
from a clean checkout.

## Config directory structure

```
.boukensha/
  .env                 # credentials, e.g. ANTHROPIC_API_KEY (never committed)
  settings.yaml        # all non-secret settings
  prompts/
    <task>/
      system.md        # per-task override for the default system prompt (optional)
```

## System prompt resolution

Per task, `Player.system_prompt` is resolved in this order:

1. **`.boukensha/prompts/<task>/system.md`** — used when the task's
   `prompt_override.system` is `true` and the file exists.
2. **`prompts/system.md`** — the default shipped with the library.

## Configuration schema

```yaml
tasks:
  player:
    provider: anthropic        # provider name (string)
    model: claude-haiku-4-5
    prompt_override:
      system: true
mud:
  host: localhost
  port: 4000
  username: dummy
  password: helloworld
```

## Run

```bash
./week1_baseline/python/bin/00_config
```

First run — set up the lesson-local virtualenv and your key:

```bash
cd week1_baseline/python/00_config
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# then paste your key into the repo-root .boukensha/.env:
#   ANTHROPIC_API_KEY=sk-ant-...
```

Expected output (values from your `.boukensha/`):

```
=== Boukensha Step 0: Configuration ===

Config dir:      /home/mahdi/claude-code-camp-2026-Q2/.boukensha
Tasks:           player

-- player task --
Provider:        anthropic
Model:           claude-haiku-4-5
Prompt override? True
System prompt:   You are a MUD player assistant. Use the tools available to y...

MUD host:        localhost:4000
MUD user:        dummy

API key set?     True

#<Boukensha::Config dir=/home/mahdi/claude-code-camp-2026-Q2/.boukensha tasks=player>
```
