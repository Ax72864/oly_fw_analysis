# PEN-F settings, editor and image structures

Build **3101** only. Addresses are hexadecimal; structure offsets and property IDs are decimal unless prefixed with `0x`. Field names describe observed use, not a recovered C header. Layout entries distinguish pointers, value copies and validity flags; unexplained padding is not declared free storage.

Read the [edit/capture function map](EDIT_AND_CAPTURE_MAP.md) for the operations that create and consume these objects. The [storage](SETTINGS_STORAGE.md), [editor](EDITOR.md) and [capture overview](CAPTURE_PARAMETERS.md) give their broader roles.

## Settings registry and the three representations

The native setting manager has three registries. All are needed before a fixture can claim normal type conversion and callbacks:

| Registry | Initializer | Runtime table | Source descriptors |
| --- | --- | --- | --- |
| Property callbacks | `0x602bb8f1` | `0x61884dec`, 64 pointer buckets | `0x60372a6c`, 460 × 60 bytes |
| Consistency rules | `0x602bd565` | `0x61885d50`, 32 pointer buckets | `0x603a0508`, 275 × 20 bytes |
| Type/value conversion | `0x602c6c37` | `0x618872c0`, 128 pointer buckets | `0x603dffcc`, 968 × 20 bytes |

Application initializer `0x602ba469` calls their wrappers. Installing the observer at `0x615fd38c` is a separate operation and does not initialize these hashes.

Settings appear as saved-bank/ACTIVE cells, LIVE values and typed current parameter records. These names are not interchangeable:

| Record key | Working address | Declared u32 elements | Role |
| --- | --- | ---: | --- |
| `0x85d4` | `0x61b7bdc8` | 22950 | Nine internal saved banks |
| `0x8b54` | `0x61b924cc` | 1275 | LIVE values |
| `0x8b64` | `0x61b938b8` | 2550 | ACTIVE two-part values |

Bank APIs use **1274 words per part**, two parts per bank, and a 2548-word bank stride. The difference from declared record lengths is not qualified extra capacity. All these records and current COLOR parameter records lie in the type `0x54` Mode store at `0x61b7bac0`, size `0x20000`. Examples of current records are saturation 931 at `0x61b9662c`, selector 912 at `0x61b96606`, source selector 1086 at `0x61b963f4`.

The Mode-store descriptor is at cached `0x61c281a8` / uncached `0xa1c281a8`. Its observed backing pointer is `0xa1ef2c00`; the second backing pointer is zero in the inspected initialization. This is not evidence for a second executable-firmware rescue copy. Validator `0x600734e3` checks store type and the complete halfword sum. Checksum writer `0x60073540` makes that sum zero. Storage preparation `0x600733d8` compares working/backing contents, updates the counter/checksum, and reaches backend `0x600720e1` when changed.

The ACTIVE part getter/setter are `0x602f06e7` / `0x602f0710`; bank load/store are `0x602f063e` / `0x602f067a`. These APIs move native cell representations. They do not substitute for the registered setting callbacks that refresh effective image parameters.

## COLOR setting IDs

| IDs | Representation and meaning |
| --- | --- |
| 111 | Public compound effective picture mode |
| 910 | Public compound COLOR source mode |
| 906 | Requested source selection; 910 selects COLOR in the mapped fixture |
| 1083 | Effective source chosen by consistency rules |
| 912 | Effective profile number 1/2/3; also read by the editor |
| 1086 | Internal COLOR-source profile number |
| 919–930 | Twelve effective saturation values; typed current record key `0xf6ea` |
| 931–942 / 943–954 / 955–966 | Stored saturation arrays for COLOR1/2/3 |
| 1095 / 1100 / 1101 | Per-profile sector cursor properties |
| 1048 / 1049 / 1050 | COLOR1/2/3 availability flags |
| 41 | Current internal bank identifier; insufficient alone for temporary-recall ownership |
| 569 | Temporary custom-recall indicator used by MyMode |

Public mode 54/55/56 is **raw mode 11 plus selector 1/2/3**, not raw 111=54/55/56. Compound 111 includes IDs111, 1144, 1084, 912, 977. Compound 910 includes IDs910, 1086. The 75-way rule table for effective 111 is at `0x6039cb34`.

