# OM-3 electronic shutter sound (build 1100)

Goal: understand why silent/e-shutter may lack an audible cue, and where a
stock or patched sound could be attached. Analysis only; no flash procedure.

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

## How to prove a fix path (offline)

1. Native call into `aud_ikey_to_wavetype_is_short_sound` with synthetic ikey
   values for silent vs mechanical shutter; record returned wave type.
2. Trace callers of `Start_Play_Sound_Ext` for shutter-complete events.
3. Diff silent vs mechanical capture completion in a future connected probe.
4. Only then consider a cave that plays `MDN_BEEP` or a short WAV on e-shutter
   complete — placement must follow [code-space caves](../../safety/om-3/CODE_SPACE.md).

PEN-F comparison: this repository’s deepest sound work is not a PEN-F e-shutter
beep patch; treat OM-3 audio as its own subsystem (`api_sound.c` / `aud_*`).
