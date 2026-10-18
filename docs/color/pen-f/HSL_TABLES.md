# HSL tables, sector order and value scales

PEN-F build 3101's COLOR table starts at `60622d74`. Its 3,028-byte layout is:

| Contents | Size |
| --- | ---: |
| Twelve records, 28 bytes each | 336 |
| Four LUTs, 96 × u32 each | 1,536 |
| Six LUTs, 96 × u16 each | 1,152 |
| Trailer | 4 |

A byte-identical table exists in the inspected Workspace OlyAcacia library.
Camera request builders and Workspace renders provide stronger correspondence
than the byte match alone. The camera ultimately uploads the coefficients and
LUTs to ISP banks; its pixel arithmetic is not CPU-emulated here.

## Sector order

OES arrays and the camera wheel use the same twelve-sector sequence. Physical
coefficient records use a different order:

| OES index | Wheel sector | Descriptive hue | Table record |
| ---: | ---: | --- | ---: |
| 0 | 1 | Yellow / gold | 0 |
| 1 | 2 | Orange | 6 |
| 2 | 3 | Red | 1 |
| 3 | 4 | Rose / pink-red | 7 |
| 4 | 5 | Magenta | 2 |
| 5 | 6 | Violet / purple | 8 |
| 6 | 7 | Blue | 3 |
| 7 | 8 | Azure / sky blue | 9 |
| 8 | 9 | Cyan | 4 |
| 9 | 10 | Teal / blue-green | 10 |
| 10 | 11 | Green | 5 |
| 11 | 12 | Yellow-green / lime | 11 |

The names describe measured response families, not recovered official labels or
sharp HSV boundaries. The internal angle geometry belongs to a chroma space;
using ordinary RGB hue angles to name records can misidentify them. “ALL” is an
editor operation on the twelve values, not an extra coefficient record.

## Slider to coefficient

For the shared −7…+7 convention:

```text
H_native = −1000 × H_slider
L_slider =  −7   −6   −5   −4   −3  −2  −1  0  1  2   3   4   5   6   7
L_native = −300 −250 −200 −150 −100 −50 −25  0 25 50 100 150 200 250 300
```

Saturation uses sector-dependent gains and fixed-point arithmetic. It is not
stored as the slider integer in the final coefficient. For example, yellow
S=+5 produces 225 and +7 produces 315 in the examined conversion. The extra
range extends strength; it does not rescale the old −5…+5 range. CMIO/OES
conversion can differ by one coefficient unit because of integer-rounding order.

The HSL extension applies H/L after the stock COLOR builder at `604f7506`, then
rejoins `604f750b`. This preserves saturation handling and the common LUTs.
Bounds must be checked before indexing the fifteen-entry conversion tables.

## Adjacent-LUT upload tail

Bleach Bypass II's last 96-halfword LUT begins at `60622cb0`, just before COLOR.
The hardware upload copies 128 halfwords. The extra 32 contain its trailer and
the beginning of the COLOR records, including H/S/L fields.

This is an over-length transfer, not a demonstrated CPU buffer overwrite or
an extra “all colors” coefficient. No following copy was found to repair it.
The corresponding desktop unpacker/interpolator consumes only the intended
96 entries. A physical yellow-lightness modification changed COLOR output while
Bleach Bypass II stayed within repeat variation, supporting an unused hardware
tail in that case. It does not prove that every ISP mode ignores the surplus.

## Extended-range integration

Extending the editor requires more than changing a clamp: the settings value
lists, ALL bounds, number widgets, wheel arrays, backup value names and RAW
range metadata all encode the stock eleven positions. The extended wheel uses
fifteen positions with radius `26 + 6 × (value + 7)`; zero stays at radius 68.
Physical tests cover endpoints, ALL, reset, custom-bank recall and persistence.
Returning to stock requires stored saturation values to be within its supported
range; flashing stock does not automatically reset settings.