Registered writes of compound 910 run profile selection and refresh. Writing 912 alone can change the readable effective selector while leaving the source and processing refresh unchanged. A tool must not equate “getter returns desired profile” with a complete profile-switch operation.

The three profiles exist in current/PASM plus four user custom contexts: fifteen user-facing recipes. Internal pairs `(1,5),(2,6),(3,7),(4,8)` are paired save/recall records, not eight additional independent custom contexts.

### Extension storage contract

Only part 1 of IDs931–966 is reused for H/L. The 54 reviewed mode/submode filters select part 0 for COLOR, while many unrelated settings actively use part 1. The whole second array is therefore not spare RAM.

Each H/L cell is a u32 `0x4831CCVV`: `VV` packs signed H in its low nibble and signed L in its high nibble; `CC=VV XOR 0xff`. The marker, complement and allowed −7…+7 values are checked; invalid cells become neutral. The 36 cells occupy 144 bytes per bank and hold 72 values. This is a format discriminator, not a concurrency counter. It inherits the stock bank-copy/store envelope rather than adding its own nonvolatile writer.

## GUI controls and setting notifications

A COLOR editor parent owns 13 children: one cursor and twelve value controls. Native constructor `0x60c7f039` initializes each stock value child:

| Offset | Width | Meaning |
| ---: | --- | --- |
| +84 | u16 | Property ID |
| +88 | u16 | Enumerated choice count:11 stock |
| +90 | u16 | Temporary choice index: `5-S` stock |
| +96 | pointer | Eligibility halfwords |
| +100 | pointer | Ordered values +5,+4,…,−5 |
| +104 | field | Non-wrapping behavior enabled |
| +108 / +112 | fields | First/last eligible index:0/10 stock |

The temporary index can change before any stored setting changes. Extended-range firmware alters the value-list/rendering contracts; this table records the stock layout, not a claim that an eleven-entry allocation is sufficient for ±7.

UserSettingManager is616 bytes, constructed by `0x6075eed9`:

| Offset | Meaning |
| ---: | --- |
| +4 | Notification timer |
| +24 | General subscriber vector |
| +40 onward | 32 grouped subscriber vectors |
| +552 | Mutex |
| +560 | Pending property-ID vector |
| +576 | Additional vector |

Vectors begin with capacity 20 and a separate 80-byte backing allocation. Native notification snapshots the relevant list before calling listeners. General registration is `0x6075f036`; grouped registration `0x6075f061`. The direct listener inventory is not an exhaustive runtime subscription list.

The GUI's edit-in-progress word is `0x61600980`, accessed through setter `0x606b6236` and predicate `0x606b5c49`. It remains set across the application request/wait and clears only when the original setter finishes. Shared capture status is a separate four-word object at `0x618d4890`, guarded per access by resource 5. The byte `0x6189a4b0` is a third mechanism: public-setting inhibition during transactions, **not** a mutex and not a barrier to internal reads/writes.

## Framework event and shooting-component objects

| Object/field | Layout or role |
| --- | --- |
| Framework singleton `0x618ea278` | 72 bytes; task adapter+52, queue+68 |
| Ordinary event | Destination pointer+24; reply wrapper+28 for request `0x404e` |
| Event vtable+36 | Virtual destination getter, not destination field+36 |
| Shared responder | 180-byte object; singleton pointer `0x61602470`; private semaphore pointer+120 |
| Reply wrapper | 12-byte allocation, constructor `0x606f2724` |
| Stack receiver | 36 bytes, constructor `0x606f1117` |
| Request event | 32 bytes for `0x404e` |
| Queue-query result | Two u16 waiting-task IDs followed by u32 queued-item count |

The framework task adapter stores the **creating task's ID**. The later pump can execute on task 64 without rebinding that adapter. Its stored ID is not evidence of the current execution context.

The selected component is found recursively through the root/mode/category hierarchy:

| Layer | Factory global | Embedded offset | Getter |
| --- | --- | ---: | --- |
| Camera root | `0x61606084` |1872|`0x60934b3d`|
| Shooting mode | `0x61606174` |532|`0x6094a075`|
| Still category | `0x61606178` |508|`0x6094b142`|
| NEW shooting component | `0x61606044` |1152|`0x609274a3`|

