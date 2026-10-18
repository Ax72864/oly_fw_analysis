# COLOR editor: input, commit and display

PEN-F build 3101 has a reusable property-based editor. Each COLOR profile binds
one cursor and twelve value controls. CRT shares its viewer, so an HSL change
must distinguish COLOR from CRT rather than redirect the shared viewer blindly.

## Entry and controls

The manual documents front-dial COLOR entry and reopening with the rear lever.
Firmware 3.x also allows moving between color, tone and shading editors. Selecting
a profile in the Super Control Panel is not by itself proof of a direct wheel
entry route.

Group 18's editor descriptors use keys `13b2`, `13b3`, `13b4` for COLOR1–3,
and `13a8` for CRT. Viewer type 88 selects constructor `60c84664`; update is
`60c84901`. State entry `60cefa1d` selects the COLOR key through property 912.

| Profile | Cursor property | Saturation properties |
| --- | ---: | --- |
| COLOR1 | 1095 | 931–942 |
| COLOR2 | 1100 | 943–954 |
| COLOR3 | 1101 | 955–966 |

The front command dial selects a sector, the rear dial changes its value,
INFO selects ALL, short OK exits and held OK resets. The HSL extension uses
Delete to cycle S/L/H while retaining these controls. One shared sector cursor
must be used by both the display and actuator: restoring only an axis-specific
visible cursor causes the next dial move to jump from stale internal state.

## Single-value edit

```text
editor FSM 60bcba4d → local handler 60cefd3d
  → controller 60cd03cc → actuator 60c73065
  → COLOR Up/Down 60cb0684 / 60cb08e5
  → child index update and internal 900c commit
  → 60c836cd → generic commit 60c80913
  → GUI setter 607363b3
  → settings manager 6075fbed → 602b9dac → 602badc5
  → profile callback → 602c50be
```

Internal event `900c` here means committing the child's selected enumeration.
It is not a physical OK press. The stock list is +5 down to −5; dial changes
move through indices rather than performing arithmetic on HSL coefficients.

The GUI setter checks capture/busy state. Its resource-5 mutex protects specific
status reads, not the whole subsequent operation. A separate GUI worker and
application dispatcher exchange a request and replies: event 404e is followed
by acknowledgement 11771 and completion 11770. Completion releases the caller's
private semaphore; then notifications and viewer callbacks finish. These event
numbers are decimal, unlike the hexadecimal addresses.

Bounded probes execute both the base and NEW shooting-component handlers under
initialized state-14 fixtures. They do not reproduce every boot-to-editor
transition or hardware schedule. See [per-image ownership](CAPTURE_PARAMETERS.md)
for why H/L must be captured with the image rather than read later from the UI.

## Numeric text and wheel graphics are separate consumers

The numeric viewer builds display parameter 179. The polygon/dots follow another
route:

```text
6081b780, command 5 → profile/cursor and twelve values
  → 13-byte payload → 60300b3d (Draw_C3d_Async)
  → 602fc370, value-code conversion
```

An extension must redirect both sources. Correct text and a correct selection
radial line do not prove that the polygon uses the edited values. The cursor
occupies the thirteenth payload byte and remains independent of H/S/L strength.
[Resource rendering](../../tooling/pen-f/RESOURCES.md) covers labels, palettes and fonts.

## ALL and reset

ALL has two native representations: an INFO flag with public cursor 255 and a
retained single sector, or cursor-child index zero with remembered sector zero.
Both are valid states for changing axes. A group increment stops if any band is
at its upper bound; decrement stops at the lower bound. This differs from
independently clipping each band.

Held OK arms timer 537. Its callback emits `f802`, which dispatches reset event
`903e`. The parent visits its 13 children and commits each available default
through the ordinary property interface. Redirecting getter, setter and default
lookup consistently therefore also redirects reset. H/L defaults are neutral;
stock S uses profile-specific defaults. Resetting the wheel, a whole profile,
a custom bank and all camera settings are different operations.

The extended ±7 implementation updates value lists, ALL bounds, numeric widgets
and wheel buffers together. Its physical tests include switching axes in ALL,
profile resets, persistence and custom-bank assign/recall. Exact event timing
and arbitrary concurrent capture are not exhaustively proven by those tests.
