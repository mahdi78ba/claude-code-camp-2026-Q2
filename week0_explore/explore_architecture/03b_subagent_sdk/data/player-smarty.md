# Player State — Smarty

_Last updated: 2026-08-02 (status-only check-in, fifth session — hunger/
thirst check only, no movement). Login works
fine. **IMPORTANT:**
`scripts/mud.py` defaults to character `dummy` (DEFAULT_NAME="dummy") — must
pass `--name Smarty --password helloworld` explicitly or it logs into the
wrong character!_

## Character Information
- **Name**: Smarty
- **Class**: Magic User (Mage) — confirmed via `score`: "Smarty the
  Apprentice of Magic (level 1)".
- **Level**: 1
- **Experience**: 1 exp / needs 2499 more to reach level 2
- **Gold**: 0 gold coins
- **Quest Points**: 0, not on a quest, 0 quests completed

## Stats (from `score`, 2026-08-02 later session — reconnect, confirmed)
- **HP**: 16/16
- **Mana**: 100/100
- **Movement**: 83/83 (full — regenerated since last session)
- **Armor Class**: 80/10
- **Alignment**: 0
- **Not hungry/thirsty — re-confirmed 2026-08-02 (fifth session)**: `score`
  output has no "You are hungry"/"You are thirsty" lines (full text: age,
  hit/mana/move, AC, alignment, exp/gold/qp, exp-to-next-level, quests,
  playtime, title/level, "You are standing."). tbaMUD only prints those
  condition lines when hunger/thirst is actually low, so their absence means
  Smarty is currently fine on both counts. No `condition` command tried yet
  (would give exact numeric hunger/thirst/drunk values if needed later).

## Current Location
- **Room**: **The Entrance To The Mages' Guild** — "The entrance hall to this
  guild is a small, poor lighted room." Exits: **n, s**. Has an ATM. A
  sorcerer is guarding the entrance (present); a Peacekeeper was here too but
  left north during this check. No hostility. `s` leads further into the
  guild, unexplored.
- Character resumed here on reconnect (position persists between sessions).

## Inventory
- **Confirmed empty**: "You are carrying: Nothing."

## Equipment
- **Confirmed empty**: "You are using: Nothing." (fully naked, AC 80/10 base)

## Skills & Abilities
- Not yet checked — run `practices`/`spells` next session now that the
  Mages' Guild has been located (relevant for a mage to learn/practice
  spells there).

## Status
- Standing, not fighting, no visible status effects (hungry/thirsty not yet
  checked via `score`, but nothing flagged).

## Current Goals
1. **Done this session (2026-08-02, fifth session, hunger/thirst check
   only)**: reconnected, ran `look` + `score` only, no movement. Confirmed
   not hungry/not thirsty (score shows no condition warning lines). Stats
   unchanged: 16/16 HP, 100/100 mana, 83/83 movement, same room (Entrance To
   The Mages' Guild), same sorcerer present, no hostility.
1b. **Done earlier (2026-08-02, fourth session, hunger/thirst check
   only)**: reconnected, ran `score` + `look` only, no movement. Confirmed
   not hungry/not thirsty (score shows no condition warning lines). Stats
   unchanged: 16/16 HP, 100/100 mana, 83/83 movement, same room (Entrance To
   The Mages' Guild), same sorcerer present, no hostility.
2. **Done earlier (2026-08-02, third session, status-only check-in)**:
   reconnected, ran `look` + `score` only, no movement. Location, HP/mana/
   movement, level/exp/gold all unchanged from prior session (confirms
   nothing happened to the character while idle — still 16/16 HP, 100/100
   mana, 83/83 movement, same room).
2. **Next**: go `s` from the guild entrance to see what's further inside
   (likely the guildmaster/practice room); run `practices` and `spells` to
   see what a level-1 mage already knows and what can be learned.
3. Longer-term: gain exp/gold, learn spells, general exploration — no
   specific quest assigned by the user beyond "reach the Mages' Guild"
   (achieved) and ongoing demonstration of a second concurrent sub-agent
   session alongside `dummy`.

## Notes
- This character was created manually by the user via `nc localhost 4000`
  on 2026-08-02. Exists to demonstrate **two concurrent sub-agent sessions**
  (this one, and `dummy`'s) playing the same server without sharing state.
- Do **not** confuse this file with `data/player.md` (that one is `dummy`'s).
- Password: `helloworld`.
- Each `mud.py` run reconnects; character resumes in the last room, so the
  room recorded above is the starting point of the next session.
