# Player State — Smarty

_Last updated: 2026-08-02. Login now works fine — the earlier "BLOCKED /
character does not exist" note below is **stale/resolved**: the character
exists on the server (was presumably finished being created after that
session), and `scripts/mud.py`'s `login()` already handles the
`Did I get that right (Y/N)?` prompt natively. No script changes were needed
this session._

## Character Information
- **Name**: Smarty
- **Class**: Magic User (Mage) — confirmed via `score`: "Smarty the
  Apprentice of Magic (level 1)".
- **Level**: 1
- **Experience**: 1 exp / needs 2499 more to reach level 2
- **Gold**: 0 gold coins
- **Quest Points**: 0, not on a quest, 0 quests completed

## Stats (from `score`, 2026-08-02)
- **HP**: 16/16
- **Mana**: 100/100
- **Movement**: 76/83 (spent ~7 walking to the Mages' Guild this session)
- **Armor Class**: 80/10
- **Alignment**: 0

## Current Location
- **Room**: **The Entrance To The Mages' Guild** — "The entrance hall to this
  guild is a small, poor lighted room." Exits: **n, s**. Has an ATM. A
  cityguard and a sorcerer (guarding the entrance) are present; neither
  attacked. `s` leads further into the guild, unexplored.
- Reached this session by walking from The Temple Of Midgaard (see route in
  `world-smarty.md`).

## Inventory
- Not yet checked this session (only `look`/`score` run) — run `inventory`
  next session.

## Equipment
- Not yet checked this session — run `equipment` next session.

## Skills & Abilities
- Not yet checked — run `practices`/`spells` next session now that the
  Mages' Guild has been located (relevant for a mage to learn/practice
  spells there).

## Status
- Standing, not fighting, no visible status effects (hungry/thirsty not yet
  checked via `score`, but nothing flagged).

## Current Goals
1. **Done this session**: log in, navigate to the Mages' Guild entrance.
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
