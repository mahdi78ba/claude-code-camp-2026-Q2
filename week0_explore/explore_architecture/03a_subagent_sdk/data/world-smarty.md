# World Information — Smarty's copy

_Seeded 2026-08-02 from `dummy`'s `data/world.md` (same physical MUD world),
so Smarty's sessions do not read/write the same file as `dummy`'s concurrent
sessions. Everything below was observed by `dummy`, not yet re-confirmed by
Smarty — treat unconfirmed entries as a hint, not ground truth, and correct
them from what the game actually shows Smarty. Last updated: 2026-08-01._

Server is **tbaMUD 2025** (CircleMUD/DikuMUD lineage) on `localhost:4000`,
development port.

## Explored Rooms

### The Temple Of Midgaard — exits: n, e, s, w, d  ← respawn/hometown room, city hub start
"Southern end of the temple hall... Large steps lead down through the grand
temple gate, descending... to the temple square below. West: the Reading
Room. East (small alcove): the donation room." Has an ATM ("automatic teller
machine... installed in the wall"). This is the character's death-respawn
location, confirmed on 2026-08-01 after a deliberate death to escape the
drainpipe trap (see player.md notes). **This is the real hub city — Midgaard
— a classic CircleMUD/DikuMUD town.** The whole sewer maze explored earlier
is a separate, disconnected area reached only via the original login room,
not from here.
- **Re-confirmed 2026-08-01 (later session)**: reconnected here directly (room
  persisted between sessions as expected), room text/exits matched exactly.
  Character was already in the "resting" state on login and stayed
  undisturbed — no mobs appeared across ~5 minutes of resting from 1/25 to
  25/25 HP. Confirms this room is safe to rest in for extended periods.
- **d** → likely the way down to the sewers (steps/mound described go down to
  "the temple square below" — probably **s** or **d**; not yet confirmed).
- **w** → Reading Room
- **e** → Donation Room (small alcove)
- **s** → **CONFIRMED 2026-08-01: The Temple Square** (see below, part of the
  real Midgaard city — this is the way "down through the grand temple gate").
- **n** → still UNEXPLORED
- Being the hometown temple, this room and its immediate surroundings are
  almost certainly safe (no mobs seen on arrival).

### The Temple Square — exits: n, e, s, w
"Huge marble steps lead up to the temple gate. The entrance to the Clerics'
Guild is to the west, and the old Grunting Boar Inn, is to the east. Just
south of here you see the market square, the center of Midgaard." Has a large
marble fountain and (in this visit) two Peacekeepers standing guard —
Peacekeepers appear to be non-hostile order-keeping NPCs typical of safe town
squares.
- **n** → The Temple Of Midgaard
- **w** → Clerics' Guild (unexplored beyond the entrance)
- **e** → old Grunting Boar Inn (unexplored beyond the entrance)
- **s** → Market Square
- Safe: two Peacekeepers present, nothing hostile, no attack.

### Market Square — exits: n, e, s, w
"You are standing on the market square, the famous Square of Midgaard. A
large, peculiar looking statue is standing in the middle of the square. Roads
lead in every direction, north to the temple square, south to the common
square, east and westbound is the main street." A Peacekeeper stands here too.
- **n** → The Temple Square
- **s** → Common Square (unexplored beyond the name)
- **e** → Main Street (general-store block, see below)
- **w** → Main Street (bakery/armory block, see below)
- Safe: Peacekeeper present, no hostiles seen.

### Main Street (general store / pet shop block) — exits: n, e, s, w
"The main street crossing through town. To the north is the general store,
and the main street continues east. To the west you see and hear the market
place, to the south a small door leads into the Pet Shop."
- **w** → Market Square
- **n** → General Store (unexplored beyond entrance)
- **s** → Pet Shop (unexplored beyond entrance)
- **e** → Main Street (town-edge block, see below)

### Main Street (town edge, weapon shop / Guild of Swordsmen block) — exits: n, e, s, w
"To the north is the weapon shop and to the south is the Guild of Swordsmen.
To the east you leave town and to the west the street leads to the market
square." A Peacekeeper and **two "beastly fido"** mobs seen here (scavenging
garbage — did not attack, likely harmless/passive scavengers, but untested —
treat with caution since character is naked/AC 100).
- **w** → Main Street (general store block)
- **n** → Weapon Shop (unexplored beyond entrance)
- **s** → Guild of Swordsmen (unexplored beyond entrance)
- **e** → leaves town (unexplored, likely road toward wilderness/Newbie Zone)

