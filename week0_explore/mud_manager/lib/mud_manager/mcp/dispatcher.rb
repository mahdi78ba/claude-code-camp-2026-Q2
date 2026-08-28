module MudManager
  module Mcp
    # Holds the MCP tool catalog (name -> description/schema/handler) and
    # dispatches calls into it. This is the one piece both the Server (talks
    # MCP on the wire) and Tools (knows about MudManager::Session/Primitives)
    # share — Server never sees MudManager, and Tools never sees JSON-RPC.
    class Dispatcher
      Tool = Struct.new(:name, :description, :input_schema, :handler, keyword_init: true)

      def initialize
        @tools = {}
      end

      # Register one tool. `parameters` is a Hash of {name => {type:,
      # description:}} — the exact shape Boukensha's registry.tool
      # `parameters:` argument already uses, so porting a tool definition here
      # is copy/paste, not translation. Which parameters are required is read
      # off the handler block's own keyword arguments (a required Ruby keyword
      # -> a required MCP parameter) — one source of truth for required-ness,
      # not a second hash to keep in sync by hand.
      def tool(name, description:, parameters: {}, &handler)
        required = handler.parameters.select { |type, _| type == :keyreq }.map { |_, n| n.to_s }
        schema = { type: "object", properties: parameters, required: required }
        @tools[name.to_s] = Tool.new(name: name.to_s, description: description,
                                      input_schema: schema, handler: handler)
      end

      def tool?(name)
        @tools.key?(name.to_s)
      end

      # The tools/list result: [{name:, description:, inputSchema:}, ...]
      def list
        @tools.values.map do |t|
          { name: t.name, description: t.description, inputSchema: t.input_schema }
        end
      end

      # Invoke a registered tool by name. Returns [text, is_error] — never
      # raises, so the caller (the MCP Server) can always send a well-formed
      # tools/call response, even for an unknown tool, missing/extra
      # arguments, or a handler that raises.
      def call(name, arguments = {})
        tool = @tools[name.to_s]
        return ["error: unknown tool #{name.inspect}", true] unless tool

        begin
          [tool.handler.call(**symbolize(arguments)).to_s, false]
        rescue ArgumentError => e
          ["error: #{e.message}", true]
        rescue StandardError => e
          ["error: #{e.class}: #{e.message}", true]
        end
      end

      private

      def symbolize(hash)
        hash.each_with_object({}) { |(k, v), h| h[k.to_sym] = v }
      end
    end
  end
end
