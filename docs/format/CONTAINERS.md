# Firmware containers and checksums

The inspected Olympus `OE` update files are sequences of independently packaged
components. A component is not a flash sector and is not the program's `main()`
function. It can contain application code, resources or peripheral firmware.

## Component layout

| Part | Length | Meaning |
| --- | ---: | --- |
| Header | 32 bytes | Model, address, payload length, build and component kind |
| Encoded payload | Header-defined; multiple of 16 | Scrambled component contents |
| Trailer | 32 bytes | Repeated metadata and additive checksum |

Header offsets used by the parser:

| Offset | Type | Field |
| --- | --- | --- |
| `0` | 2 bytes | `OE` signature |
| `2` | 2 bytes | Model identifier bytes |
| `8` | little-endian u32 | Container address |
| `12` | little-endian u32 | Payload length |
| `16` | little-endian u16 | Internal build |
| `20` | little-endian u16 | Component kind |
| `28` | 4 bytes | Zero in the reviewed header form |

The first 28 header and trailer bytes must agree. The parser rejects mixed model
identifiers, invalid lengths, incomplete components and unexpected header forms.
It supports the scrambled `OE` form; other formats require separate handling.

## Payload transform

Decode each 16-byte group by reading input positions
`1,3,0,2,6,4,7,5,11,10,9,8,13,14,12,15`, then XOR each byte with `0xff`.
Encoding reverses that permutation. This is reversible obfuscation, not evidence
of a cryptographic signature.

Treat the header, **decoded** payload and trailer as little-endian 32-bit words.
Their sum must be zero modulo `2^32`. The final trailer word makes that sum zero.
Repacking must preserve all other metadata; merely repairing the checksum can
leave a malformed header or the wrong model/build identifier.

[oly_container.py](../../tools/oly_container.py) provides `parse`, `decode`,
`encode`, `reconstruct` and same-sized `replace_payload`. Its unchanged round
trip must reproduce the entire input byte for byte.

```sh
python3 tools/oly_container.py firmware.BIN --out decoded --expect-sha256 HASH
```

The transform was independently implemented from the
[Altsoph/mx3 Olympus analysis](https://chdk.setepontos.com/d/2471-olympus-emjustylus-series-fw-analysis).
Historical stock/hack pairs provide additional whole-file round-trip checks.

## Partial-component update files

PEN-F 3101 contains four components. Native updater tests accept a complete
main component without the unchanged resource components. Physical HSL update
and stock-restoration tests also exercise component-selective packages.

| PEN-F package | Bytes |
| --- | ---: |
| Full stock update | 87,031,808 |
| Main component only | 21,364,736 |
| Main plus OSD component | 44,433,408 |

The smaller package omits components; it does not compress or relink the main
payload. Including an OSD bitmap edit requires its resource component as well.
The updater writes each included component's full extent, not just changed bytes.

The `9999` suffix used for SD installation is file-selection data, separate from
the internal build field. Same-version installation is accepted on the tested
camera-side path; Workspace's download eligibility is a different layer.

See [address spaces](pen-f/ADDRESS_SPACES.md), [recovery](../boot/pen-f/RECOVERY.md), and
[historical patch behavior](../features/HISTORICAL_HACKS.md).
