# World Information

_Last updated: 2026-08-02. Everything below was observed directly in-game._

## CRITICAL 2026-08-02 finding: no light source ⇒ sewers are unreadable
Character has no equipment/inventory (confirmed empty via `inventory` and
`equipment`). Every sewer room now shows only `It is pitch black...` with no
room name, description, or reliable exit list. The `exits` command in the
dark is **not fully trustworthy**: in one case a `s` move succeeded even
though the immediately-prior `exits` output for that room had NOT listed
south as an obvious exit. Until a torch/lantern is acquired, do not expect to
confirm named sewer rooms — new blind movement should be treated as
unmapped/unreliable. See "Blind Sewer Area" section below for the raw move
log from this session.

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
- **d** → **CONFIRMED 2026-08-02: same room as `s`, The Temple Square.** Not a
  separate route to the sewers — Temple has no direct sewer connection. The
  only known sewer entrances are (1) the original login room, and (2) the
  well in The Tournament And Practice Yard (see Fighter's Guild section
  below).
- **w** → Reading Room
- **e** → Donation Room (small alcove)
- **s** → The Temple Square (part of the real Midgaard city — this is the way
  "down through the grand temple gate").
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
- **s** → **The Common Square** — explored 2026-08-02, see below (new city
  branch, not toward the sewers/Minotaur; noted for completeness).
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
- **s** → **The Entrance Hall To The Guild Of Swordsmen** — explored 2026-08-02,
  see below.
- **e** → leaves town (unexplored, likely road toward wilderness/Newbie Zone —
  still an untried candidate route to the Newbie Zone/Minotaur)

### The Entrance Hall To The Guild Of Swordsmen — exits: n, e
"A place where one has to be careful not to say something wrong (or right).
To the east is the bar and to the north is the main street." A knight guards
the entrance; an ATM is here too.
- **n** → Main Street (town edge block)
- **e** → The Bar Of Swordsmen

### The Bar Of Swordsmen — exits: s, w
"Once upon a time beautifully furnished. But now the furniture is all around
you in small pieces." A waiter is here; a large sociable bulletin board is
mounted on a wall (worth `read board` next visit — untried).
- **w** → The Entrance Hall To The Guild Of Swordsmen
- **s** → The Tournament And Practice Yard

### The Tournament And Practice Yard — exits: n, d  ← **Fighter's Guild, confirmed 2026-08-02**
"This is the practice yard of the fighters. To the north is the bar. A well
leads down into darkness." Your guildmaster is standing here sharpening an
axe (kick-practice NPC, per earlier notes — not yet interacted with, 0 gold).
- **n** → The Bar Of Swordsmen
- **d** → a well, **ONE-WAY down** (confirmed: `u` from below fails with
  "Alas, you cannot go that way..."), leads into a pitch-black sewer room —
  **a second, separate entrance into the sewer system**, distinct from the
  original login-room entrance. See "Blind Sewer Area" section below —
  currently unusable for reliable mapping because we have no light source.
- **Full route from Temple Of Midgaard**: `s, w, n, e, e, s, e, s` (Temple →
  Temple Square → Market Square → Main Street(general store) → Main
  Street(town edge) → Entrance Hall → Bar Of Swordsmen → Practice Yard).

### Main Street (bakery / armory block) — exits: n, e, s, w  ← **bakery is here**
"The main street passing through the City of Midgaard. South of here is the
entrance to the Armory, and the bakery is to the north. East of here is the
market square."
- **e** → Market Square
- **n** → **The Bakery**
- **s** → Armory (unexplored beyond entrance)
- **w** → unexplored (continues west, not yet walked)

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

### The Common Square — exits: n, e, s, w  ← new 2026-08-02, not sewer-related
"People pass you, talking to each other. To the west is the poor alley and to
the east is the dark alley. To the north, this square is connected to the
market square. From the south you notice a nasty smell." A Peacekeeper and
**three "beastly fido"** mobs here (scavenging, did not attack).
- **n** → Market Square
- **w** → Poor Alley (unexplored)
- **e** → The Dark Alley
- **s** → unexplored ("nasty smell" — likely toward a sewer/drain, untried)

### The Dark Alley — exits: e, s, w
"To the west is the common square and to the south is the Guild of Thieves.
The alley continues east." Three mercenaries "waiting for a job" here — did
not attack.
- **w** → The Common Square
- **s** → Guild of Thieves (unexplored beyond the name)
- **e** → The Dark Alley At The Levee

