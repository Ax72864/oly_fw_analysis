# OM-3 HSL patch (B, stacked on feature pack)

Hue / Lightness for Color Creator 2 (COLOR1–4, IDs **928–975**) on OM-3 **1.1 /
1100**, stacked on ring + 5 GHz + shutter (+ WAV / menu-order).

## Build

Needs `mn10300-elf` `as`/`ld` under `toolchains/mn103-gas-ld-build/` (MSYS
`PATH`), plus `objcopy`. Baseline:

`generated/om3-db-ring-wifi-shutter-slots123-final-menufix/main.decoded.bin`

```bash
py -3.12 patches/hsl/om-3/gen_patch_json.py
py -3.12 patches/hsl/om-3/build.py --out generated/om3-db-ring-wifi-shutter-hsl-b
```

Install: `generated/om3-sd-install/patched-ring-wifi-shutter-hsl/DCOLYMP/E1479999.BIN`.

## Groups

| Group | Role |
| --- | --- |
| `image_parameters` | COLOR builder hook |
| `editor_storage` | editor, persist, wheel, transport, RAW, ORF |
| `settings_backup` | named backup line OM3_HSL_V1 |

Abandoned by request: Wi‑Fi HSL1, ±7 wheel encode / value labels.

See [docs/color/om-3/HSL.md](../../../docs/color/om-3/HSL.md).
