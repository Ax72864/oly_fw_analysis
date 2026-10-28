# OM-3 startup (bounded notes)

Addresses refer to OM-3 build **1100** unless stated otherwise. This page records
what the repository can reproduce offline. It is **not** a PEN-F-depth boot map.

## Known entry and loader facts

- Decoded main analysis base: `0x60021020`.
- Section descriptor table used by the V22 code-space audit: `0x60029b28`
  (ten 12-byte entries).
- Section-end getter: `0x60045e6c`; loader: `0x60045ed5`; storage read helper:
  `0x600232d1`; loaded-bit word: `0xa32de590`.

These symbols are exercised by
[om3_code_space_audit.py](../../../tools/om3_code_space_audit.py) and the smoke
path in [om3_probe.py](../../../tools/om3_probe.py). Passing those probes shows
native return from the named helpers under modeled storage, not a complete
camera UI boot.

## Explicit gaps versus PEN-F

PEN-F has a large family of `penf_boot_*.py` harnesses that model GPIO, SD,
semaphores and multi-core startup through USTART tasks. OM-3 does **not** yet
have an equivalent connected boot replay. Do not substitute PEN-F task IDs,
section-3 load ranges or MMIO responses when claiming OM-3 startup coverage.

## Recovery

No independent OM-3 brick/recovery map is established here. Contributor reports
about the V22 tethering patch recovering from a failed flash are attributed in
[HISTORICAL_HACKS](../../features/HISTORICAL_HACKS.md); they do not identify a
pre-main recovery ROM path for OM-3 in this tree. Treat
[PEN-F recovery limits](../pen-f/RECOVERY.md) as methodological caution, not as
an OM-3 procedure.
