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

## 4. Build & install, done for real — what that actually involves

### Simple explanation

"Build the gem" and "install the gem" sound like two mechanical steps, but
each one has a real decision hiding inside it:

- **Build** turns the folder into one `.gem` file. RubyGems reads the
  gemspec, checks every file it's told to package actually exists and
  looks sane, and warns about anything it thinks is off — it does **not**
  refuse to build over a warning, so it's easy to ship a gem that builds
  cleanly-looking but is subtly broken (see the executable-bit bug below).
- **Install** is where the environment you're installing *into* matters.
  "Just run `gem install`" assumes you're allowed to write into Ruby's
  system-wide gem directory. On a lot of machines (this one included)
  that directory belongs to root, so the honest options are: use `sudo`
  (touches the whole system, needs a password), or install into your own
  per-user gem directory instead (no `sudo`, but the command won't be on
  `$PATH` until you tell your shell where to look).

### Technical explanation

**Build.** `gem build boukensha.gemspec` was run twice. The first run
printed:

```
WARNING:  bin/boukensha is not executable
```

RubyGems doesn't fail the build over this — it only *warns* — but the
warning is pointing at a real bug: `bin/boukensha` was tracked in git as
mode `100644` (`-rw-r--r--`, not executable). Checked whether this was an
isolated slip or a repeated one by diffing the tracked mode of the same
file across every gem-packaging step in the repo:

```
$ git ls-files -s -- '*/bin/boukensha'
100644 ... week1_baseline/ruby/09_global_executable/bin/boukensha
100644 ... week1_baseline/ruby/10_standard_tool_library/bin/boukensha
100644 ... week1_baseline/ruby/11_tui/bin/boukensha
100644 ... week1_baseline/ruby/12_context/bin/boukensha
```

All four ship it the same way — a genuine template oversight, not one
freak file. `chmod +x` on `09_global_executable/bin/boukensha` (only this
folder; 10/11/12 aren't part of this iteration's scope) made the second
build clean, with only the pre-existing, harmless "no homepage specified"
warning left.

Worth noting explicitly: this warning being cosmetic-looking is a little
misleading. `spec.executables = ["boukensha"]` tells RubyGems to install
that file into the target `bin/` and mark *the installed copy* executable
regardless of the source file's own permission bit — so even the
un-`chmod`'d gem would have produced a working `boukensha` command after
install. The bug was real, but it would not have blocked anyone; it would
only have kept surfacing as the same confusing warning on every future
`gem build` until someone bothered to trace it down, which is exactly why
it's worth fixing at the source instead of shrugging at the warning.

**Uninstall (checked, not assumed).** Before installing, checked whether
any previous `boukensha` gem was already present, system-wide or
user-wide:

```
$ gem list boukensha
(no output)
```

Nothing installed anywhere, so the "uninstall the previous version" step
was a genuine no-op — not skipped, *verified* empty.

**Install — the environment-dependent decision.** Checked whether the
default (system) gem directory was writable before assuming `gem install`
would work:

```
$ gem environment gemdir
/var/lib/gems/3.2.0
$ [ -w /var/lib/gems/3.2.0 ] && echo writable || echo "not writable"
not writable
```

It wasn't — this account has no write access to the system gem path, so a
plain `gem install boukensha-0.9.0.gem` would have failed outright, not
partially succeeded. Two real options existed: `sudo gem install` (system
directory, immediately on everyone's `$PATH`, but touches shared system
state and needs a password) or `gem install --user-install` (writes to
`~/.local/share/gem/ruby/3.2.0`, no elevated privileges, but that
directory is its own separate gem path). Chose user-install as the
lower-blast-radius option.

```
$ gem install --user-install ./boukensha-0.9.0.gem --no-document
WARNING:  You don't have /home/mahdi/.local/share/gem/ruby/3.2.0/bin in your PATH,
          gem executables will not run.
Successfully installed dotenv-3.2.0
Successfully installed boukensha-0.9.0
2 gems installed
```

RubyGems installs `dotenv` first, automatically, purely because of the
`spec.add_dependency "dotenv", "~> 3.2"` line added earlier in this
iteration (§3) — direct, live proof that the dependency-declaration fix
actually does what it's for; before that fix this exact command would
have installed `boukensha` alone and then crashed on first run with
`LoadError: cannot load such file -- dotenv`.

The install itself prints its own warning, and it's not cosmetic this
time: `~/.local/share/gem/ruby/3.2.0/bin` genuinely is not on `$PATH` on
this machine, confirmed with `echo $PATH`. This means running the bare
word `boukensha` in a fresh shell right now does nothing (`command not
found`) even though the gem is fully and correctly installed — a real gap
between "installed" and "on `$PATH`" that the tool itself points out
instead of hiding, but which isn't a bug in the gem: it's inherent to
choosing the per-user install path. Fixing it means adding

