# OM-3 Wi-Fi protocol notes

OM-3 hosts a private Wi-Fi HTTP service in the same family as other OM System
cameras. The research client joins only after the ordinary camera Wi-Fi
workflow; it does not configure credentials.

## Relative to PEN-F

PEN-F 3100/3101 advertise a compact OI.Share 2.60 command set. OM-3 1.1 has a
larger description that can include named settings-backup and partial-transfer
commands. Presence of those names does **not** establish a safe automated
transfer path in this repository.

Unadvertised `get_mcon` / `set_mcon` behaviour that PEN-F uses for COLOR
readback and the HSL1 extension has **not** been qualified here for stock OM-3.
Do not assume PEN-F mode IDs or the `4850`/`4851`/`4852` write tags.

## Research client

[camera_client/om3_wifi](../../../camera_client/om3_wifi/README.md) supports
read-only `identify` / `discover`. It refuses COLOR/HSL uploads by design.
PEN-F recipe workflows remain under `camera_client/penf_wifi`.

## Evidence limits

No physical OM-3 capture log is checked into this tree. Protocol statements
beyond discovery must cite a new fixture or camera test before becoming write
paths.
