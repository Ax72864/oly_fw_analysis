# OSD graphics, text and palettes

PEN-F build 3101 stores UI resources in a component separate from main code.
Its indexed banks contain bitmaps, symbols and language fonts. Resource loading,
individual decoding and drawing are distinct operations.

## Resource loading and checksums

Initializer `602b8573` reads the OSD header/directory at logical `41800000`.
Loader `602b8919` loads an indexed extent and caches its bank state. Bank 0
contains common symbols; bank 69 contains additional bitmaps. Many panel requests
can load bank 69, not only COLOR entry.

The executed loader checks sizes and bank state but performs no identified
per-bitmap CRC. A bitmap edit still changes the containing component's additive
checksum. Native updater tests reject a stale resource checksum before writing
any component, including a valid main component in the same file. Reviewed
combined updates program OSD before main, regardless of file order.

## In-place bitmap replacement

Stock “Vivid” is bitmap 4222, not dynamically rendered text. Its descriptor is
`a2bbb84c`, payload `a2bbb498`, decoded OSD offset `01287a78`: 52×26 pixels in a
948-byte allocation. Replacing it with “Value” preserves its dimensions,
descriptor, pointers, palette roles and token allocation. The regular replacement
changes 725 decoded resource bytes; the component length stays constant.

Two host decoders check pixel count, row bounds, palette indices and padding.
A scan of other descriptors finds no overlapping payload. Native resource-load
replay uses the same storage requests and flow. Physical tests confirm the
replacement renders correctly. This is evidence for that asset, not a universal
format proof for every bitmap: one unrelated stock asset exceeds the extractor's
current strict interpretation.

## Text colors depend on the drawing layer

The formatter builds glyph palette `[0, foreground+2, foreground+1, foreground]`.
Foreground 4 is white only on the intended text palette. Palette 6 has white/gray
at indices 4/5/6; overlay palette 4 has green/blue/translucent black there. Wrong
layer selection can therefore look like a pixel-format error.

Palette words use AARRGGBB, established by native channel extraction. Shooting
layout uses logical layer 1 with palette 5, layer 2 with palette 6, and layer 3
with palette 4. Logical, backend and device-layer indices are different mappings.
Stock child traversal checks a child's layer; a new parent paint hook must enforce
its own layer condition.

Native rendering entry points include:

- Text/symbol formatter: `60bc1fbf`.
- Full bitmap: `60bc49b6 → 60bcc182 → 60bcd0cf → 606e1258`.
- Filled rectangle: `60bc69b8 → 60bc722b → 60bcc0e8 → 60bccf1b → 606e15cc`.

A translucent backdrop can use palette 5 index 2 (`88000000`) on layer 1, with
lettering on layer 2. Separate layers avoid depending on whether blank glyph
pixels skip writes or overwrite the earlier rectangle with transparency.

## Font size and layout

The general English font bank resolves several requested size keys to the same
32-pixel glyph family; the generic scaling callback is null on this camera.
There is also a complete separate 12×24 bitmap alphabet. It can compose a short
fixed caption without a new scaling backend. The stock trash symbol is 44×32.

Screen container dimensions do not necessarily describe the visible wheel area.
Two child layouts shift their X coordinates by 80 while leaving Y unchanged.
Anchoring added labels to the stock heading avoids falsely centering against an
800-wide container on a differently clipped surface. Preview actual glyph cells,
not just their ink: later transparent cells may erase neighboring content.

The native drawing context is 684 bytes. Copying it before changing font, pen,
brush or clip avoids altering the caller's context. Include that copy in stack
accounting, and do not keep a large extra frame active during recursive stock
child painting. Naturally align style structures; see
[validation](../../safety/VALIDATION.md).

Tools: [bitmap extractor](../../../tools/penf_osd_bitmaps.py),
[symbol extractor](../../../tools/penf_osd_symbols.py),
[native text probe](../../../tools/penf_color_text_probe.py).