The NEW factory occupies 7520 bytes. Root/mode/category selected-child pointer is+148; pending child is root/mode+296 and category+300. The category controller pointer is+328; its controller is348 bytes.

For the NEW shooting component:

| Offset | Meaning in the qualified event contract |
| ---: | --- |
| +0 | Vtable `0x60a4769c`; base alternative `0x609f0410` |
| +0…111 | Reactive-base state initialized by `0x60950afc` |
| +118 | Diagnostic level |
| +148 | Selected child; self when this leaf is active |
| +256 | Current state |
| +264 | Owned reply-manager pointer |
| +556 | Initialization substate |
| +928 / +932 | Primary/secondary sequence pointers |
| +980 | Running-state field, 14 in the qualified active state |

Sequence wrapper+176 controls event interception; +2836 points to a cache object. The cache's twelve halfwords at offsets 162…184 reflect IDs1147, 111, 140, 216, 405, a derived value from 405, 1140, 90, 146, 600, 1146, 762. It does not contain the twelve per-sector saturation values. A warm cache can therefore remain unchanged during a saturation-only edit.

## Display parameter records

Viewer initializer `0x60c848ed` installs callbacks `0x60c849b3`, `0x60c84bcd`, `0x60c84cf0`, `0x60c8504f`; full updater `0x60c84901` reads, modifies and stores two records:

| Parameter ID | Destination | Size | Relevant content |
| ---: | --- | ---: | --- |
|179|`0x619bd870`|96|Wheel/cursor/value presentation; observed signed-value magnitude at byte 2|
|209|`0x619c0b30`|12|Auxiliary indicators|
|176|`0x619bd18c`|1556|Generic child dependency read before commit; not the COLOR wheel record|

Display-store constructor `0x60bbaa1b` registers 211 descriptors from `0x6160b31c` through `0x60bbaa75`. The viewer's local value fields include+37/+38 for sign/magnitude and+124 for COLOR state. Native RAM writes to these records are not evidence that a drawing observer or physical LCD executed.

A separate asynchronous draw route packs 13 bytes: twelve signed saturation bytes plus cursor, then converts at `0x602fc370`. Its stock display codes are `S+5`; cursor 255 denotes ALL. This is neither the 152-byte processing builder output nor the 96-byte GUI record.

## Capture-owner pool

The table at `0x618689b8` has 41 records of20 bytes; public IDs1…40 are valid, slot 0 is not.

| Record offset | Width | Meaning |
| ---: | --- | --- |
|+0|u16|Validity flags; bit `0x4` owns parameter storage|
|+12|pointer|Capture parameter block|
|+16|u16|Parameter-pool handle|
|+18|u16|Additional release state; full policy not assigned|

Pool descriptor `0xa1c69c38` has type `0x1500`, base `0xadafa3c0`, stride `0xa400` (41984 bytes), capacity 40. Capture population copies 22080 bytes from `0x618bb6b8` before filling shot fields. Neither the capacity nor the unfilled stride remainder implies space for forty complete pixel images or universally unused bytes.

| Capture parameter offset | Meaning |
| ---: | --- |
|+4884|Halfword used by complete conversion through descriptor+124|
|+18595|Picture-mode byte:11 for COLOR|
|+18600|Twelve signed saturation halfwords in wheel order|
|+18625|COLOR profile 1/2/3|
|+21840|Subsidiary resource handle cleared on allocation|
|+21942|Geometry halfwords consumed by conversion; fixture values require an explicit producer contract|

The376-byte conversion descriptor has type byte+8=5 and capture pointer+124. Descriptor+0/+4 refer to separate pixel-buffer inputs, not capture parameter ownership. Release clears validity even when old pointer bytes remain. A raw pointer can therefore become stale while still numerically addressing the same storage.

## Compact owners and their copies

The primary ring at `0xa1c6cab8` contains five 632-byte slots. Control fields are:

| Location/offset | Meaning |
| --- | --- |
|`0xa1c6ca66`|Next build slot|
|`0xa1c6ca68`|Current refresh slot|
|`0xa1c6ca6a/0xa1c6ca6c`|Retained indices|
|`0xa1c6ca64/0xa1c6ca65`|Enable bytes for retained indices|
|slot+24|Type `0x0700` resource handle|
|slot+172|Copied upstream request byte 107; affects ordinary/blank processing selection|
|slot+204, bit `0x8000`|Skips the COLOR refresh in the tested helper|
|slot+328|Substructure passed with the slot to the refresh helper|
|slot+382|Twelve saturation halfwords|
|slot+597|Quality/geometry selector copied into shared-job configuration|
|slot+612|State;1 queued, 2 acquired; these states are skipped by reuse selection|

