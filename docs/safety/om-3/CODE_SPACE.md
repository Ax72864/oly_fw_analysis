# OM-3 code-space caves (build 1100)

General method: [safety/CODE_SPACE.md](../CODE_SPACE.md).

The V22 tethering patch places added code in three **loaded** section tails:

| Section | Loaded range | FF suffix within load | Added span |
| --- | --- | --- | --- |
| 1 | `60134000..6031f000` | `6031e910..6031f000` | `6031e920..6031efeb` |
| 4 | `60828000..60a8f800` | `60a8f088..60a8f800` | `60a8f100..60a8f800` |
| 9 | `61809000..619a9800` | `619a966c..619a9800` | `619a9680..619a9800` |

Ends are exclusive. Usable suffixes are 1,776 / 1,912 / 404 bytes. Larger FF
runs outside the load bounds are not established free code space.

Native qualification uses [om3_code_space_audit.py](../../../tools/om3_code_space_audit.py)
and the shared probe harness [om3_probe.py](../../../tools/om3_probe.py).
Working USB live view remains a contributor report, not a claim proved by the
offline audit alone.
