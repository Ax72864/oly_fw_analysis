# OM-3 electronic-shutter short-sound table patch (offline L2)

Build **1100** only. Analysis / offline acceptance — **does not flash a camera**.

## Goal

Demonstrate a reproducible, hash-gated data patch that flips
`PRM_AUD_CSHUT*_VOL` from non-short (`0`) to short (`1`) in the
`aud_ikey_to_wavetype_is_short_sound` table at `0x60ddb9e4`.

This is a **proof of the L2 pipeline**, not a finished product beep patch.
A real e-shutter cue still needs a capture-complete call-site hook (see
`docs/features/om-3/SHUTTER_SOUND.md`).

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
