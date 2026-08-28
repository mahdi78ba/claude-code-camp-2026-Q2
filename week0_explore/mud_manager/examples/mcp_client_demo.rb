#!/usr/bin/env ruby
# frozen_string_literal: true
#
# Drives the bundled MCP server as a client, over stdio, against a live
# CircleMUD. Everything below the `require "mud_manager/mcp/client"` line
# is generic MCP: no MudManager::Session, no telnet, no CircleMUD command
# syntax appears here at all — that's the point of putting the server
# between this file and the MUD.
#
#   MUD_NAME=dummy MUD_PASSWORD=helloworld ruby examples/mcp_client_demo.rb

$LOAD_PATH.unshift File.expand_path("../lib", __dir__)
require "mud_manager/mcp/client"

client = MudManager::Mcp::Client.new(env: {
  "MUD_HOST"     => ENV.fetch("MUD_HOST", "localhost"),
  "MUD_PORT"     => ENV.fetch("MUD_PORT", "4000"),
  "MUD_NAME"     => ENV.fetch("MUD_NAME", "dummy"),
  "MUD_PASSWORD" => ENV.fetch("MUD_PASSWORD", "helloworld")
})

server_info = client.handshake
puts "connected to #{server_info[:name]} v#{server_info[:version]}"

tools = client.list_tools
puts "#{tools.size} tools available: #{tools.map { |t| t[:name] }.join(', ')}"
puts

text, = client.call_tool("look")
puts "look ->\n#{text}\n"

text, = client.call_tool("check", kind: "score")
puts "check score ->\n#{text}\n"

client.close