### Main Street (bakery / armory block) — exits: n, e, s, w  ← **bakery is here**
"The main street passing through the City of Midgaard. South of here is the
entrance to the Armory, and the bakery is to the north. East of here is the
market square."
- **e** → Market Square
- **n** → **The Bakery**
- **s** → Armory (unexplored beyond entrance)
- **w** → **CONFIRMED 2026-08-02 (Smarty)**: Main Street (west end, see below)

### Main Street (west end / magic shop / city gate block) — exits: n, e, s, w  ← **confirmed 2026-08-02, Smarty**
"You are at the end of the main street of Midgaard. South of here is the
entrance to the Guild of Magic Users. The street continues east towards the
market square. The magic shop is to the north and to the west is the city
gate." A cityguard and beastly fidos seen here (no hostility).
- **e** → Main Street (bakery/armory block)
- **s** → **The Entrance To The Mages' Guild**
- **n** → Magic Shop (unexplored beyond entrance)
- **w** → City Gate (unexplored beyond entrance — likely leaves the city)

### The Entrance To The Mages' Guild — exits: n, s  ← **confirmed 2026-08-02, Smarty**
"The entrance hall to this guild is a small, poor lighted room." Has an ATM.
A cityguard and a sorcerer (guarding the entrance) present, no hostility.
- **n** → Main Street (west end / magic shop / city gate block)
- **s** → UNEXPLORED — likely deeper into the guild (guildmaster/practice
  room), not yet walked.

### The Common Square — exits: n, e, s, w  ← **confirmed 2026-08-02, Smarty**
"The common square, people pass you, talking to each other. To the west is
the poor alley and to the east is the dark alley. To the north, this square
is connected to the market square. From the south you notice a nasty smell."
Three "beastly fido" mobs mucking through garbage here — passive, no attack.
- **n** → Market Square
- **w** → The Eastern End Of Poor Alley
- **e** → The Dark Alley
- **s** → UNEXPLORED ("nasty smell" — likely sewer/levee access)

### The Eastern End Of Poor Alley — exits: e, s, w
"You are at the poor alley. South of here is the Grubby Inn and to the east
you see common square. The alley continues further west." Beastly fidos here
too, passive.
- **e** → The Common Square
- **s** → Grubby Inn (unexplored beyond entrance)
- **w** → UNEXPLORED

### The Dark Alley — exits: e, s, w
"The dark alley, to the west is the common square and to the south is the
Guild of Thieves. The alley continues east." Three "mercenary" NPCs here
("waiting for a job"), no hostility observed.
- **w** → The Common Square
- **s** → Guild of Thieves (unexplored beyond entrance)
- **e** → The Dark Alley At The Levee

### The Dark Alley At The Levee — exits: e, s, w
"You are standing in the alley which continues east and west. South of here
you see the levee." A Peacekeeper stands here.
- **w** → The Dark Alley
- **s** → the levee (unexplored)
- **e** → The Eastern End Of The Alley

### The Eastern End Of The Alley — exits: s, w  ← dead end east (city wall)
"You are standing at the eastern end of the alley, the city wall is just
east, blocking any further movement. A small warehouse is directly south of
here."
- **w** → The Dark Alley At The Levee
- **s** → small warehouse (unexplored)
- **e** → blocked: "Alas, you cannot go that way..." (city wall)

### The Bakery — exits: s  ← dead end, shop room
"You are standing inside the small bakery. A sweet scent of danish and fine
bread fills the room. The bread and Danish are arranged in fine order on the
shelves, and seem to be of the finest quality. A small sign is on the
counter." A friendly baker NPC is here ("looks at you calmly, wiping flour
from his face"); no hostility.
- **s** → Main Street (bakery/armory block)
- **Menu (via `list`), confirmed 2026-08-01:**
  | # | Item | Cost |
  |---|------|------|
  | 1 | A danish pastry | 7 |
  | 2 | A bread | 15 |
  | 3 | A waybread | 76 |
