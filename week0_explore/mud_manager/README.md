# MudManager

The MudManager has the following responsibilities:

- manages long-lived telnet sessions
- manages the multi-step process of logging back in
- provides generic primitives for MUD commands
- (since 0.2.0) exposes gameplay as MCP tools via `MudManager::Mcp`, so
  any MCP-capable client — in any language — gets full MUD gameplay
  without requiring this gem, a telnet client, or CircleMUD command
  syntax itself. `Session`/`Primitives` stay the single owner of the
  actual connection either way; the MCP layer is just another consumer
  of them, in-process with the code above instead of a separate gem.

## Build the Gem

From this directory:

```sh
gem build mud_manager.gemspec
gem install ./mud_manager-0.3.0.gem
```

Expected output:

```text
MudManager
```

## Uninstall

```sh
gem uninstall mud_manager
```

## Examples

Test the live session directly (`Session`/`Primitives`, no MCP):

```sh
MUD_NAME=YourCharacterName MUD_PASSWORD=yourpassword ruby examples/live_session_test.rb
```

Run as an MCP server and drive it with the bundled client
(`examples/mcp_client_demo.rb`) — this is what `Boukensha::Tools::Mcp`
(`week1_baseline/ruby/10_standard_tool_library`) spawns under the hood:

```sh
MUD_NAME=YourCharacterName MUD_PASSWORD=yourpassword ruby examples/mcp_client_demo.rb
```

Or run the server standalone, once installed, and drive it by hand with
raw JSON-RPC on stdin:

```sh
MUD_NAME=YourCharacterName MUD_PASSWORD=yourpassword mud_manager --mcp
```
