# OM-3 USB mass-storage probe (read-only)

Captured on the analyst Windows host with the camera in USB **Storage** mode.
**No writes, formats, setting changes, or firmware installs were performed.**

## Device identity

| Field | Value |
| --- | --- |
| Disk | `OMSYSTEM OM-3 USB Device` |
| USB | `VID_33A2` / `PID_013A` / rev `1.00` |
| Serial | `BJSA04743` |
| Class | USB MSC (`Class_08` / `SubClass_06` / `Prot_50`) |
| Volume | `H:` label `OM SYSTEM`, exFAT |

Also enumerated as a WPD volume named `OM SYSTEM`. No separate PTP/MTP/WIA
camera interface was present while Storage mode was active.

## Sessions

### 2026-10-09 (initial)

Volume ~119.5 GiB. Layout as below.

### 2026-10-29 (reconnect; Asia/Hong_Kong)

Disk **Online / Healthy**, BusType USB, MBR, ~119.5 GiB. Volume `H:` **OK**.
Automated read-only scan via `tools/om3_sd_updater_probe.py --msc-root H:/`.

## Card layout (read-only listing)

```text
H:\
  ALBM\ALB27ZY3.BIN
  DCIM\107OMSYS\  (ORF/JPG captures)
  System Volume Information\  (Windows indexer; host-side)
```

No `PRIVATE`, `MISC`, or `DCOLYMP` updater package directory was visible at the
volume root in either session. Absence of `DCOLYMP` is normal for day-to-day
use; community SD firmup expects that folder only when intentionally staging
`E1479999.BIN` (see [boot/om-3/RECOVERY.md](../../boot/om-3/RECOVERY.md)).

## Capability conclusion

In Storage mode the host only sees a removable exFAT volume (photos + ALBM).
That is sufficient for offline file copy by the user; it does **not** expose a
command channel for settings, live view, or firmware update. Other USB modes
(MTP/PTP / PC connect) were not exercised here.

Host-local dry staging of `DCOLYMP/E1479999.BIN` (stock container copy under
`generated/`) must never target the camera volume; the probe refuses MSC-looking
`--stage-out` paths.