- Character has 0 gold, so nothing purchased yet. Food here would solve the
  "hungry" status once gold is available.

Several rooms share the name "The Dark Passageway" — they are distinguished
here by their exits.

### The Dark Passageway (hub) — exits: n, e, w
"You can't see anything but the ground where you put your feet. The passageway
seems to continue west and north. To the east there is water covering the floor
and that leads through an arched entry to a watery sewer."
- **n** → The Dark Passageway (corridor)
- **e** → The Watery Sewer Bend
- **w** → The Junction
- This is the crossroads of the explored area; route everything through it.

### The Dark Passageway (corridor) — exits: n, s
"...the passageway seems to continue south and north."
- **s** → The Dark Passageway (hub)
- **n** → UNEXPLORED

### The Junction — exits: n, e, w
"You stand in a junction leading north, west and east."
- **e** → The Dark Passageway (hub)
- **n** → The Sewers (dead end)
- **w** → The Junction Going Three Ways

### The Sewers (dead end) — exits: s only
"You stand in a dead end of the sewer. The only way out is south. You can see
a shaft leading up but it looks too difficult to go up that way." Dead end,
no climbable shaft. Not useful — skip in future.
- **s** → The Junction

### The Junction Going Three Ways — exits: n, e, w
"You are in a passageway in the pipes of the sewer system leading north, east
and west."
- **e** → The Junction
- **w** → The Ordinary Junction
- **n** → UNEXPLORED

### The Ordinary Junction — exits: n, e, w
"This looks like an ordinary junction... The pipelines lead west, east and
north."
- **e** → The Junction Going Three Ways
- **w** → A Bend In The Sewer Pipe
- **n** → UNEXPLORED

### A Bend In The Sewer Pipe — exits: n, e
"A strong smell seeps in from the north. The sewer goes north and east."
- **e** → The Ordinary Junction
- **n** → The Sewer Junction

### The Sewer Junction — exits: n, e, s, w
"You stand in the middle of a huge junction of sewer pipes right under what
you'd think was an air shaft... impossible to force your way up." Air shaft
here too, also not climbable.
- **s** → A Bend In The Sewer Pipe
- **n** → A Muddy Intersection
- **e**, **w** → UNEXPLORED
- This whole western branch (Junction → Junction Going Three Ways → Ordinary
  Junction → Bend → Sewer Junction) is a **second maze cluster**, still no
  exit to open air/city found. Two dead-end air shafts seen so far.

### A Muddy Intersection — exits: n, e, s
"Feet stuck in mud... total darkness... depressing." Mud costs more movement
(~3/move) than dry passageway.
- **s** → The Sewer Junction
- **n** → The Muddy Sewer Bend
- **e** → UNEXPLORED

### The Muddy Sewer Bend — exits: s, w
- **s** → A Muddy Intersection
- **w** → The Muddy Sewer Junction

### The Muddy Sewer Junction — exits: n, e, s
"The muddy sewer stretches into the dark to the south... leads north, south
and east from here."
- **e** → The Muddy Sewer Bend
- **n** → The Muddy Sewer (dead end, exits: s only)
- **s** → The Mudhole
- **This is now the "mud" cluster**, a third distinct area branching off The
  Sewer Junction. Mud costs ~3-6 mv/move, pricier than dry stone (~1) or
  watery sewer (~6).

### The Mudhole — exits: n, d
"Mud all the way up to your thighs... In the middle you can just make out an
enormous drainpipe leading down."
- **n** → The Muddy Sewer Junction
- **d** → Under The Mudhole — **ONE-WAY**, confirmed by trying `u` from below
  ("Alas, you cannot go that way...").

### Under The Mudhole — exits: e
"A great big opening in the ceiling... impossible to force the muddy
descent [back up]." Confirmed dead-end/one-way landing spot; `u` fails here.
- **e** → A Muddy Bend In The Sewer System — **DANGER, see below**.
- This room itself is mob-free and safe to rest/wait in.