A second five-slot 632-byte ring at `0xa1c6d714`, control `0xa1c6d710`, participates in builder and auxiliary/AWB release. A separate global 632-byte copy at `0x61bc9d6c` is overwritten by `0x605553bf`; getter `0x605553e4` returns it. It is a reusable global configuration snapshot, not permanent frame-owned storage.

The compact processing handoff carries a208-byte allocated descriptor. Its first word is the shared-job pointer; halfword+70 influences completion/free behavior. The16-byte queue message is `[reply_destination, tag, operation, descriptor_pointer]`: for the mapped ordinary path `[0x2002,0,1,pointer]`, so `0x2002` is **not** the operation code.

## Shared processing job and H/L value ownership

Constructor `0x604c1c0a` allocates a14920-byte job and 5624-byte companion. Both select a16384-byte heap class with 16448-byte physical stride. Extending the logical job to14944 bytes stays in that class; native construction must still explicitly initialize the added member.

| Job-relative field | Meaning |
| --- | --- |
|+23|Geometry selector used by stage setup|
|+36|6032-byte processing-parameter block|
|+36+5684|Twelve saturation bytes in that block|
|+36+5808|Converted crop/geometry fields|
|+12228|Embedded 1132-byte request|
|request+0|Completion callback `0x604c4011` on qualified route|
|request+4|Pointer to selected operation record|
|request+1076|Twelve packed saturation bytes|
|+14076+i*52, i=0…15|Sixteen operation records|
|record+0|Parent job pointer|
|record+16|Per-CPU completion token|
|record+32|Completion status written for event 9|
|+14920|Extension: twelve signed H bytes followed by twelve signed L bytes|

The final HSL selector consumes the request and writes 12 sector records at companion+`0x2a4`. The uploaded coefficient bank is292 bytes including its control/trailer fields; it is distinct from the 3028-byte source LUT/sector structure.

The lower processing context is another object, not the whole shared job:

| Context field | Native allocation/configuration meaning |
| --- | --- |
| +4 | Request pointer |
| +8 | Processing-buffer allocation |
| +12 | Color-output pointer, equal to allocation+`0x20c` |
| +52 | LUT-cache tag |
| +100 | Dirty mask; bit `0x4` forces enabled HSL LUT uploads |
| +189 | LUT bank selector |

Allocator `0x604b38c5` creates this relationship. Its output holds twelve 24-byte coefficient records at+`0x2a4`, their control word at+`0x3c4`, tone pointer at+`0x1230`, and ten HSL LUT pointers at+`0x1434..0x1458`. These are pointers/coefficients for a peripheral, not a CPU pixel array. Context and shared-job offsets must not be mixed merely because both descriptions use the word “request.”

A valid request can use **any of the sixteen operation records**. Reader validation checks callback identity, record range/alignment and its parent link before accessing the extension. Record index is not a chronological stage number.

The integrated transport uses 45 packed 12-byte acquisition rows:40 large-capture owners plus five primary compact owners, 540 bytes total. Each sector byte holds H/L nibbles; conversion expands them into the 24-byte job member. Every valid acquisition overwrites its entire row; unknown owners produce neutral job H/L. The second compact ring and global configuration copy are not silently counted as additional qualified owners. Linked code/data addresses belong to the specific patch build, so use its build manifest rather than historical prototype placements.

## Evidence limits

The structures above are supported by native constructors/getters, bounded lifecycle tests and aligned code inspection. Some advanced probes depend on a partial emulated boot checkpoint, including explicitly captured calibration/configuration records. They do not reconstruct arbitrary camera RAM from scratch.

Current/staging, acquired-frame and prepared-job representations have different lifetimes. Per-access mutexes, API inhibition and pool reference counts protect their stated operations; none alone proves an atomic transaction spanning all of them. See [function and lifetime map](EDIT_AND_CAPTURE_MAP.md) for tested joins and remaining hardware/scheduling boundaries.
