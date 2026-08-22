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
