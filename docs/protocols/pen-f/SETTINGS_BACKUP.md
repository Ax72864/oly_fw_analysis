# Workspace settings backup and extensions

The camera supplies named setting records. The inspected Workspace implementation
preserves those records through its save/load envelope rather than enforcing a
fixed per-model dictionary of all names. Extending the camera's exporter **and**
importer can therefore add settings without changing Workspace.

This is established for PEN-F build 3101 with the HSL extension, including a
physical Windows backup/restore test and inspection of combined and separate
Current/C1–C4 files. Restore automatically restarts the camera. The result should
not be generalized to every Workspace feature: JPEG recipe import is a separate,
limited field mapping.

## H/L record

Each selected bank adds this line before its type-3 terminator:

```text
2,PENF_HSL_V1,<72 hexadecimal digits>\r\n
```

The line is 88 bytes. Its 36 bytes hold COLOR1 sectors 0–11, then COLOR2 and
COLOR3. Each byte packs signed H in the low nibble and signed L in the high
nibble. Both axes must be −7…+7. Export uses uppercase hex; import also accepts
lowercase hex, but the record name is case-sensitive. Saturation keeps its stock
named records.

Current reads ACTIVE alternate cells. C1–C4 export paired Myset/DialMyset banks:
selection bits 1/2/4/8 select those pairs; `0x100` selects Current. This accounts
for nine internal banks and fifteen user-facing COLOR profiles.

The extension is emitted for export kind 2 (`current`). Kind 1 (`diff`) and
kind 4 (`factory`) retain stock semantics.

## Import contract

A bank header resets temporary extension state. The handler checks family/version,
length, CRLF, hex syntax, range and duplicate records before the native setting
lookup. Ordinary names continue through the stock parser.

At a complete bank terminator:

- Valid H/L applies all 72 values in that bank.
- Missing or invalid H/L supplies neutral values for that completed bank.
- A bank with no terminator does not apply its H/L.
- Unselected banks retain their values, subject to the stock Current save at
  restore entry.

Restore is per-bank, not an atomic transaction over the entire file. A failure
in a later bank does not undo an earlier completed bank. The extra parsing state
uses 64 bytes added to the existing temporary allocation, cleared and freed with
that operation. Stock save/checksum/reload code performs persistence.

PEN-F hook boundaries are export `602c1829`, accepted header `602c1e8f`, type-2
record `602c1ed2`, and terminator `602c1f73`. The allocation/clear sizes are at
`602c1d7f` and `602c1d9d`. These identify integration points, not a standalone
patch specification.

Physical backup files contain valid H/L in all nine internal banks; combined and
separate exports agree. Malformed-record and fallback behavior has bounded
native-test coverage, not an exhaustive physical test of every corrupt file.

[penf_settings_backup_probe.py](../../../tools/penf_settings_backup_probe.py) explores
the native settings machinery. [Persistent storage](../../color/pen-f/SETTINGS_STORAGE.md)
describes the data beneath the named export format.
