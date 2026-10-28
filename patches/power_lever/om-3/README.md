# OM-3 power-lever / function-button default patch (offline L2)

Build **1100** only. Analysis / offline acceptance — **does not flash a camera**.

## Goal

Set the stock default of `changeFunctionButton` settings word `0x60366e58`
so key **11** appears enabled (`getChangeFunctionButton(11) → 1`) without a
prior native set call. This proves the L2 data-patch + preflash regression
loop for lever remapping.

Located settings selectors (not all are rewritten by this patch):

| Name | Evidence |
| --- | --- |
| `MODE_DIAL` property enum | id **`0x60`** at table `0x612f1c54` |
| `LEVER_SWITCH` property enum | id **`0x61`** at table `0x612f1c60` |
| Function-button bits | RAM/image word **`0x60366e58`** |
| KeyAssignment mode_dial cache | **`0x603713d4`** / **`0x603713d8`** |
| `GUI_FN_LEVER_POWER_SWITCH` | function id **`0x400000d`** |

## Build

```bash
python patches/power_lever/om-3/build.py --out generated/om3-lever-patch
```

## Caveats

- Does not by itself implement “mode dial as power” product logic; it only
  demonstrates offline acceptance of a default-bit remapping.
- Full dual-mode product contrast still needs the live property service for
  ids 1482/1483 (`MODE_DIAL_B_ONOFF` path).
