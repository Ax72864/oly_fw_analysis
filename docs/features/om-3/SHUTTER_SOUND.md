# OM-3 electronic shutter sound (build 1100)

Goal: understand why silent/e-shutter may lack an audible cue, and where a
stock or patched sound could be attached.

**Physical status:** research packages with db.firmware-style shutter-sound plus
three custom WAV slots were SD-flashed to an OM-3; silent shooting played slots
**1 / 2 / 3**. Current stable Caduceus merge:
[CADUCEUS_V0262_SHUTTER_STABLE.md](CADUCEUS_V0262_SHUTTER_STABLE.md)
（v0.26.2 resident，`71e5de2c…`，2026-11-13 机身通过）。

**Known limitation:** custom e-shutter sound is audible only when the body’s
**focus-lock confirmation beep** is enabled; with that beep off, slot select
still works but playback is silent. Not treated as intentional patch gating;
left unfixed for now.

## Sound pipeline leads

ASCII leads in the pinned main (`tools/om3_string_leads.py`):

| Symbol / string | Analysis address | Notes |
| --- | --- | --- |
| `PLAY_SOUND` | `0x602ee0d8` | ptr xref `0x60219365` |
| `API_SOUND` / `api_sound.c` | `0x6035fc79` / `0x606298e8` | API surface name |
| `Start_Play_Sound_Ext` assert | `0x60628ac6` | External play entry with param checks |
| `aud_ikey_to_wavetype_is_short_sound` | `0x60ddba74` | ptr `0x60adf84d`; maps UI/ikey → wave type |
| `aud_soundic_*` / `aud_seq_power_util_soundic_poweron` | `0x60a8c7bf` family | Codec / power sequencing |
| `MDN_BEEP` | `0x61954e69` | ptr `0x619553f8`; menu/beep media name |
| `SILENT_SETTING` | `0x612f16b6` | ptr `0x612f1d68`; silent-shooting settings subtree |
| Embedded `RIFFWAVEfmt` | `0x60366df0` | At least one in-image WAV container |

Silent UI also exposes touch/synchro-scan “SILENT_TAB” strings around
`0x60e3c7c9` and shutter-speed silent setting change-info at `0x61348dda`.

## Why e-shutter may be quiet

Working hypothesis from naming (not yet natively executed):

1. Mechanical paths drive shutter motor/magnet sequences (`SHUTTER_MOTOR_*`,
   `SHUTTER_MAGNET_*` near `0x6021c1d1`) that are inherently audible.
2. Silent / e-shutter routes through `SILENT_SETTING` and may suppress or never
   call `Start_Play_Sound_Ext` / short-sound wave selection.
3. Even if a wave type is selected, `aud_soundic` power/format must be up;
   HDMI/sound-format helpers show separate enable paths.

## Resolved entries (build 1100, offline)

| Symbol | Entry / evidence | ABI notes |
| --- | --- | --- |
| `aud_ikey_to_wavetype_is_short_sound` | `0x60adf844` | `a0` = ikey C string; `d0` = short? (0/1); call mask `0xf0` frame `0x1c` |
| ikey → short table | `0x60ddb9e4` (18×8) | `PRM_AUD_SHUT*_VOL` → 1; `PRM_AUD_CSHUT*_VOL` → 0 |
| `Start_Play_Sound_Ext` | `0x604375d6` | prologue `movm`+`add -48`; probe CALLER **mask=0 frame=0**; stable return with peer stubs |

Native map + play return + L2 CSHUT table patch:
`python tools/om3_preflash_validate.py --out generated/om3-preflash-validate`  
(`patches/sound/om-3/` flips `PRM_AUD_CSHUT*_VOL` short flags for offline acceptance).

## How to prove a fix path (offline)

1. Native call into `aud_ikey_to_wavetype_is_short_sound` with synthetic ikey
   values for silent vs mechanical shutter; record returned wave type. **Done**
   in `om3_preflash_validate` (`PRM_AUD_SHUT*` short, `PRM_AUD_CSHUT*` not).
2. Trace callers of `Start_Play_Sound_Ext` for shutter-complete events.
3. Diff silent vs mechanical capture completion in a future connected probe.
4. The **shipping** research path is not a one-off `MDN_BEEP` cave: it reuses
   upstream multibody shutter-sound code caves + PCM arenas
   (`tools/om3_db_feature_patch.py` + `tools/om3_shutter_slots.py`). WAV target
   format and bank budget: [POLICY.md](../../../generated/om3-shutter-sounds/POLICY.md).

The older L2 table flip under `patches/sound/om-3` remains an offline acceptance
experiment only; it is **not** the verified three-slot package.

PEN-F comparison: treat OM-3 audio as its own subsystem (`api_sound.c` / `aud_*`).
