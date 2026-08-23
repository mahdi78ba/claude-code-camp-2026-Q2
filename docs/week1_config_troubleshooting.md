# Week 1 Troubleshooting Log — `bin/00_config`

Living log: every problem hit while getting `bin/00_config` (and its Ruby
example) working, with the fix and the reason, kept short. Updated as new
issues come up — no need to ask.

Format per entry: **Problem → Fix → Why / retain.**

---

### 1. `env: 'bash\r': No such file or directory`

**Problem:** `bin/00_config` had Windows CRLF line endings. The shebang
line was actually `#!/usr/bin/env bash\r`, so the kernel looked for an
interpreter literally named `bash\r`.

**Fix:** `sed -i 's/\r$//' bin/00_config`

**Why / retain:** The kernel parses shebang lines byte-for-byte — a
trailing `\r` isn't treated as whitespace, it's part of the interpreter
name. Any `env: 'X\r': No such file` error = CRLF, not a missing tool.
Comes from editing/checking out a script on Windows.

---

### 2. `cd: ./bin/../ruby/00_config: No such file or directory`

**Problem:** Script did `cd "$(dirname "$0")/../ruby/00_config"`, but the
Ruby project actually lives one level deeper, at
`week1_baseline/ruby/00_config`.

**Fix:** Corrected the path to
`cd "$(dirname "$0")/../week1_baseline/ruby/00_config"`.

**Why / retain:** `dirname "$0"` only makes the *base* of a path
invocation-independent — the relative path appended after it still has to
be hand-verified against the real directory tree (`ls`), it's not
self-checking.

---

### 3. `bundle: command not found` (no Ruby/Bundler on host)

**Problem:** Neither `ruby`, `gem`, nor `bundle` were installed.
`sudo apt-get install ruby-full build-essential` failed:
`sudo: a terminal is required to read the password` — this session's shell
has no TTY, so `sudo` can't prompt. Tried `rbenv` (no-root Ruby installer)
as a workaround, but `rbenv`/`ruby-build` compiles Ruby from source and
there's no C compiler on the box either (`gcc` not installed) — installing
one hits the same broken `sudo`. No `conda`/`brew`/`asdf` available either.

**Fix:** Rewrote `bin/00_config` to run Ruby entirely inside Docker
(Docker Desktop was already reachable from this session):
```bash
docker run --rm \
  -v "$REPO_ROOT:/app" \
  -v boukensha_ruby_bundle:/usr/local/bundle \
  -w "/app/$APP_DIR" \
  ruby:3.3 \
  bash -c "bundle install --quiet && bundle exec ruby examples/example.rb"
```

**Why / retain:**
- Docker needs no root and no compiler — the image ships a prebuilt Ruby.
- `-v "$REPO_ROOT:/app"` mounts the *whole repo*, not just the Ruby
  subfolder, because `example.rb` resolves `.boukensha/` relative to its
  own location and expects the repo root to be present too.
- `-v boukensha_ruby_bundle:/usr/local/bundle` is a **named volume** — it
  survives `--rm` (only the container is disposable, not the volume), so
  `bundle install` isn't repeated from scratch every run.
- This made `bundle` work *inside the container only* — running `bundle`
  directly at the host shell prompt still fails, correctly, because Ruby
  was never installed on the host. That's not a bug, it's the design
  (see #4).

---

### 4. `NoMethodError: undefined method '[]' for nil` in `Boukensha::Tasks::Base#provider`

**Problem:** Real bug in committed code, not infra. `example.rb` computed:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)
```
using 3 `../` from `.../week1_baseline/ruby/00_config/examples`, landing on
`week1_baseline/.boukensha` (doesn't exist) instead of the real
`<repo-root>/.boukensha`. `settings.yaml` came back empty → `tasks(:player)`
returned `nil` → `.fetch` on `nil` crashed.

**Fix:** Added the missing `../` level:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
```

**Why / retain:** `File.expand_path(relative, base)` is purely lexical —
wrong `../` counts don't error, they just silently produce a different
valid-looking path. When a hash/method blows up on `nil`, trace back to
where the value *should* have been populated, not just where it exploded.

**Verified, both ways:**

Via Docker (`./bin/00_config`):
```
Config dir:     /app/.boukensha
```
Via native Ruby, run directly from `week1_baseline/ruby/00_config`:
```
Config dir:     /home/mahdi/claude-code-camp-2026-Q2/.boukensha
```

These look like different paths but are **the same directory** — `/app` is
only a name that exists *inside the container*. `bin/00_config` bind-mounts
the repo with `-v "$REPO_ROOT:/app"` (see the Docker breakdown further
below), so `/app` inside the container and
`/home/mahdi/claude-code-camp-2026-Q2` on the real disk point at identical
files. Whichever way you run it, `Config dir` correctly lands on
`<repository-root>/.boukensha` — confirming the fixed `../` count is
right, not just "a" valid-looking path.

This is specifically an **override for the example script**. The class
default (`Boukensha::Config::DEFAULT_DIR`, in
`lib/boukensha/config.rb`) is `~/.boukensha` — that's what a real user gets
automatically, with no `BOUKENSHA_DIR` env var involved at all. `example.rb`
only sets `BOUKENSHA_DIR` (via `||=`, so it never clobbers an env var you
already set yourself) so the smoke-test example can find *this repo's*
sample config without you needing a `~/.boukensha` to exist on your machine
just to try the example out.

---

### 5. `bundle: command not found` at the **host** shell (separate from #3)

