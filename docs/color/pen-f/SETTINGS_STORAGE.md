# Settings banks and persistent H/L

PEN-F build 3101 stores settings through typed APIs and bank copies. Reusing
those APIs preserves ordinary save/checksum behavior; an extension does not
need its own flash-write routine.

## Banks and lifecycle

Three COLOR profiles exist in current settings and in each of C1–C4: fifteen
user-facing recipes. Internally, Current and paired custom/dial records occupy
nine banks. These pairs participate in registration and recall; they are not
additional independent user profiles.

Key boundaries include:

| Function | Address |
| --- | --- |
| Read ACTIVE alternate setting | `602f06e7` |
| Write ACTIVE alternate setting | `602f0710` |
| Paired bank save | `6075fb08` |
| Registered recall | `602ba07b` |
| Save/checksum preparation | `600733d8` |
| Reload | `6007333e` |
| Profile refresh | `602c50be` |

These names describe observed roles, not exported symbols. The stock settings
store has its own checksums and redundant records; these do not provide a
rollback copy of the main firmware.

## Alternate cells used by the HSL extension

Settings 931–966 have two parts. COLOR uses part 0 for stock saturation. The
extension uses **part 1**, 36 allocated u32 cells per bank, for H/L. They are
alternate setting cells, not arbitrary unused RAM. The reviewed mode filters
select part 0; stock bank operations already carry part 1 through save/recall.
This is a build-specific ownership finding, not a rule for all Olympus settings.

Each word is:

```text
0x4831CCVV
VV: signed 4-bit H in low nibble; signed 4-bit L in high nibble
CC: VV XOR 0xff
```

The marker and complemented byte distinguish valid extension data from ordinary
or uninitialized values. Valid axes are −7…+7; nibble −8 is invalid. An invalid
word decodes to a neutral pair. This admits 225 of the 256 nibble pairs. Editing
one axis preserves the other. The 36 words hold 72 values across COLOR1–3 and
occupy 144 bytes per bank.

The format check is not a mutex, transaction counter or replacement for the
stock bank checksum. It makes absent/invalid data harmless at the reader.

## Recall has a staging phase

During recall, ACTIVE storage can already contain the destination H/L while
some committed image settings still describe the source bank. A notification
alone is not permission to publish the new data.

The observed sequence stages settings at `602bd696`, runs context-1 profile
refresh, commits through `602f0b80`, then performs the bank/profile change at
`602f0c58`; `602bd7f9` marks the state after the inhibit byte clears, before post-commit callbacks. The inhibit
flag at `6189a4b0` is a lifecycle indicator, not a general lock.

The HSL extension publishes its live values with the corresponding committed
stock settings. Image processing uses an acquired snapshot, so a later bank
change cannot recolor an already acquired image. See
[per-image parameters](CAPTURE_PARAMETERS.md).

Physical tests support reboot persistence, COLOR1–3 edits, C1–C4-related
assignment/recall and reset behavior. Extension data also has a named
[Workspace backup record](../../protocols/pen-f/SETTINGS_BACKUP.md); silently preserving
an unknown RAM word is not sufficient for portable settings backups.