### The Dark Alley At The Levee — exits: e, s, w
"The alley continues east and west. South of here you see the levee." A
cityguard stands here.
- **w** → The Dark Alley
- **e** → unexplored
- **s** → The Levee

### The Levee — exits: n, s
"South of here you see the river gently flowing west. The river bank is very
low making it possible to enter the river." A retired captain sells boats
here.
- **n** → The Dark Alley At The Levee
- **s** → unexplored (river)
- Side note only — this branch is not on the path to the sewers/Minotaur;
  recorded for completeness, not pursued further this session.

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

### A Ledge By A Dark Pool — exits: n, w, d  ← NOT current position (was as of 2026-08-01; see "Blind Sewer Area" below for 2026-08-02 position)
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

### Blind Sewer Area (new, via Practice Yard well) — 2026-08-02, NO LIGHT SOURCE
All rooms below were entered with zero equipment/inventory, so every room
showed only `It is pitch black...`, no name/description, and the `exits`
command was the only (unreliable) navigation aid. Treat this whole map as
**tentative** — room identities are unconfirmed, and it is NOT known whether
this connects to the previously-mapped Dark Passageway/Watery Sewer/Muddy
network above (contradictory evidence either way — see below).

Move log this session (each line = one command from the previous position):
1. `d` from The Tournament And Practice Yard → **Room A** (well bottom).
   `u` fails ("Alas, you cannot go that way...") — one-way, same as the old
   drainpipe. `exits` → south only.
2. `s` → **Room B**. `exits` → north, east, west (3 exits — superficially
   matches "Dark Passageway (hub)" pattern, but unconfirmed).
