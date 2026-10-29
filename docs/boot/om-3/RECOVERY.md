# OM-3 firmware update and recovery (build 1100)

Analysis and landmarks only. **This tree does not flash a camera.**  
Narrative (Chinese) and experiment queue:
store docs `om3-flash-workflow.md` / `om3-recovery.md` on the research fork.

Public label **1.1**, internal build **1100**, container
`OLY_E_147_1100_0000_0000.BIN`, catalog model id **1470**.

## What is established offline (stock main)

| Lead | Analysis address / note |
| --- | --- |
| SD directory name `DCOLYMP` | `0x606253b5`, `0x612ea303` |
| Body update pattern `E147????BIN` | `0x612ea12c`, `0x612eaeab` (matches community `E1479999.BIN`) |
| Sibling patterns | `S/G/H/W/A/M/V/D/T/I/K147????BIN` near `0x612ea120` |
| Possible boot-class pattern | `S147????BIN` (analogy to PEN-F `S122`; **untested** on OM-3) |
| Client / logs | `api_firmup.c`; `[firmup]mount_ok`, `[firmup]ld_img_st`; `[fupsrv]…` |
| SD firmup client | `0x6106b87a` (path helper `0x6106be34`) |
| Service task name | `FIRMUP_SRV` @ `0x602ee307` (task **entry PC not yet pinned**) |
| Body program strings | `Execute_FirmwareUpdate` / `Check_FirmwareUpdate` / `FirmUp_Update_Firmware for BODY` @ `0x60ef7726+` |
| Body update sites | `Execute` body ~`0x60d41ea8`; `Check` string `0x60ef7793` / xref `0x60d42032` (same body) |
| USB TPC firmup strings | `[TPCFirmup]GetFirmwareUpdateMode` … `UpdateInitiate` @ `0x61996177+` |

These show OM-3 firmware **contains** the same family of SD + USB firmup
surfaces documented for PEN-F. They do **not** by themselves prove the physical
OK+power edge or an independent USB-ROM rescue.

## Official end-user paths (external)

- **OM Workspace** over USB (**MTP** for OM-3 with Workspace ≥ 2.4.0); remove SD;
  do not disconnect until the camera shows OK; updates are generally
  **not downgradable**.
- **OI.Share** over Wi-Fi; SD must be inserted (FAQ QID 007267 lists OM-3).

This repository can download the stock container
(`tools/om_firmware_catalog.py --model-id 1470`) and decode it. It does **not**
automate Workspace or OI.Share installs.

## Community SD path — multi-channel evidence (no device flash here)

Independent write-ups describe the same layout and OK+power ritual:

| Channel | What it says | Weight |
| --- | --- | --- |
| GitHub `iKenndac/om-1-manual-firmware-install` | `DCOLYMP` + `E1479999.BIN` (OM-3) + Slot1 + hold **OK** while powering on; solid orange = programming; blink = done | Primary published recipe; author reports success on own body (not OM-3-specific proof in-repo) |
| Mu-43 threads (e.g. model-family SD “backdoor”) | Same `DCOLYMP` / `E###9999.BIN` / OK+power / orange LED pattern across OM/E-M bodies | Independent forum corroboration of the **family** procedure |
| DPReview / older DSLR threads | Same `DCOLYMP` + `E…9999.BIN` + OK ritual on earlier Olympus bodies | Longevity of the naming scheme |
| Stock OM-3 1100 main (this tree) | Strings `DCOLYMP`, `E147????BIN`, client `0x6106b87a`, `FIRMUP_SRV`, TPC firmup | Offline cross-check: naming/layout is **in firmware**, not forum-only |
| Live OM-3 MSC (read-only) | Card root has `DCIM`/`ALBM`; **no** `DCOLYMP` in daily use | Expected; updater folder is intentional staging only |

**Verdict:** the community claim is **corroborated** across guide + forums + firmware
strings. This repository still has **not** executed OK+power on a physical OM-3
and **does not** run intentional failure / brick recovery tests.

## Native simulation fixture (offline)

`tools/om3_firmup_sim.py` runs a bounded MN103 path:

1. **Read/search** — SD client `0x6106b87a` with modeled path helper; walks
   sibling `????BIN` patterns; `E147????BIN` hit or miss.
2. **Validate** — `Check_FirmwareUpdate` / `Execute_FirmwareUpdate` sites with
   synthetic package; flash backends trapped.
3. **FIRMUP_SRV-class** — same update body with flash traps; RTOS task entry PC
   and client↔service queues are **not** fully reconstructed (PEN-F still has
   the deeper `penf_sd_path_probe.py` transaction).

```bash
python tools/om3_firmup_sim.py --scenario both --out generated/om3-firmup-sim
```

Flash backends never program; no camera or SD writes.

## Gaps (block “research patch on camera” safety)

1. `FIRMUP_SRV` **task entry PC** still unpinned; sim uses class-body + traps.
2. No builder that emits `install/DCOLYMP/E1479999.BIN` + matching restore stock
   for OM-3 research patches (L2 under `patches/*/om-3` patches **decoded main**
   only).
3. Physical OK selector and orange-lamp timing are **unverified** here
   (recovery live tests are out of scope until explicitly authorized; do **not**
   propose intentional brick tests).
4. No evidence of an immutable USB recovery ROM for OM-3 in this tree.
5. Official policy: no downgrade via Workspace / OI.Share.

PEN-F recovery limits still apply as a conservative baseline:
[pen-f/RECOVERY.md](../pen-f/RECOVERY.md), [USB update](../../protocols/pen-f/USB_UPDATE.md).

## Related tools (do not write camera flash)

- Firmup landmarks: `tools/om3_firmup_landmarks.py`
- Native SD→validate→FIRMUP_SRV-class sim: `tools/om3_firmup_sim.py`
- SD updater surface + MSC read-only: `tools/om3_sd_updater_probe.py`
  (`--msc-root H:/`; optional host-only `--stage-out`, refuses camera paths)
- Pre-flash offline bar: `tools/om3_preflash_validate.py`
- Container decode: `tools/oly_container.py`
- V22 audit only: `tools/om3_patch_audit.py` (no installable package)
- USB Storage read-only note: [USB_MSC_PROBE.md](../../features/om-3/USB_MSC_PROBE.md)

Example (camera Storage connected; still no device writes):

```bash
python tools/om3_sd_updater_probe.py --msc-root H:/ --out generated/om3-sd-updater-probe
python tools/om3_sd_updater_probe.py \
  --container firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN \
  --stage-out generated/om3-sd-host-stage \
  --out generated/om3-sd-stage-report
python tools/om3_firmup_sim.py --scenario both --out generated/om3-firmup-sim
```
