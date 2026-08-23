# `09_global_executable` — Reviewing `boukensha_loader.rb`

Companion to
[`week1_global_executable_overview.md`](week1_global_executable_overview.md)
(which covers the whole iteration: the gemspec, `bin/boukensha`, and the
bundled `lib/`'s parity gap against `08_the_repl_loop`). This doc is
scoped to exactly `lib/boukensha_loader.rb` — the module the README calls
"a wrapper and a default."

## Simple explanation

`BoukenshaLoader` has exactly one job: decide *which file* to `require`
before handing off to `Boukensha.repl`. It never loads more than one step
at a time and never mixes code from two steps — it picks one
`lib/boukensha.rb`, requires it, and starts the REPL against whatever that
file defines.

## Walking through `resolve`

```ruby
def self.resolve
  if ENV["BOUKENSHA_PATH"]
    dir  = File.expand_path(ENV["BOUKENSHA_PATH"])
    main = File.join(dir, "lib", "boukensha.rb")
    return main if File.exist?(main)
    abort <<~MSG
      ...points to a step folder, e.g.: BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha
    MSG
  end

  rc = File.expand_path("~/.boukensharc")
  if File.exist?(rc)
    dir = File.read(rc).strip
    unless dir.empty?
      main = File.join(File.expand_path(dir), "lib", "boukensha.rb")
      return main if File.exist?(main)
      abort <<~MSG ... MSG
    end
  end

  BUNDLED_LIB
end
```

Three tiers, checked top to bottom, first match wins:

1. **`BOUKENSHA_PATH`** — highest priority, meant for one-off "try a
   different step this run" usage. If set but wrong (no
   `lib/boukensha.rb` at that path), this is a **hard failure**
   (`abort`, non-zero exit) rather than silently falling through to tier
   2 or 3 — an explicit request for a specific step that can't be
   honored should not be silently ignored.
2. **`~/.boukensharc`** — lowest-ceremony way to set a *permanent*
   default without exporting an env var in every shell. Same
   fail-loud behavior: a stale/broken path in the file aborts rather
   than silently falling back to the bundled default, so a typo in the
   rc file doesn't get masked by "well, it ran, so it must be fine."
3. **`BUNDLED_LIB`** — `File.expand_path("../boukensha.rb", __FILE__)`,
   i.e. this same gem's own `lib/boukensha.rb`. No abort possible here;
   it's guaranteed to exist because it shipped with the gem.

Each `abort` message includes a concrete, runnable example
(`BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha`) rather
than just naming the broken env var — worth preserving as a pattern: a
CLI error that fails loud should also fail *helpfully*.

**Bug found and fixed here:** that example folder name was
`07_the_repl_loop` — a folder that has never existed in this repo. The
REPL loop step is `08_the_repl_loop`; `07_the_run_dsl` is the one step
back. This was a leftover from before `06_the_logger` was inserted into
the curriculum (which shifted every subsequent step's number up by one)
and was never updated here. Confirmed live:

```
$ BOUKENSHA_PATH=/nonexistent bundle exec ruby bin/boukensha
boukensha: BOUKENSHA_PATH is set but no lib/boukensha.rb found at:
       /nonexistent
       Make sure BOUKENSHA_PATH points to a step folder, e.g.:
       BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha   # ← now correct
```

## Walking through `load_and_start_repl`

```ruby
def self.load_and_start_repl
  main = resolve
  step_dir = File.dirname(File.dirname(main))
  puts "[boukensha] loading from: #{step_dir}" if ENV["BOUKENSHA_DEBUG"]
  require main
  unless Boukensha.respond_to?(:repl)
    abort <<~MSG
      does not support the interactive REPL (added in step 8).
      Run its examples directly, e.g.: ruby #{step_dir}/examples/*.rb
      Or point BOUKENSHA_PATH at step 8 or later.
    MSG
  end
  Boukensha.repl
end
```

`step_dir` is derived by walking back up from `main`
(`.../lib/boukensha.rb` → `.../lib` → `...`), purely for display/error
text — it's never used to load anything, `require main` already has the
exact file. `ENV["BOUKENSHA_DEBUG"]` gates one `puts` line; confirmed live
that it prints `[boukensha] loading from: <step_dir>` and is silent
otherwise.

The `respond_to?(:repl)` check is what turns "you pointed `BOUKENSHA_PATH`
at a step that predates the REPL" into a helpful abort instead of a bare
`NoMethodError: undefined method 'repl' for Boukensha`. Confirmed live
against `07_the_run_dsl` (a real step, correctly lacks `.repl`):

```
$ BOUKENSHA_PATH=.../07_the_run_dsl bundle exec ruby bin/boukensha
boukensha: the step at .../07_the_run_dsl
       does not support the interactive REPL (added in step 8).
       Run its examples directly, e.g.:
         ruby .../07_the_run_dsl/examples/*.rb
       Or point BOUKENSHA_PATH at step 8 or later.
```

**Bug found and fixed here too:** this message previously said "added in
step 7" and "point BOUKENSHA_PATH at step 7 or later" — self-contradictory
once you notice it's rejecting `07_the_run_dsl` itself while claiming step
7 is where REPL support begins. REPL support was added in
`08_the_repl_loop`, i.e. step 8; both numbers are now `8`.

## Retain — the short list

1. **Fail loud, not silent, on an explicit-but-wrong `BOUKENSHA_PATH` or
   `~/.boukensharc`.** Only the *absence* of both falls through to the
   bundled default; a *present-but-broken* value aborts with a concrete
   example rather than degrading to "well, something ran."
2. **`BOUKENSHA_PATH` (code) and `BOUKENSHA_DIR` (config) are
   orthogonal** — this loader only ever touches the former; conflating
   the two in an error message or a fix would be a real bug, not just a
   style nit.
3. **Every abort message here doubles as a runnable example** — worth
   keeping error text copy-pasteable, and worth re-checking those
   examples any time the underlying folder numbering changes, since nothing
   type-checks a string embedded in a heredoc.
