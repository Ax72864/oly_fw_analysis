# OM-3 power switch vs mode dial (build 1100)

User report: firmware already allows moving power on/off onto the mode dial;
after that, the physical On/Off control is inert. Desired: remap that freed
control to another function. Analysis only.

## Identified surfaces

| Lead | Address | Role |
| --- | --- | --- |
| `key_matrix_power` | `0x60240d54` | ptr `0x60179c7d` — power in key matrix |
| `PWR LEVER` / `[SRC CHK]PWR LEVER` | `0x60120805` / `0x601207fc` | Maintenance/source check for power lever |
| `EV_CHANGE_LEVER_SW` | `0x60dee084` | ptr `0x60df0378` — lever switch event |
| `EV_CHANGE_MODE_DIAL` | `0x60dedc89` | ptr `0x60df01d0` — mode dial event |
| `CameraCommon::getLeverSwitchState` | `0x60df13fd` | Lever state API |
| `changeFunctionButton` / `getChangeFunctionButton` | `0x60df141f` family | Function-button remapping; logs `key` and `lever` |
| `[GUI KeyAssignment]` / `customKeyAssignment_sw0N` | `0x615d2a8c` / `0x615d2af0+` | Custom key assignment UI/state machine |
| `app modedial` shell | `0x60621fb0` | Debug: change mode dial value |
| `API_WUI_POWER_BUTTON` | `0x60e2ef6d` | ptr `0x60b3c16c` — wake/UI power button id |
| `API_SHUTDOWN_REASON_BUTTON` | `0x60e2ea0f` | Shutdown reason bit for button |

## Feasibility reading

1. **Mode dial as power** is already a product feature path (event
   `EV_CHANGE_MODE_DIAL` plus assignment UI). That path likely **consumes** the
   power-on/off semantic and stops delivering it from the physical lever.
2. The physical control still appears in the matrix (`key_matrix_power`,
   `PWR LEVER`, `EV_CHANGE_LEVER_SW`). “Inert” after remapping usually means
   the assignment table maps it to *none* / power-only, not that GPIO died.
3. Custom key assignment already enumerates `customKeyAssignment_sw01`…
   `sw06` / `sw12`. Whether the power lever is one of those software IDs is the
   critical unknown.
4. `changeFunctionButton` takes `(key, lever)` — evidence that lever position
   participates in function-button logic separately from pure power.

## PEN-F contrast

PEN-F boot models an **exposure-mode ADC dial** (`penf_boot_mode_dial.py`,
channel 7 / `0x98c00058`) and ordinary button descriptors
([INPUTS](../../boot/pen-f/INPUTS.md)). PEN-F does not document an official
“power on mode dial” product mode in this tree. Do not reuse PEN-F ADC numbers
for OM-3 lever/power.

## Next proof steps (still offline / read-only)

1. Dump the custom-assignment table records near `0x615d2af0` and identify which
   `swXX` (if any) is the power lever.
2. Native-read `getLeverSwitchState` / `getChangeFunctionButton` with synthetic
   lever levels after a settings bank where power-on-dial is enabled.
3. If the lever remains a distinct key ID with assignment slot `none`, a patch
   or settings edit could point it at an existing function ID already accepted
   by `customKeyAssignment_*`.
4. If power-on-dial **aliases** the lever away at the event source, remapping
   needs a new event producer — higher risk, needs cave space.

No flashable patch is proposed here.
