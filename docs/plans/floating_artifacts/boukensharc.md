# Floating Artifact: `~/.boukensharc`

"Floating" because it lives outside every step directory and outside git
entirely (home directory, single untracked file), yet its content decides
which step's code the globally-installed `boukensha` command actually
runs. Nothing about advancing from one step to the next — building a new
gem version, editing a step's `lib/` — touches this file automatically.
Forget it, and `boukensha` keeps quietly running an old step's code even
after installing a brand-new gem version for the current one.

## What Step 09 introduced

`ruby/09_global_executable` is where `boukensha` first became a real,
globally-installed command (`gem build` + `gem install`) instead of
something run via `ruby examples/example.rb` from inside a step folder.
That step added `lib/boukensha_loader.rb`, whose `BoukenshaLoader.resolve`
picks which step's `lib/boukensha.rb` to `require`, in this order:

1. `BOUKENSHA_PATH` env var, if set — highest priority, one-off override.
2. **`~/.boukensharc`** — a file containing a single path, read once at
   startup, `.strip`'d. This is the "floating artifact" this doc tracks.
3. The currently-installed gem's own bundled `lib/` — whichever step was
   most recently `gem install`'d, if neither of the above is set.

Every step from 09 onward carries its own copy of `boukensha_loader.rb`
forward (cosmetic diffs only — the step number in comments, later on the
MUD env-var handling added in step 10 — the resolution logic itself is
unchanged since it was introduced). `~/.boukensharc` itself is not part of
that carry-forward — it's runtime state on the machine actually running
`boukensha`, not repo content, so nothing in git ever updates it.

## Current value

```
/home/mahdi/claude-code-camp-2026-Q2/week1_baseline/ruby/10_standard_tool_library
```

## History

| Date | Step pointed at | Set by |
|---|---|---|
| (predates this doc — first set when step 09 was completed) | `09_global_executable` | — |
| 2026-08-25 | `10_standard_tool_library` | Updated while verifying the MCP refactor's `boukensha` command launch (MCP Part 3, 2.3) — the rc file was still pointing at step 09, which predates any MUD tooling, so testing "does `boukensha` launch" against it would have exercised none of the changed code. |

## Carrying this forward

Whenever a step that supports the REPL (08+) becomes "the current one,"
update the file:

```sh
echo -n "/absolute/path/to/week1_baseline/ruby/<NN_step_name>" > ~/.boukensharc
```

No trailing newline required either way (`resolve` strips it), but a
literal path is required — `~` is not expanded by the loader itself
(`File.expand_path` runs on whatever string is in the file, and `~` only
expands under `File.expand_path` when it's the *whole* leading component,
so an absolute path is the safe choice here regardless).

Gem version and `.boukensharc`'s target are **independent** — installing
`boukensha-0.10.0.gem` does not change what `.boukensharc` points at, and
vice versa. Both need updating together when advancing steps; this repo
has no automation for either.

## Related

- Loader: `ruby/<step>/lib/boukensha_loader.rb` (`BoukenshaLoader.resolve`)
- Introduced in: `ruby/09_global_executable` (see its README's "Switching
  steps with BOUKENSHA_PATH" section for the original documentation)
- Verified end-to-end for step 10 in `docs/week1_mcp_part3_review.md`
  (section 1.3) and the MCP Part 3 gem rebuild/launch test that prompted
  this doc