3. `n` → **Room C**. `exits` → south only.
4. `n` again from Room C → **fails**, "Alas, you cannot go that way..."
   (confirms Room C is a north dead-end — if this really is "Dark
   Passageway (corridor)", this **resolves that lead as a dead end**, but
   identity is not certain since we couldn't read the room name).
5. `s` → back to **Room B** (or a room that behaves like it: `exits` again
   showed north, east, west).
6. `e` → **Room D**. `exits` → north, east, west (again 3 exits — if Room B
   were truly the "Dark Passageway hub" and this were "Watery Sewer Bend",
   we'd expect only n/w, not n/e/w; **this mismatch is why the whole area is
   marked tentative/unreliable**).
7. `s` from Room D → **Room E** (this move succeeded even though Room D's
   `exits` output had NOT listed south — **direct evidence the `exits`
   command is not fully trustworthy in the dark**, or that this is not
   actually Room D but a different room; unclear which).
8. Session ended at Room E after a final `score` check: 25/25 HP, 100/100
   mana, 37/84 movement, still hungry/thirsty, **no combat encountered at
   any point** in this blind area — good sign that it may be low-danger, but
   not proof.

**Conclusion**: cannot reliably confirm any of the named unexplored leads
(Dark Passageway corridor `n`, Sewer Junction `e`/`w`, Muddy Intersection
`e`, Junction Going Three Ways `n`, Ordinary Junction `n`, Ledge `n`, Watery
Sewer north `n`) while blind. **Get a light source before continuing this
branch.** No way back up from Room A (well is one-way), so the character is
committed forward into this blind area until either (a) it finds a lit room/
exit to the surface, or (b) a future session brings a light source in from
outside — not currently possible without first exiting, which may not be
possible. This is a real risk worth flagging prominently.

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
| **The Temple Of Midgaard** | **The Bakery** | `s, s, w, n` (Temple → Temple Square → Market Square → Main Street(bakery/armory block) → Bakery) |
| **The Bakery** | **The Temple Of Midgaard** | **Corrected 2026-08-02**: `s, e, n, n` (was wrongly recorded as `s, e, e, n, n` — the extra `e` overshoots to the General Store) |
| **The Temple Of Midgaard** | **The Tournament And Practice Yard (Fighter's Guild)** | `s, w, n, e, e, s, e, s` (Temple→Temple Square→Market Square→Main St(general store)→Main St(town edge)→Entrance Hall→Bar Of Swordsmen→Practice Yard) |
| **The Tournament And Practice Yard** | pitch-black sewer (Room A) | `d` — **ONE-WAY, no route back** (`u` fails) |

## Unexplored Leads (next targets)
0. **Midgaard city (from Temple Of Midgaard, non-sewer side)**: Temple `n`;
   Temple Square `w` (Clerics' Guild) and `e` (Grunting Boar Inn); Main
   Street(general store block) `n` (General Store — **check for a cheap
   torch/lantern here, top priority**) and `s` (Pet Shop); Main Street
   (town-edge block) `n` (Weapon Shop), and `e` (leaves town, probably
   toward the Newbie Zone — untried candidate route to the Minotaur that
   bypasses the sewers entirely); Main Street (bakery/armory block) `s`
   (Armory) and `w` (unexplored, continues further west); Common Square `w`
   (Poor Alley) and `s`; Dark Alley `s` (Guild of Thieves) and Dark Alley At
   The Levee `e`; The Levee `s` (river). Guild of Swordsmen is now **fully
   explored** (Entrance Hall → Bar → Practice Yard, see above).
1. **PRIMARY BLOCKER: acquire a light source.** Until then, all the leads
   below (2-7) cannot be reliably confirmed even if walked, since every
   sewer room reads as pitch black with no name. See "Blind Sewer Area"
   section for this session's blind attempt.
2. **A Muddy Intersection: e**, **The Sewer Junction: e, w** — untried
   branches closer to the surface (status: still untried with light; this
   session's blind wandering could not confirm/deny these).
3. **The Junction Going Three Ways: n** and **The Ordinary Junction: n** —
   untried side branches off the main westward corridor.
4. **A Ledge By A Dark Pool: n** — free to try; `d` is the risky waterfall drop.
5. **Watery Sewer (north): n** — one room from the junction.
6. **Dark Passageway (corridor): n** — **possibly resolved as a dead end**
   this session (blind Room C's second `n` failed), but unconfirmed since
   room identity couldn't be read. Re-verify once a light source is had.
- Two dead-end air shafts found (The Sewers off The Junction; The Sewer
  Junction itself) — shafts look like red herrings, not the way out.

## NPCs & Mobs
- None encountered yet in the sewers (old or new blind area). Nothing has
  attacked, including during 2026-08-02's blind wandering near the Practice
  Yard well.
- City mobs seen but non-hostile so far: beastly fido (x2-3, scavenging,
  Main Street town-edge block and Common Square), mercenaries (x3, Dark
  Alley, "waiting for a job"), cityguard (Dark Alley At The Levee), knight
  (guarding Guild Of Swordsmen entrance), Peacekeepers (various squares) —
  none have attacked on sight.

## Guild Information — **CONFIRMED 2026-08-02**
- **Fighter's Guild — The Tournament And Practice Yard**: practice yard with the
  Guildmaster (sharpening an axe). North of it is The Bar of Swordsmen; a well
  leads down (one-way) toward a sewer, currently pitch black (see Blind
  Sewer Area). Reached via: The Entrance Hall To The Guild Of Swordsmen ← `s`
  from Main Street (town-edge block) ← The Bar Of Swordsmen (`e`) ← The
  Tournament And Practice Yard (`s`). Full route from Temple: `s, w, n, e,
  e, s, e, s`.
- The Guildmaster teaches/practices skills such as `kick` and charges gold
  (not yet interacted with — still 0 gold).
- **Route confirmed working from the city side.** The connection from the
  *old* sewer maze (original login-room entrance) up to this yard is still
  not confirmed — the well only confirmed one-way *down*, with no return
  path found from below (`u` fails at the well bottom).

## Movement / Survival Notes
- Sewer rooms cost roughly **6 movement points** each; dry passageway rooms
  cost 1–2. Plan sewer trips against the current movement pool.
- The sewer water is waist-deep but is not a usable drink source.
- Sewer rooms are dark-flavoured; they were readable in earlier sessions
  because a candle was equipped. **That candle was lost with all equipment
  on the 2026-08-01 death.** As of 2026-08-02, with no light source, sewer
  rooms show only "It is pitch black..." — see the CRITICAL note at the top
  of this file.
- Each `mud.py` run reconnects and the character resumes in the last room, so
  the room recorded in `player.md` is the starting point of the next session.
- **Regen while resting** (observed 2026-08-01 in Temple Of Midgaard): about
  **+4 HP and +6 movement per tick**, tick length roughly 60-75s real time.
  Regen continues even while disconnected (HP had already risen from 1→4
  between the previous session's end and this session's first login), so a
  short break between `mud.py` runs also heals for free.