### A Muddy Bend In The Sewer System — exits: s, w
"The pipe leads west and south." **Multiple mobs seen here simultaneously:**
a giant maggot ("simply existing"), a snake ("looks very mean," slithering
toward the player — reads as aggressive), and *two* "horrifying Mudmonster"s.
No attack landed on a walk-through, and the maggot wandered off on its own
("The maggot leaves south") — mobs do move/despawn over time, room contents
are not fixed.
- **w** → Under The Mudhole (the one-way drop landing spot)
- **s** → UNEXPLORED — blocked by the mob cluster; do not push through at
  level 1 / 25 HP without backup, better gear, or the room clearing out.
- **CRITICAL: this is currently the only way forward from the drainpipe
  branch.** Under The Mudhole → here is one-way, and here is the only
  unexplored branch of that whole drainpipe path. If this room can't be
  passed safely, the drainpipe lead is a dead end for now.

### The Watery Sewer Bend — exits: n, w
"You can't see anything but the water you're in up to your hips. The sewer
seems to bend and lead west and north."
- **w** → The Dark Passageway (hub)
- **n** → The Watery Sewer

### The Watery Sewer (south) — exits: n, s
- **s** → The Watery Sewer Bend
- **n** → The Watery Sewer Junction
- **u** does NOT work here ("Alas, you cannot go that way...") — no ladder up.

### The Watery Sewer Junction — exits: n, e, s
"The sewer seems to lead into a junction that goes north, south and east."
- **s** → The Watery Sewer (south)
- **n** → The Watery Sewer (north) — a *second, distinct* room with the same
  name and the same `n s` exits. Do not confuse the two; the one you are in is
  whichever side of the junction you walked from.
- **e** → A Ledge By A Dark Pool

### The Watery Sewer (north) — exits: n, s
- **s** → The Watery Sewer Junction
- **n** → UNEXPLORED

### A Ledge By A Dark Pool — exits: n, w, d  ← current position
"...the echo tells you that there is quite a drop down. You can just make out a
huge dark pool out there in the darkness... The water from the sewer actually
washes over this ledge and makes it quite slippery. From here it drops, like a
waterfall, into the pool far down. Under you there is a small fissure in the
rock. It seems big enough to contain a few people."
- **w** → The Watery Sewer Junction
- **n** → UNEXPLORED
- **d** → UNEXPLORED — drops into the dark pool. **Slippery ledge + a waterfall
  drop; do not go `d` at 25 HP without a way back up.**
- The "small fissure in the rock" is worth a `look fissure` / `enter fissure`.

## Map

```
                          (n?)
                            |
                  Watery Sewer (north)
                            |
   (n?) — Ledge By A Dark Pool — w — Watery Sewer Junction
                 |(d? waterfall)             |
                                    Watery Sewer (south)
                                             |
    The Junction                    Watery Sewer Bend
    (n?, w?)                                 |
        |                                    |
        +-------- Dark Passageway (hub) -----+
                          |
                 Dark Passageway (corridor)
                          |
                        (n?)
```
`?` marks an exit that has not been walked yet.
The Ledge is currently the eastern edge of the map; the two Watery Sewer rooms
sit north and south of the junction.

## Routes

| From | To | Commands |
| ---- | -- | -------- |
| Dark Passageway (hub) | Watery Sewer Junction | `e, n, n` |
| Watery Sewer Junction | Dark Passageway (hub) | `s, s, w` |
| Watery Sewer Junction | A Ledge By A Dark Pool | `e` |
| A Ledge By A Dark Pool | Dark Passageway (hub) | `w, s, s, w` (~24 mv) |
| Dark Passageway (hub) | The Junction | `w` |
| Dark Passageway (hub) | Dark Passageway (corridor) | `n` |
| **The Temple Of Midgaard** | **The Bakery** | `s, s, w, w, n` (Temple → Temple Square → Market Square → Main Street(general store block) → Main Street(bakery/armory block) → Bakery) |
| **The Bakery** | **The Temple Of Midgaard** | `s, e, e, n, n` |
| **The Temple Of Midgaard** | **The Entrance To The Mages' Guild** | `s, s, w, w, s` (Temple → Temple Square → Market Square → Main Street(bakery/armory block) → Main Street(west end/magic shop/city gate block) → Mages' Guild entrance). **Confirmed 2026-08-02, Smarty.** ~7 movement points. |
| **The Entrance To The Mages' Guild** | **The Temple Of Midgaard** | `n, e, e, n, n` (reverse of above, untested but symmetric) |
| Market Square | The Common Square | `s, s` (via Market Square → Common Square) |
| The Common Square | The Eastern End Of The Alley | `e, e, e` (Common Square → Dark Alley → Dark Alley At The Levee → Eastern End Of The Alley, dead end at city wall) |

