# Player State

_Last updated: 2026-08-02, after finding a new well entrance to the sewers via
the Fighter's Guild practice yard, and discovering we are now blind (no light
source) once underground. See Current Location / Notes for details._

## Character Information
- **Name**: Dummy ("Dummy the Swordpupil")
- **Class**: Warrior / Fighter
- **Level**: 1
- **Experience**: 1 XP (need 1999 more to reach level 2)
- **Gold**: 0 coins
- **Quest Points**: 0 (0 quests completed, not on a quest)
- **Age**: 18; played 0 days 1 hour

## Stats
- **HP**: 25/25 — fully healed (confirmed 2026-08-01, see Current Location).
- **Mana**: 100/100
- **Movement**: 37/84 — spent walking to and through the sewers this
  session (2026-08-02); regenerates over time like HP (~+6/tick while
  resting, untested whether resting works the same while blind).
- **Armor Class**: 100/10 (naked — see Equipment; the old 39/10 note is stale
  from before the equipment was lost).
- **Alignment**: 0
- Regen rate confirmed while resting in Temple Of Midgaard: **+4 HP and +6
  movement per tick, ~60-75s real-time per tick** (observed 1→4→8→12→16→20→
  24→25 HP over ~5 real minutes, whether or not connected — regen continues
  between `mud.py` sessions too, since HP had already risen 1→4 before this
  session's first login).

## Current Location
- **Room: somewhere in a PITCH-BLACK sewer maze, exact room unknown** —
  reached 2026-08-02 by going `d` (well) from The Tournament And Practice
  Yard (Fighter's Guild). Session ended after blind wandering; last confirmed
  moves from the well-bottom room were `s` (worked), `n` (dead end, "Alas you
  cannot go that way"), `s` (back), `e` (worked), `s` (worked) — see world.md
  "Blind Sewer Area (new, via Practice Yard well)" for the exact move log.
  **Do not trust directional assumptions here** — the `exits` command in the
  dark has been shown to be unreliable (a `s` move succeeded from a room
  whose `exits` output had NOT listed south as an obvious exit).
- **No way back up**: the well is one-way (`u` fails with "Alas, you cannot
  go that way...", same as the old drainpipe). We are committed forward,
  exactly as with the earlier drainpipe trap.
- **HP 25/25, Mana 100/100, Movement 37/84** — no combat this session, no
  damage taken. Still hungry and thirsty.
- Route from the surface to this well (for reference, in case of respawn
  navigating back down intentionally): from The Temple Of Midgaard:
  `s, w, n, e, e, s, e, s, d` — Temple→Temple Square→Market Square→Main
  Street(general store)→Main Street(town edge)→Entrance Hall To The Guild Of
  Swordsmen→The Bar Of Swordsmen→The Tournament And Practice Yard→(down the
  well, one-way, goes dark).

## Inventory
- Carrying: nothing

## Equipment
- **NONE — lost on death (2026-08-01).** Corpse with all starting gear is
  stuck in the unreachable "A Muddy Bend In The Sewer System" room, behind
  mobs too dangerous to fight. Treat as permanently lost; do not plan a
  corpse-retrieval trip. AC is now 100/10 (naked, much worse than the prior
  39/10). Need to find a way to re-equip (shops, starting-gift NPCs, or
  cheap gear from mobs) once healed.
- **CRITICAL, confirmed 2026-08-02: no light source means the entire sewer
  system is unnavigable-by-name.** Every sewer room this session showed only
  "It is pitch black..." with no room text. This is why the old candle
  mattered — without it, sewer rooms cannot be identified even if they are
  the same rooms mapped before. `inventory` and `equipment` both confirmed
  empty. **Top priority now: get any light source (torch/lantern) and enough
  gold to buy one** before further sewer exploration will produce reliable
  map data. 0 gold currently, so this likely requires either finding gold on
  the surface first, or finding a light item lying in a room by luck.

## Skills & Abilities
- **kick** — proficiency: bad (not yet practiced)
- **Practice sessions available**: 0 (regenerate on level up)

## Status
- Standing
- **Hungry** — no food carried
- **Thirsty** — no drink carried, and the sewer water is not drinkable
- Not in combat; nothing has attacked yet

## Current Goals — main quest: **defeat the Massive Minotaur in the Newbie Zone**
1. **DECISION (user-approved 2026-08-01): deliberately die to reset position.**
   Genuinely trapped below the one-way drainpipe drop (Under The Mudhole) with
   no other exits (`exits`/`search`/`dig`/`climb` all failed) and no recall
   spell available (Warriors can't cast it; it's Cleric-only, level 12). The
   only way out, A Muddy Bend In The Sewer System, has mobs `consider` rates
   as "you would need a lot of luck and great equipment" (snake) and "You ARE
   mad!" (Mudmonster x2) — unwinnable at level 1. User chose to accept death
   as a reset over risking a real fight. **Expected cost: full equipment lost
   as an unreachable corpse in that room.** After respawn, re-equip from
   scratch is not needed to survive, just re-plan navigation.
2. ~~After respawn, check `score`/`inventory`/`equipment` and the spawn room
   name~~ **DONE (2026-08-01)** — confirmed The Temple Of Midgaard via `look`,
   rested from 1/25 to 25/25 HP. Still 0 gold, no inventory, no equipment
   (AC 100/10, naked).
3. **Avoid the drainpipe branch entirely going forward.** Try the untried
   *non-lethal-looking* leads instead: Ledge `n`, Watery Sewer (north) `n`,
   Dark Passageway (corridor) `n`, Sewer Junction `e`/`w`, Muddy Intersection
   `e`, Junction Going Three Ways `n`, Ordinary Junction `n`.
   **STATUS 2026-08-02: BLOCKED — see goal 3a below.** Found a *second*
   sewer entrance (the well in The Tournament And Practice Yard, `d`), took
   it, and confirmed we now have **no light source**, so every sewer room
   reads as "It is pitch black..." with no name/exits confirmable. Could not
   verify any of these named leads this session; one dead end was found
   blind (see 3a #2) but its identity (whether it's really "Dark Passageway
   corridor") is unconfirmed.
3a. **NEW — top priority before resuming goal 3:**
   1. **Get a light source (torch/lantern) and enough gold to afford one.**
      Until then, sewer exploration cannot produce reliable named-room data
      — everything is blind guesswork. Check the General Store (Main
      Street, general-store block, `n`) for a cheap torch once any gold is
      had; also worth asking the Guildmaster or checking the bulletin board
      in The Bar Of Swordsmen for newbie equipment/quests that grant gold or
      gear.
   2. **We are currently stuck mid-maze, blind, with no way back up** (the
      practice-yard well is one-way, `u` fails there just like the old
      drainpipe). The next session must either continue cautiously forward
      blind (using `exits`, but note it has proven unreliable — see
      world.md) or, if a mob is met, retreat/flee rather than fight naked
      and blind.
   3. **Do NOT deliberately die again as a first resort.** Try blind
      movement and `exits`/`consider` first; only consider death-as-reset if
      truly wedged with no options, same bar as last time.
4. **Locate the Massive Minotaur** once out of the sewers — likely a notable
   mob in the Newbie Zone proper, not the sewers. Note: the surface route
   Main Street (town-edge block) `e` ("leaves town") is still an untried
   candidate lead for reaching the Newbie Zone directly, bypassing the
   sewers entirely — worth trying if the sewer path stays blocked by
   darkness.
5. **Assess combat readiness before engaging the Minotaur** — always
   `consider` a mob before attacking now; that check would have caught this
   trap earlier if used sooner. The Fighter's Guild (Guildmaster in The
   Tournament And Practice Yard) has been **found and reached** this
   session — practice `kick` there once some gold is available. Keep a
   retreat route in mind (though note: the well down from that yard is
   one-way, so don't go down again without a light source).
6. **Find food and water** — hungry and thirsty with 0 gold.
7. **Earn XP toward level 2** (1999 needed) via easier, `consider`-checked
   mobs first.

## Notes
- Room names repeat in this zone ("The Dark Passageway", "The Watery Sewer").
  Always identify a room by name *plus* exits before trusting the map.
- **2026-08-01 side exploration (not the Minotaur quest): found the bakery.**
  Walked south out of the Temple into the real Midgaard city streets (Temple
  Square → Market Square → Main Street) instead of the sewers. Confirmed the
  bakery exists and got its menu (see Current Location / world.md). Also spotted
  a "Guild of Swordsmen" on the town-edge Main Street block (`s` from there) —
  worth checking next as a candidate for the Fighter's Guild / kick-practice
  lead in Goal 5, and an unexplored `e` exit from that same block that "leaves
  town," a plausible lead toward the Newbie Zone / Minotaur (Goal 4).
- **2026-08-02: found and confirmed the Fighter's Guild, AND a second sewer
  entrance.** Route from Market Square: `e` → Main Street(general store
  block) → `e` → Main Street(town-edge block) → `s` → **The Entrance Hall To
  The Guild Of Swordsmen** (`n`,`e`; knight guarding, has an ATM) → `e` →
  **The Bar Of Swordsmen** (`s`,`w`; waiter, bulletin board) → `s` → **The
  Tournament And Practice Yard** (`n`,`d`; Guildmaster sharpening an axe) →
  `d` → a well, **one-way down**, into a pitch-black sewer (see world.md).
  This is a *second, separate* way into the sewer system besides the
  original login-room entrance, but it currently only leads to darkness
  because we have no light source.
- **Route correction**: the previously recorded "Bakery → Temple: `s, e, e,
  n, n`" was WRONG (tested 2026-08-02, the extra `e` overshoots into the
  General Store). Correct route is **`s, e, n, n`** (Bakery → Main
  Street(bakery/armory) → Market Square → Temple Square → Temple). Also
  found: Market Square `s` leads to **The Common Square** (new area, not the
  sewers) → `e` → Dark Alley (mercenaries) → `e` → Dark Alley At The Levee
  (cityguard) → `s` → The Levee (river, boat seller) — an unexplored city
  branch, noted but not pursued this session (not on the current goal path).
