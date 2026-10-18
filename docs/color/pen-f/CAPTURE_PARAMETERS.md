# Per-image parameters and asynchronous processing

PEN-F build 3101 uses separate live settings, capture records, compact-processing
records and processing jobs. A “working record” is one such parameter object,
not a single color sector. Editing one sector changes one setting, but later
refresh and conversion routines copy complete arrays into these objects.

## Ownership chain

```text
committed profile settings
  → capture or compact owner acquires values
  → conversion creates a processing job
  → one of the job's operation records is submitted
  → HSL builder produces coefficients
  → ISP request and eventual completion
```

The capture pool has 40 slots of 41,984 bytes at `adafa3c0` in this build.
A slot's metadata includes ownership flags, parameter pointers and a handle.
Its picture-mode byte is at +18595, twelve saturation halfwords at +18600,
and COLOR profile at +18625. Address bounds and slot alignment both matter
when identifying an owner.

A separate five-slot compact path copies saturation through several forms:
source +382 → 212-byte descriptor +37 → 1,852-byte temporary +1703 →
6,032-byte parameters +5684. Slot reuse and completion are controlled by native
state and resource handles. Those intermediate copies must carry added H/L too.

## HSL transport design

One byte packs a sector's H/L nibbles. Twelve bytes per owner require 540 bytes
for the 40 capture and five compact owners. Each acquisition overwrites its
whole row. Unknown owners produce neutral H/L rather than indexing outside
that storage. The rows use a consistent uncached alias; firmware loading and
real cache behavior are separate concerns.

The final job grows from 14,920 to 14,944 bytes, still in its native 16 KiB
allocation class. The added member contains twelve signed H bytes followed by
twelve signed L bytes. The stock constructor's zeroing is extended to cover it,
and ordinary job destruction owns its lifetime. Once copied, it no longer
depends on the current UI or later reuse of the source slot.

## Distinct conversion routes

Preview/recview and saved recording do not share every converter. The capture
copy at `605205f9` is insufficient by itself. Recording converter `60531fdb`
has its own saturation copy; the H/L adapter at `605323f8` covers that route.
Otherwise live preview can show an edit while the saved JPEG remains neutral.

In-camera RAW editing also allocates an existing capture owner. Its preparer
`60af2edc` and `60af3c7f` populate processing parameters before the normal recording
path. An acquisition hook at `60af2f56` captures the **selected edit profile's**
H/L into that owner. It is not a generic ORF-loader hook, and does not mean that
RAW editing restores the captured H/L slider positions from CMIO.

## Sixteen operation records per job

The embedded request is at job+12228. Sixteen 52-byte records begin at job+14076;
each active record points back to its parent job. Selector `604c2ef9` can choose
any free record; validator `604c3f93` recognizes all sixteen.

A reader must validate the callback, record bounds/alignment and parent link.
Accepting only record zero silently discards valid H/L on other records. Record
number is not necessarily chronological pipeline stage number. Tests should
occupy earlier records and exercise the last record, not only create many
separate jobs that each happen to use record zero.

## Concurrency limits

GUI edits, recording work and compact processing run on different RTOS tasks
and cores. The stock edit request keeps a busy flag across its asynchronous
acknowledgement, and shooting readiness checks that flag. These specific gates
help preserve the native edit boundary; they are not a global transaction lock
covering every profile copy.

Physical live-view/JPEG and RAW-edit tests validate the integrated paths exercised.
Emulation covers bounded ownership, completion and rejection cases. It does not
establish arbitrary hardware scheduling, DMA coherence or all exceptional
completion paths. Hooks should preserve the stock snapshot boundaries instead
of reading live settings from a late ISP callback.
