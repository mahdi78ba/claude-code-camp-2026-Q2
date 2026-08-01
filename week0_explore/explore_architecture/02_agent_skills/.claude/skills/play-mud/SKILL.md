---
name: play-mud
description: Connect to and play the CircleMUD server with autonomous agent assistance
category: utility
---

# Play MUD Skill

This skill enables Claude to connect to and play the CircleMUD/tbaMUD server with
agent-assisted interaction, keeping persistent memory between sessions.

## Features

- Connect to the MUD server and log in as the existing character
- Run batches of commands and read the transcript back
- Maintain player and world memory across sessions in `data/`
- Provide autonomous agent assistance for gameplay

## Usage

Run a batch of commands (the mode to use when the agent is driving):

```bash
python3 scripts/mud.py --cmds "look;score;inventory;n;look"
```

Other flags:

| Flag            | Meaning                                                   |
| --------------- | --------------------------------------------------------- |
| `--interactive` | Human REPL instead of batch                                |
| `--no-quit`     | Stay in-game after the batch instead of sending `quit`     |
| `--delay`       | Seconds between commands (default `0.3`)                   |
| `--host/--port` | Override `localhost:4000`                                  |

Each command's output is printed under a `===== > <command> =====` header, so
the transcript can be read back turn by turn.

## Connecting & Login

Connect to `localhost:4000` and log in as the **existing main character — do NOT create a new one:**

| Setting  | Value        |
| -------- | ------------ |
| Host     | `localhost`  |
| Port     | `4000`       |
| Name     | `dummy`      |
| Password | `helloworld` |

`mud.py` performs this login automatically: name → password → blank line at
*"PRESS RETURN"* → `1` at *"Make your choice:"*. It aborts rather than creating
a character if the prompts do not look right.

Important quirks:
- The server runs a telnet **"Attempting to Detect Client"** negotiation on
  connect. `mud.py` answers it (refusing all options); without an answer the
  name prompt never arrives.
- The **first input after connecting can take ~20 seconds** to register
  (ident/DNS lookup) — wait for it, don't resend.
- `dummy` is a **mortal Warrior**. Navigate with normal movement (`n/s/e/w/u/d`);
  do **not** use immortal commands like `goto`.
- If login lands in the *"Immortal Board Room"* or shows 500 HP, you are on a
  blank/re-seeded world — stop and report it instead of creating a character.
- Each batch run reconnects. The character keeps its room between runs, so
  **the position recorded in `data/player.md` is where the next run starts.**

## Memory

Two files under `data/` are the skill's memory between sessions. If something is
not written down there, it is gone next time.

- `data/player.md` — the character: identity, stats, equipment, inventory,
  current location, goals, and status.
- `data/world.md` — the world: rooms visited, exits between them, navigation
  routes, NPCs, shops/guilds, and observations worth remembering.

### The loop

Every session, in this order:

1. **Read** `data/player.md` and `data/world.md` before sending any command.
2. **Observe** — start the batch with `look` (and `score` if stats matter).
3. **Act** — take the next step toward the goals listed in `player.md`.
4. **Update** both files with what changed and what was learned, *before*
   ending the turn. Update as you go rather than batching at the end, so
   progress survives an interrupted session.

### What to record

In `player.md`: level/XP/gold, HP-mana-movement, equipment and inventory,
**exact current room**, current goals (ordered, with the next concrete action),
and status effects (hungry, thirsty, wounded).

In `world.md`: every room by its exact in-game name, the exits it reports and
where each one leads, **which exits are still unexplored**, routes between
important places as command strings (e.g. `w, n, n`), mobs met and whether they
attacked, and anything that killed you or nearly did.

### Rules

- **The game is the source of truth.** If a memory file disagrees with what the
  server just printed, trust the server and correct the file.
- **Record exact room names** — several different rooms share the name
  "The Dark Passageway", so disambiguate them by their exits and neighbours.
- Note failures too (`Alas, you cannot go that way...`) — a wrong guess written
  down once saves repeating it.
- Keep entries terse. These files are re-read in full every session.

## Data Files

- `data/player.md` - Current player state, location, and goals
- `data/world.md` - Room map, routes, and world observations

## Related Skills

- None yet
