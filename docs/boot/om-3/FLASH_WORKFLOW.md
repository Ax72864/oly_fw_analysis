# OM-3 research firmware — SD firmup workflow (build 1100)

Practical install path for the offline-built OM-3 **1.1 / 1100** research
container. Landmarks and limits: [RECOVERY.md](RECOVERY.md). Feature notes:
[SHUTTER_SOUND.md](../../features/om-3/SHUTTER_SOUND.md),
[CUSTOM_FEATURES.md](../../features/om-3/CUSTOM_FEATURES.md).

## Status (physical)

| Item | Result |
| --- | --- |
| Method | Community SD firmup: `DCOLYMP/E1479999.BIN` + Slot 1 + hold **OK** while powering on |
| Body | OM-3, stock base **1.1 / 1100** |
| Package | `generated/om3-sd-install/patched-ring-wifi-shutter-hsl/` (HSL research) or `…/feature-only-rollback/` |
| Boot after flash | Normal (2026-11-04 feature pack); **HSL package untested on body** |
| Features checked | Panasonic aperture-ring path, 5 GHz Wi‑Fi hotspot, electronic-shutter custom sound menus **1 / 2 / 3** |
| Current package | Feature pack + HSL B (±5; om-emu E147 boots to menu); container `610e3cdf…` — see [HSL.md](../../color/om-3/HSL.md) |
| Date recorded | 2026-11-04 |

This is a **single-body** verification of the offline rebuild + SD install path.
It does not replace offline hash gates, and it does not mean Workspace / OI.Share
will install the same research container.

## Artifacts

| Role | Path | Container SHA-256 (prefix) |
| --- | --- | --- |
| HSL + features install | `generated/om3-sd-install/patched-ring-wifi-shutter-hsl/DCOLYMP/E1479999.BIN` | `610e3cdf…` |
| Feature-only rollback | `generated/om3-sd-install/feature-only-rollback/DCOLYMP/E1479999.BIN` | `1275b0a3…` |
| Stock restore tree | `generated/om3-sd-install/stock-1.1-restore/DCOLYMP/E1479999.BIN` | `8c133084…` |
| HSL lab | `generated/om3-db-ring-wifi-shutter-hsl-b/OLY_E_147_1100_patched_lab.bin` | same as HSL install |
| Index | `generated/om3-sd-install/INDEX.json` | — |

Rebuild (offline; does not touch a camera):

```bash
# Code sites: ring-native + wifi-5ghz + shutter-sound (no Korean pack)
python tools/om3_db_feature_patch.py --out generated/om3-db-ring-wifi-shutter

# Place three 48 kHz / 16-bit / stereo WAVs into slots 1/2/3 (needs CPython 3.12)
py -3.12 tools/om3_shutter_slots.py \
  --main generated/om3-db-ring-wifi-shutter/main.decoded.bin \
  --slot1 generated/om3-shutter-sounds/final/360329_Nikon_mechanical-dslr_edit_153ms_48k.wav \
  --slot2 generated/om3-shutter-sounds/final/sfxmint_impact-gunshot-08_edit_450ms_48k.wav \
  --slot3 generated/om3-shutter-sounds/final/combo_hakimi_edit_529ms_48k.wav \
  --out generated/om3-db-ring-wifi-shutter-slots123-final
```

The earlier `menu_payload` Off→1→2→3 reorder under `…-final-menufix/` **regressed
on device** (blank captions, sticky labels, missing digits) and was **reverted** to
the upstream shutter choice order (`1→2→3→Off` / `1…5→Off`). The `…-final-menufix/`
tree now matches `…-final/` for menu bytes; staged install uses container
`1275b0a3…`.

## Settings backup

SD firmup **does not** run OM Workspace’s “save settings → flash → reload”
pipeline. That backup is a **PC / MTP** feature.

Before flashing:

1. OM Workspace → **Camera → Custom Settings → Save** (or OI.Share equivalent), or
2. Note critical settings manually.

After flashing, reload from the saved file if needed. Some settings are not
covered by Custom Settings export (official limitation).

## Card install steps

1. Charge the battery; preferably use a spare formatted SD card.
2. On the **host**, copy only the chosen tree’s `DCOLYMP` folder to the SD **root**
   (Slot 1). Resulting path on card: `DCOLYMP/E1479999.BIN`.
3. Eject the card from the PC; insert into camera **Slot 1**; camera **off**.
4. Hold **OK**, then power on while holding OK.
5. Screen stays blank; front **orange lamp solid** = programming (release OK).
6. When the orange lamp **blinks**, power off, wait a moment, power on normally.
7. Confirm version / features; then **delete `DCOLYMP`** from the card so the
   next OK+power does not reinstall.

Do **not** remove power or the card while the lamp is solid.

## Restore to stock 1.1

Repeat the same ritual with
`generated/om3-sd-install/stock-1.1-restore/DCOLYMP/`. Official Workspace
updates are generally **not downgradable**; the SD path is the practical
same-version / research restore route used here.

## What the repo tools still refuse

`tools/om3_sd_updater_probe.py`, `om3_firmup_sim.py`, and related probes
**never write** the camera volume. Staging under `generated/` is host-local.
Copying `DCOLYMP` onto a card and performing OK+power is an **operator** step
outside those tools.
