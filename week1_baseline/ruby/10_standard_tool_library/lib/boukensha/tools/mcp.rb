require "mud_manager/mcp/client"
require "timeout"

module Boukensha
  module Tools
    # Mcp is the generic bridge between Boukensha's Registry and any number
    # of configured MCP servers. It doesn't know what any server's tools
    # actually do — MUD gameplay is just data (one entry in `servers:`) to
    # this module, not a special case. Replaces the old, MUD-specific
    # Tools::Mud, which is removed rather than kept as a compatibility
    # wrapper (see docs/week1_mcp_refactor_plan_review.md) — the config
    # format already changed (settings.yaml's mud: block -> mcp_servers:),
    # so keeping a Ruby-level shim on top would just leave two ways to
    # configure the same thing.
    #
    # NOTE: this requires "mud_manager/mcp/client" — MudManager::Mcp::Client's
    # actual behavior (spawn a command, speak MCP over stdio) is fully
    # generic; only its name and its own default `command:` are
    # MUD-flavored. The MCP layer used to be a separate mud_mcp gem
    # depending on mud_manager; the two were merged into one gem
    # (docs/week1_mud_manager_mcp_merge_plan.md) so there's a single home
    # for everything MUD-manager-related instead of two gems, one
    # depending on the other.
    #
    # Usage:
    #
    #   Boukensha::Tools::Mcp.register(registry, servers: [
    #     { name: "mud", command: [], env: {"MUD_HOST" => "localhost", ...} }
    #   ])
    #
    # An empty/absent `command:` falls back to MudManager::Mcp::Client's own
    # default (the installed `mud_manager --mcp` executable, resolved via
    # $PATH — see docs/week1_mcp_server_config_update.md). settings.yaml's
    # own `mcp_servers:` entry specifies this command explicitly rather
    # than relying on that fallback, but a caller of this module directly
    # (as opposed to through Boukensha.run/.repl's config loading) can
    # still omit it.
    #
    # Returns [{name:, client:}, ...] — one entry per server that actually
    # started. A server that fails to spawn, hangs past the handshake
    # timeout, or errors is warned about and simply absent from the result,
    # so one bad server doesn't take any other configured server down with
    # it.
    module Mcp
      HANDSHAKE_TIMEOUT = 10 # seconds

      def self.register(registry, servers:)
        servers.filter_map { |server| register_one(registry, server) }
      end

      def self.register_one(registry, server)
        command = server[:command] && !server[:command].empty? ? server[:command] : nil
        client  = command ? MudManager::Mcp::Client.new(command: command, env: server[:env] || {})
                           : MudManager::Mcp::Client.new(env: server[:env] || {})

        Timeout.timeout(HANDSHAKE_TIMEOUT) do
          client.handshake
          client.list_tools.each do |tool|
            register_proxy_tool(registry, server[:name], client, tool, server[:prefix])
          end
        end

        at_exit { client.close }
        { name: server[:name], client: client }
      rescue StandardError => e
        warn "[boukensha] MCP server #{server[:name].inspect} failed to start: #{e.class}: #{e.message}"
        nil
      end

      # Wire one MCP tool straight into the Boukensha registry: same
      # description, same parameters (an MCP inputSchema's `properties` is
      # already the exact shape `registry.tool`'s `parameters:` expects).
      # The handler just forwards the call over MCP and returns the text —
      # MCP's `isError` flag doesn't need surfacing here, since whenever
      # it's true the text itself already carries an "error: " prefix (see
      # mud_manager/mcp/dispatcher.rb), exactly like every other Boukensha
      # tool that hands the agent an error string instead of raising.
      #
      # `prefix`, when set on the server's config entry, disambiguates
      # every tool from that server (e.g. "mud_look") — an opt-in escape
      # hatch, not automatic; see the collision check below for the default
      # behavior when two servers expose the same bare tool name.
      def self.register_proxy_tool(registry, server_name, client, tool, prefix)
        name = prefix ? "#{prefix}_#{tool[:name]}" : tool[:name]

        if registry.registered?(name)
          warn "[boukensha] MCP server #{server_name.inspect}: tool #{name.inspect} " \
               "collides with an already-registered tool — skipped (use prefix: on this " \
               "server's config entry to disambiguate)"
          return
        end

        registry.tool name,
          description: tool[:description],
          parameters: tool[:inputSchema][:properties] do |**args|
          text, = client.call_tool(tool[:name], args)
          text
        end
      end
      private_class_method :register_proxy_tool
    end
  end
end
