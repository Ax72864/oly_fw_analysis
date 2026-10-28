# OM-3 startup (build 1100)

Addresses refer to OM-3 build **1100** unless stated otherwise. Use the offline
harness for debugging; it is not a complete board boot.

## Entry

- Decoded main analysis base / entry: `0x60021020`
- Stock main SHA-256: `5e8d376e9111a44ac0352f26030d7c1b17026d42c45f3600cfa02a0e8c5b7d59`
- Section descriptor table (V22 audit): `0x60029b28`
- Section-end getter / loader: `0x60045e6c` / `0x60045ed5`

Observed early entry helpers:

| Address | Role (from disassembly) |
| --- | --- |
| `0x600210b5` | Read controller word `0x98e0009c`, store to `0x628ac680` |
| `0x600210aa` | RMW halfword at `0x8070` |
| `0x60021046` | Store via `a2=0x98100000` offset 8 → write `0x98100008` |

## Debug harness

```bash
# First frontier (stop on unmodeled access)
python tools/om3_boot.py prefix --out generated/om3-boot-prefix

# Continue with a larger budget / breakpoints
python tools/om3_boot.py run --limit 200000 --breakpoint 0x600216b1 --out generated/om3-boot-run

# Idle peers are not ported yet (explicit incomplete status)
python tools/om3_boot.py idle
```

How to extend toward idle:

1. Read `fault.address` / `fault.pc` from the JSON report.
2. Disassemble the PC window with MN103 `objdump`.
3. Add only that register/RAM model in `OM3BootState` with an assumption note.
4. Re-run; do not copy PEN-F peer schedules until addresses are remapped.

`penf_boot_*` multi-core idle / console / SD peers are **not** interchangeable.

## Gaps versus PEN-F

PEN-F has a deep connected boot (`penf_boot_sd_mount`, `penf_boot_console_idle`,
mode-dial ADC models, …). OM-3 currently has a main-image debugging front-end
plus qualified code-space loader probes. Physical OK+power / USB wake selection
is not established.
