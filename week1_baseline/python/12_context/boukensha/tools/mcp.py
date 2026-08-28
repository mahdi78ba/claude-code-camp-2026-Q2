"""The generic bridge between Boukensha's Registry and any number of
configured MCP servers.

Python port of Boukensha::Tools::Mcp. Doesn't know what any server's tools
actually do — MUD gameplay is just one entry in `servers`, not a special
case.

No `mud_manager` package exists for Python to import an MCP client from
(Ruby's Tools::Mcp requires "mud_manager/mcp/client", a class from a
separate teaching gem), so this module carries its own minimal client:
spawn a command, speak newline-delimited JSON-RPC 2.0 over its
stdin/stdout. Mirrors MudManager::Mcp::Client
(week0_explore/mud_manager/lib/mud_manager/mcp/client.rb) — same four
calls (handshake, list_tools, call_tool, close), same wire format,
talking to the exact same server process (e.g. `mud_manager --mcp`,
unchanged by this port; the server side is not reimplemented here).

Usage:

    boukensha.tools.mcp.register(registry, servers=[
        {"name": "mud", "command": ["mud_manager", "--mcp"], "env": {...}}
    ])

Returns [{"name":, "client":}, ...] — one entry per server that actually
started. A server that fails to spawn, hangs past the handshake timeout,
or errors is warned about and simply absent from the result, so one bad
server doesn't take any other configured server down with it.
"""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading

HANDSHAKE_TIMEOUT = 10  # seconds

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "boukensha-mcp-client", "version": "1.0"}


class McpError(Exception):
    pass


class _McpClient:
    """Minimal MCP client: spawn, handshake, tools/list, tools/call, close.

    Deliberately synchronous (one request in flight at a time) — that's
    all a single interactive agent needs.
    """

    def __init__(self, *, command, env=None):
        # Additive env, matching Ruby's Open3.popen2(env, *command) — a bare
        # env=env here would *replace* the child's entire environment
        # (including PATH), breaking a bare executable name like
        # "mud_manager" in `command`.
        full_env = {**os.environ, **(env or {})}
        self._proc = subprocess.Popen(
            command, env=full_env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self._next_id = 0

    def handshake(self):
        result = self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        })
        self._notify("notifications/initialized")
        return result.get("serverInfo")

    def list_tools(self):
        return self._request("tools/list")["tools"]

    def call_tool(self, name, arguments=None):
        """Returns (text, is_error)."""
        result = self._request("tools/call", {"name": str(name), "arguments": arguments or {}})
        content = result.get("content") or []
        text = content[0].get("text", "") if content else ""
        return text, result.get("isError") is True

    def close(self):
        """Graceful shutdown: closing stdin signals the server's own read
        loop to see EOF and exit on its own; wait() gives it a couple of
        seconds to do so before killing. Only safe to call once no other
        thread can still be blocked reading self._proc.stdout — see
        kill() below for the case where that isn't true.
        """
        if self._proc.stdin and not self._proc.stdin.closed:
            self._proc.stdin.close()
        if self._proc.stdout and not self._proc.stdout.closed:
            self._proc.stdout.close()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()

    def kill(self):
        """Best-effort forceful cleanup for a client whose handshake never
        completed (e.g. the process hung, or the handshake timed out
        while a background thread — see _run_with_timeout — was still
        blocked in a read on this client's stdout).

        Deliberately does NOT close self._proc.stdout/.stdin the way
        close() does: a file object's close() blocks until it can take
        an internal lock that a concurrent blocking read on the same
        object is holding for the duration of that read — so calling
        close() here, while that background thread might still be stuck
        in readline(), would deadlock this thread too. Killing the
        process instead makes the OS deliver EOF to that blocked read
        (once the child actually dies), unblocking it independently,
        without this thread having to touch the same file object.
        """
        try:
            self._proc.kill()
        except OSError:
            pass

    # ---------- private -----------------------------------------------

    def _request(self, method, params=None):
        self._next_id += 1
        request_id = self._next_id
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        response = self._read_until_id(request_id)
        if "error" in response:
            err = response["error"]
            raise McpError(f"{err['message']} (code {err['code']})")
        return response["result"]

    def _notify(self, method, params=None):
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _write(self, payload):
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

    def _read_until_id(self, request_id):
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise McpError("server closed the connection")
            message = json.loads(line)
            if message.get("id") == request_id:
                return message


def register(registry, *, servers):
    return [r for r in (_register_one(registry, server) for server in servers) if r is not None]


def _register_one(registry, server):
    name = server.get("name")
    command = server.get("command") or None
    if not command:
        # Unlike MudManager::Mcp::Client (which falls back to its own
        # bundled `mud_manager --mcp` default), this client has no
        # gem-equivalent package to default to, so an empty command is a
        # hard configuration error rather than a silent MUD-flavored
        # default. Every server this repo actually configures
        # (settings.yaml's mcp_servers:) always sets command: explicitly.
        print(
            f"[boukensha] MCP server {name!r} failed to start: "
            f"ValueError: no command configured (no default, unlike Ruby's mud_manager fallback)",
            file=sys.stderr,
        )
        return None

    client = None
    try:
        # Spawning the client (subprocess creation) is inside this same
        # try/except, not just the handshake — mirrors Ruby's
        # register_one, where `Client.new` and the handshake are both
        # covered by one method-level `rescue StandardError`. A bad
        # command (ENOENT) is exactly as much "this server failed to
        # start" as a handshake timeout is; it must not raise past this
        # function.
        client = _McpClient(command=command, env=server.get("env") or {})
        _run_with_timeout(HANDSHAKE_TIMEOUT, lambda: _do_handshake(registry, server, client))
    except Exception as e:  # noqa: BLE001 - mirrors Ruby's rescue StandardError
        print(f"[boukensha] MCP server {name!r} failed to start: {type(e).__name__}: {e}", file=sys.stderr)
        if client is not None:
            client.kill()
        return None

    atexit.register(client.close)
    return {"name": name, "client": client}


def _run_with_timeout(seconds, fn):
    """Run fn() in a helper thread, raising TimeoutError if it outlives
    `seconds`. Python has no single-call equivalent of Ruby's
    Timeout.timeout that works portably across platforms and threads
    (signal.alarm is POSIX/main-thread-only) — a thread with a
    timeout-bounded join() interrupts the *caller's* wait, in the same
    spirit as Ruby's Timeout, without those restrictions.
    """
    result = {}

    def target():
        try:
            result["value"] = fn()
        except Exception as e:  # noqa: BLE001
            result["error"] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise TimeoutError(f"MCP handshake exceeded {seconds}s")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _do_handshake(registry, server, client):
    client.handshake()
    for tool in client.list_tools():
        _register_proxy_tool(registry, server.get("name"), client, tool, server.get("prefix"))


def _register_proxy_tool(registry, server_name, client, tool, prefix):
    name = f"{prefix}_{tool['name']}" if prefix else tool["name"]

    if registry.registered(name):
        print(
            f"[boukensha] MCP server {server_name!r}: tool {name!r} collides with an "
            f"already-registered tool — skipped (use prefix: on this server's config "
            f"entry to disambiguate)",
            file=sys.stderr,
        )
        return

    def call(**kwargs):
        text, _is_error = client.call_tool(tool["name"], kwargs)
        return text

    registry.tool(
        name,
        description=tool.get("description"),
        parameters=tool["inputSchema"]["properties"],
        block=call,
    )
