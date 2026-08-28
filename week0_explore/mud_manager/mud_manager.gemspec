Gem::Specification.new do |spec|
  spec.name        = "mud_manager"
  spec.version     = "0.3.1"
  spec.summary     = "MudManager — CircleMUD session management, command primitives, and an MCP server"
  spec.description = "Provides MudManager::Session (a long-lived telnet connection with " \
                     "background buffering and IAC stripping), MudManager::Primitives " \
                     "(a stateless library of typed CircleMUD command builders), and " \
                     "MudManager::Mcp (an MCP server/client pair exposing gameplay as MCP " \
                     "tools, formerly the separate mud_mcp gem — merged in 0.2.0 so this " \
                     "gem is the single home for everything MUD-manager-related). The " \
                     "bin/mud_manager executable (0.3.0, was bin/mud_manager_mcp_server) " \
                     "takes a --mcp flag to run in MCP-server mode, invoked directly as " \
                     "the installed command rather than via `ruby <path-to-script>`. " \
                     "0.3.1: Session#login now recognizes a duplicate-session takeover " \
                     "(\"already in use\") the same way it already recognized a linkless " \
                     "reconnect, instead of blocking for the full read_until timeout and " \
                     "raising Timeout on an already-successful login."
  spec.authors     = ["Andrew Brown"]
  spec.email       = ["andrew@exampro.co"]
  spec.license     = "MIT"

  spec.required_ruby_version = ">= 3.0"

  spec.files = Dir["lib/**/*.rb"] + ["bin/mud_manager"]

  spec.bindir      = "bin"
  spec.executables = ["mud_manager"]

  # json/open3/rbconfig/socket/thread are all stdlib — no external dependencies.
end
