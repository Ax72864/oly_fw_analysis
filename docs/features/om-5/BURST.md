# Silent burst rates and Pro Capture capacity

OM-5, E-M1 II and E-M1 III use comparable software rate descriptors, but their
buffer configuration differs substantially. A menu constant is only the first
of several limits. Mechanical shutter rates are outside this analysis.

Compared builds: OM-5 1200, E-M1 II 3700, E-M1 III 1600 and E-M5 III 1700.

## Rate lists

| Mode | OM-5 | E-M1 II / III |
| --- | --- | --- |
| Silent H / Pro Capture H | 15, 20, 30 fps | 15, 20, 30, 60 fps |
| Silent L | 1…10 fps | Also 15 and 18 fps |
| Pro Capture L | 10 fps | 10, 15, 18 fps |
| Pre-shutter bound | 14 | 35 in the compared later firmware |

Firmware arrays store tenths of fps. Their descriptors are 20-byte records with
key, pointer, count, element size and flags. OM-5 Silent H/Pro H arrays are at
`605097cc` / `60509db2`; E-M1 III at `604d9ae8` / `604da0d4`; E-M1 II at
`604ede02` / `604ee3e6`. Public setting IDs differ; typed keys `f142`, `f152`,
`5402`, `5412` identify corresponding routes.

Replacing an OM-5 list value 300 with 600 in a memory fixture is accepted by the
native menu consumer. That does not establish sensor readout at 60 fps.

## Runtime rate selection

A second table is copied into initialized RAM. On OM-5 its pointer array is at
`61e34374`, sourced from `602590b4`; corresponding mode-14 tables are at
`601d3b74` / `601d473c`. E-M1 III uses `61e744a0`, source `602541e0`, tables
`601d587c` / `601d6444`.

Both native consumers accept a requested 60 in the tested flag-0 path. The
flag-1 path caps at 30. This is stronger than finding a menu constant, but still
only validates software selection under supplied mode/flag fixtures.

## Queues and image pools

| Resource | OM-5 | E-M1 III |
| --- | --- | --- |
| Frame-handle ring | 32 × 4 bytes at `620cfd60` | 64 × 4 bytes at `6210f254` |
| Frame bookkeeping | 32 usable 20-byte records | 64 usable 20-byte records |
| Large-image pool, stride 32,798,208 | 18 slots | 50 slots |
| Auxiliary pool, stride 53,760 | 18 slots | 50 slots |
| Metadata pool, stride 41,984 | 32 slots | 64 slots |

The ring is fixed allocated state: following fields begin immediately after it.
Increasing a bound alone overwrites those fields. Image-pool allocation assigns
handles within configured regions; it is not evidence of an unrestricted heap
that can simply grow the capture capacity. Moving the ring would require tracing
all references, and would not create additional large-image buffers.

Pool registries are at `60575c70` (OM-5) and `60545cdc` (E-M1 III). Region addresses
are virtual/alias mappings, not proof of installed physical RAM. Shared TruePic
branding likewise does not establish identical memory or sensor wiring.

Pre-capture settings use typed keys `5462`/`5472`, with related limiters
`5421`/`5432`/`5441`/`5452`. The native trimming calculation uses configured
pre-count, queue length and a caller-supplied limit; it does not establish that
the latter equals all physically available frames. Total-frame bounds also
include pre-capture frames.

The [pool probe](../../../tools/om5_image_pool_probe.py) exercises allocation,
exhaustion and release using modeled memory. These results do not qualify a
60-fps or enlarged-prebuffer camera patch.
