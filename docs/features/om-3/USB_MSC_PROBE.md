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
| Volume | `H:` label `OM SYSTEM`, exFAT, ~119.5 GiB |

Also enumerated as a WPD volume named `OM SYSTEM`. No separate PTP/MTP/WIA
camera interface was present while Storage mode was active.

## Card layout (read-only listing)

```text
H:\
  ALBM\ALB27ZY3.BIN
  DCIM\107OMSYS\  (ORF/JPG captures)
  System Volume Information\  (Windows indexer; host-side)
```

No `PRIVATE`, `MISC`, or Olympus updater package directory was visible at the
volume root in this session.

## Capability conclusion

In Storage mode the host only sees a removable exFAT volume (photos + ALBM).
That is sufficient for offline file copy by the user; it does **not** expose a
command channel for settings, live view, or firmware update. Other USB modes
(MTP/PTP / PC connect) were not exercised here.
