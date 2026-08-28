# Building and installing the `11_tui` gem

How to package `ruby/11_tui` as an installable gem, why each step is
necessary, and the schemas involved (`boukensha.gemspec`, `settings.yaml`'s
`mcp_servers:` list). Written after rebuilding `boukensha-0.11.0.gem` from
this step following the MCP/loader delta merge from `10_standard_tool_library`
(see `docs/week1_config_troubleshooting.md` entries #32–#35).

## Why you rebuild the gem at all

`bin/boukensha` (the *installed* executable) is a tiny shim:

```ruby
#!/usr/bin/env ruby
$LOAD_PATH.unshift File.expand_path("../lib", __dir__)
require "boukensha_loader"
BoukenshaLoader.load_and_start_repl
```

`gem install` copies whatever is on disk under `lib/` *at build time* into
`~/.local/share/gem/.../gems/boukensha-<version>/lib/`. Editing
`ruby/11_tui/lib/boukensha.rb` (or adding `tools/mcp.rb`, or bumping the
`mud_manager` dependency) changes nothing for anyone actually running
`boukensha` until you `gem build` + `gem install` again — the installed
copy is a snapshot, not a symlink. That's the whole reason this step exists
in the delta: the code changes only "count" once the gem is rebuilt.

## The gemspec — what actually gets packaged

`boukensha.gemspec` is the schema RubyGems reads to build the `.gem` file:

```ruby
Gem::Specification.new do |spec|
  spec.name        = "boukensha"
  spec.version     = Boukensha::VERSION        # from lib/boukensha/version.rb
  spec.summary     = "..."
  spec.description = "..."
  spec.authors     = ["Andrew Brown"]
  spec.license     = "MIT"
  spec.required_ruby_version = ">= 3.0"

  spec.files       = Dir["lib/**/*.rb"] + ["bin/boukensha"]  # <- globbed, not hand-listed
  spec.bindir      = "bin"
  spec.executables = ["boukensha"]                            # installs bin/boukensha on $PATH

  spec.add_dependency "mud_manager", "~> 0.3"                  # MCP client (bumped from ~> 0.1)
  spec.add_dependency "charm"                                  # TUI (bubbletea/lipgloss/bubbles/...)
end
```

| Field | Meaning | Why it matters here |
|---|---|---|
| `spec.files` | `Dir["lib/**/*.rb"]` — every `.rb` under `lib/`, resolved fresh on each `gem build` | Deleting `tools/mud.rb` and adding `tools/mcp.rb` needed **no gemspec edit** — the glob just picks up whatever's on disk |
| `spec.executables` | Which files in `bindir` become `$PATH` commands | This is what makes `boukensha` a global command after install |
| `spec.add_dependency` | Runtime deps RubyGems must resolve on install | `mud_manager ~> 0.3` is required *now* — 0.1.x doesn't have `MudManager::Mcp::Client` |

## Build

```sh
cd ruby/11_tui
chmod +x bin/boukensha        # only if `gem build` warns "bin/boukensha is not executable"
gem build boukensha.gemspec
```

```
Successfully built RubyGem
  Name: boukensha
  Version: 0.11.0
  File: boukensha-0.11.0.gem
```

`gem build` doesn't touch anything installed — it just zips up whatever
`spec.files` matches into `boukensha-0.11.0.gem` in the current directory.
Safe to re-run any number of times; each run overwrites the local `.gem`
file.

## Install

```sh
gem install --user-install boukensha-0.11.0.gem
```

Two flags matter, both situational:

- **`--user-install`** — needed whenever the system gem directory
  (`gem env` → `INSTALLATION DIRECTORY`) isn't writable by your user
  (common on a shared box; not a root shell). Installs to
  `gem env` → `USER INSTALLATION DIRECTORY` instead
  (`~/.local/share/gem/ruby/<ver>/`). Same root cause as
  `docs/week1_config_troubleshooting.md` entry #29. Drop it if your gem
  install dir is already writable.
- **`--ignore-dependencies`** — only needed if `charm`'s own dependency
  tree (`bubbletea`, `lipgloss`, `bubbles`, `bubblezone`, `glamour`, `gum`,
  `harmonica`, `ntcharts`) isn't already installed *and* you have no
  network path to rubygems.org to fetch them. That was true in this
  sandbox at the time this gem was built (a plain `gem install` just hung
  resolving those) — but check `gem list charm bubbletea -a` before
  assuming it still is; this environment's installed-gem set isn't fixed
  (see `docs/week1_config_troubleshooting.md` entry #35, where those gems
  turned up installed a short time later). Drop this flag anywhere those
  gems can actually be fetched or are already present — you want real
  dependency resolution in a normal environment, this flag is a sandbox
  workaround, not the default way to install this gem.

## Verify

```sh
gem list boukensha -a                     # confirms 0.11.0 is now installed alongside older versions
gem contents boukensha -v 0.11.0 | grep tools/
#   .../boukensha-0.11.0/lib/boukensha/tools/file_system.rb
#   .../boukensha-0.11.0/lib/boukensha/tools/mcp.rb          <- present
#   .../boukensha-0.11.0/lib/boukensha/tools/shell.rb        <- no mud.rb
```

`gem install` never removes older installed versions (`0.9.0`/`0.10.0` stay
installed) — RubyGems supports multiple versions side by side, and picks
the newest unless something pins a version.

## Installing the gem alone doesn't change what `boukensha` runs

Installing `0.11.0` makes RubyGems treat it as the newest `boukensha` gem,
but `bin/boukensha`'s own resolution order (`lib/boukensha_loader.rb`)
looks *past* the gem's bundled `lib/` first:

```
1. BOUKENSHA_PATH env var       # e.g. BOUKENSHA_PATH=~/Sites/boukensha/11_tui
2. ~/.boukensharc                # a file containing one path
3. the gem's own bundled lib/    # whatever version is "active"
```

If `~/.boukensharc` already points at another step's checkout, running
plain `boukensha` still loads *that* step's code, regardless of which gem
version you just installed. **Watch for a version-skew trap here**: the
loader itself (`boukensha_loader.rb`) comes from whichever gem is newest,
so once `0.11.0` is installed, plain `boukensha` runs *0.11.0's* loader —
which always passes `tui:` into `Boukensha.repl` — against whatever step
`~/.boukensharc` points at. If that's still an older step without a `tui:`
keyword (e.g. `10_standard_tool_library`), it crashes:
```
.../10_standard_tool_library/lib/boukensha.rb:128:in `repl': unknown keyword: :tui (ArgumentError)
```
So repointing `~/.boukensharc` isn't just about *which code* runs, it also
resolves a genuine boot-breaking mismatch once a newer gem is installed.

## Updating the global config

```sh
echo /home/mahdi/claude-code-camp-2026-Q2/week1_baseline/ruby/11_tui > ~/.boukensharc
```

Verified after repointing (`BOUKENSHA_DEBUG=1` prints the resolved
`step_dir` before loading):

```sh
$ BOUKENSHA_DEBUG=1 boukensha --no-tui
[boukensha] loading from: .../week1_baseline/ruby/11_tui
...
  mcp servers: mud (connected)
boukensha> /exit
Goodbye.

$ BOUKENSHA_DEBUG=1 boukensha        # tui: true (default)
[boukensha] loading from: .../week1_baseline/ruby/11_tui
# real charm/bubbletea alt-screen TUI: boxed banner, live status line
# ("boukensha v0.11.0 · claude-haiku-4-5 · ctx 0 · 34 tools · <clock>"),
# input textarea — the four-zone layout only 11_tui's Boukensha::Tui has.
```

`pgrep -af mud_manager` / `pgrep -af "ruby.*boukensha"` both came back
empty after each run — clean shutdown, no orphaned MCP subprocess or Ruby
process left behind. `--no-tui` is optional here (only mandatory if
`charm`'s gems aren't actually installed) — full details and the
version-skew gotcha are in `docs/week1_config_troubleshooting.md`
entry #35.

## The other schema: `settings.yaml`'s `mcp_servers:`

This is the config shape `Config#mcp_servers` (`lib/boukensha/config.rb`)
parses, and what the gem's `mud_manager ~> 0.3` dependency exists to talk
to:

```yaml
mcp_servers:
  - name: mud                       # string, required — used for banner/log labeling and prefix fallback
    command: ["mud_manager", "--mcp"]   # array of strings — argv to spawn; omit/empty -> client's own default
    env:                             # hash of string -> string, required keys depend on the server
      MUD_HOST: localhost
      MUD_PORT: "4000"               # always a string here — see troubleshooting entry #34 (resolve_env caveat)
      MUD_NAME: dummy
      MUD_PASSWORD: "$MUD_PASSWORD"  # a "$VAR" value resolves against ENV (populated from .env) instead of being literal
    prefix: null                     # optional string — disambiguates tool names when two servers collide
```

| Key | Type | Required | Notes |
|---|---|---|---|
| `name` | String | yes | Shown in the REPL/TUI banner as `"#{name} (connected)"` |
| `command` | Array\<String\> | no | Falls back to `MudManager::Mcp::Client`'s own default (the installed `mud_manager --mcp` binary) when empty/absent |
| `env` | Hash\<String, String\> | no (default `{}`) | Values starting with `"$"` resolve against `ENV`; every other value must already be a **string** — an unquoted YAML integer (`MUD_PORT: 4000`) passes through unconverted and will raise a `TypeError` when handed to `Process.spawn` |
| `prefix` | String or nil | no | Prepended as `"#{prefix}_#{tool_name}"` to every tool that server exposes, only needed if two servers expose a same-named tool |

One server config can expose dozens of tools — `Tools::Mcp.register` calls
that MCP server's `tools/list` at handshake time and registers each result
into the Boukensha registry automatically; nothing about the tool surface
itself is hand-declared in Ruby anymore (that was the whole point of the
`Tools::Mud` → `Tools::Mcp` refactor this delta carried over).
