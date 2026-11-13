# OM-3 HSL (Hue / Lightness) research build

Experimental Color Creator 2 H/L on OM-3 **1.1 / 1100**, stacked on ring + 5 GHz +
shutter. Not an official OMDS feature. **Not yet verified on a camera body.**

## Emulator (om-emu)

Loaded as E147 main block in `third_party/om-emu/unpacked/E147/` (digest pinned in
`emu/src/fw/models.mjs`). Play URL kept:
`http://127.0.0.1:8765/?t=0_EYOX71RmtCZ__4kxolDg`

Checked so far: lab reaches `phase=running` with TFT frames; MENU enters
`SS_MENU/ID_ST_MENU`. COLOR H/L UI path not yet scripted in-emu. Prior crash from
a broken Delete dispatch (`jmp` into callee) is fixed (`call` + resume).

## Package

| Role | Path | SHA-256 prefix |
| --- | --- | --- |
| Flash (HSL + features) | `generated/om3-sd-install/patched-ring-wifi-shutter-hsl/DCOLYMP/E1479999.BIN` | `610e3cdf…` |
| Feature-only rollback | `generated/om3-sd-install/feature-only-rollback/DCOLYMP/E1479999.BIN` | `1275b0a3…` |
| Stock restore | `generated/om3-sd-install/stock-1.1-restore/DCOLYMP/E1479999.BIN` | `8c133084…` |
| Lab / report | `generated/om3-db-ring-wifi-shutter-hsl-b/` | see `report.json` |

## Behaviour (user-facing)

- COLOR1–4; Delete cycles Saturation → Hue → Lightness
- Range **−5…+5** (stock UI lists; H/L paths clamped the same)
- Live preview / JPEG path: H/L applied via COLOR builder when capture/recording transport runs

## Persistence / carry — exact status (code vs product)

All rows below are **implementation facts**. None are body-confirmed.

| Path | Result | Why |
| --- | --- | --- |
| Power-off / mode change keeps H/L in COLOR editor | **Yes (wired)** | Edit writes ACTIVE bank (`0x4831` packed); boot / commit / refresh republish into live source |
| JPEG / electronic shutter still use those H/L values | **Yes (wired)** | `capture_acquire` + `recording_to_job` unpack into job; builder consumes them. Compact path **not** hooked |
| In-camera RAW develop carries H/L | **Yes (wired)** | `raw_acquire` copies current profile packed H/L into the owner row used by that path |
| ORF → OM Workspace “Adjust Color” shows H/L | **No** | Only a packed copy at `owner+37694`; full CMIO table rewrite was **not** ported |
| Camera settings backup / restore keeps H/L | **Yes (wired)** | Custom type-2 line `2,OM3_HSL_V1,…` on export/import hooks |

“Wired” means the hooks and cave code are present end-to-end in this BIN. It does **not** mean a body has confirmed them.

## Omitted

- Wi‑Fi remote H/L
- ±7 UI / schemas / wheel encode
- Compact acquire/to-job
- Full ORF CMIO / Workspace Adjust Color H/L
