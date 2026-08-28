require "json"
require_relative "version"

module MudManager
  module Mcp
    # A minimal MCP server: JSON-RPC 2.0 over stdio — one message per line on
    # stdin/stdout, no embedded newlines, per the MCP stdio transport. Handles
    # exactly what a tools-only server needs: `initialize`, the
    # `notifications/initialized` notification, `tools/list`, `tools/call`,
    # and `ping`. Never writes anything to $stdout except JSON-RPC messages —
    # all diagnostics go to $stderr (matching MudManager::Session's own use of
    # `warn` for connection problems).
    class Server
      PROTOCOL_VERSION = "2024-11-05"

      # `session` is optional and only used for a graceful close on shutdown —
      # the Server itself never calls anything on it besides #open?/#close.
      def initialize(dispatcher, session: nil, name: "mud-manager-mcp-server", version: VERSION,
                     in_io: $stdin, out_io: $stdout)
        @dispatcher = dispatcher
        @session    = session
        @name       = name
        @version    = version
        @in         = in_io
        @out        = out_io
      end

      def run
        @out.sync = true
        while (line = @in.gets)
          line = line.strip
          next if line.empty?

          handle_line(line)
        end
      ensure
        shutdown
      end

      private

      def handle_line(line)
        message = JSON.parse(line, symbolize_names: true)
      rescue JSON::ParserError => e
        send_error(nil, -32_700, "parse error: #{e.message}")
      else
        dispatch(message)
      end

      def dispatch(message)
        id     = message[:id]
        method = message[:method]
        params = message[:params] || {}

        case method
        when "initialize"
          send_result(id, {
            protocolVersion: PROTOCOL_VERSION,
            capabilities: { tools: {} },
            serverInfo: { name: @name, version: @version }
          })
        when "notifications/initialized"
          nil # notification — no response expected
        when "ping"
          send_result(id, {})
        when "tools/list"
          send_result(id, { tools: @dispatcher.list })
        when "tools/call"
          handle_tools_call(id, params)
        else
          send_error(id, -32_601, "method not found: #{method}") unless id.nil?
        end
      end

      def handle_tools_call(id, params)
        name      = params[:name]
        arguments = params[:arguments] || {}
        text, is_error = @dispatcher.call(name, arguments)
        send_result(id, { content: [{ type: "text", text: text }], isError: is_error })
      end

      def send_result(id, result)
        return if id.nil? # would-be response to a notification — drop it

        write(jsonrpc: "2.0", id: id, result: result)
      end

      def send_error(id, code, message)
        write(jsonrpc: "2.0", id: id, error: { code: code, message: message })
      end

      def write(payload)
        @out.puts(JSON.generate(payload))
      end

      def shutdown
        @session.close if @session&.open?
        warn "[mud_manager/mcp] server shutting down"
      end
    end
  end
end
