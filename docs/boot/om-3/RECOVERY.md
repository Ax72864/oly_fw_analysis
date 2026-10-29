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
| Service task name | `FIRMUP_SRV` @ `0x602ee307` |
| Body program strings | `Execute_FirmwareUpdate` / `Check_FirmwareUpdate` / `FirmUp_Update_Firmware for BODY` @ `0x60ef7726+` |
| USB TPC firmup strings | `[TPCFirmup]GetFirmwareUpdateMode` … `UpdateInitiate` @ `0x61996177+` |

These show OM-3 firmware **contains** the same family of SD + USB firmup
surfaces documented for PEN-F. They do **not** by themselves prove the physical
OK+power edge, flash-backend error handling, or an independent USB-ROM rescue.

## Official end-user paths (external)

- **OM Workspace** over USB (**MTP** for OM-3 with Workspace ≥ 2.4.0); remove SD;
  do not disconnect until the camera shows OK; updates are generally
  **not downgradable**.
- **OI.Share** over Wi-Fi; SD must be inserted (FAQ QID 007267 lists OM-3).

This repository can download the stock container
(`tools/om_firmware_catalog.py --model-id 1470`) and decode it. It does **not**
automate Workspace or OI.Share installs.

## Community SD path (third-party; at own risk)

Independent write-ups (e.g. `iKenndac/om-1-manual-firmware-install`) describe:

1. Card root folder `DCOLYMP`
2. File `E1479999.BIN` for OM-3
3. Power on while holding **OK**; solid orange lamp = programming; blink = done

That layout **matches** the string table above. This repo has **not** run that
procedure on a physical OM-3 and does not instruct agents to do so.

## Gaps (block “research patch on camera” safety)

1. No OM-3-native SD client → `FIRMUP_SRV` probe (PEN-F has `penf_sd_path_probe.py`).
2. No builder that emits `install/DCOLYMP/E1479999.BIN` + matching restore stock
   for OM-3 research patches (L2 under `patches/*/om-3` patches **decoded main**
   only).
3. Physical OK selector and orange-lamp timing are **unverified** here.
4. No evidence of an immutable USB recovery ROM for OM-3 in this tree.
5. Official policy: no downgrade via Workspace / OI.Share.

PEN-F recovery limits still apply as a conservative baseline:
[pen-f/RECOVERY.md](../pen-f/RECOVERY.md), [USB update](../../protocols/pen-f/USB_UPDATE.md).

## Related tools (do not write camera flash)

- Firmup landmarks: `tools/om3_firmup_landmarks.py`
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
```

## Still open

Native OM-3 SD client → `FIRMUP_SRV` transaction fixture (PEN-F analogue:
`penf_sd_path_probe.py`) with flash backends trapped.