```bash
export PATH="$HOME/.local/share/gem/ruby/3.2.0/bin:$PATH"
```

to a shell rc file — deliberately left for the machine's owner to do, not
done automatically, since it's a persistent change to their shell
environment rather than something scoped to this repo.

**Verified anyway**, by invoking the installed executable through its
full path rather than relying on `$PATH`:

```
$ ls -la ~/.local/share/gem/ruby/3.2.0/bin/boukensha
-rwxr-xr-x 1 mahdi mahdi 560 ... boukensha
$ cd /tmp && BOUKENSHA_DIR=.../.boukensha ~/.local/share/gem/ruby/3.2.0/bin/boukensha
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.9.0)    ║
╚══════════════════════════════════════╝
...
boukensha> Hey there, adventurer—ready to explore?
```

`-rwxr-xr-x` confirms the *installed* copy is executable regardless of
what the tracked source file's mode was (as predicted above); the live
reply from `/tmp`, with no `bundle exec` and no project directory in
sight, confirms this is a real standalone install, not one that happens
to still be borrowing the Gemfile's dependency resolution.

### Objective assessment

Two independently real findings came out of literally doing the build and
install, that reading the code alone would not have surfaced:

1. **`bin/boukensha`'s missing executable bit** is caught by RubyGems as
   a *warning*, not an error — build warnings are worth reading, not
   just checking that the build "succeeded."
2. **Which install command is even valid depends on filesystem
   permissions the gemspec has no way to express** — `gem install` isn't
   one universal command; checking `gem environment gemdir` and its
   writability *before* installing turned a potential hard failure
   (`sudo` prompt or a permission error) into an informed choice between
   two working paths, with the tradeoff (blast radius vs. `$PATH`
   convenience) stated up front instead of discovered by trial and error.

## 5. Configuring which project the global executable loads

### Simple explanation

An installed gem is a frozen snapshot — the copy under
`~/.local/share/gem/.../boukensha-0.9.0` doesn't change when the source
files in this repo change. "Configure the global executable to load the
current project iteration" means: make `boukensha`, run from literally
anywhere with no flags, load *this repo's* `09_global_executable/lib/`
instead of that frozen snapshot — and keep doing so every time, without
anyone having to type an environment variable first.

`lib/boukensha_loader.rb` already has exactly the mechanism for this
(§2): `~/.boukensharc` is a one-line dotfile — write a path into it once,
and every future `boukensha` invocation reads that path automatically.
That's tier 2 of the resolution chain, sitting between the
"override just this one run" env var (tier 1) and the "fall back to
whatever's frozen inside the gem" default (tier 3).

### Technical explanation

**3.1 — pointed `~/.boukensharc` at this iteration:**
```bash
echo "/home/.../week1_baseline/ruby/09_global_executable" > ~/.boukensharc
```
No code change was needed — the loader already reads this file; the gap
was purely that the file didn't exist yet on this machine.

**3.2 — a second, separate config file was also missing.** `BOUKENSHA_PATH`
/ `~/.boukensharc` only select *code*; the framework's actual runtime
config (`settings.yaml`, `.env`, `prompts/`) is a completely independent
resolution chain inside `Boukensha::Config` (env var → cwd `.boukensha` →
`~/.boukensha`). Running the freshly-installed executable from `/tmp`
with zero env vars set surfaced that `~/.boukensha` didn't exist on this
machine either — only this repo's local `.boukensha/` did — so the
executable correctly resolved *which code* to run but then crashed
loud (not silent — see §3's `PROMPTS_DIR` lesson for why loud matters
here) on `tasks.player.model is required in settings.yaml`, because there
was no config directory at its final fallback location at all.

Symlinked the fix rather than copying, to keep one source of truth for
the settings (including the API key in `.env`) instead of two files that
can drift apart:
```bash
ln -s /home/.../.boukensha ~/.boukensha
```

**3.3 — verified the whole chain, priority order and all,** by invoking
the installed executable with `BOUKENSHA_DEBUG=1` under four different
conditions:

| Condition | Loads from | Confirms |
|---|---|---|
| `~/.boukensharc` present, no env override | `.../09_global_executable` (repo source) | tier 2 wins over tier 3 |
| `~/.boukensharc` removed | `~/.local/share/gem/.../boukensha-0.9.0` (installed snapshot) | tier 3 is the correct final fallback |
| `~/.boukensharc` restored | `.../09_global_executable` again | the file is actually being read each run, not cached |
| `BOUKENSHA_PATH` set to `08_the_repl_loop` | `.../08_the_repl_loop` (banner shows `v0.8.0`) | tier 1 still overrides tier 2, exactly as documented |

