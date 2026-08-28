require "yaml"
require "dotenv"
require "pathname"

module Boukensha
  class Config
    # The .boukensha config directory is resolved in this order:
    #   1. BOUKENSHA_DIR environment variable (set before loading .env)
    #   2. ~/.boukensha  (default)
    DEFAULT_DIR = File.join(Dir.home, ".boukensha").freeze

    attr_reader :dir, :settings, :system_prompt

    def initialize
      @dir = resolve_dir
      load_env
      @settings     = load_settings
      @system_prompt = load_system_prompt
    end

    # ---------- provider --------------------------------------------------

    def provider_type
      dig(:tasks, :player, :provider) || "anthropic"
    end

    def model
      dig(:tasks, :player, :model) || "claude-haiku-4-5"
    end

    # ---------- system prompt ---------------------------------------------

    def system_override?
      dig(:system, :override) == true
    end

    # ---------- MCP servers -------------------------------------------------

    # [{name:, command: [...], env: {...}, prefix:}, ...] from settings.yaml's
    # mcp_servers: list. An env value of the literal form "$VAR" resolves
    # against ENV (already populated from .env by load_env) instead of being
    # taken as a literal string — settings.yaml is documented above as
    # commit-safe, so a real credential should never have to sit in it as
    # plaintext just because this file is the only place to configure an MCP
    # server's connection details.
    def mcp_servers
      (dig(:mcp_servers) || []).map do |entry|
        {
          name:    entry["name"],
          command: Array(entry["command"]),
          env:     resolve_env(entry["env"] || {}),
          prefix:  entry["prefix"]
        }
      end
    end

    # ---------- agent limits ----------------------------------------------
    # Static per-turn circuit breakers, read where the agent is constructed.
    # A value of 0 or nil means "disabled" (no ceiling) — useful for debugging.

    def agent_max_iterations
      v = dig(:agent, :max_iterations)
      v.nil? ? 25 : Integer(v)
    end

    def agent_max_output_tokens
      v = dig(:agent, :max_output_tokens)
      v.nil? ? 1024 : Integer(v)
    end

    def agent_max_turn_tokens
      v = dig(:agent, :max_turn_tokens)
      v.nil? ? 60_000 : Integer(v)
    end

    def agent_compaction_threshold
      v = dig(:agent, :compaction_threshold)
      v.nil? ? 0.85 : Float(v)
    end

    # ---------- low-level helpers -----------------------------------------

    # Fetch a nested key path from settings, e.g. dig(:provider, :model)
    def dig(*keys)
      keys.reduce(@settings) do |node, key|
        case node
        when Hash then node[key.to_s] || node[key.to_sym]
        else nil
        end
      end
    end

    def to_s
      "#<Boukensha::Config dir=#{@dir} provider=#{provider_type} model=#{model}>"
    end

    def inspect = to_s

    private

    def resolve_dir
      raw = ENV.fetch("BOUKENSHA_DIR", nil) || DEFAULT_DIR
      Pathname.new(raw).expand_path.to_s
    end

    def load_env
      env_file = File.join(@dir, ".env")
      if File.exist?(env_file)
        Dotenv.load(env_file)
      end
    end

    def load_settings
      settings_file = File.join(@dir, "settings.yaml")
      if File.exist?(settings_file)
        YAML.safe_load(File.read(settings_file)) || {}
      else
        {}
      end
    end

    def resolve_env(raw)
      raw.transform_values { |v| v.is_a?(String) && v.start_with?("$") ? ENV[v[1..]] : v }
    end

    # Resolves the system prompt. When the player task opts into a prompt
    # override (tasks.player.prompt_override.system: true), the task-scoped
    # file prompts/player/system.md wins; otherwise (and as a fallback) the
    # flat prompts/system.md is used. Returns nil when neither exists.
    def load_system_prompt
      if dig(:tasks, :player, :prompt_override, :system) == true
        task_file = File.join(@dir, "prompts", "player", "system.md")
        return File.read(task_file).strip if File.exist?(task_file)
      end

      system_file = File.join(@dir, "prompts", "system.md")
      File.exist?(system_file) ? File.read(system_file).strip : nil
    end
  end
end
