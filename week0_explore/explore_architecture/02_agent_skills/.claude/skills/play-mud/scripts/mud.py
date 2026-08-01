#!/usr/bin/env python3
"""
CircleMUD Agent-Assisted Player
Connects to CircleMUD server and enables agent-assisted gameplay.

Two modes:
  - Batch (agent-driven):  mud.py --cmds "look;score;inventory"
  - Interactive (human):   mud.py --interactive
"""

import argparse
import socket
import sys
import time
import re
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4000
DEFAULT_NAME = "dummy"
DEFAULT_PASSWORD = "helloworld"

class MUDConnection:
    """Manages connection to CircleMUD server"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.connected = False
        self.last_response = ""
        self.state_dir = Path(__file__).parent.parent / "data"
        self.state_dir.mkdir(exist_ok=True)

    def connect(self) -> bool:
        """Establish connection to MUD server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"[+] Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Close MUD connection"""
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.connected = False
        print("[*] Disconnected from server")

    def send_command(self, command: str) -> bool:
        """Send command to MUD server"""
        if not self.connected:
            return False
        try:
            self.socket.sendall(f"{command}\n".encode('utf-8'))
            return True
        except Exception as e:
            print(f"[-] Send failed: {e}")
            self.connected = False
            return False

    def _handle_telnet(self, data: bytes) -> bytes:
        """Strip telnet IAC sequences and refuse every option.

        The server runs a "Detect Client" negotiation on connect. If nobody
        answers it, the name prompt never arrives — so answer DO->WONT and
        WILL->DONT and let the login proceed.
        """
        IAC, SE, SB, WILL, WONT, DO, DONT = 255, 240, 250, 251, 252, 253, 254
        out = bytearray()
        reply = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            if b != IAC:
                out.append(b)
                i += 1
                continue
            if i + 1 >= len(data):
                break
            cmd = data[i + 1]
            if cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= len(data):
                    break
                opt = data[i + 2]
                if cmd == DO:
                    reply += bytes([IAC, WONT, opt])
                elif cmd == WILL:
                    reply += bytes([IAC, DONT, opt])
                i += 3
            elif cmd == SB:
                end = data.find(bytes([IAC, SE]), i)
                i = len(data) if end == -1 else end + 2
            else:
                i += 2

        if reply and self.connected:
            try:
                self.socket.sendall(bytes(reply))
            except Exception:
                pass
        return bytes(out)

    def read_until(self, patterns: List[str], timeout: float = 25.0, settle: float = 0.6) -> str:
        """Read until one of `patterns` appears, or the stream goes quiet.

        The first input after connecting can take ~20s (ident/DNS lookup), so
        the default timeout is generous. `settle` is how long the stream must
        be silent before we call a response complete when no pattern matches;
        pass `settle=None` to wait the full timeout for a pattern instead.
        """
        if not self.connected:
            return ""

        buf = ""
        deadline = time.time() + timeout
        last_data = time.time()
        self.socket.settimeout(0.4)

        while time.time() < deadline:
            try:
                raw = self.socket.recv(4096)
                if not raw:
                    self.connected = False
                    break
                buf += self._handle_telnet(raw).decode('utf-8', errors='replace')
                last_data = time.time()
                if patterns and any(p in buf for p in patterns):
                    # Let the rest of the burst arrive.
                    time.sleep(0.3)
                    try:
                        buf += self._handle_telnet(self.socket.recv(8192)).decode('utf-8', errors='replace')
                    except Exception:
                        pass
                    break
            except socket.timeout:
                if settle is not None and buf and time.time() - last_data >= settle:
                    break
            except Exception as e:
                print(f"[-] Receive failed: {e}")
                self.connected = False
                break

        self.last_response = buf
        return buf

    def execute_command(self, command: str, timeout: float = 6.0) -> str:
        """Send a game command and return the server's response"""
        if not self.send_command(command):
            return ""
        return self.read_until([], timeout=timeout, settle=0.6)

    def login(self, name: str = DEFAULT_NAME, password: str = DEFAULT_PASSWORD) -> bool:
        """Log in as the existing character. Never creates a new one."""
        banner = self.read_until(["By what name", "name do you wish"], timeout=40.0, settle=None)
        print(banner, end="")

        if "By what name" not in banner and "name do you wish" not in banner:
            print("[-] Never saw the name prompt; aborting login.")
            return False

        resp = self.send_and_read(name, ["Password:", "already a name", "new character"], timeout=30.0)
        if "Password:" not in resp:
            print("[-] Unexpected reply to name; refusing to create a character.")
            return False

        resp = self.send_and_read(password, ["PRESS RETURN", "Wrong password", "password"], timeout=25.0)
        if "Wrong password" in resp:
            print("[-] Wrong password.")
            return False

        resp = self.send_and_read("", ["Make your choice:"], timeout=25.0)
        resp = self.send_and_read("1", ["<", "$"], timeout=25.0)

        if "Immortal Board Room" in resp:
            print("[!] Landed in the Immortal Board Room — the world may have been re-seeded. Stopping.")
            return False

        print("[+] Logged in as %s" % name)
        return True

    def send_and_read(self, text: str, patterns: List[str], timeout: float = 15.0) -> str:
        """Send text and echo the response (used during login)"""
        self.send_command(text)
        resp = self.read_until(patterns, timeout=timeout)
        print(resp, end="")
        return resp