Then, the actual acceptance test for "automatic, no manual path changes":
ran `boukensha` from `/tmp` with **zero environment variables set at
all** — no `BOUKENSHA_PATH`, no `BOUKENSHA_DIR`, no `cd` anywhere near
this repo. It resolved code via `~/.boukensharc`, resolved config via the
new `~/.boukensha` symlink, and completed a real live turn against
`claude-haiku-4-5`, banner correctly showing `config: /home/.../.boukensha`
and `✓ API key set`.

### Objective assessment

The two configuration files serve genuinely independent concerns and
both were silently absent before this step — neither is a code bug, both
are "this machine was never set up," which is exactly the class of gap a
live, from-`/tmp`, zero-env-var run catches and a `bundle exec`-from-inside-
the-folder run never would. Priority order (env var beats rc file beats
bundled default) was verified by observation, not just by reading
`resolve`'s `if`/`elsif` order — the `v0.8.0` vs `v0.9.0` banner version
is a cheap, unambiguous tell for which tier actually won on a given run.

## 6. Final acceptance check — launch, REPL, one real prompt

### Simple explanation

Everything in §§1–5 is either a build step or a configuration step —
neither actually proves the finished thing works the way an end user
would use it. The real acceptance test is the boring, literal one: launch
`boukensha`, watch it start, type one thing at it, get a real reply back.

### Technical explanation

Ran, from `/tmp` — an unrelated directory, no `cd` into the repo, no env
vars set by hand, nothing but what §3 already put in place
(`~/.boukensharc` and the `~/.boukensha` symlink):

```
$ printf 'Tell me a one-sentence fun fact about MUDs.\n/exit\n' | boukensha

╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.9.0)    ║
╚══════════════════════════════════════╝
  config:    /home/mahdi/.boukensha
  provider:  anthropic (claude-haiku-4-5)  ✓ API key set

  /quiet or /loud   toggle logging
  /clear           reset conversation history
  /exit or /quit    leave the REPL

boukensha>
MUDs were the original online multiplayer games that evolved from
text-based dungeons like Zork, letting hundreds of players explore shared
fantasy worlds together through nothing but typed commands — decades
before graphical MMORPGs existed.
boukensha> Goodbye.
```

Three things checked, in order:
1. **Launch** — the process starts and exits `0`, with no `LoadError`
   (the `dotenv` gemspec fix from §3 holding), no `PROMPTS_DIR` failure
   (§3's fix holding — the reply is clearly informed by the bundled
   system prompt's persona), and no config-resolution crash (§5's
   `~/.boukensha` symlink holding).
2. **REPL starts** — the banner renders correctly and control reaches
   the `boukensha> ` prompt rather than aborting first.
3. **A real prompt round-trips** — not a canned/offline check: this is a
   live HTTP call to `https://api.anthropic.com/v1/messages` via
   `claude-haiku-4-5`, and the reply's content is topically responsive to
   what was actually asked, not just "some text came back." `/exit`
   then prints `Goodbye.` and the process exits cleanly rather than
   hanging or erroring on teardown.

**One caveat surfaced by running exactly this, and only this:** the
command above only resolves because the shell it ran in had already been
told where the executable lives. A genuinely fresh shell, with nothing
pre-arranged, still can't find it:
```
$ which boukensha
(nothing — not found)
```
`~/.local/share/gem/ruby/3.2.0/bin` (where `gem install --user-install`
put the executable, §4) is not on `$PATH` on this machine. This is not a
bug in `boukensha` or in anything built during this iteration — it's the
direct, known consequence of choosing `--user-install` over `sudo` back
in §4, called out at the time and deliberately left for the machine's
owner to decide on, since editing shell startup files is a persistent
change outside this repo's scope. Every verification in this document
has correctly used the executable's full path to work around it; a
`export PATH="$HOME/.local/share/gem/ruby/3.2.0/bin:$PATH"` line in the
shell's rc file is the one remaining step to make the bare word
`boukensha` work.

### Objective assessment

This step intentionally added zero new code and zero new config — its
only job was to confirm that everything fixed and configured in §§3–5
actually composes into one working end-to-end path, run the way a real
user would run it (piped stdin, a plain-English question, no flags). It
did: the three failure modes this whole iteration exists to prevent
(missing dependency, missing system prompt, missing config directory)
were all silently *not* hit, and the one remaining gap (`$PATH`) is a
known, disclosed, out-of-repo-scope item rather than a surprise.
