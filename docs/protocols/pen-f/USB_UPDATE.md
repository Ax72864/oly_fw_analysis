# USB firmware update

Workspace 2.5's host code and PEN-F build 3101 use a memory upload followed by
validation and a commit request. This is not copying an update file to the
camera's SD filesystem.

## Host sequence

| Operation | Code | Purpose |
| --- | --- | --- |
| GetFirmwareUpdateMode | `911c` | Query the supported update mode |
| Transfer metadata | `9125`, otherwise `100c` | Describe object and length |
| Split transfer | `9119` | Transfer chunks, at most `f800` bytes in this path |
| FirmwareCheck | `9121` | Request validation |
| CheckStatus | `9122` | Poll until validation completes |
| UpdateInitiate | `9123` | Request application handling and commit |

The host initiates only after its successful check. Host status 1 means busy,
2 success; failure and transport errors prevent initiation in the executed cases.
Mode query `911c` returns 1 on this camera. It does not put the camera into a
bootloader or restart it.

OlyBar invokes OlyGin's interface. Its storage transport carries PTP-style vendor
operations in Olympus SCSI commands: C0 command, C1 data, C3 response. The Windows
implementation uses `IOCTL_SCSI_PASS_THROUGH`. A historical XZ-1 USB capture
contains the same protocol family and check/poll/initiate sequence, supporting
continuity across models without proving equal recovery behavior.

## Camera route

```text
UpdateInitiate 60ac39bc
  → system event 06000001
  → DeviceLink callback 60bb1746
  → CAM event 0300004e (CBK_DEVLINK_REQ_FIRMUP)
  → PC state 6004, then state 6000 / event 09000000
  → startFirmUp 60bb1f7c
  → maintenance request 254, body selector 0
  → readiness check and body preparation
  → 608937bf → 602ef14d (Execute_FirmwareUpdate)
  → TPC command 3 → FIRMUP_SRV event 4
```

These links were traced and exercised in bounded fixtures, not as one complete
USB session with real asynchronous scheduling. The maintenance request's
selector 1 is for accessory updates, not PEN-F body SD task 95.

Three fields must be distinguished:

| Address | Meaning |
| --- | --- |
| `619a3040`, u16 | All declared transfer bytes have arrived |
| `619a3054`, u32 | Pending/success/failure check status |
| `619a3042`, u16 | Separate successful-validation/readiness flag |

The initiation handler checks transfer completeness. A later application gate
at `6089397c` checks readiness through `60ac2ec2`; an update-related event alone
is not authorization to program flash.

## Relationship to SD updating

Both routes reach task 19, `FIRMUP_SRV`, entry `60b1d012`, and shared updater
`60b1d527`:

- SD event 1: mode 0, validate then program.
- USB check event 3: mode 2, validate only.
- USB commit event 4: mode 1, programming phase.

Workspace therefore depends on main-application services in the inspected route.
There is no demonstrated independent USB-ROM recovery path. Exposed reconnect
(`9709`) and reboot (`970a`) operations do not establish one either.

Desktop input hashes and disassembly identities are recorded in
[provenance](../../../provenance/README.md). Desktop addresses in source records use
DLL bases/RVAs; they are not camera addresses.
