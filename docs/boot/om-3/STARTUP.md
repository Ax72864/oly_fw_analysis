# OM-3 startup (build 1100)

Addresses refer to OM-3 build **1100** unless stated otherwise. The offline
harness starts at the downloaded main entry and can auto-stub unmodeled
MMIO/RAM so long runs reach `stable_under_budget`. That outcome means the
instruction budget finished without an unhandled fault — **not** a claimed
UI/RTOS idle, and not silicon-qualified timing.

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
| `0x600210a0` | SP switch (`mov a0,sp`) then jump to `0x600210c5` |
| `0x60021530` / `0x600215e9` | DMA/copy ready poll on `0x9bc00004` bit0 |
| `0x600216b1` | Historical frontier write to `0x988004a0` |
| `0x60022e99` | Storage busy clear poll on `0x98d002f0` bit0 |
| `0x600333e9` | 4-core ready mask poll on `0x97f00000` (expect `0xf`) |
| `0x600335fa` | Peer doorbell poll on `0x8958` bit4 |
| `0x60036a13` | Intentional `bra self` when CPU object `+0x168 != 1` |
| `0x60036a2b` | `bra self` after idle callback `*(obj+0x134)` returns |
| `0x6003330b` | Pending-callback walker (used as synthetic idle target) |

## Debug harness

Requires the MN103 engine from `tools/build_mn103_emulator.py` and the pinned
stock main under `analysis/om3_1100/`.

```bash
# First unmodeled access (no auto-stub)
python tools/om3_boot.py prefix --out generated/om3-boot-prefix

# Past the old 0x988004a0 / pc=0x600216b1 frontier; auto-stub + completions
python tools/om3_boot.py advance --limit 2000000 --out generated/om3-boot-advance

# Large budget; leave bra-self parks and re-enter init (default)
python tools/om3_boot.py idle --out generated/om3-boot-idle

# Stay on the intentional self-halt (old debug steady state)
python tools/om3_boot.py idle --no-beyond-halt --out generated/om3-boot-halt

# Breakpoint helper
python tools/om3_boot.py run --breakpoint 0x600335fa --out generated/om3-boot-bp
```

Reports land in `--out` as `om3-boot.json`, `auto-stubs.json`, and `events.json`.
`--out` may be reused: the directory is created if missing, and those three files
are overwritten on re-run. Omit `--out` to print only the compact stdout summary.

Observed results (stock 1100, synthetic peers/completions):

- Historical frontier `0x988004a0` / `pc=0x600216b1` is cleared.
- With `--no-beyond-halt`: parks at `0x60036a13` (`bra self`).
- Default `--beyond-halt` success target **`deeper_idle`**:
  - arms CPU object `+0x168=1`
  - points idle callback `+0x134` at synthetic trampoline `0x50003000`
  - leaves stock bra-self parks without thrashing on wild PCs
  - settles at `pc=0x50003000` for the remaining instruction budget

### Full-chain verify

```bash
python tools/om3_boot.py idle --limit 5000000 --out generated/om3-boot-fullchain
# expect: outcome=deeper_idle, pc=0x50003000, app_ready_armed=true, fault=null
```

`deeper_idle` means **synthetic app-schedulable steady state** after peer/DMA/storage
stubs — not GUI, not real multi-core RTOS idle.

### Pre-flash feature validation (not deeper_idle)

For offline acceptance of sound / lever / settings hooks before any flash, use:

```bash
python tools/om3_preflash_validate.py --out generated/om3-preflash-validate
```

That harness resolves and natively probes `aud_ikey_to_wavetype_is_short_sound`,
`Start_Play_Sound_Ext` entry smoke, `changeFunctionButton` /
`getChangeFunctionButton` settings round-trip, and synthetic
`getLeverSwitchState` contrast. See `docs/features/om-3/SHUTTER_SOUND.md` and
`POWER_SWITCH.md`. Do **not** treat `deeper_idle` as the pre-flash bar.

## Simulation boundary (what this is / is not)

**This is a CPU + MMIO offline harness**, not a camera GUI emulator.

| Have now | Do **not** have |
| --- | --- |
| MN103 instruction execution of stock main | On-screen live-view / menu window |
| Logged MMIO/RAM stubs and peer assumptions | Touch, dial, OK/power as real inputs |
| JSON PC/SP/fault reports for bring-up | Interactive setting changes “like the body” |
| Breakpoints / instruction budgets | Display, lens, ISP, Wi-Fi, USB gadget fidelity |

To debug firmware *paths* and *registers*, use `prefix` / `advance` / `idle` /
`--breakpoint`. To behave like a handset UI, this tree still needs a display
pipeline, input models, and much deeper peripheral fidelity (closer to a full
PEN-F connected boot + UI, which OM-3 has not ported).

### What the harness models

Seed / service stubs (logged; synthetic):

- Early MMIO: `0x98e0009c` strap, `0x988004a0` clock gate, IRQ/UART shadows
- DMA engine page `0x9bc00000` with `+0x04` ready
- Early SRAM `0x97f00000..0x97f01fff` and secondary `rwx` window `0x50000000`
- Auto-stub of DRAM (cached + `0xa0000000` uncached alias), MMIO pages, main promote
- Completions each chunk: storage busy clear, controller `0x98e000f4=0`,
  `0x8958 |= 0x10`, ready mask `0x97f00000 |= 0xf`, peer bytes `0x97f00095..97=1`,
  dummy peer CPU objects at `0x97f00008..14` whose `+0x14c` points at a `-1`
  word (skip sentinel for `0x60031cc9`)

### How to extend further

1. Read `fault` / final `pc` from the JSON report (or use `--breakpoint`).
2. Disassemble the PC window with `mn10300-elf-objdump`.
3. Add a seed, completion, or narrower stub in `OM3BootState` with an assumption note.
4. Re-run `advance` / `idle`. Do not copy PEN-F peer schedules until addresses are remapped.

## Gaps versus PEN-F

PEN-F has connected multi-core idle (`penf_boot_console_idle`, SD mount, mode-dial
ADC, …). OM-3 `idle` can reach the firmware’s own `0x60036a13` self-branch with
assumed peer readiness and auto-stubs — useful for debugging, but not a full
four-core schedule, ISP, NAND physics, Wi-Fi, or USB gadget. Physical OK+power /
USB wake selection is not established.
