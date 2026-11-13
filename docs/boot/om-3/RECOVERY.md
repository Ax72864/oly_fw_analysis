# OM-3 firmware update and recovery (build 1100)

Public label **1.1**, internal build **1100**, container
`OLY_E_147_1100_0000_0000.BIN`, catalog model id **1470**.

**Operator flash / restore guide:** [FLASH_WORKFLOW.md](FLASH_WORKFLOW.md).  
**Feature pack (ring / 5 GHz / e-shutter sounds):** [CUSTOM_FEATURES.md](../../features/om-3/CUSTOM_FEATURES.md).

Repository tools still **do not write** a camera volume or drive OK+power
themselves. Staging trees under `generated/om3-sd-install/` are host-local;
copying to an SD card and performing OK+power is an operator step.

## Physical verification (2026-11-04)

| Claim | Evidence |
| --- | --- |
| SD firmup path works on OM-3 | Operator flashed `DCOLYMP/E1479999.BIN` (Slot 1, hold OK at power-on); camera rebooted normally |
| Research container is installable | Package from `generated/om3-sd-install/patched-ring-wifi-shutter-slots123/` (current container SHA prefix `1275b0a3…`) |
| Feature pack survives flash | Aperture ring, 5 GHz Wi‑Fi, and e-shutter custom sound slots **1 / 2 / 3** all functioned; silent shooting played the injected WAVs |

Earlier community guides + firmware strings were therefore confirmed on at least
one OM-3 body for this build. Intentional brick / recovery-failure tests remain
out of scope.

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
surfaces documented for PEN-F. Physical OK+power for a research container is
now separately recorded above.

## Official end-user paths (external)

- **OM Workspace** over USB (**MTP** for OM-3 with Workspace ≥ 2.4.0); remove SD;
  do not disconnect until the camera shows OK; updates are generally
  **not downgradable**.
- **OI.Share** over Wi-Fi; SD must be inserted (FAQ QID 007267 lists OM-3).

Workspace may save/reload Custom Settings around an official update. That PC
pipeline is **not** part of SD firmup — save settings manually before a research
flash ([FLASH_WORKFLOW.md](FLASH_WORKFLOW.md)).

This repository can download the stock container
(`tools/om_firmware_catalog.py --model-id 1470`) and decode it. It does **not**
automate Workspace or OI.Share installs, and those channels are not the path
used for the verified research package.

## Community SD path — multi-channel evidence

| Channel | What it says | Weight |
| --- | --- | --- |
| **This tree (2026-11-04)** | OM-3 OK+power installed the offline research `E1479999.BIN`; boot + ring / 5 GHz / three custom e-shutter sounds OK | Primary in-repo physical confirmation |
| GitHub `iKenndac/om-1-manual-firmware-install` | `DCOLYMP` + `E1479999.BIN` (OM-3) + Slot1 + hold **OK** while powering on; solid orange = programming; blink = done | Published recipe |
| Mu-43 / DPReview threads | Same `DCOLYMP` / `E###9999.BIN` / OK+power / orange LED pattern across OM/E-M bodies | Family corroboration |
| Stock OM-3 1100 main | Strings `DCOLYMP`, `E147????BIN`, client `0x6106b87a`, `FIRMUP_SRV`, TPC firmup | Offline naming/layout cross-check |
| Live OM-3 MSC (read-only) | Card root has `DCIM`/`ALBM`; **no** `DCOLYMP` in daily use | Expected; updater folder is intentional staging only |

## Staged install trees (host)

```text
generated/om3-sd-install/
  patched-ring-wifi-shutter-slots123/DCOLYMP/E1479999.BIN
  stock-1.1-restore/DCOLYMP/E1479999.BIN
  INDEX.json
```

Rebuild notes and operator steps: [FLASH_WORKFLOW.md](FLASH_WORKFLOW.md).

## Native simulation fixture (offline)

`tools/om3_firmup_sim.py` runs a bounded MN103 path:

1. **Read/search** — SD client `0x6106b87a` with modeled path helper; walks
   sibling `????BIN` patterns; `E147????BIN` hit or miss.
2. **Validate** — `Check_FirmwareUpdate` / `Execute_FirmwareUpdate` sites with
   synthetic package; flash backends trapped.
3. **FIRMUP_SRV-class** — same update body with flash traps; RTOS task entry PC
   and client↔service queues are **not** fully reconstructed.

```bash
python tools/om3_firmup_sim.py --scenario both --out generated/om3-firmup-sim
```

Flash backends never program; no camera or SD writes from the tool.

## Remaining gaps

1. `FIRMUP_SRV` **task entry PC** still unpinned; sim uses class-body + traps.
2. No evidence of an immutable USB recovery ROM for OM-3 in this tree.
3. Official policy: no downgrade via Workspace / OI.Share (SD stock restore is
   the practical research rollback used with `stock-1.1-restore`).
4. Intentional failure / brick recovery tests remain out of scope.

PEN-F recovery limits still apply as a conservative baseline:
[pen-f/RECOVERY.md](../pen-f/RECOVERY.md), [USB update](../../protocols/pen-f/USB_UPDATE.md).

## Related tools (do not write camera flash)

- Firmup landmarks: `tools/om3_firmup_landmarks.py`
- Native SD→validate→FIRMUP_SRV-class sim: `tools/om3_firmup_sim.py`
- SD updater surface + MSC read-only: `tools/om3_sd_updater_probe.py`
  (`--msc-root H:/`; optional host-only `--stage-out`, refuses camera paths)
- Feature code patch: `tools/om3_db_feature_patch.py`
- Shutter WAV slots (CPython 3.12): `tools/om3_shutter_slots.py`
- Pre-flash offline bar: `tools/om3_preflash_validate.py`
- Container decode: `tools/oly_container.py`
- V22 audit only: `tools/om3_patch_audit.py`

Example (camera Storage connected; still no device writes from the tool):

```bash
python tools/om3_sd_updater_probe.py --msc-root H:/ --out generated/om3-sd-updater-probe
python tools/om3_firmup_sim.py --scenario both --out generated/om3-firmup-sim
```
