# World Information

_Last updated: 2026-08-01. Everything below was observed directly in-game._

Server is **tbaMUD 2025** (CircleMUD/DikuMUD lineage) on `localhost:4000`,
development port.

## Explored Rooms

### The Temple Of Midgaard — exits: n, e, s, w, d  ← respawn/hometown room
"Southern end of the temple hall... Large steps lead down through the grand
temple gate, descending... to the temple square below. West: the Reading
Room. East (small alcove): the donation room." Has an ATM ("automatic teller
machine... installed in the wall"). This is the character's death-respawn
location, confirmed on 2026-08-01 after a deliberate death to escape the
drainpipe trap (see player.md notes). **This is the real hub city — Midgaard
— a classic CircleMUD/DikuMUD town.** The whole sewer maze explored earlier
is a separate, disconnected area reached only via the original login room,
not from here.
- **d** → likely the way down to the sewers (steps/mound described go down to
  "the temple square below" — probably **s** or **d**; not yet confirmed).
- **w** → Reading Room
- **e** → Donation Room (small alcove)
- **n**, **s** → UNEXPLORED
- Being the hometown temple, this room and its immediate surroundings are
  almost certainly safe (no mobs seen on arrival).

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

## Unexplored Leads (next targets)
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

## Guild Information (from earlier sessions, route not yet re-confirmed)
- **Fighter's Guild — The Tournament And Practice Yard**: practice yard with the
  Guildmaster (sharpening an axe). North of it is The Bar of Swordsmen; a well
  leads down toward the sewers.
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