class MUDParser:
    """Parses MUD responses and extracts meaningful information"""

    PROMPT_RE = re.compile(r'<(\d+)H (\d+)M (\d+)V|<(\d+)/(\d+)h?p? ')

    @staticmethod
    def parse_prompt(response: str) -> dict:
        """Parse CircleMUD prompt: `< 25H 100M 38V >` or `<25/25 100/100 38/84>`"""
        m = re.search(r'<\s*(\d+)H\s+(\d+)M\s+(\d+)V', response)
        if m:
            return {'hp': int(m.group(1)), 'mana': int(m.group(2)), 'movement': int(m.group(3))}

        m = re.search(r'<(\d+)/(\d+) (\d+)/(\d+) (\d+)/(\d+)>', response)
        if m:
            return {
                'hp': int(m.group(1)), 'max_hp': int(m.group(2)),
                'mana': int(m.group(3)), 'max_mana': int(m.group(4)),
                'movement': int(m.group(5)), 'max_movement': int(m.group(6)),
            }
        return {}

    @staticmethod
    def extract_room_description(response: str) -> Tuple[str, List[str], List[str]]:
        """Extract room name, items, and exits from response"""
        lines = [l.rstrip() for l in response.split('\n')]
        room_name = ""
        items: List[str] = []
        exits: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not room_name and stripped and not stripped.startswith('<') and not stripped.startswith('['):
                room_name = stripped
            if 'You see:' in line or 'lying here' in line or 'is here' in line:
                items.append(stripped)
            if 'Exits:' in line or '[ Exits:' in line:
                exits = re.findall(
                    r'\b(north|south|east|west|up|down|northeast|northwest|southeast|southwest|[NSEWUD])\b',
                    line)

        return room_name, items, exits

    @staticmethod
    def is_combat_mode(response: str) -> bool:
        """Check if player is in combat"""
        return 'You are fighting' in response or 'attacks you!' in response

def run_batch(mud: MUDConnection, commands: List[str], delay: float) -> None:
    """Run a list of commands and print a labelled transcript for the agent."""
    for cmd in commands:
        cmd = cmd.strip()
        if not cmd:
            continue
        print(f"\n===== > {cmd} =====")
        resp = mud.execute_command(cmd)
        print(resp, end="")
        if MUDParser.is_combat_mode(resp):
            print("\n[!] Combat detected.")
        if delay:
            time.sleep(delay)
    print(f"\n===== session end {datetime.now().isoformat(timespec='seconds')} =====")

def run_interactive(mud: MUDConnection) -> None:
    """Human-driven REPL."""
    while mud.connected:
        try:
            command = input("> ").strip()
            if not command:
                continue
            if command.lower() in ['quit', 'exit']:
                mud.send_command("quit")
                break
            print(mud.execute_command(command), end="")
        except KeyboardInterrupt:
            print("\n[*] Interrupted. Type 'quit' to exit properly.")
            break
        except EOFError:
            break

def main():
    ap = argparse.ArgumentParser(description="CircleMUD agent-assisted player")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--name", default=DEFAULT_NAME)
    ap.add_argument("--password", default=DEFAULT_PASSWORD)
    ap.add_argument("--cmds", help="Semicolon-separated commands to run after login")
    ap.add_argument("--delay", type=float, default=0.3, help="Pause between commands")
    ap.add_argument("--interactive", action="store_true", help="Human REPL instead of batch")
    ap.add_argument("--no-quit", action="store_true", help="Leave the character in-game (link-dead) instead of quitting")
    args = ap.parse_args()

    print("CircleMUD Agent-Assisted Player")
    print("================================")

    mud = MUDConnection(args.host, args.port)
    if not mud.connect():
        return 1

    try:
        if not mud.login(args.name, args.password):
            return 1

        if args.interactive:
            run_interactive(mud)
        elif args.cmds:
            run_batch(mud, args.cmds.split(";"), args.delay)
        else:
            run_batch(mud, ["look", "score"], args.delay)

        if not args.no_quit and not args.interactive:
            mud.send_command("quit")
            time.sleep(0.4)
    finally:
        mud.disconnect()

    return 0

if __name__ == "__main__":
    sys.exit(main())
