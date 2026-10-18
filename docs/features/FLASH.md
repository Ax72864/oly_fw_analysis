# External-flash identification and hardware controls

PEN-F, E-P7, OM-3 and OM-5 share a recognizable external-flash protocol parser.
Support cannot be inferred from that parser alone: hotshoe contacts, GPIO
configuration and power electronics can differ.

An uncovered E-P7 hotshoe photograph shows one large sync contact and three small
contacts, excluding the rails. It lacks the additional-contact arrangement used
with FL-LM3. The [official compatibility table](https://support.jp.omsystem.com/en/support/imsg/digicamera/compati/pen_flashes.html)
also lists E-P7 as incompatible. Matching visible contacts on other models would
still not prove matching power conversion or populated circuitry.

## Identification parser

Compared builds are PEN-F 3101, E-P7 1100, OM-3 1100 and OM-5 1200.

| Model | Parser | Class-2 control branch | Logical port |
| --- | --- | --- | ---: |
| PEN-F | `602d139d` | `602d0756` | 95 |
| E-P7 | `6016b22c` | `6016a2e9` | 255 |
| OM-3 | `601e75ba` | `601e6644` | 22 |
| OM-5 | `60188d14` | `60187dd2` | 104 |

The parser accepts a seven-byte command-`86` reply. Its checksum is the low byte
of `86 + sum(first six bytes)`. The identifier is reply byte 0's low seven bits;
77 has special handling. Reply byte 2 bit `40` selects class 2 rather than 1.
No captured FL-LM3 reply establishes its actual protocol ID; an EXIF model number
must not be substituted for it.

The E-P7/OM-3/OM-5 parser instructions agree after normalizing addresses and
helper destinations. PEN-F shares the tested class behavior, but newer models
also map reply byte 5 bit `20` into capability bit `80`.

## E-P7's disabled output route

E-P7 startup initializes five remap descriptors with zero remap entries. Port
255 therefore remains 255 through wrapper `60172e44`, dispatcher `600688cf`,
handler `600691c3` and remapper `60022254`. It returns before MMIO or callback.
The corresponding release helper `6016bb7b` is also a bare return; the other
compared cameras have active GPIO handling.

Native tests cover five descriptors with output values zero/one and allow no
MMIO access. This establishes a compiled no-output route, not merely a guessed
“invalid port” convention. Together with the contact difference, it supports a
hardware/configuration distinction. Replacing 255 with an invented port number
would not establish electrical compatibility.

No equivalent unsupported OM-5 II or new PEN image was available for this
comparison. Manufacturer motives such as licensing or product segmentation
cannot be inferred from these observations.

Tools: [parser comparison](../../tools/compare_external_flash.py) and
[E-P7 GPIO probe](../../tools/ep7_flash_gpio_probe.py).
