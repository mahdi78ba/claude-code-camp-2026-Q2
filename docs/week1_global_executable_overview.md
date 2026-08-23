# `09_global_executable` — Packaging `boukensha` as a Gem Overview

## 1. Simple explanation

Every earlier step is run with `bundle exec ruby examples/example.rb` from
inside its own numbered folder. `09_global_executable` packages the whole
framework as a real RubyGem, `boukensha`, so that once it's installed the
`boukensha` command works **from any directory**, with no `cd` into a
lesson folder and no `bundle exec` required.

```bash
cd 09_global_executable
gem build boukensha.gemspec        # → boukensha-0.9.0.gem
gem install boukensha-0.9.0.gem    # installs the `boukensha` executable + its deps
boukensha                          # works from anywhere on $PATH
```

The gem doesn't copy or symlink the numbered step folders — it ships one
snapshot of the lib as its bundled default and can be told, via an
environment variable or a dotfile, to load a *different* step's lib
instead. Teaching material and packaging are kept deliberately separate.

## 2. Technical explanation

### `boukensha.gemspec`

Declares the gem: name (`boukensha`), version (from
`lib/boukensha/version.rb`, currently `0.9.0`), the files to ship
(`Dir["lib/**/*.rb"] + ["bin/boukensha"]`), and the executable
(`spec.executables = ["boukensha"]`, resolved via `spec.bindir = "bin"`).
It also now declares `spec.add_dependency "dotenv", "~> 3.2"` — see §3,
this was missing and broke the standalone install.

### `bin/boukensha`

The shebang script RubyGems turns into the global `boukensha` command:

```ruby
#!/usr/bin/env ruby
$LOAD_PATH.unshift File.expand_path("../lib", __dir__)
require "boukensha_loader"
BoukenshaLoader.load_and_start_repl
```

Four lines: put this gem's own `lib/` on the load path, require the
loader, and hand off. All of the actual "which step, from where" logic
lives in `boukensha_loader.rb`, not here.

### `lib/boukensha_loader.rb` — the resolution chain

`BoukenshaLoader.resolve` picks which `lib/boukensha.rb` to `require`, in
priority order:

1. **`BOUKENSHA_PATH` env var** — `boukensha` looks for
   `$BOUKENSHA_PATH/lib/boukensha.rb`. If the var is set but that file
   doesn't exist, `resolve` `abort`s with a message telling the user what
   a valid step folder looks like.
2. **`~/.boukensharc`** — a plain-text file containing one path, checked
   the same way, for a *permanent* default without exporting an env var
   every session.
3. **The bundled default** — `BUNDLED_LIB`, i.e. this gem's own
   `lib/boukensha.rb` (a snapshot of step 8's lib — see §3).

`load_and_start_repl` then requires whichever `main` was resolved and
calls `Boukensha.repl`. If the resolved step doesn't define `.repl` (true
for any step before `08_the_repl_loop`, which is where the REPL was
added), it `abort`s with a message pointing the user at
`examples/*.rb` instead of crashing on a `NoMethodError`.

This is deliberately independent from `BOUKENSHA_DIR` (`Boukensha::Config`,
step 0 onward), which resolves the **config** directory
(`settings.yaml`/`.env`/`prompts/`) — `BOUKENSHA_PATH` selects *code*,
`BOUKENSHA_DIR` selects *config*. The two can point anywhere independently,
e.g. running step 4's code against the same shared `~/.boukensha`
everything else uses.

### The bundled `lib/`

`lib/boukensha.rb` + `lib/boukensha/*` is a full copy of the framework —
not a reference to the numbered folders, an actual independent snapshot,
so the gem still works if the numbered lesson folders are deleted. The
README states this is "step 8's lib" (`08_the_repl_loop`, the newest
step with a working `.repl`), which matches: the bundled copy has the
same file set and, once patched (see §3), the same behavior as
`08_the_repl_loop`.

## 3. Objective assessment

**What it adds:** a real install/uninstall story and a way to pin a
specific lesson step's code (`BOUKENSHA_PATH`) independently of which
`.boukensha` config directory is in use (`BOUKENSHA_DIR`) — genuinely new
capability, no changes to the agent loop / backends / prompt logic itself.

**What it cost, before review — the bundled `lib/` was stale:** because
this folder's `lib/` is its own snapshot rather than a literal copy of
`08_the_repl_loop`'s already-reviewed folder, it had drifted out of sync
with that step's fixes. Confirmed by diffing against `08_the_repl_loop`
and fixed (see `docs/week1_config_troubleshooting.md` entry #27 for the
full list):
- `PROMPTS_DIR` was `../../../prompts` (one level too high — resolves
  outside the project, doesn't exist). `Tasks::Base` swallows a missing
  prompt file silently (`File.exist?` → `nil`, no error), so the bundled
  default's REPL was booting with **no system prompt at all** and no
  visible symptom.
- `Config#resolve_dir` was missing `08`'s cwd `.boukensha` tier.
- `Logger#provider_name` was missing the OpenAI special case (would log
  `"open_ai"` instead of `"openai"`, breaking cost-estimation lookups
  keyed on the `"openai"` string).
- `Client#call` was missing the 401-specific `ApiError` message.
- `Repl#banner` was missing the API-key/config-exists status line.

**A genuinely new bug, unique to this step:** `boukensha.gemspec` declared
no runtime dependency on `dotenv`, despite `lib/boukensha/config.rb`
requiring it unconditionally and the gemspec's own comment claiming "no
external dependencies." This one is invisible under `bundle exec` (the
`Gemfile` installs `dotenv` regardless of what the gemspec says) and only
surfaces once the gem is built and installed on its own — exactly the
scenario the README's Install section walks through. Fixed by adding
`spec.add_dependency "dotenv", "~> 3.2"`.

**Documentation drift:** the README and `boukensha_loader.rb`'s own abort
messages hardcoded step numbers from before `06_the_logger` was inserted
into the curriculum — e.g. pointing users at a nonexistent
`07_the_repl_loop` folder and calling this step "Step 8" while building
`boukensha-0.1.0.gem` as the install example. Corrected throughout to the
current numbering (companion doc:
[`week1_global_executable_review.md`](week1_global_executable_review.md)
covers `boukensha_loader.rb` specifically).

**Verified behavior** (`./bin/ruby/09_global_executable`, live Anthropic
call, piped stdin):
- Banner: `v0.9.0`, correct `.boukensha` config dir, `anthropic
  (claude-haiku-4-5)`, `✓ API key set`.
- The bundled `prompts/system.md` is now actually loaded — the reply
  self-identifies as "Boukensha, an autonomous player exploring a
  CircleMUD world," confirming the `PROMPTS_DIR` fix (previously this
  would have been silently `nil`).
- `/exit` prints `Goodbye.` and exits cleanly.

**Verified as an actual global install** (the point of this whole step):
`gem build boukensha.gemspec` → `boukensha-0.9.0.gem` → `gem install
./boukensha-0.9.0.gem` into an empty, bundler-free `GEM_HOME` pulled in
`dotenv` automatically, and running `boukensha` from an unrelated
directory (`/tmp`) with only `BOUKENSHA_DIR` set completed a real, live
turn against `claude-haiku-4-5`. Also confirmed `BOUKENSHA_PATH=.../
07_the_run_dsl boukensha` correctly aborts with the "doesn't support the
interactive REPL (added in step 8)" message (now pointing at the right
step number) rather than crashing, and `BOUKENSHA_DEBUG=1` prints the
`[boukensha] loading from: ...` trace line — both through the installed
gem, not `bundle exec`.