**Problem:** After #3 was fixed via Docker, running `bundle install`
directly at the host terminal (outside Docker) still says not found —
apt's command-not-found hook even suggests `sudo apt install ruby-bundler`.
This is expected, not a regression: Ruby/Bundler were deliberately never
installed on the host, only inside the container (#3).

**Fix:** the apt package name for Bundler on Ubuntu/Debian is
`ruby-bundler`, **not** `bundler` (that name doesn't exist as an apt
package — `bundler` is only a *gem* name). Correct command, run in a real
terminal (not the Claude Code shell, which has no TTY for `sudo`):
```
sudo apt update && sudo apt install -y ruby-full ruby-bundler
```
Confirmed installed:
```
ruby 3.2.3
RubyGems 3.4.20
Bundler 2.4.20
```

**Why / retain:** apt package names don't always match the gem/library
name — when `apt install <name>` fails, check what the tool actually
distributes it as (here, `command-not-found`'s own suggestion had the
answer).

---

### 6. Native `bundle install` → `Bundler::PermissionError` writing to `/var/lib/gems/...`

**Problem:** With Ruby/Bundler now installed via apt, `bundle install`
inside `week1_baseline/ruby/00_config` failed two ways in sequence:
1. `Gemfile.lock` says `BUNDLED WITH 4.0.10`, but apt only installed
   Bundler 2.4.20. Bundler tried to auto-install version 4.0.10 for
   itself to match the lockfile.
2. That auto-install attempt crashed with
   `Bundler::PermissionError: ... /var/lib/gems/3.2.0/cache ... need to
   grant write permissions`.

**Fix:** two commands, run once per project:
```bash
cd week1_baseline/ruby/00_config
bundle config set --local path 'vendor/bundle'   # install gems into ./vendor/bundle, not system-wide
bundle _2.4.20_ install                          # force the installed Bundler version, skip the 4.0.10 auto-switch
```
After that, plain `bundle install` / `bundle exec ruby examples/example.rb`
work normally (the `--local path` config is remembered in
`.bundle/config`). Added `.bundle/` and `vendor/bundle/` to `.gitignore` —
they're machine-local installs, not something to commit.

**Why / retain:** apt's `ruby-full` installs gems into a **system-wide**
directory (`/var/lib/gems/...`) owned by root — a deliberate Debian/Ubuntu
choice so all users on a shared machine get the same gems. That's the
opposite of how version managers like `rbenv`/`rvm` work (per-user
directories, writable by default). Two independent consequences of that
one design choice:
- Installing/updating *any* gem system-wide needs `sudo` — so
  `bundle config set --local path 'vendor/bundle'` opts this one project
  into a local, per-project, no-sudo-needed install instead (same idea as
  Node's `node_modules` — self-contained, doesn't touch anything global).
- Bundler auto-installing a *different Bundler version* to satisfy the
  lockfile is itself a gem install — same permission wall. Pinning to the
  already-installed version with `bundle _2.4.20_ install` sidesteps that
  entirely rather than fighting for permission to install 4.0.10.

---

## Docker vs. native Ruby — what each piece in `bin/00_config` means, and why Docker first

**What `docker run` is actually doing, piece by piece:**

```bash
docker run --rm \                                    # (a)
  -v "$REPO_ROOT:/app" \                              # (b)
  -v boukensha_ruby_bundle:/usr/local/bundle \        # (c)
  -w "/app/$APP_DIR" \                                # (d)
  ruby:3.3 \                                          # (e)
  bash -c "bundle install --quiet && bundle exec ruby examples/example.rb"  # (f)
```

- **(a) `docker run --rm ruby:3.3 ...`** — start a brand-new, temporary Linux
  container **from the `ruby:3.3` image** (an official, pre-built image
  that already contains a full Ruby 3.3 install — interpreter, RubyGems,
  Bundler — nobody on this machine had to install or compile anything).
  `--rm` deletes the *container* the moment the command inside it exits —
  it's meant to be thrown away every run, like a disposable sandbox.
- **(b) `-v "$REPO_ROOT:/app"`** — a **bind mount**: makes the real
  `claude-code-camp-2026-Q2` folder on your WSL disk visible *inside* the
  container at the path `/app`. It's the same files, not a copy — edits
  either side are instantly visible on the other. Needed because
  `example.rb` expects to find `.boukensha/` up at the repo root, so the
  *whole* repo has to be visible, not just the Ruby subfolder.
- **(c) `-v boukensha_ruby_bundle:/usr/local/bundle`** — a **named volume**,
  which is different from (b): it's storage *managed by Docker itself*
  (not a folder you can browse directly in WSL), used here as the
  location where gems get installed inside the container
  (`/usr/local/bundle` is where the `ruby` image looks for gems by
  default). Because `--rm` only deletes the *container*, not volumes, this
  survives between runs — so gem installs aren't repeated from scratch
  every single time you run the script.
- **(d) `-w "/app/$APP_DIR"`** — sets the container's working directory to
  where the `Gemfile` lives, same purpose as `cd` in a normal script.
- **(e) `ruby:3.3`** — the image name. This one line is the *entire* Ruby
  install — no apt, no compiler, no version manager.
- **(f) the command that actually runs *inside* the container** — install
  gems, then run the example. Everything here happens in the
  container's filesystem/Ruby, completely separate from the host.

**Why Docker was reached for *first* (recap of the actual constraint, not
just a preference):** at that point in the session, `sudo apt-get install`
had no working password prompt (no TTY — #3 above), and the no-root
fallback (`rbenv`, which *compiles* Ruby) needed a C compiler that also
wasn't there and also needed the same broken `sudo` to install. Docker was
the only thing already present that could produce a working Ruby without
needing root access *at that moment*. It wasn't chosen for being
"better" — it was chosen for being unblocked.

**Now that native Ruby is installed** (via your own terminal, where `sudo`
does work — entries #5 and #6), both paths genuinely work:

| | Docker (`ruby:3.3` image) | Native (apt `ruby-full` + `ruby-bundler`) |
|---|---|---|
| Setup cost | ~1 min image pull, first run only | One `sudo apt install`, one `bundle config set --local path` |
| Version control | Exact (`ruby:3.3` pinned in the script) | Whatever apt ships (3.2.3 here) — drifts with OS upgrades |
| Isolation | Fully isolated; can't affect/be affected by host Ruby | Shares the host's Ruby install with anything else you run |
| Needs `sudo` | No, ever | Once, up front, to install the packages |
| Speed per run | Slightly slower (container start overhead) | Faster — no container layer |
| Editor tooling (Solargraph, Rubocop, IDE gem lookups) | Doesn't see the container's gems | Works normally — VS Code can find `ruby`/`bundle` directly |

Neither is objectively "the" right answer — Docker was this session's way
past a dead end, native is generally the more convenient default *once it's
actually installable*, especially for editor integration. `bin/00_config`
currently still uses Docker; switching it to native is a one-line-ish
change (drop the `docker run ...` wrapper, `cd` into `APP_DIR`, run
`bundle _2.4.20_ exec ruby examples/example.rb` directly) — not done yet,
pending your call on which one you want as the project's actual default.

---

## End state (as of entry #6)

Both paths verified working.

**Via Docker** (`./bin/00_config`):
```
Config dir:     /app/.boukensha
Tasks:          player
Provider:       anthropic
Model:          claude-haiku-4-5
API key set?    false   ← expected, .boukensha/.env has no key yet (gitignored)
```

**Native** (from `week1_baseline/ruby/00_config`, after entry #6's fix):
```
$ bundle _2.4.20_ exec ruby examples/example.rb
Config dir:     /home/mahdi/claude-code-camp-2026-Q2/.boukensha
Tasks:          player
...same output...
```

**Files changed so far:**
- `bin/00_config` — LF endings, corrected path, currently runs via Docker +
  cached bundle volume (native alternative available, see comparison
  above).
- `week1_baseline/ruby/00_config/examples/example.rb` — fixed `../` count.
- `.gitignore` — added `.bundle/` and `vendor/bundle/` (native gem install
  artifacts, machine-local, not committed).

---

## `01_struct_skeleton` — new runner at `week1_baseline/bin/ruby/01_struct_skeleton`

### 7. `Bundler::PermissionError` when installing `dotenv` for `01_struct_skeleton`

**Problem:** `01_struct_skeleton` has its own `Gemfile`/`Gemfile.lock`
(separate gem install from `00_config`'s), and hits the exact same wall as
entry #6: a plain `bundle install` tries to write to the system-wide
`/var/lib/gems/3.2.0/cache`.

**Fix:** same fix as #6, applied per-project again (bundle config is local
to each project's `.bundle/`, doesn't carry over from `00_config`):
```bash
cd week1_baseline/ruby/01_struct_skeleton
bundle config set --local path 'vendor/bundle'
bundle install
```
This time `bundle install` alone succeeded — no need for `bundle
_2.4.20_ install` version-pinning — because `--local path` was set *before*
the first `bundle install`, so even the auto-installed Bundler 4.0.10 (to
match `Gemfile.lock`'s `BUNDLED WITH`) landed in `./vendor/bundle` instead of
the root-owned system path.

**Why / retain:** `.bundle/config` is per-project, not global — every new
Ruby iteration under `ruby/<NN_name>/` needs this same one-time
`bundle config set --local path 'vendor/bundle'` before its first `bundle
install`. Setting it *before* installing (rather than after hitting the
permission error) avoids the error entirely, including for Bundler's own
self-install.

---

### 8. Same off-by-one `../` bug as entry #4, now in `01_struct_skeleton/examples/example.rb`

**Problem:** Running the new `week1_baseline/bin/ruby/01_struct_skeleton`
crashed identically to entry #4:
```
NoMethodError: undefined method `[]' for nil:NilClass
  from lib/boukensha/tasks/base.rb:39:in `fetch'
  from lib/boukensha/tasks/base.rb:17:in `prompt_override?'
  ...
  from examples/example.rb:6:in `<main>'
```
Root cause was the same class of bug as #4, in a different file:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)
```
Only 3 `../` from `.../week1_baseline/ruby/01_struct_skeleton/examples`
lands on `week1_baseline/.boukensha` (doesn't exist), instead of the real
`<repo-root>/.boukensha`.

**Fix:** added the missing `../` level, matching `00_config`'s (already
fixed) version:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
```
Confirmed working via `./bin/ruby/01_struct_skeleton`:
```
Config:   #<Boukensha::Config dir=/home/mahdi/claude-code-camp-2026-Q2/.boukensha tasks=player>
Context:  #<Context task=player turns=2 tools=1>
Tool:     #<Tool name=move description=Move the player in a direction (north, so params=[:direction]>
Messages:
  #<Message role=user content=Explore north and tell me what you find....>
  #<Message role=assistant content=Sure, let me head north and take a look....>
```

**Why / retain:** each iteration under `ruby/<NN_name>/` ships its **own
independent copy** of `examples/example.rb` — fixing this bug once in
`00_config` (entry #4) did not carry forward, because the file was copied
(not shared/required) into `01_struct_skeleton` before the fix landed there.
**When adding a runner for any new iteration, re-check its `example.rb`'s
`BOUKENSHA_DIR` `../` count against the actual folder depth** — don't assume
a fix made in an earlier iteration's copy is still present in a later one.
The correct count is always "however many directories separate
`examples/` from the repo root," which grows by one exactly when the
iteration folder itself is one level deep (it always is here, so the count
is constant at 4 for every `NN_name/examples/example.rb` in this repo) —
but verify per-file rather than assuming.

### 9. `.gitignore`'s `vendor/bundle/` rule didn't actually ignore any project's `vendor/bundle/`

**Problem:** After entry #7's install, `git status` still showed
`week1_baseline/ruby/01_struct_skeleton/vendor/` as untracked — and,
checking further, `week1_baseline/ruby/00_config/vendor/` had silently been
untracked the same way since entry #6, unnoticed. `git check-ignore -v` on
either path returned nothing — the existing `.gitignore` rule wasn't
matching at all:
```
vendor/bundle/
```

**Fix:** changed the rule to anchor at any depth:
```
**/vendor/bundle/
```
Confirmed both are now ignored:
```
$ git check-ignore -v week1_baseline/ruby/01_struct_skeleton/vendor/bundle
.gitignore:20:**/vendor/bundle/	week1_baseline/ruby/01_struct_skeleton/vendor/bundle
$ git check-ignore -v week1_baseline/ruby/00_config/vendor/bundle
.gitignore:20:**/vendor/bundle/	week1_baseline/ruby/00_config/vendor/bundle
```

**Why / retain:** per `gitignore(5)`, a pattern containing a slash **anywhere
except the very end** (`vendor/bundle/` has one between `vendor` and
`bundle`) is anchored to the directory holding the `.gitignore` file — it
only matches `<repo-root>/vendor/bundle/`, never a nested one like
`ruby/00_config/vendor/bundle/`. Only a pattern with **no** non-trailing
slash (like `.bundle/` on the line above it, which matched fine) — or an
explicit `**/` prefix — matches at every depth. A rule "working" for one
project's bundle install can still be silently failing for every other
project's, because each one nests one directory deeper than the repo root
where the untested assumption was formed. Re-verify gitignore rules with
`git check-ignore -v <path>` per project, don't assume one clean `git
status` generalizes.

**Files changed for this iteration:**
- `week1_baseline/bin/ruby/01_struct_skeleton` — new runner, `chmod u+x`.
- `week1_baseline/ruby/01_struct_skeleton/examples/example.rb` — fixed
  `../` count (entry #8).
- `week1_baseline/ruby/01_struct_skeleton/.bundle/config` — local bundle
  path (gitignored, entry #7).
- `week1_baseline/ruby/01_struct_skeleton/vendor/bundle/` — installed gems
  (gitignored, entries #7 and #9).
- `.gitignore` — fixed `vendor/bundle/` → `**/vendor/bundle/` so it actually
  ignores nested project vendor dirs, not just a hypothetical top-level one
  (entry #9). This also retroactively fixes the same latent miss for
  `00_config`.

---

## `02_the_registry` — new runner at `week1_baseline/bin/ruby/02_the_registry`

### 10. Same off-by-one `../` bug as entries #4/#8, now in `02_the_registry/examples/example.rb`

**Problem:** `02_the_registry` ships with only 3 `../` in its
`BOUKENSHA_DIR` line, the same mistake as `00_config` (entry #4) and
`01_struct_skeleton` (entry #8):
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)
```
`bundle exec ruby examples/example.rb` crashed identically:
```
NoMethodError: undefined method `[]' for nil:NilClass
  from lib/boukensha/tasks/base.rb:39:in `fetch'
  from lib/boukensha/tasks/base.rb:17:in `prompt_override?'
  ...
  from examples/example.rb:6:in `<main>'
```
A repo-wide grep shows every iteration from `02_the_registry` through
`08_the_repl_loop` still has the 3-`../` version — this bug is latent in
all of them, only `00_config` and `01_struct_skeleton` have been fixed so
far because those are the only ones exercised to date.

**Fix:** same one-line fix as before, add the missing `../`:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
```
Confirmed working via `./bin/ruby/02_the_registry`:
```
Config:  #<Boukensha::Config dir=/home/mahdi/claude-code-camp-2026-Q2/.boukensha tasks=player>
Context: #<Context task=player turns=0 tools=2>
Tools:
  #<Tool name=move ...>
  #<Tool name=shout ...>
Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED
Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.
UnknownToolError caught: No tool registered as 'flee'
```

**Why / retain:** confirms entry #8's rule — the fix does not propagate
across iterations because each `examples/example.rb` is an independent
copy, not shared code. **Before wiring up a runner for iterations 03–08,
expect and fix this same bug first** rather than rediscovering it each
time.

**Also needed (same as entry #7, applied fresh — bundle config is
per-project):**
```bash
cd week1_baseline/ruby/02_the_registry
bundle config set --local path 'vendor/bundle'
bundle install
```

**README discrepancies noticed while reviewing (not fixed — flagging for
awareness, not code bugs):**
- `## Expected Output` shows `Context: #<Context turns=0 tools=2
  budget=8192>`, but `Boukensha::Context#to_s` (unchanged since
  `01_struct_skeleton`) actually prints `task=player turns=0 tools=2` — no
  `budget` field exists yet. Real output is otherwise identical.
- `## Run Example` says `./week1_baseline/bin/01_the_registry` — wrong
  iteration number; the real path is `./week1_baseline/bin/ruby/02_the_registry`.

**Files changed for this iteration:**
- `week1_baseline/ruby/02_the_registry/examples/example.rb` — fixed `../`
  count (entry #10).
- `week1_baseline/bin/ruby/02_the_registry` — new runner, `chmod u+x`.
- `week1_baseline/ruby/02_the_registry/.bundle/config` — local bundle path
  (gitignored).
- `week1_baseline/ruby/02_the_registry/vendor/bundle/` — installed gems
  (gitignored).

---

## `03_prompt_builder` — new runner at `week1_baseline/bin/ruby/03_prompt_builder`

### 11. Same off-by-one `../` bug as entries #4/#8/#10, now in `03_prompt_builder/examples/example.rb`

**Problem:** Identical bug, third occurrence in a row. `03_prompt_builder`
shipped with only 3 `../`:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)
```
`bundle exec ruby examples/example.rb` crashed the same way:
```
NoMethodError: undefined method `[]' for nil:NilClass
  from lib/boukensha/tasks/base.rb:39:in `fetch'
  from lib/boukensha/tasks/base.rb:17:in `prompt_override?'
  from lib/boukensha/tasks/base.rb:24:in `prompt'
  from lib/boukensha/tasks/base.rb:32:in `system_prompt'
  from examples/example.rb:7:in `<main>'
```

**Fix:** same one-line fix, add the missing `../`:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
```
Confirmed working via `./bin/ruby/03_prompt_builder`, printing a full
Anthropic-shaped `to_api_payload` JSON body (`model`, `system`, `tools`,
`messages`).

**Also needed (same as entries #7/#10, per-project):**
```bash
cd week1_baseline/ruby/03_prompt_builder
bundle config set --local path 'vendor/bundle'
bundle install
```

**Why / retain:** third confirmation of entry #8's rule — every
`ruby/<NN_name>/examples/example.rb` is an independent copy with its own
un-fixed 3-`../` bug until touched. Entry #10 already predicted this exact
failure for iterations 03–08. **Before wiring up a runner for 04–08, expect
and fix this same bug first, don't rediscover it.**

**Files changed for this iteration:**
- `week1_baseline/ruby/03_prompt_builder/examples/example.rb` — fixed `../`
  count (entry #11).
- `week1_baseline/bin/ruby/03_prompt_builder` — new runner, `chmod u+x`.
- `week1_baseline/ruby/03_prompt_builder/.bundle/config` — local bundle path
  (gitignored).
- `week1_baseline/ruby/03_prompt_builder/vendor/bundle/` — installed gems
  (gitignored).

Code review (delegation to backends, per-backend model tables, and a real
interface bug found in `PromptBuilder#to_messages`) is in
[`week1_prompt_builder_review.md`](week1_prompt_builder_review.md).

---

## `04_api_client` — new runner at `week1_baseline/bin/ruby/04_api_client`

### 12. Same off-by-one `../` bug as entries #4/#8/#10/#11, now in `04_api_client/examples/example.rb`

**Problem:** Fourth occurrence in a row. `04_api_client` shipped with only
3 `../`:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)
```

**Fix:** same one-line fix, add the missing `../`:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
```

**Also needed (same as entries #7/#10/#11, per-project):**
```bash
cd week1_baseline/ruby/04_api_client
bundle config set --local path 'vendor/bundle'
bundle install
```

**Why / retain:** fourth confirmation of entry #8's rule. Iterations `05`–`08`
still have the unfixed 3-`../` version per the repo-wide grep in entry #10 —
expect and fix on sight when wiring up their runners.

---

### 13. A *second*, different off-by-one — this time in shipped library code, not an example script

**Problem:** `lib/boukensha/config.rb`'s `PROMPTS_DIR` constant:
```ruby
PROMPTS_DIR = File.expand_path("../../../prompts", __dir__).freeze
```
uses 3 `../` from `lib/boukensha/config.rb`. `03_prompt_builder`'s copy of
the same file (and the actual on-disk layout — `04_api_client/prompts/`
sits two levels up from `lib/boukensha/`, not three) uses the correct
`"../../prompts"`. Three `../` walks one level too far, out of the
iteration's own directory and into `ruby/prompts` — which doesn't exist.

**Why it didn't crash the smoke test:** `Tasks::Base.system_prompt` checks
`prompt_override?` first — this repo's `.boukensha/settings.yaml` has
`tasks.player.prompt_override.system: true`, and
`.boukensha/prompts/player/system.md` exists, so the user-prompt path
returns a string before `PROMPTS_DIR` (the broken default) is ever
consulted. `read_default_prompt` returns `nil` for a missing file rather
than raising, so a config *without* that override would get a silently
missing system prompt instead of a clear error — same failure shape as
entry #4, just reachable through a different code path this time.

**Fix:** one line, matching `03_prompt_builder`'s correct version:
```ruby
PROMPTS_DIR = File.expand_path("../../prompts", __dir__).freeze
```

**Why / retain:** the off-by-one `../`-count bug is a *class* of bug in this
codebase, not confined to `examples/example.rb` — it can appear in any
hand-written `File.expand_path("../..."​, __dir__)` line that got
copy-pasted across iterations. **Grep each new iteration's `lib/` (not just
its `examples/`) for `File.expand_path("../` before trusting a clean smoke
test** — a passing run only proves the code paths it happened to exercise,
not every path constant in the file.

Confirmed working via `./bin/ruby/04_api_client` — real, live POST to
`https://api.anthropic.com/v1/messages`, response came back
`stop_reason: "tool_use"` selecting `list_directory`, matching the README's
documented response shape.

**Files changed for this iteration:**
- `week1_baseline/ruby/04_api_client/examples/example.rb` — fixed `../`
  count (entry #12).
- `week1_baseline/ruby/04_api_client/lib/boukensha/config.rb` — fixed
  `PROMPTS_DIR`'s `../` count (entry #13).
- `week1_baseline/bin/ruby/04_api_client` — new runner, `chmod u+x`.
- `week1_baseline/ruby/04_api_client/.bundle/config` — local bundle path
  (gitignored).
- `week1_baseline/ruby/04_api_client/vendor/bundle/` — installed gems
  (gitignored).

Full code review (retry/error handling in `Client`, the new
`Backends::Base`/`Tasks::Base` model and prompt machinery, and re-verified
carry-forward findings from `03_prompt_builder`) is in
[`week1_api_client_review.md`](week1_api_client_review.md).

---

## `python/04_api_client` — Python port

### 14. `Config.mud_host`/`mud_port` returned the wrong value for a configured `0` or `""`

**Problem:** A real `code-review` pass (run against the staged Python port,
per [[feedback_port_review_rigor]]) flagged that
`python/04_api_client/boukensha/config.py` used Python's `or` for
defaulting:
```python
@property
def mud_port(self):
    return self.dig("mud", "port") or 4000
```
Ruby's equivalent, `dig(:mud, :port) || 4000`, only falls back when the
value is `nil`/`false` — `0` is truthy in Ruby and gets returned as-is. In
Python, `0` (and `""`) are falsy, so `self.dig(...) or 4000` silently
discards a legitimately-configured `mud.port: 0` (or `mud.host: ""`) and
returns the default instead. Not hit by the example script, since
`.boukensha/settings.yaml`'s `mud.port` is `4000` already (a value that
happens to equal the default, masking the bug either way).

**Fix:** switched both properties to explicit `is None` checks, matching
Ruby's actual falsy set:
```python
@property
def mud_port(self):
    value = self.dig("mud", "port")
    return 4000 if value is None else value
```
Confirmed interactively both ways: `{"mud": {"port": 0, "host": ""}}` now
returns `0`/`""` unchanged; no `mud` key still returns the correct
defaults (`4000`/`"localhost"`).

**Why / retain:** Python's `or`-for-defaulting is not a safe stand-in for
Ruby's `||` whenever the configured value could legitimately be `0`, `""`,
or an empty collection — Ruby's falsy set is `nil`/`false` only, Python's
is much bigger. This is a bug *class*, the same way the Ruby
`../`-count bugs were (entries #4/#8/#10/#11/#12/#13 above) — just
appearing on the Python side of the port instead. `backends/base.py`'s
`estimate_cost` already used explicit `is None` checks and got this right;
`config.py`'s `mud_host`/`mud_port` (carried over unchanged from
`02_the_registry`/`03_prompt_builder`) didn't, until this review. **Grep
for bare `... or <default>` reading `settings.yaml`-sourced values in any
future Python port** rather than assuming a passing smoke test proves
every defaulting branch is correct — the same "a clean run only proves the
paths it happened to exercise" lesson from entry #13, now confirmed on the
Python side too. The bug is not fixed in `02_the_registry`'s or
`03_prompt_builder`'s copies of `config.py` — only in `04_api_client`'s,
per "fix on sight in the copy under review," not retroactively.

Full code review (Client retry/backoff parity with `client.rb`, the
`urllib.error.HTTPError`-before-`URLError` catch-order requirement, and
this finding) is in
[`week1_api_client_python_review.md`](week1_api_client_python_review.md).

---

## `ruby/05_agent_loop`

### 15. Same off-by-one `../` bug as entries #4/#8/#10/#11/#12, now in `05_agent_loop/examples/example.rb`

**Problem:** Fifth occurrence in a row, exactly as entry #12 predicted.
`05_agent_loop` shipped with only 3 `../`:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)
```
This silently resolves to `week1_baseline/.boukensha` (doesn't exist), so
`Config#load_settings` finds no `settings.yaml`, `tasks(:player)` comes back
`nil`, and `Tasks::Base.provider` raises `ArgumentError: tasks.player.provider
is required in settings.yaml` — a clear error this time, not a silent one.

**Fix:** same one-line fix, add the missing `../`:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
```

**Also needed (same as entries #7/#10/#11/#12, per-project):**
```bash
cd week1_baseline/ruby/05_agent_loop
mkdir -p .bundle && printf -- '---\nBUNDLE_PATH: "vendor/bundle"\n' > .bundle/config
bundle install
```

**Why / retain:** fifth confirmation of entry #8's rule — every new
iteration's `examples/example.rb` ships with the same wrong `../` count and
needs the same fix. Iterations `06`–`08` should be assumed to have it too;
fix on sight when wiring up their runners.

---

### 16. Same `PROMPTS_DIR` off-by-one as entry #13, carried into `05_agent_loop/lib/boukensha/config.rb`

**Problem:** `05_agent_loop` copied `config.rb` forward with the same
uncorrected constant entry #13 found and fixed in `04_api_client`:
```ruby
PROMPTS_DIR = File.expand_path("../../../prompts", __dir__).freeze
```
Three `../` from `lib/boukensha/config.rb` walks out of `05_agent_loop`
entirely (into `ruby/prompts`, which doesn't exist) instead of landing on
`05_agent_loop/prompts/system.md`.

**Why it didn't crash the smoke test:** identical masking to entry #13 —
`.boukensha/settings.yaml` has `tasks.player.prompt_override.system: true`
and `.boukensha/prompts/player/system.md` exists, so `Tasks::Base.prompt`
returns the user-override text before `PROMPTS_DIR` (the broken default) is
ever consulted.

**Fix:** one line, matching `04_api_client`'s corrected version:
```ruby
PROMPTS_DIR = File.expand_path("../../prompts", __dir__).freeze
```
Confirmed via `bundle exec ruby -r./lib/boukensha -e '...'`:
`Boukensha::Config::PROMPTS_DIR` now points at
`05_agent_loop/prompts/system.md`, and the file exists there.

**Why / retain:** entry #13's warning holds — this bug travels with the
copy-pasted `config.rb`, not with any one iteration, and a clean example run
only proves the prompt-override branch, not the default-prompt branch.
**Check `PROMPTS_DIR` in every new iteration's `config.rb` even when the
example runs cleanly**, since `.boukensha/settings.yaml` always has the
override on and will keep masking this for iterations `06`+ too.

Confirmed working via `./week1_baseline/bin/ruby/05_agent_loop` — real, live
call to `https://api.anthropic.com/v1/messages` using `claude-haiku-4-5`,
one `tool_use` iteration (`read_file` on `README.md`) followed by
`end_turn`, matching the README's documented transcript shape.

**Files changed for this iteration:**
- `week1_baseline/ruby/05_agent_loop/examples/example.rb` — fixed `../`
  count (entry #15).
- `week1_baseline/ruby/05_agent_loop/lib/boukensha/config.rb` — fixed
  `PROMPTS_DIR`'s `../` count (entry #16).
- `week1_baseline/bin/ruby/05_agent_loop` — new runner, `chmod u+x`.
- `week1_baseline/ruby/05_agent_loop/.bundle/config` — local bundle path
  (gitignored).
- `week1_baseline/ruby/05_agent_loop/vendor/bundle/` — installed gems
  (gitignored).

---

## `python/05_agent_loop` — Python port

### 17. `Agent._call_opts` treated `max_output_tokens=0` as falsy — Python truthy-check bug, same class as entry #14

**Problem:** Ported from Ruby's `@max_output_tokens ? { max_output_tokens: @max_output_tokens } : {}`
as a literal truthy check:
```python
def _call_opts(self):
    return {"max_output_tokens": self._max_output_tokens} if self._max_output_tokens else {}
```
Ruby's `?:` truthy check only excludes `nil`/`false` — `0` is truthy in
Ruby and would be included. Python's truthy check excludes `0` too, so a
task configured with `max_output_tokens: 0` would silently fall back to
`Client`'s own default (`1024`) instead of actually sending `0`. Same bug
*class* as entry #14 (`mud_port`), caught this time during review, not by
the smoke test — the real `.boukensha/settings.yaml` uses `1024`, which is
truthy either way, so a passing live run would never have surfaced this.

**Fix:** explicit `is None` check, matching Ruby's actual falsy set:
```python
def _call_opts(self):
    if self._max_output_tokens is None:
        return {}
    return {"max_output_tokens": self._max_output_tokens}
```
Confirmed via an offline fake-client test harness (no live API needed) that
exercises the multi-tool-call loop, the `max_iterations` wind-down path
(`tools=[]` passed correctly), the `ApiError` → fallback-message path, and
`max_iterations=0` disabling the ceiling — none of which the live smoke
test alone would have exercised.

**Why / retain:** [[feedback_port_review_rigor]] in practice — a clean
live run only proves the one path it happened to exercise
(`max_output_tokens: 1024`, one tool call, one provider). **Write a small
offline test harness (fake client/builder) for any new stateful class like
`Agent`, covering the branches a single live smoke test can't reach**
(zero/falsy config values, the wind-down path, the error path) — this is
now the second time (`mud_port` in entry #14, `max_output_tokens` here) a
Python `or`/truthy-check stand-in for Ruby's narrower nil/false falsy set
has hidden a real bug from a passing smoke test.

### 18. `openai.py`/`gemini.py` `parse_response` normalized away a real asymmetry already present in the Ruby backends

**Problem:** `ollama.rb`/`ollama_cloud.rb` guard the text block with
`if message["content"] && !message["content"].empty?`, but `openai.rb`
only has `if message["content"]` (no `!empty?` guard) — since `""` is
truthy in Ruby, OpenAI's Ruby backend **does** emit a `{"type": "text",
"text": ""}` block for empty-string content, while Ollama's doesn't. Same
gap in `gemini.rb`: `elsif part["text"]` has no `!empty?` guard either. The
first draft of the Python port used a single truthy check
(`if message.get("content"):` / `elif part.get("text"):`) everywhere,
which silently erased this asymmetry — Python's `""` is falsy, so both
backends would have behaved like Ollama, not like their actual Ruby
counterparts.

**Fix:** `openai.py`/`gemini.py`'s `parse_response` use
`is not None` instead of a bare truthy check, so an empty string is
included (matching Ruby's `if message["content"]`/`elsif part["text"]`)
while `None`/missing is excluded — `ollama.py`/`ollama_cloud.py` correctly
keep their truthy check (Python's `if x:` on a string already matches
Ruby's `x && !x.empty?` exactly, no change needed there). Confirmed with an
offline test asserting `openai.parse_response` includes a `text: ""` block
that `ollama.parse_response` correctly omits for the identical input shape.

**Why / retain:** an inconsistency between two Ruby backends is not
automatically a bug to fix during a port — **the job is to port what Ruby
actually does, asymmetry included**, unless explicitly asked to fix it.
Reaching for one "obviously correct" Python idiom (a bare truthy check) for
all five backends at once erases a real, source-verified difference between
them. Diff each backend's actual guard condition individually rather than
assuming they're all the same shape.

**Files changed for this iteration:**
- `week1_baseline/python/05_agent_loop/boukensha/agent.py` — new file;
  fixed `_call_opts` truthy check (entry #17).
- `week1_baseline/python/05_agent_loop/boukensha/errors.py` — added
  `LoopError`.
- `week1_baseline/python/05_agent_loop/boukensha/__init__.py` — exports
  `Agent`, `LoopError`.
- `week1_baseline/python/05_agent_loop/boukensha/prompt_builder.py` —
  `to_api_payload` gained `tools=`; added `parse_response`.
- `week1_baseline/python/05_agent_loop/boukensha/client.py` — `call` gained
  `tools=`.
- `week1_baseline/python/05_agent_loop/boukensha/tasks/base.py` — added
  `max_iterations`/`max_output_tokens`/`_integer_setting`.
- `week1_baseline/python/05_agent_loop/boukensha/backends/*.py` — `tools=`
  on `to_payload`; `parse_response` on all five; `_assistant_message`/
  `_assistant_parts` on four of five; fixed the truthy-check asymmetry bug
  in `openai.py`/`gemini.py` (entry #18).
- `week1_baseline/python/05_agent_loop/examples/example.py` — rewritten to
  build and run an `Agent`.
- `week1_baseline/python/05_agent_loop/README.md` — rewritten for this
  step (the copy step had left `04_api_client`'s README in place).
- `week1_baseline/bin/python/05_agent_loop` — new runner.
- `week1_baseline/python/05_agent_loop/.venv/` — lesson-local virtualenv
  (gitignored).

Confirmed working via `./week1_baseline/bin/python/05_agent_loop` — real,
live call to `https://api.anthropic.com/v1/messages` using
`claude-haiku-4-5`, one `tool_use` iteration (`read_file` on `README.md`)
followed by `end_turn`, matching both the Ruby transcript shape and
`ruby/05_agent_loop`'s own verified run. Additionally verified offline
(no live API) with a fake-client test harness covering the multi-tool-call
loop, the `max_iterations` wind-down path, the `ApiError` fallback path,
and `max_iterations=0`, plus a second harness exercising each backend's
`parse_response`/`_assistant_message`/`_assistant_parts` round-trip
directly against representative raw provider payloads.

Full port plan is in
[`week1_agent_loop_port_plan.md`](week1_agent_loop_port_plan.md).

---

## `ruby/06_the_logger` — new runner at `week1_baseline/bin/ruby/06_the_logger`

### 19. Same off-by-one `../` bugs as entries #4/#8/#10/#11/#12/#15 and #13/#16, sixth occurrence of each

**Problem:** `06_the_logger` shipped with both known off-by-one mistakes,
copy-pasted forward unfixed from the original template:
```ruby
# examples/example.rb
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)

# lib/boukensha/config.rb
PROMPTS_DIR = File.expand_path("../../../prompts", __dir__).freeze
```

**Fix:** same two one-line fixes as every prior iteration:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
PROMPTS_DIR = File.expand_path("../../prompts", __dir__).freeze
```

**Also needed (per-project, same as every prior iteration):**
```bash
cd week1_baseline/ruby/06_the_logger
mkdir -p .bundle && printf -- '---\nBUNDLE_PATH: "vendor/bundle"\n' > .bundle/config
bundle install
```

**Why / retain:** sixth confirmation of entry #8's rule for `BOUKENSHA_DIR`
and third for `PROMPTS_DIR` (after #13, #16) — both bugs travel with the
copy-pasted template, not with any one iteration. Iterations `07`/`08`
should be assumed to have both; fix on sight when wiring up their runners.

### 20. `Logger#provider_name` mislabels the OpenAI backend as `"open_ai"` — real bug in the new logging code

**Problem:** `Logger#provider_name` derives the `provider` field written into
every `response` JSONL line from the backend's class name via a generic
CamelCase→snake_case gsub:
```ruby
backend.class.name.split("::").last.gsub(/([a-z\d])([A-Z])/, '\1_\2').downcase
```
This is correct for `Anthropic`, `Gemini`, `Ollama`, and `OllamaCloud`
(→ `anthropic`/`gemini`/`ollama`/`ollama_cloud`), but `Backends::OpenAI`'s
trailing acronym doesn't snake_case cleanly: the regex inserts an
underscore at every lowercase→uppercase boundary, including inside `AI`,
producing `"open_ai"`. Everywhere else in the codebase — `settings.yaml`,
`config.rb`'s provider `case` statement — the string is `"openai"` (no
underscore). Not caught by the smoke test, which only exercises the
Anthropic backend; found by explicitly instantiating all five backend
classes offline and comparing `provider_name` output against the string
each one is actually selected by in `config.rb`.

**Fix:** special-cased `Backends::OpenAI` ahead of the generic gsub:
```ruby
def provider_name(backend)
  return nil unless backend
  return "openai" if backend.is_a?(Backends::OpenAI)

  backend.class.name.split("::").last.gsub(/([a-z\d])([A-Z])/, '\1_\2').downcase
end
```
Confirmed offline (no live API) by instantiating one backend of each of the
five classes and asserting `provider_name` matches the provider string used
to select that class in `config.rb`.

**Why / retain:** a generic identifier-casing transform (CamelCase→
snake_case, plural→singular, etc.) is not safe to trust for every class
name in a codebase — acronym-bearing names (`OpenAI`, similarly `HTTPS`,
`ID`) are a known blind spot for that whole class of regex. This is data
correctness in the logging feature itself (this iteration's actual
deliverable), not an infra/path issue like entries #4–#18: anyone
filtering `.boukensha/sessions/*.jsonl` by `provider: "openai"` would
silently miss every OpenAI-backed session's `response` lines.

**Also noticed, not changed:** `Logger#close` is defined but never called
by `Agent` or `examples/example.rb` — harmless for this short-lived script
(the OS reclaims the file descriptor at process exit), but worth revisiting
once a longer-lived process (the REPL loop / TUI iterations) can create
many `Logger` instances in one run.

**`.gitignore` gap found and fixed:** this is the first iteration that
actually writes to `.boukensha/sessions/` (previous iterations' loggers
were never wired up to run). Nothing ignored it, so a live run left an
untracked `.boukensha/sessions/*.jsonl` file in `git status`. Added
`.boukensha/sessions/` to `.gitignore` — generated per-run output, not
project content, same reasoning as `**/vendor/bundle/` (entry #9).

**README discrepancy noticed, not fixed:** the README's Logger API table
documents `prompt(messages:, tools:, budget:)`, but the shipped
`Logger#prompt` (and its only call site, in `agent.rb`) takes just
`messages:` and `tools:` — no `budget:` parameter exists anywhere in this
step's code. Code and call site agree with each other, so this is a stale
doc claim, not a runtime bug — flagging for awareness only, per the same
policy as the `02_the_registry` README discrepancies above.

Confirmed working via `./week1_baseline/bin/ruby/06_the_logger` — real,
live call to `https://api.anthropic.com/v1/messages` using
`claude-haiku-4-5`; the resulting `.boukensha/sessions/<id>.jsonl` was
inspected line-by-line and matches the README's documented shape
(`session_start`, `iteration`, `prompt`, `tool_call`, `tool_result`,
`response` with `cost_usd`, `turn_end`).

**Files changed for this iteration:**
- `week1_baseline/ruby/06_the_logger/examples/example.rb` — fixed
  `BOUKENSHA_DIR` `../` count (entry #19).
- `week1_baseline/ruby/06_the_logger/lib/boukensha/config.rb` — fixed
  `PROMPTS_DIR`'s `../` count (entry #19).
- `week1_baseline/ruby/06_the_logger/lib/boukensha/logger.rb` — fixed
  `provider_name`'s OpenAI mislabeling (entry #20).
- `week1_baseline/bin/ruby/06_the_logger` — new runner, `chmod u+x`.
- `week1_baseline/ruby/06_the_logger/.bundle/config` — local bundle path
  (gitignored).
- `week1_baseline/ruby/06_the_logger/vendor/bundle/` — installed gems
  (gitignored).
- `.gitignore` — added `.boukensha/sessions/`.

---

## `ruby/log_viz` — viewing the 06_the_logger sessions

### 21. `bundle install` fails: `nio4r` native extension can't compile (no C compiler, no usable `sudo`/Docker)

**Problem:** `log_viz`'s `Gemfile` depends on `puma`, which depends on
`nio4r` — a native (C extension) gem. `bundle install` failed at the
`extconf.rb`/`mkmf` step:
```
checking for unistd.h... *** extconf.rb failed ***
...
The compiler failed to generate an executable file.
You have to install development tools first.
```
This session has neither `gcc` nor working `sudo` (`sudo -n true` →
`sudo: a password is required`, same TTY-less constraint as entry #3), and
the Docker workaround used for that entry isn't available here either —
`docker` resolves to the Windows-side binary but WSL integration isn't
active for this distro (`could not be found in this WSL 2 distro`).

**Fix:** swapped `puma` for `webrick` in the `Gemfile` — pure Ruby, no
native extension, and already present as a Ruby-bundled default gem:
```diff
 gem "sinatra"
 gem "rackup"
-gem "puma"
+gem "webrick"
```
Removed the stale `vendor/bundle/` from the failed puma install and reran
`bundle install`; it installed cleanly with `webrick` in place of
`puma`/`nio4r`. Sinatra's `App.run!` auto-picks whichever Rack handler is
available, so no code change was needed beyond the `Gemfile` — starting
`bin/log_viz` shows `Sinatra ... has taken the stage on 4567 ... with
backup from WEBrick`.

**Why / retain:** same lesson as entry #3, one level more specific — a
missing compiler doesn't just block gems that need `sudo` to install
system-wide, it blocks *any* native-extension gem regardless of install
location (`vendor/bundle` included), and the right fix is usually a
pure-Ruby alternative dependency, not fighting for compiler access. Prefer
`webrick` over `puma` for any future small Sinatra/Rack tool in this repo
under the same host constraints — it's slower under real concurrent load
but that doesn't matter for a local, single-viewer log browser.

### 22. Same off-by-one `../` bug as entries #4/#8/#10/#11/#12/#15/#19, now in `log_viz`'s default `sessions_dir`

**Problem:** `lib/log_viz/app.rb` computes its default log directory the
same way every `example.rb`/`config.rb` in this repo has:
```ruby
set :sessions_dir, ENV.fetch("LOG_VIZ_SESSIONS_DIR") {
  File.expand_path("../../../../.boukensha/sessions", __dir__)
}
```
4 `../` from `.../ruby/log_viz/lib/log_viz` lands on
`week1_baseline/.boukensha/sessions` (doesn't exist — one directory
shallower than `log_viz` itself, since `log_viz` sits at
`ruby/log_viz/`, the same depth as each `ruby/<NN_name>/`). Visiting `/`
after starting the server confirmed it silently: "No session logs found in
`.../week1_baseline/.boukensha/sessions`" — no crash, just an empty list,
the same *silent* failure shape as entry #4's original discovery (missing
file → nil/empty, not an exception).

**Fix:** added the missing `../` level, matching every other fixed
instance of this bug in the repo:
```ruby
File.expand_path("../../../../../.boukensha/sessions", __dir__)
```
Restarted the server; `/` now lists the real sessions from
`<repo-root>/.boukensha/sessions`, and `/sessions/:id` renders a full
transcript (user/assistant messages, provider/model, token counts,
`cost ≈ $0.0041`) for the `06_the_logger` session generated earlier.

**Why / retain:** seventh confirmation of entry #8's rule, and the first
time this exact bug class has shown up outside `examples/example.rb` or
`config.rb` — **any `File.expand_path("../...", __dir__)` default-path
constant anywhere in this repo is a candidate for this bug**, not just the
two files it's been found in six times before. Grep for the pattern in any
new tool before trusting its "no results" output at face value.

Confirmed working: started `bundle exec ruby bin/log_viz` (WEBrick on
`:4567`, bound to `localhost`), `curl`'d both `/` (session list, showing
start time/session id/task/model/iterations/tokens/cost) and
`/sessions/<id>` (full transcript with the real messages and computed
cost) — both returned HTTP 200 with the expected content. Left the server
running in the background for interactive viewing at
<http://localhost:4567> (WSL2 forwards `localhost` to the Windows host
automatically, so this is reachable from a Windows browser without extra
setup).

**Files changed:**
- `week1_baseline/ruby/log_viz/Gemfile` — `puma` → `webrick` (entry #21).
- `week1_baseline/ruby/log_viz/Gemfile.lock` — regenerated for the new
  dependency set.
- `week1_baseline/ruby/log_viz/lib/log_viz/app.rb` — fixed
  `sessions_dir`'s default `../` count (entry #22).
- `week1_baseline/ruby/log_viz/.bundle/config` — local bundle path
  (gitignored).
- `week1_baseline/ruby/log_viz/vendor/bundle/` — installed gems
  (gitignored).

---

## `ruby/07_the_run_dsl` — new runner at `week1_baseline/bin/ruby/07_the_run_dsl`

### 23. Same three known bugs as entries #4–#22, all three inherited unfixed into `07_the_run_dsl`

**Problem:** `07_the_run_dsl` copied all three previously-identified
template bugs forward, unfixed:
```ruby
# examples/example.rb
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)

# lib/boukensha/config.rb
PROMPTS_DIR = File.expand_path("../../../prompts", __dir__).freeze

# lib/boukensha/logger.rb
def provider_name(backend)
  return nil unless backend

  backend.class.name.split("::").last.gsub(/([a-z\d])([A-Z])/, '\1_\2').downcase
end
```

**Fix:** same three one-line fixes as `06_the_logger` (entries #19, #20):
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
PROMPTS_DIR = File.expand_path("../../prompts", __dir__).freeze
```
```ruby
def provider_name(backend)
  return nil unless backend
  return "openai" if backend.is_a?(Backends::OpenAI)

  backend.class.name.split("::").last.gsub(/([a-z\d])([A-Z])/, '\1_\2').downcase
end
```

**Also needed (per-project, same as every prior iteration):** copied
`06_the_logger`'s already-installed `.bundle/config` and `vendor/bundle/`
wholesale (identical `Gemfile`/`Gemfile.lock` between the two steps), then
confirmed with `bundle check` instead of re-running `bundle install` —
saved a redundant install since nothing in the dependency set changed
between these two consecutive iterations.

**Why / retain:** seventh confirmation of entry #8's `BOUKENSHA_DIR` rule,
fourth of entry #13's `PROMPTS_DIR` rule, second of entry #20's
`provider_name` rule — all three bugs travel with the copy-pasted
template, unmodified, into every new iteration until each one is
individually reviewed and fixed. **Never assume a new iteration is
bug-free just because an earlier sibling already got the fix** — diff the
specific known-bad lines against the new copy on sight, same as before.

Confirmed working via `./week1_baseline/bin/ruby/07_the_run_dsl` — real,
live call to `https://api.anthropic.com/v1/messages` using
`claude-haiku-4-5` through the new `Boukensha.run` DSL entry point (no
manual `Context`/`Registry`/`Client`/`Logger` wiring in the example
script); the resulting `.boukensha/sessions/<id>.jsonl` was inspected
line-by-line and shows a correct `provider: "anthropic"` tag plus a
`read_file` `tool_call`/`tool_result` pair, matching the README's
documented flow.

**Files changed for this iteration:**
- `week1_baseline/ruby/07_the_run_dsl/examples/example.rb` — fixed
  `BOUKENSHA_DIR` `../` count.
- `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/config.rb` — fixed
  `PROMPTS_DIR`'s `../` count.
- `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/logger.rb` — fixed
  `provider_name`'s OpenAI mislabeling.
- `week1_baseline/bin/ruby/07_the_run_dsl` — new runner, `chmod u+x`.
- `week1_baseline/ruby/07_the_run_dsl/.bundle/config` — local bundle path
  (gitignored).
- `week1_baseline/ruby/07_the_run_dsl/vendor/bundle/` — installed gems,
  copied from `06_the_logger`'s identical lockfile (gitignored).

---

## `python/07_the_run_dsl` — Python port

### 24. No new bugs — port executed per plan, including two reversed "drop" recommendations from `06_the_logger`'s plan

**Problem:** N/A — this entry records a clean port, not a bug fix, per
[[feedback_port_review_rigor]] (later ports need a real review, not just a
smoke test note). The full reasoning lives in
`docs/plans/python_port/07_the_run_dsl.md`; this is the short version.

**What was ported:**
- New `boukensha/run_dsl.py` (`RunDSL`, exposing only `tool`) and a new
  `boukensha.run()` function in `__init__.py`, composing the existing
  `Context`/`Registry`/`Backend`/`PromptBuilder`/`Client`/`Logger`/`Agent`
  classes — none of which needed any change themselves.
- Every Ruby `||=` in `Boukensha.run` was translated to an explicit
  `is None` check, **not** Python's `or`, to avoid the same 0-is-falsy bug
  class as entries #14/#17/#18. Verified directly: monkeypatched the
  backend/client so no live API call was needed, called
  `boukensha.run(task=..., max_output_tokens=0, ...)`, and asserted the
  `session_start` log line records `max_output_tokens: 0`, not the task's
  configured default (`1024`). A live smoke test alone — which only ever
  exercises the real, truthy, configured value — could never have caught
  a regression here.
- Ruby's `instance_eval`-based block DSL (bare `tool` calls resolving
  against an implicit receiver) has no Python equivalent. Translated to an
  explicit `configure(dsl)` callback where the caller writes
  `dsl.tool(...)` — a language-level adaptation, not a literal
  translation, but the same design intent (narrow, single-method tool
  registration surface, no access to internals).
- Re-added `mud_host`/`mud_port`/`mud_username`/`mud_password` to
  `config.py` and `LoopError` to `errors.py`/`__all__` — both had been
  *deliberately dropped* from Python (and from Ruby) during the
  `06_the_logger` port, per that port's own plan (§"Judgment calls"),
  specifically because Ruby had dropped them in that snapshot. Ruby's
  `07_the_run_dsl` restored both unchanged, so the same stated
  policy ("keep Python structurally in sync with the current Ruby
  reference") now reverses that earlier call. Both remain unused in this
  step in either language — pure structural parity, not a functional need.
- Added `Logger.turn()`/`Logger.subscribe()`, direct ports of two new
  (also unused) Ruby methods, for the same structural-parity reason.

**Why / retain:** confirms `06_the_logger`'s port-plan reasoning was
*conditional on the current Ruby snapshot*, not a permanent decision — a
"drop for parity" call can flip to "re-add for parity" in a later
iteration if the Ruby reference itself reverts. **Don't treat a prior
port's judgment call as settled forever; re-check it against the current
Ruby diff each time**, the same way path-count bugs (entries #4–#22) had
to be re-checked per iteration rather than assumed fixed once.

Confirmed working via `./week1_baseline/bin/python/07_the_run_dsl` (needed
a fresh `.venv` — created with `python3 -m venv .venv && .venv/bin/pip
install -r requirements.txt`, same as every prior Python iteration) — real,
live call to `https://api.anthropic.com/v1/messages` using
`claude-haiku-4-5` through `boukensha.run()`. The resulting
`.boukensha/sessions/<id>.jsonl` matches `ruby/07_the_run_dsl`'s verified
session shape exactly: `session_start` (`provider: "anthropic"`), one
`read_file` `tool_call`/`tool_result` pair, `turn_end`.

**Files changed for this iteration:**
- `week1_baseline/python/07_the_run_dsl/` — new, copied from
  `python/06_the_logger`.
- `week1_baseline/python/07_the_run_dsl/boukensha/run_dsl.py` — new
  (`RunDSL`).
- `week1_baseline/python/07_the_run_dsl/boukensha/__init__.py` — added
  `run()`; re-added `LoopError` to imports/`__all__`.
- `week1_baseline/python/07_the_run_dsl/boukensha/config.py` — re-added
  `mud_host`/`mud_port`/`mud_username`/`mud_password` (`is None`-style,
  matching entry #14's fix).
- `week1_baseline/python/07_the_run_dsl/boukensha/errors.py` — re-added
  `LoopError`.
- `week1_baseline/python/07_the_run_dsl/boukensha/logger.py` — added
  `turn()`/`subscribe()`, wired subscribers into `_write_log`.
- `week1_baseline/python/07_the_run_dsl/examples/example.py` — rewritten
  to use `boukensha.run()`.
- `week1_baseline/python/07_the_run_dsl/README.md` — rewritten for Step 7.
- `week1_baseline/bin/python/07_the_run_dsl` — new runner, `chmod u+x`.
- `week1_baseline/python/07_the_run_dsl/.venv/` — lesson-local virtualenv
  (gitignored).

Full port plan is in
[`07_the_run_dsl.md`](plans/python_port/07_the_run_dsl.md).

---

## `ruby/08_the_repl_loop` — new runner at `week1_baseline/bin/ruby/08_the_repl_loop`

### 25. Same three known bugs as entries #4–#23, all three inherited unfixed into `08_the_repl_loop`

**Problem:** `08_the_repl_loop` copied all three previously-identified
template bugs forward, unfixed:
```ruby
# examples/example.rb
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../.boukensha", __dir__)

# lib/boukensha/config.rb
PROMPTS_DIR = File.expand_path("../../../prompts", __dir__).freeze

# lib/boukensha/logger.rb
def provider_name(backend)
  return nil unless backend

  backend.class.name.split("::").last.gsub(/([a-z\d])([A-Z])/, '\1_\2').downcase
end
```

**Fix:** same three one-line fixes as `06_the_logger`/`07_the_run_dsl`
(entries #19/#20, #23):
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
PROMPTS_DIR = File.expand_path("../../prompts", __dir__).freeze
```
```ruby
def provider_name(backend)
  return nil unless backend
  return "openai" if backend.is_a?(Backends::OpenAI)

  backend.class.name.split("::").last.gsub(/([a-z\d])([A-Z])/, '\1_\2').downcase
end
```

**Also needed (per-project, same as every prior iteration):** `bundle
config set --local path 'vendor/bundle'` before `bundle install` — the
system gem dir (`/var/lib/gems/3.2.0/cache`) still isn't writable, same
`Bundler::PermissionError` as entry #6. `Gemfile`/`Gemfile.lock` are
identical to `07_the_run_dsl`'s (`dotenv` only), so this was a fresh
`bundle install` into `./vendor/bundle` rather than a copy — either works,
this session just didn't copy the sibling's `vendor/bundle/` this time.

**Why / retain:** eighth confirmation of entry #8's `BOUKENSHA_DIR` rule,
fifth of entry #13's `PROMPTS_DIR` rule, third of entry #20's
`provider_name` rule. Per [[feedback_port_review_rigor]], a clean
smoke-test run only proves the code paths it happens to exercise — this
iteration's `provider_name` fix specifically is *not* exercised by the
Anthropic-backend smoke test below (only reachable via the OpenAI
backend), so it was verified by direct diff against the already-fixed
`07_the_run_dsl` copy, not by running it.

Also reviewed (not a bug, a doc/behavior mismatch): the README documents
`Logger#turn` as printing a `╔══ turn N ══╗` header to the screen at each
REPL turn. The shipped method only writes to the JSONL session file —
consistent with `Logger` being a file-only logger since step 6, but it
means no turn header (and no `/quiet`/`/loud` effect) is actually visible
in the terminal. See `docs/week1_repl_loop_overview.md` §3 for detail; no
code change made for this, since adding new stdout output isn't part of
this step's shipped feature set.

Confirmed working via `./week1_baseline/bin/ruby/08_the_repl_loop` — real,
live calls to `https://api.anthropic.com/v1/messages` using
`claude-haiku-4-5` through `Boukensha.repl`, piped stdin exercising: a
`list_directory` tool call and reply on turn 1, a second turn
(`what did I just ask you?`) answered correctly from the shared `Context`
(confirms `Agent#run`'s new `@context.add_message(:assistant, text)` before
`return text`), `/clear` verified to actually wipe history (a follow-up
"what number did I mention?" got a correct "no record" answer), and
`/exit` printing `Goodbye.` and exiting cleanly. The session's `.jsonl` log
shows two `turn` entries, each starting its own `iteration` count at 1.

**Files changed for this iteration:**
- `week1_baseline/ruby/08_the_repl_loop/examples/example.rb` — fixed
  `BOUKENSHA_DIR` `../` count.
- `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/config.rb` — fixed
  `PROMPTS_DIR`'s `../` count.
- `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/logger.rb` — fixed
  `provider_name`'s OpenAI mislabeling.
- `week1_baseline/bin/ruby/08_the_repl_loop` — new runner, `chmod u+x`.
- `week1_baseline/ruby/08_the_repl_loop/.bundle/config` — local bundle path
  (gitignored).
- `week1_baseline/ruby/08_the_repl_loop/vendor/bundle/` — installed gems
  (gitignored).
- `docs/week1_repl_loop_overview.md` — new overview/review doc.

---

## `python/08_the_repl_loop` — Python port

### 26. No new bugs — port executed per plan, all three "genuinely new" items confirmed via unit-level checks

**Problem:** N/A — this entry records a clean port, not a bug fix, per
[[feedback_port_review_rigor]] (later ports need a real review, not just a
smoke test). The full reasoning lives in
`docs/plans/python_port/08_the_repl_loop.md`; this is the short version.
An independent `code-review` pass (comparing every changed file against
its Ruby reference line-by-line) came back with zero findings.

**What was ported:**
- New `boukensha/repl.py` (`Repl`) and `boukensha/version.py`
  (`VERSION = "0.8.0"`), plus a new `boukensha.repl()` function in
  `__init__.py` — same setup as `run()` (config load, system/model/
  backend/api_key resolution, `Context`/`Registry`/`RunDSL`, backend/
  builder/client/logger construction), handed off to a `Repl` instead of
  one `Agent` call.
- `Context.clear_messages()` — direct port of `clear_messages!`.
- `Agent.run()`/`_wrap_up()` — added `context.add_message("assistant",
  ...)` at **all three** return points (normal completion, wind-down
  success, wind-down `ApiError`), not just the obvious one. Verified with
  three separate fake-`Client`/fake-`Builder` unit checks (one per return
  path, since only the normal path is reachable without deliberately
  forcing a wind-down) — each asserts `context.messages[-1]` is the
  `"assistant"` message actually returned.
- `Client.call()` — a `401` now raises `ApiError("authentication failed
  (401) — check your API key")` instead of the generic attempt-count
  message. Verified by monkeypatching `urllib.request.urlopen` to raise a
  canned `HTTPError(code=401)` and asserting the exact message — a live
  smoke test can't exercise this path without an actually-bad key.
- `Config._resolve_dir()` — gained the same new middle tier Ruby's
  `resolve_dir` did: a `.boukensha/` directory in the current working
  directory, checked before falling back to `~/.boukensha`. Verified by
  `chdir`-ing into a temp directory containing a `.boukensha/` subdir with
  `BOUKENSHA_DIR` unset and asserting `Config().dir` resolves there — a
  live smoke test always runs with `BOUKENSHA_DIR` set, so it can never
  exercise this tier on its own.
- Two Ruby idioms with no Python equivalent, both flagged in the port plan
  and confirmed working as designed rather than "fixed":
  - `$stdin.gets` returning `nil` on EOF → Python's `input()` *raising*
    `EOFError` instead. `Repl.start()` wraps the read in
    `try/except EOFError: break`.
  - Ruby's `rescue Interrupt` living in `Boukensha.repl`, not
    `Repl#start` → Python's `repl()` catches `KeyboardInterrupt` around
    `repl_obj.start()`, leaving `Repl.start()` itself with no signal
    handling of its own, exactly mirroring where Ruby catches it.

**Why / retain:** same lesson as entry #24 — a clean live smoke test only
proves the code paths it happens to exercise. Of this iteration's three
genuinely new behaviors (`Agent` persistence, the 401 message, the config
cwd tier), **the live smoke test below only exercised the `Agent`
persistence path** (confirmed by the session log showing correct
multi-turn recall) — the 401 message and the cwd config tier both needed
dedicated unit-level checks with fakes/monkeypatches, because triggering
them for real would require an actually-invalid API key or an actually-set
cwd `.boukensha/` directory, neither of which a normal smoke test run
produces. **Always write the offline check for anything a live run can't
naturally trigger, don't rely on "it ran without erroring."**

Confirmed working via `./week1_baseline/bin/python/08_the_repl_loop` (fresh
`.venv`, same as every prior Python iteration) — real, live calls to
`https://api.anthropic.com/v1/messages` using `claude-haiku-4-5` through
`boukensha.repl()`: a `list_directory` tool call, a follow-up question
answered from `Context`'s accumulated history, `/clear` verified to
actually wipe history (a follow-up "what was the first thing I asked you?"
got "I don't have access to our conversation history before this
message"), and `/exit` printing `Goodbye.` and exiting cleanly. The
resulting `.boukensha/sessions/<id>.jsonl` matches `ruby/08_the_repl_loop`'s
verified session shape exactly, including the `/clear`-resets-the-turn-
counter behavior from entry #25 (a second `{"phase":"turn","n":1}` entry
appears in the same session file after the clear).

**Files changed for this iteration:**
- `week1_baseline/python/08_the_repl_loop/` — new, copied from
  `python/07_the_run_dsl`.
- `week1_baseline/python/08_the_repl_loop/boukensha/repl.py` — new
  (`Repl`).
- `week1_baseline/python/08_the_repl_loop/boukensha/version.py` — new
  (`VERSION`).
- `week1_baseline/python/08_the_repl_loop/boukensha/__init__.py` — added
  `repl()`; imported `VERSION`/`Repl`; updated `__all__`.
- `week1_baseline/python/08_the_repl_loop/boukensha/context.py` — added
  `clear_messages()`.
- `week1_baseline/python/08_the_repl_loop/boukensha/agent.py` — added the
  three `add_message("assistant", ...)` calls.
- `week1_baseline/python/08_the_repl_loop/boukensha/client.py` — added the
  401-specific `ApiError` message.
- `week1_baseline/python/08_the_repl_loop/boukensha/config.py` — added the
  cwd-based middle tier to `_resolve_dir()`.
- `week1_baseline/python/08_the_repl_loop/examples/example.py` — rewritten
  to call `boukensha.repl(configure=...)`.
- `week1_baseline/python/08_the_repl_loop/README.md` — rewritten for
  Step 8.
- `week1_baseline/bin/python/08_the_repl_loop` — new runner, `chmod u+x`.
- `week1_baseline/python/08_the_repl_loop/.venv/` — lesson-local virtualenv
  (gitignored).

Full port plan is in
[`08_the_repl_loop.md`](plans/python_port/08_the_repl_loop.md).

---

## `ruby/09_global_executable` — new runner at `week1_baseline/bin/ruby/09_global_executable`

### 27. Bundled `lib/` was forked from a *pre-review* copy of `08_the_repl_loop`: one recurring template bug plus three of `08`'s own fixes missing, plus a new gemspec bug unique to packaging as a gem

**Problem:** unlike `06`/`07`/`08`, which each copy the *previous* folder
forward, `09_global_executable`'s `lib/` ships as its own independent
snapshot (per the README: "step 8's lib, bundled as the default"). That
snapshot predates `08_the_repl_loop`'s review pass (entry #25), so it
reintroduced one of the long-recurring template bugs plus regressed on all
three fixes/features that review pass actually added:
```ruby
# lib/boukensha/config.rb — recurring template bug (entry #13's family)
PROMPTS_DIR = File.expand_path("../../../prompts", __dir__).freeze  # resolves to ruby/prompts, doesn't exist

# lib/boukensha/config.rb#resolve_dir — 08's cwd tier missing entirely
raw = ENV.fetch("BOUKENSHA_DIR", nil) || DEFAULT_DIR   # no cwd/.boukensha check

# lib/boukensha/logger.rb — recurring template bug (entry #20's family)
# provider_name has no `return "openai" if backend.is_a?(Backends::OpenAI)` case

# lib/boukensha/client.rb — 08's 401-specific message missing
# just falls through to the generic "API request failed ... (401): ..." raise

# lib/boukensha/repl.rb#banner — 08's API-key/config-exists status line missing
```
Confirmed live: `Boukensha::Config::PROMPTS_DIR` resolved to
`ruby/prompts` (one directory too high, and nonexistent) under the exact
depth this folder ships at; `Tasks::Base.read_default_prompt` just checks
`File.exist?` and returns `nil` on a miss, so the failure is **silent** —
`Boukensha.repl` boots with `system: nil`, no error, no visible symptom
short of the agent behaving as if it had no system prompt at all.

A second, new-to-this-iteration bug: **the gemspec declares no runtime
dependency on `dotenv`**, despite its own comment claiming "no external
dependencies" and `lib/boukensha/config.rb` `require`-ing it
unconditionally. `dotenv` is not stdlib. Confirmed by building the gem and
`gem install`-ing it into a throwaway `GEM_HOME` with no bundler in the
picture: `boukensha` (the actual global executable this whole iteration
exists to ship) crashed on the first `require "boukensha"` with
`LoadError: cannot load such file -- dotenv`. This is the one bug in this
entry that isn't a copy-forward regression — it's specific to packaging
as a gem, where `Gemfile`/bundler no longer stands between the code and
its dependencies.

Also found, independent of the code: the README and
`lib/boukensha_loader.rb` both hardcode step numbers that predate
`06_the_logger` being inserted into the curriculum, off by one throughout
— e.g. `lib/boukensha_loader.rb`'s own abort message telling the user to
run `BOUKENSHA_PATH=~/Sites/boukensha/07_the_repl_loop boukensha`
(`07_the_repl_loop` doesn't exist; the actual REPL-loop folder is
`08_the_repl_loop`), and the README's `# Step 8 — Global Executable`
heading / `cd 08_global_executable` / `gem install boukensha-0.1.0.gem`
(this folder is step 9, at `09_global_executable`, building
`boukensha-0.9.0.gem`).

**Fix:** ported `08`'s three fixes/features forward into `09`'s `lib/`
(the same `PROMPTS_DIR`/`provider_name` one-liners as entries #13/#20's
family, plus the `resolve_dir` cwd tier and the 401 message verbatim from
`08_the_repl_loop`, plus the fuller `banner` from `08`'s `repl.rb`); added
`spec.add_dependency "dotenv", "~> 3.2"` to `boukensha.gemspec`; corrected
every step-number/folder-name reference in `README.md` and
`lib/boukensha_loader.rb` to match the current numbering (REPL loop =
step 8, Run DSL = step 7, this folder = step 9).

**Why / retain:** ninth confirmation of entry #13's `PROMPTS_DIR` rule,
fourth of entry #20's `provider_name` rule — but the more important
lesson is new: **a "bundled default lib" that isn't literally copied from
the prior step's already-reviewed folder will silently drift out of sync
with that step's fixes.** Per [[feedback_port_review_rigor]], the dotenv
gemspec bug specifically could not have been caught by running anything
via `bundle exec` (bundler installs it from the `Gemfile` regardless of
what the gemspec declares) — it only surfaces once the gem is actually
built and installed standalone, which is the literal scenario this
iteration's README instructs the user to perform. Always test a
packaging step by doing the packaging, not just running the code through
the same harness every other step used.

Confirmed working via `./week1_baseline/bin/ruby/09_global_executable`
(bundled default REPL, live Anthropic call): banner shows
`v0.9.0` / correct `.boukensha` config dir / `anthropic (claude-haiku-4-5)`
/ `✓ API key set`; the bundled `system.md` prompt is now actually loaded
(the reply correctly self-identifies as the MUD player, confirming the
`PROMPTS_DIR` fix); `/exit` prints `Goodbye.` and exits cleanly. Separately
confirmed `gem build` → `gem install ./boukensha-0.9.0.gem` into an empty
`GEM_HOME` (no bundler, no `Gemfile` in scope) pulls in `dotenv` as a real
dependency and the resulting `boukensha` executable runs a live call from
an unrelated directory — the actual "global executable" behavior this step
promises. Also confirmed `BOUKENSHA_PATH` switching and the
`BOUKENSHA_DEBUG=1` trace line both work through the installed gem, with
corrected step numbers in the "doesn't support the REPL" message.

**Files changed for this iteration:**
- `week1_baseline/ruby/09_global_executable/lib/boukensha/config.rb` —
  fixed `PROMPTS_DIR`'s `../` count; restored the cwd `.boukensha` tier in
  `resolve_dir`.
- `week1_baseline/ruby/09_global_executable/lib/boukensha/logger.rb` —
  restored the OpenAI special case in `provider_name`.
- `week1_baseline/ruby/09_global_executable/lib/boukensha/client.rb` —
  restored the 401-specific `ApiError` message.
- `week1_baseline/ruby/09_global_executable/lib/boukensha/repl.rb` —
  restored the fuller banner (API-key status, config-dir-exists check).
- `week1_baseline/ruby/09_global_executable/lib/boukensha_loader.rb` —
  fixed step numbers/folder names in the two abort messages.
- `week1_baseline/ruby/09_global_executable/boukensha.gemspec` — added the
  missing `dotenv` runtime dependency.
- `week1_baseline/ruby/09_global_executable/README.md` — corrected step
  numbering and version-number examples throughout.
- `week1_baseline/bin/ruby/09_global_executable` — new runner, `chmod u+x`.
- `week1_baseline/ruby/09_global_executable/.bundle/config` — local bundle
  path (gitignored).
- `week1_baseline/ruby/09_global_executable/vendor/bundle/` — installed
  gems (gitignored).
- `docs/week1_global_executable_overview.md` — new overview/review doc.
- `docs/week1_global_executable_review.md` — new companion doc, scoped to
  `lib/boukensha_loader.rb`.
