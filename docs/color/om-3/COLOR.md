# OM-3 COLOR (build 1100)

Cross-checked against PEN-F 3101 and E-P7 1100 by
[compare_color_generations.py](../../../tools/compare_color_generations.py).
Pixel equality and ISP execution are outside that audit.

## Landmarks

| Item | OM-3 1100 |
| --- | --- |
| HSL / COLOR table | `0x606ba608` |
| Sector gains | `0x606d413c` |
| Builder | `0x60518381` … `0x60518560` |
| Selector | `0x60518573` … `0x6051869e` |
| Writer | `0x604a3e73` … `0x604a4041` |

E-P7 and OM-3 share closely corresponding table structures and add **COLOR4**.
Inspected default saturation for the newer models is
`-4,0,0,0,-1,-1,-1,0,0,0,0,-4` with shadows/midtones/highlights `-3,0,+3`.
See the topic-level [MODES](../MODES.md) summary.

## What this does not establish

- A stock full-HSL wheel UI on OM-3.
- That PEN-F HSL1 Wi-Fi write encodings work unchanged.
- That table addresses may be patched identically across models.

Required inputs are listed under `native_om3` in
[tools/inputs.json](../../../tools/inputs.json).
