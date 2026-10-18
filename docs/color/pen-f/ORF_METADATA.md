# Captured HSL in ORF metadata

An ORF can preserve the HSL **rendering effect** in native Olympus metadata
without a private tag. That differs from restoring the H/L slider positions
in Workspace's Adjust Color panel.

## Native fields

Olympus ImageProcessing IFD `2040` contains two CMIO data blocks:

| Block | Tag | Length |
| --- | --- | ---: |
| Parameters (P) | `0635` | 5,764 bytes |
| Tables (T) | `0636` | 119,360 bytes |

These are processing data, not executable code. The relevant decoded offsets are:

| Contents | sRGB | AdobeRGB | Length per slot |
| --- | --- | --- | ---: |
| P H/S/L coefficients | `398` | `3e0` | 72 bytes |
| T base table | `2498` | `306c` | 3,028 bytes |

The representation used by the PEN-F extension places the creative COLOR base
table in both Natural T slots and captured H/S/L triplets in both P slots.
Workspace replaces the base coefficients with P values. Dynamic H/L therefore
need not be baked into a separate full T table for each photo.

PEN-F 3101 provides COLOR template `60622d74`, Natural templates `60619f84` and
`6061ab58`, encoded T at `6067e000`, and saturation-gain pointers at `6062fef8`.
Sector order and H/L scales are in [HSL tables](HSL_TABLES.md).

## Encoding and ownership

In the affected T region, encoding follows:

```text
C[p] = P[p] XOR P[p-1] XOR K[p]
```

A known plaintext change at p affects encoded bytes p and p+1. Adjacent
replacement ranges share a boundary byte, so the combined change must be checked
against a full decode. The host helper rejects repeated application rather than
accidentally undoing an XOR delta.

The camera serializer reads the image-owned captured H/L, not the current
editor. Metadata-only test copies preserve RAW strips, length and unrelated
metadata. Their embedded JPEG still shows the original image until a fresh
render is requested.

## Workspace behavior

Original Workspace batch exports reproduce the embedded effect, including
nonzero values in every sector and both output color spaces. Camera-created ORFs
also preserve the captured coefficients. In the tested Windows GUI:

- Initial display can use the embedded JPEG.
- Fresh development after an adjustment/reset uses the CMIO HSL look.
- Adjust Color remains disabled; H/L sliders are not initialized from CMIO.
- Enabling Adjust Color explicitly replaces that embedded look with panel values.

GUI export option selection is distinct from the separately tested batch-export
path. These findings concern COLOR/Natural-based processing; they do not imply
that arbitrary ART modes use the same fields.

## Slider metadata and edit recipes are separate

CameraSettings tag `0539` contains fourteen signed shorts: minimum, maximum and
twelve saturation values. The inspected reader copies those twelve values;
appending H/L would not make it interpret them. The ±7 extension updates the
range metadata accordingly.

Workspace's local edit history uses database `filter_data`. Portable OES recipes
carry `ColorCreater2` arrays `HueValue`, `SatValue` and `LumValue`. Neither is the
same as native captured CMIO. Remembering an edit on one desktop installation
is not evidence that its sliders were written into the ORF.

Use [penf_orf_native_cmio.py](../../../tools/penf_orf_native_cmio.py) on a copy with
matching PEN-F data. Its checks protect the expected structure; they are not a
general ORF repair facility.
