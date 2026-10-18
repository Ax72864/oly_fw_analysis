# Picture modes and creative controls

PEN-F's JPEG settings have several distinct entry points. They eventually share
parts of the image-processing machinery, but are not aliases for one saturation
wheel.

| Family | Controls and processing |
| --- | --- |
| Natural, Vivid, Muted, Portrait and other picture presets | Preset color tuning plus ordinary contrast, saturation and sharpness settings |
| Monotone | Monochrome conversion, virtual color filter and tint |
| Front-dial COLOR | Twelve sector saturation values, three stored profiles; tone and creative shading controls |
| Front-dial MONO | Three profiles with monochrome filter, grain, tint, tone and creative shading |
| Front-dial CRT | Color Creator: a different hue/saturation control, sharing some editor infrastructure |
| ART | Effect-specific processing, sometimes several jobs and intermediate images |

COLOR's twelve sectors must not be confused with CRT's thirty hue positions.
Stock PEN-F COLOR exposes saturation −5…+5. The native HSL tables also contain
hue and lightness coefficients; their existence is separate from a UI that edits
those coefficients.

## Presets enter through more than one color control

Native request construction exercises a six-axis hue/saturation control in
addition to the twelve-record HSL table. Example arrays from the same fixture:

| Preset | Six saturation coefficients | Six hue coefficients |
| --- | --- | --- |
| Vivid | `18,4,24,0,8,8` | `0,2,4,-1,-6,0` |
| Muted | `-22,4,-16,0,4,-8` | `3,0,-3,9,8,10` |
| Portrait | `14,0,0,5,0,0` | `-1,0,2,-2,0,0` |
| Natural / COLOR / MONO | zero in this fixture | zero in this fixture |

These are internal coefficients, not slider units or an exhaustive description
of each look. Matrix, gamma, tone, chroma and HSL controls are built separately.
A portrait look need not be implemented by writing lightness into the COLOR
wheel's table.

## Across generations

PEN-F, E-P7 and OM-3 have closely corresponding COLOR table structures. The first
three factory COLOR recipes also correspond. E-P7 and OM-3 add COLOR4; their
inspected default saturation array is `-4,0,0,0,-1,-1,-1,0,0,0,0,-4`, with
shadows/midtones/highlights `-3,0,+3`.

This comparison does not reveal a stock full-HSL wheel on the newer models.
A table's common layout is useful for locating code, not evidence that its
address, load section or hardware interface can be patched identically.

On PEN-F there are **15 user-facing COLOR profiles**: three in current settings
and three in each of C1–C4. The nine internal settings banks include paired custom
records and do not imply 27 independent profiles. See
[saved settings](pen-f/SETTINGS_STORAGE.md).

Tools: [generation comparison](../../tools/compare_color_generations.py) and
[factory-profile comparison](../../tools/compare_color_profile_defaults.py).
