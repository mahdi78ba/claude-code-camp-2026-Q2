require "json"
require "open3"
require "timeout"
require_relative "version"
require_relative "server"

module MudManager
  module Mcp
    # A minimal MCP client: spawns an MCP server as a subprocess and drives it
    # over stdio with the same newline-delimited JSON-RPC 2.0 the Server
    # speaks. Deliberately synchronous (one request in flight at a time) —
    # that's all a single interactive agent needs, and it doubles as the
    # reference implementation for what an MCP client in any other language
    # has to do: spawn, handshake, tools/list, tools/call, close.
    class Client
      class Error < StandardError; end

      # The installed executable, invoked directly (relies on `gem install`
      # having put a proper stub for it on $PATH) — not `ruby <path-to-script>`,
      # which would require knowing where this gem happens to be installed.
      DEFAULT_COMMAND = ["mud_manager", "--mcp"].freeze

      def initialize(command: DEFAULT_COMMAND, env: {})
        @stdin, @stdout, @stderr, @wait_thread = Open3.popen3(env, *command)
        @next_id = 0

        # The server logs normal operational messages to its own stderr
        # (e.g. "server shutting down") via `warn`. With Open3.popen2 that
        # passed straight through to this process's own terminal for free;
        # popen3 hands us a private pipe instead, so without this thread
        # those messages — and any crash backtrace — would just sit in the
        # pipe, unread and invisible, until something (nothing does, during
        # normal operation) drained it. Forward every line live, keeping a
        # copy so a mid-handshake crash can still report it below.
        @stderr_lines = []
        @stderr_mutex = Mutex.new
        @stderr_thread = Thread.new do
          @stderr.each_line do |line|
            @stderr_mutex.synchronize { @stderr_lines << line }
            warn line.chomp
          end
        rescue IOError
          # @stderr was closed out from under this thread by #close.
        end
      end

      # Perform the MCP handshake (initialize request, then the initialized
      # notification). Returns the server's serverInfo.
      def handshake
        result = request("initialize", {
          protocolVersion: Server::PROTOCOL_VERSION,
          capabilities: {},
          clientInfo: { name: "mud-manager-mcp-client", version: VERSION }
        })
        notify("notifications/initialized")
        result[:serverInfo]
      end

      def list_tools
        request("tools/list")[:tools]
      end

      # Returns [text, is_error].
      def call_tool(name, arguments = {})
        result = request("tools/call", { name: name.to_s, arguments: arguments })
        [result.dig(:content, 0, :text).to_s, result[:isError] == true]
      end

      def close
        @stdin.close unless @stdin.closed?
        @stdout.close unless @stdout.closed?
        @stderr_thread&.join(2)
        @stderr.close unless @stderr.closed?
        @wait_thread&.join(2)
      end

      private

      def request(method, params = {})
        id = (@next_id += 1)
        write(jsonrpc: "2.0", id: id, method: method, params: params)
        response = read_until_id(id)
        raise Error, "#{response[:error][:message]} (code #{response[:error][:code]})" if response[:error]

        response[:result]
      end

      def notify(method, params = {})
        write(jsonrpc: "2.0", method: method, params: params)
      end

      def write(payload)
        @stdin.puts(JSON.generate(payload))
        @stdin.flush
      end

      def read_until_id(id)
        loop do
          line = @stdout.gets
          raise Error, server_died_message if line.nil?

          message = JSON.parse(line, symbolize_names: true)
          return message if message[:id] == id
          # anything else (e.g. a stray notification) is skipped
        end
      end

      # @stdout hitting EOF just means the process ended before answering —
      # it doesn't say why. The real reason (a Ruby exception backtrace, a
      # connection error, a missing env var) almost always went to the
      # process's stderr instead, which a caller has no other way to see:
      # nothing else in this class exposes it, and a plain "server closed
      # the connection" was leaving every real cause looking identical.
      def server_died_message
        status = begin
          Timeout.timeout(2) { @wait_thread&.value }
        rescue Timeout::Error
          nil
        end
        # Give the stderr-forwarding thread a beat to drain whatever the
        # dying process last wrote before we read back what it collected.
        @stderr_thread&.join(2)
        stderr_output = @stderr_mutex.synchronize { @stderr_lines.join }.strip

        parts = ["server closed the connection"]
        parts << "exit status #{status.exitstatus}" if status
        parts << "stderr: #{stderr_output}" unless stderr_output.empty?
        parts.join(" — ")
      end
    end
  end
end
