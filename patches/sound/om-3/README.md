# OM-3 electronic-shutter short-sound table patch (offline L2)

Build **1100** only. Analysis / offline acceptance — **does not flash a camera**.

For the **verified** three-slot custom e-shutter sound package (physical SD
firmup 2026-11-04), see `docs/boot/om-3/FLASH_WORKFLOW.md` and
`docs/features/om-3/CUSTOM_FEATURES.md` — that path uses
`tools/om3_db_feature_patch.py` + `tools/om3_shutter_slots.py`, not this L2 table
flip.

## Goal

Demonstrate a reproducible, hash-gated data patch that flips
`PRM_AUD_CSHUT*_VOL` from non-short (`0`) to short (`1`) in the
`aud_ikey_to_wavetype_is_short_sound` table at `0x60ddb9e4`.

This is a **proof of the L2 pipeline**, not the shipping shutter-sound feature.


## Build

```bash
python patches/sound/om-3/build.py --out generated/om3-sound-patch
```

Inputs: pinned decoded main under `analysis/om3_1100/` (SHA in `patch.json`).
No MN103 assembler required (data-only).

Outputs:

- `patched-main.bin` / `restore-main.bin`
- `build.json` (input/output hashes)
- `acceptance.json` (native `aud_ikey` probe on patched image)

## Caveats

- Table lives in a loaded code/data section; treat as a candidate edit, then
  re-run `tools/om3_code_space_audit.py` before any larger code cave.
- Does not model speaker/codec silicon.
