# OM-3 address spaces (build 1100)

File offsets, container addresses and CPU analysis addresses are different.
Numbers below refer to the stock container
`OLY_E_147_1100_0000_0000.BIN`
(SHA-256 `8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d`).

## Container components

| Index | Kind | Payload bytes | Container payload address | Decoded SHA-256 (prefix) |
| --- | ---: | ---: | --- | --- |
| 0 | `0x100` main | 33,554,368 | `0x50000020` | `5e8d376e…7d59` |
| 1 | `0x101` | 60,817,344 | `0x41ec0020` | `6d2bef74…8226` |
| 2 | `0x106` | 143,523,776 | `0x458c0020` | `3d9fd442…b059` |
| 3 | `0x10e` | 262,080 | `0x20` | `b9200daf…ca87` |
| 4 | `0x102` | 2,097,088 | `0x4e1a0020` | `494cd9ef…4c09` |
| 5 | `0x107` | 262,080 | `0x8000020` | `9a9e7abe…e377` |

Model bytes are `1470`. Public version label is 1.1; internal build is `1100`.
Prepare with:

```bash
python3 tools/oly_container.py \
  firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN \
  --expect-sha256 8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d \
  --code-base 0x60021020 --out analysis/om3_1100
```

## Analysis base

Decoded main is mapped for disassembly and probes at `0x60021020`, matching the
repository's PEN-F analysis convention. The container header address
`0x50000000` / payload `0x50000020` is **not** that CPU base.

See also the shared [container format](../CONTAINERS.md) and the
[PEN-F address-space notes](../pen-f/ADDRESS_SPACES.md) for section-load caveats
that also apply when judging FF gaps on OM-3.
