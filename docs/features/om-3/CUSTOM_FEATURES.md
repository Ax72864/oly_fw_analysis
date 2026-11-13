# OM-3 custom feature pack (build 1100)

Offline reconstruction of selected **db.firmware 0.3.1** sites for OM-3
`OLY_E_147_1100`, without the Korean UI pack. Physical SD install verified:
[FLASH_WORKFLOW.md](../../boot/om-3/FLASH_WORKFLOW.md).

## Features in the verified package

| Feature id | What it does | Physical check (2026-11-04) |
| --- | --- | --- |
| `ring-native` | Panasonic lens aperture-ring path on body | Reported working after flash |
| `wifi-5ghz` | 5 GHz Wi‑Fi hotspot support | Reported working after flash |
| `shutter-sound` | Electronic-shutter sound menu + PCM banks | Silent shooting played custom sounds |
| Custom slots 1 / 2 / 3 | User WAVs placed via `tools/om3_shutter_slots.py` | All three slots audible |

Verified slot map for the shipped install tree:

| Slot | Source WAV (under `generated/om3-shutter-sounds/candidates/`) |
| --- | --- |
| 1 | `es-wav/360329_Nikon_mechanical-dslr.wav` (~165 ms) |
| 2 | `guns/sfxmint_impact-gunshot-08.wav` (~450 ms) |
| 3 | `memes/muyu-guoji_科比Man-1707729239_科比Man-1707729239.wav` (~550 ms) |

WAV target for the bank tool: **48 kHz / 16-bit / stereo PCM**. Policy and
capacity notes: [generated/om3-shutter-sounds/POLICY.md](../../../generated/om3-shutter-sounds/POLICY.md).

## Offline build chain

1. `tools/om3_db_feature_patch.py` — applies ring / wifi / shutter **code** sites
   onto stock decoded main; emits lab container under
   `generated/om3-db-ring-wifi-shutter/`.
2. `tools/om3_shutter_slots.py` (CPython **3.12**) — runs upstream
   `multi_sound` / `sound_bank_fit` from pinned `db.firmware.0.3.1` PYZ; writes
   PCM + descriptors into the three banks; re-encodes container under
   `generated/om3-db-ring-wifi-shutter-slots123/`.
3. Host staging — copy lab BIN to `DCOLYMP/E1479999.BIN` under
   `generated/om3-sd-install/…` (see [FLASH_WORKFLOW.md](../../boot/om-3/FLASH_WORKFLOW.md)).

Stock pin: container SHA-256
`8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d`.

## How to test on camera

### Electronic shutter sound

Silent / e-shutter + drive; menu sound banks 1–3. Burst is **mono retrigger**
(next shot cuts the previous clip) — match the lab simulator default under
`generated/om3-shutter-sounds/simulator/`.

### 5 GHz Wi‑Fi hotspot

No special lens required (any lens or body cap is fine).

1. Enable the camera Wi‑Fi / hotspot as usual.
2. On a phone, open Wi‑Fi scan and check whether the camera advertises a
   **5 GHz** band (often shown as 5 GHz / channel ≥ 36, or a dual-band SSID).
3. Join and confirm OI.Share / transfer still works.
4. Optional A/B: restore stock 1.1 and confirm the same menu path is 2.4 GHz-only
   (or lacks the 5 GHz network) on your unit.

### Aperture ring (`ring-native`)

Needs a **Panasonic (Leica DG) lens that has a physical aperture ring**. The
ring is ignored on stock OM bodies; the patch makes the body honour it.

**Cannot test with** Lumix G Vario **14–140 mm** (II/III) — that zoom has **no**
aperture ring (aperture is body-dial only). Mounting it only proves AF/exposure
compatibility, not the ring patch.

Lenses commonly used to test the ring (non-exhaustive):

| Lens | Notes |
| --- | --- |
| Leica DG Summilux **15 mm f/1.7** | Common, compact; A / click-stop ring |
| Leica DG Summilux **12 mm f/1.4** | Ring |
| Leica DG Nocticron **42.5 mm f/1.2** | Ring |
| Other Panasonic primes that ship with a marked aperture ring | Confirm the ring exists before buying for this test |

Test procedure: set camera to A or M, turn the lens ring off **A**, watch F-number
track the ring; return to **A** and confirm body dials control aperture again.

## Related offline-only patches

`patches/sound/om-3` (CSHUT short-sound table) and `patches/power_lever/om-3`
remain **separate L2 acceptance experiments**. They are not part of the
verified SD package above.
