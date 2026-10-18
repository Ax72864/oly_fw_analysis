# Button, dial and wakeup inputs

These mappings are for PEN-F main build 3101. Board variants matter: logical
button events are more portable than an assumed GPIO number.

## OK level and events

The native kind-2 button descriptor defines **raw 0 as pressed**, 1 as released.
This is a software polarity mapping, not an electrical voltage measurement.

| Raw level | Event from `60199ef5` | UI translation |
| ---: | --- | --- |
| 0 | `02000004` | `44`, `EV_PRESS_OK_KEY` |
| 1 | `02010004` | `45`, `EV_RELEASE_OK_KEY` |

Two modeled descriptor variants use different sources:

| Variant | Source | Cached level |
| --- | --- | --- |
| Controller | `98e00068`, bit 31 | `a1c583f0`, bit 4 |
| GPIO | logical GPIO 77; `9b800954`, bit 4 | `a1c583ec`, bit 13 |

The tested ordinary event chain is:

```text
controller IRQ callback 6007d6d0
  → key acquisition/filter
  → snapshot ring 6019a477 / 6019a482
  → flag 88, mask 1
  → UI_IN task 60197dbe
  → snapshot comparison and event formation
  → application delivery 600424dc
```

The ring at `a1c57fe4` uses six-byte records: four snapshot bytes, width and group.
Native code queues and consumes transitions. Merely changing a level without
an input interrupt does not exercise that route. An unchanged held snapshot
does not produce another press event.

Initialization copies current button levels into saved state. Holding OK through
startup therefore need not create an ordinary press event. An early recovery
selector could instead poll a level or read a latched wake reason.

## Three controller fields with different roles

- `98e00068`: live button level.
- `98e00050`: pending input events and acknowledgement.
- `98e00048`: wake/command state used in startup decoding.

These must not be substituted for each other in an emulator. Paired held/released
OK tests reach the same bounded startup path; they do not resolve physical
OK+power recovery selection.

## Dials and application gates

The exposure-mode dial and front creative dial are separate controls. The
exposure-mode acquisition uses an ADC producer; changing a downstream cached
mode is not the same test as supplying that ADC input. No required PASM position
for the physical SD updater has been established.

Logical main/sub dial events include `02031902` and `02031903`; their physical
front/rear association must be checked against the board and UI context.
Ordinary input delivery has startup and application-state gates, including
`a1c58028` and an application check at `a1c588ba`.

In the COLOR editor, short OK exits and held OK resets. Delete is used by the
HSL extension to switch axes. That local binding does not establish that a
button is unassigned in live view, playback, menus or every global state.
See [editor behavior](../../color/pen-f/EDITOR.md).