## Unexplored Leads (next targets)
0. **Midgaard city (from Temple Of Midgaard, non-sewer side)**: Temple `n`;
   Temple Square `w` (Clerics' Guild) and `e` (Grunting Boar Inn); Market
   Square `s` (Common Square — **now explored, see below**); Main Street
   (general store block) `n` (General Store) and `s` (Pet Shop); Main Street
   (town-edge block) `n` (Weapon Shop), `s` (Guild of Swordsmen — likely the
   Fighter's Guild lead from player.md!), and `e` (leaves town, probably
   toward the Newbie Zone); Main Street (bakery/armory block) `s` (Armory).
   The Bakery itself is a dead end (`s` only).
0b. **Mages' Guild found 2026-08-02 (Smarty)**: Main Street (bakery/armory
   block) `w` → Main Street (west end/magic shop/city gate block) `n`
   (Magic Shop, unexplored) / `w` (City Gate, unexplored) / `s` → **The
   Entrance To The Mages' Guild** (`s` further in, unexplored — likely the
   guildmaster/practice room, next target for Smarty).
0c. **Common Square branch found 2026-08-02 (Smarty)**: Common Square `s`
   (unexplored, "nasty smell" — likely sewer/levee); `w` → Eastern End Of
   Poor Alley `s` (Grubby Inn, unexplored) / `w` (unexplored); `e` → Dark
   Alley `s` (Guild of Thieves, unexplored) → Dark Alley At The Levee `s`
   (the levee, unexplored) → Eastern End Of The Alley `s` (small warehouse,
   unexplored) / `e` blocked by city wall (dead end).
1. **The Muddy Sewer Junction: n, s** — current position, deepest point in the
   mud cluster; try next.
2. **A Muddy Intersection: e**, **The Sewer Junction: e, w** — untried
   branches closer to the surface.
3. **The Junction Going Three Ways: n** and **The Ordinary Junction: n** —
   untried side branches off the main westward corridor.
4. **A Ledge By A Dark Pool: n** — free to try; `d` is the risky waterfall drop.
5. **Watery Sewer (north): n** — one room from the junction.
6. **Dark Passageway (corridor): n**.
- Two dead-end air shafts found (The Sewers off The Junction; The Sewer
  Junction itself) — shafts look like red herrings, not the way out.

## NPCs & Mobs
- None encountered yet in the sewers. Nothing has attacked.

## Guild Information
- **Mages' Guild — CONFIRMED 2026-08-02 (Smarty), route walked and verified:**
  from The Temple Of Midgaard: `s, s, w, w, s` → The Entrance To The Mages'
  Guild (small, poorly lit room; ATM; cityguard + sorcerer guarding, no
  hostility). `s` from there is unexplored (likely guildmaster/practice
  room) — next step for a mage character.
- **Fighter's Guild — The Tournament And Practice Yard** (from earlier
  `dummy` sessions, route not yet re-confirmed by Smarty): practice yard with
  the Guildmaster (sharpening an axe). North of it is The Bar of Swordsmen; a
  well leads down toward the sewers.
- The Guildmaster teaches/practices skills such as `kick` and charges gold.
- **Warning:** the connection from the sewers up to the yard has not been found
  from this side. Treat the guild as unreached until a route is walked and
  written into the table above.

## Movement / Survival Notes
- Sewer rooms cost roughly **6 movement points** each; dry passageway rooms
  cost 1–2. Plan sewer trips against the current movement pool.
- The sewer water is waist-deep but is not a usable drink source.
- Rooms are dark-flavoured but readable — the equipped candle is providing light.
- Each `mud.py` run reconnects and the character resumes in the last room, so
  the room recorded in `player.md` is the starting point of the next session.
- **Regen while resting** (observed 2026-08-01 in Temple Of Midgaard): about
  **+4 HP and +6 movement per tick**, tick length roughly 60-75s real time.
  Regen continues even while disconnected (HP had already risen from 1→4
  between the previous session's end and this session's first login), so a
  short break between `mud.py` runs also heals for free.
