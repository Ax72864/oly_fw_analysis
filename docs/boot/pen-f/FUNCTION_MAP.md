# PEN-F startup function and service map

All addresses refer to the decoded **PEN-F 3.1 build 3101** main component. Addresses are hexadecimal; task, IRQ and flag identifiers are decimal unless prefixed with `0x`. A function name below is a descriptive research label unless quoted from firmware diagnostics. This is an address-level companion to [startup](STARTUP.md), [inputs](INPUTS.md) and [recovery](RECOVERY.md).

**Evidence notation:** **N** = original instructions executed in a bounded native-emulation contract; **C** = reached in a connected replay starting at main; **S** = static instruction/caller relationship. C still includes the explicit peripheral models below. No row should be read as a physical reset-to-updater trace.

## Entry, kernel and task foundations

| Address or object | Role and contract | Evidence |
| --- | --- | --- |
| `0x60021020` | Downloaded main entry; calls use an incoming stack before the explicit stack installation at `0x600210ce..0x600210d4` | C |
| `0x600210dc → 0x600210f9` | Internal indirect handoff to C initialization; not evidence for an external reset vector | C |
| `0x600213ed`, `0x6002794d` | Program hardware RAM-clear requests; the harness supplies their bounded completion | C + model |
| `0x47000800..0x47002000` | Six-KiB helper relocation into core-local RAM | C |
| `0x60027035`, `0x60027511` | CPU1 and CPU2 startup entries published by CPU0 | C |
| `0x6003008c`, `0x60032a11`, `0x60032a1f` | CPU0/1/2 kernel initialization | C |
| `0x60033563` | Shared kernel-ready barrier; each core publishes its bit in `0x8ff00000`, complete mask 7 | C |
| `0x6006ad97` | CPU0 initial task | C |
| `0x6006bf05`, `0x6007025b` | CPU0 connection-service and CPU-switch task entries | C |
| `0x60041ae3` | System-service/peripheral initializer; precedes application section loading | C |
| `0x60041d9a` | Normal application-section load boundary | C |
| `0x600697ff → 0x600307dd` | Ordinary task-start wrapper and local kernel start API | N/C |
| `0x60032654` | Lower activation primitive; consumes the descriptor priority as a halfword at +12 | N |
| `0x600319aa` | Native task exit/delete, used by dynamic service workers | C |

The static descriptor sets contain 140 CPU0, 49 CPU1 and 21 CPU2 tasks. Only the first initial task is marked for automatic activation in the reviewed enumeration. A compiled descriptor does not mean a task is running. CPU1 and CPU2 task IDs encode their CPU (`0x1001`, `0x2001`, etc.); do not strip upper bits or equate queue IDs with task IDs.

The kernel has two separate synchronization layers. Early notification routines use local control word `0x8958`, bit 4, and CPU-specific writes at `0x99200310`, `0x99300310`, `0x99b00310`. The later shared-ready mask at `0x8ff00000` is set only after each core's actual object initialization. Supplying ready bits without running peer initialization bypasses real pointer/object creation.

## Startup tasks and later service launches

| Task | ID | Entry | Important native caller relationships |
| --- | ---: | --- | --- |
| USTART1 | 47 | `0x601a70cc` | Starts USTART3 at call `0x601a7130`; initializes application services; requests section 3 at `0x601a72f0` |
| USTART3 | 49 | `0x601a7644` | Input-registration prefix includes `0x601a7663`; waits for section 3 and USTART1 completion; starts FILECLBK at `0x601a7801`, USTART4 at `0x601a7cae` |
| USTART4 | 48 | `0x601a7ed1` | Loads sections 4/5, installs application callbacks, crosses a progress barrier, then loads/waits for sections 6/7/8; starts USTART5 at `0x601a7fe1` |
| USTART5 | 46 | `0x601a8019` | Starts TPC at `0x601a86bf`, FIRMUP_SRV at `0x601a871d` |
| TPC | 42 | `0x60ab8ec8` | Normal USB/PTP worker |
| FIRMUP_SRV | 19 | `0x60b1d012` | Shared firmware-update service |
| Compiled SD client | 95 | `0x60b1cbb5` | File-service client; activation from physical OK+power remains unconnected |

USTART1 and parts of USTART3 are in the connected trace. Later caller relationships are supported by static analysis and isolated native caller contracts; direct callees were not all executed in the caller survey. They must not be spliced into a claimed uninterrupted cold boot.

Keep these state variables distinct:

| Address/API | Meaning established by its consumers |
| --- | --- |
| `0x618656a8` | Readiness dependency polled by USTART1 at `0x601a7285` |
| `0x618656ac` | USTART1 completion dependency polled by USTART3 at `0x601a76a4` |
| `0x618642cc` | Power-readiness result consumed by USR_FAST; callback `0x60041a8a` publishes success |
| `0x618642c4` | Signed worker-progress ordinal; `0x601a50b7` waits for at least 4 |
| `0x618642c8` | Permit ordinal written by `0x601a50f9`; values 1, 2 and 4 are thresholds, not event masks |
| `0x601a50e7` | Event-post interface, whose argument *is* a bitmask |
| `0x618656a0` | Result retained from USTART1's media-state consumer `0x601a88cf` |

A later BOOT-state handler can start the GUI through `0x60ba1eb0 → 0x60bb8d4b`; boot services 8 and 9 skip that branch. Separate application fixtures connect power/USB/wake events to higher-level requests. They do not prove which events the missing pre-main environment produces.

## Section loading and cross-core transport

Section 3 contains the COLOR builder and coefficient tables. Its normal load contract is:

```text
USTART1 call 0x601a72f0
  → 0x60042063(section=3)
  → 0x600700a8(target CPU1)
  → 0x6006fcd2; native write 8 to 0x99300308
  → CPU1 IRQ120, handler 0x6006c840
  → ring drainer 0x6006feb0
  → callback 0x600701ff posts queue 4105
  → CPU1 dispatch task 4124, entry 0x600702de
  → queued loader 0x600421e1
  → flash wrapper 0x600720e1
```

The sender uses task slot `0xa1c274e0`, interrupt-ring slot `0xa1c26cc8`, and ring indices `0xa1c26fc8/0xa1c26fc9`. The reviewed transaction advances indices from 1/0 to 1/1. The section selector is `0xa1c583fc`; loaded-section mask is `0xa1c58404`.

The loader reads 2, 527, 232 bytes from logical flash `0x407b1800` (submitted alias `0x807b1800`) to `0x60432800..0x6069b800` (uncached destination `0xa0432800`). SHA-256 of that decoded section is `bad0af0c8829d9a3af653b6619a2772c890b8ebbd834192957bb6711919c5ed8`.

The read wrapper acquires CPU0 semaphore 116 before storage access and releases it afterwards. A third remote operation posts flag 182, mask 4. These native service transactions execute in the connected replay; the actual flash read is a modeled logical backend using pinned bytes.

| Service | Sender/consumer relationship | Completion |
| --- | --- | --- |
| 8: wait semaphore | `0x60069606 → 0x6006c30d → 0x6006c5dc`; CPU0 dispatch `0x6006c483 → 0x60037f9c` | Semaphore 116 count 1→0 |
| 7: signal semaphore | `0x600696f9 → 0x6006c2d9 → 0x6006c5dc`; CPU0 `0x600367ef` | Count 0→1 |
| 3: set flag | Cross-core flag producer `0x6006c1a4`; CPU0 `0x600366eb` | Flag 182 pattern 0→4 |

Sem116's native object is `0x6182abc8`, count +24. Flag 182's object is `0x6182ddc8`, pattern +20. Completion means bytes arrived and the worker notified its caller. It does **not** mean section initialization completed.

Waiter `0x60042123` subsequently performs memory/cache-related setup, invokes initializer dispatcher `0x6006da8c` for sections 1–5, sets the loaded-mask bit and clears the outstanding selector. Section 3's table at `0x6069b240` contains eleven constructors. In the connected trace at its mapped frontier, the copy/completion has happened but the section-3 waiter/constructors have not: selector 3, loaded mask 3, completion pattern 4. Isolated constructor tests are separate evidence.

### Cross-core request records

Ordinary request slots are 52 bytes. The pool starts at `0xa1bed36c + cpu*0x64c`, 31 slots per source CPU; IRQ requests start at `0xa1bee650 + cpu*0x340`, 16 slots.

| Offset | Field |
| ---: | --- |
| +0 | Operation code |
| +12 | Source CPU |
| +16 | Completion bit, `1 << slot` |
| +20 | Requested task/flag/semaphore ID |
| +24 | Operation-specific argument, e.g. flag mask or timeout |
| +40 | Routing object ID |
| +44 | Source task identity, or CPU bits for IRQ form |
| +48 | Publication state: 3 ordinary, 2 IRQ |

For the semaphore transaction, slot `0xa1bed9b8` progresses through states 3 (published), 4 (worker executing), 5 (reply ready), 6 (reply received). CPU0 IRQ handler `0x6006c73f` acknowledges request bit 0 and signals flag 217/mask `0x80000000`. Service task 138 at `0x6006bf05` scans via `0x6006c379`, creates a priority-15 worker with a 1024-byte stack, and dispatches through `0x6006bf73`. Reply writes 2 to CPU1 doorbell `0x99300308`; CPU1 signals flag 4115/mask 1. Native worker exit/delete and interrupt return execute; the host does not clear their task objects as a substitute.

The startup mailboxes are a different mechanism. CPU1 `0x6002729a → 0x601a887c → 0x600703e4` uses `0x8ff00088`; CPU2 `0x600276f7 → 0x601a889a → 0x6007085c` uses `0x8ff000b4`. Both initialize all ten words, erasing inherited commands. Their local task-start calls reject task 95 with −25 at the core-ownership check `0x6003183f`. A queued cross-core request can explicitly target CPU0 task 95, but no physical-update producer of such a request has been identified.

## Input, power and auxiliary-controller dependencies

| Chain | Native behavior | Modeled input or unresolved boundary |
| --- | --- | --- |
| Battery ADC `0x60041d5f → 0x60076cd5` | Logical 13 selects ADC channel 6; logical 4 channel 0; five samples per request; `0x60075e15` discards sample 0 and averages four | Conversion complete/acknowledgement and raw samples supplied |
| ADC driver | Completion `0x98c00014`; channel 6 data `0x98c00054`; IRQ114 handler `0x6007a4d3` for interrupt modes | Initial battery operations poll; deferred cleanup needs software IRQ31 |
| Exposure dial | Logical 15/channel 7 → read `0x98c00058` at `0x6007a2b2` → callback `0x6019afd7` → decoder `0x6019b892` | Sample 415 is inside A interval 392…437; it is not a measured voltage |
| Dial publication | One-hot `0x0100` → `0x6019b08f → 0x6019a2f3`; cached selector `0x61c5802c=8`; `0x601a4db8` returns 2 | Native startup mode `0x618642e0=2` means A in this contract |
| Power task 100 | Entry `0x60087ddd`; queued selectors 7→8→9 complete through `0x600424ba`, `0x600423d4`, `0x600423f1`, `0x6004240e` | Real controller replies/timing are not inferred from readiness-word zero |
| Input delivery gate | `0x60199329` writes `0xa1c58028`, consumes special marker at `0xa1c57fd4` | Ordinary input enable is not identified as the recovery selector |

“Alex” is a firmware diagnostic name for an auxiliary serial/bulk peer, not an established physical chip identification. Its block-transfer chain is `0x6007ca4b → 0x6007cdea → 0x6007cf6e`; three source blocks are uploaded:

| Cached source | Bytes | Big-endian u32 sum modulo 2³² |
| --- | ---: | --- |
| `0x60042c00` | 97472 | `0xc15f2584` |
| `0x6005b0c0` | 2048 | `0x84af24b0` |
| `0x6005a8c0` | 2048 | `0xa4c3f383` |

Native serial commands `0x66/0x67` request checksum halves; the modeled peer computes them from the actual source bytes. Final commands `0xe5/0x65/0xe2` complete the initialization. CPU1 publishes result at `0x8ff00070` and completion at `0x8ff0006c`; CPU0 consumes them at `0x60070e46`. These are peripheral initialization transfers, not SD firmware installation.

Cleanup at `0x6007d1a4..0x6007d1a8` explicitly passes a null descriptor to GPIO helper `0x60084664` for GPIO97. The helper uses word 0 as output bit, word 4 as optional callback, word 8 as its argument if nonzero. Connected execution supplies a narrowly scoped zero-memory hypothesis. That suppresses a possible callback and must remain visible as an assumption. A nonzero-callback native control confirms the indirect call is real.

## Display, resources and camera-controller setup

USF initialization writes the reviewed `0x9b800008/0x9b800124/0x9b80012c` registers. Its synchronous/asynchronous request entries are `0x600906ca/0x6009071b`; asynchronous state retains a caller pointer at `0x616fd2dc`, and completion helper `0x600909e2` calls through that record. Initializing USF does not qualify any invented completion.

Display initializer `0x60315edd` starts automatic-dimming helper 80 (`0x6031a115`) and DISPLAY61 (`0x603160f8`). Shared software words at `0x8ff001a4..0x8ff001af` are initialized through `0x60042664`; change reader `0x6004268d` compares current and previous values. A returned initializer or scheduled display task does not prove panel/backlight readiness or a visible frame.

Resource initializer `0x602b8573` executes logical reads from these directories:

| Logical address | Meaning and supplied contents |
| --- | --- |
| `0x46160000` | Picture directory: exact component 0102 bytes |
| `0x42e00000` plus subdirectories | Common resources: exact component 0106 bytes |
| `0x41800000` | OSD directory: exact component 0101 bytes |
| `0x47560000`, `0x44560000` | Sound and mode 17 directories absent from E-package; destination CPU reads remain prohibited |
| `0x40240000` | Lens directory; explicit erased scenario triggers `LENSDAT` fallback from `0x603713ac` |
| `0x40160000` | Saved-lens metadata; explicit invalid/erased input triggers native empty defaults |

Unknown directories are not treated as valid zero-filled resources. The model permits their transfer while leaving the resulting memory unreadable, so a later consumer must stop for review.

The camera-controller chain is:

```text
USTART1 → 0x6025b91d → 0x6029ea4a
  → 0x602a31cc controller initialization
  → five subordinate unit initializers
  → 0x6027cd50 → 0x6027e7ca → 0x60283dd2
  → 0x6029e407 → 0x602a64fa
  → read 0x9b000000 at 0x602a6500 [mapped frontier]
```

Controller initialization copies 276 bytes from `0x6036b4e0` to `0x61883f60`, registers IRQ4/5/6 at priority 2 with handlers `0x602a6243/0x602a6277/0x602a62ab`, and links 188 twelve-byte nodes. It returns natively. The subsequent initialized units are:

| Initializer | Configuration destination | Bytes | IRQs |
| --- | --- | ---: | --- |
| `0x6025d92c` | `0x61869dbc` | 84 | 8–10 |
| `0x6025e8d5` | `0x61869f48` | 40 | 17 |
| `0x60296ad8` | `0x61870e8c` | 40 | 15 |
| `0x60298b7a` | `0x61870f84` | 96 | 11–14 |
| `0x6029c3b2` | `0x618715dc` | 92 | 16 |

The last configuration copies 23 stack words although its builder initializes only 21. IRQ16 handler `0x6029e1da` combines status `0x9b10002c` with mask `0x9b100430`; bits 20/22 can select callback fields `0x6187162c/0x61871634`. Their preceding stack contents are retained. No IRQ16 is fabricated in the connected replay, and no stock-camera failure is inferred from these fields.

## Peripheral assumptions that must accompany this map

| Boundary | Harness interpretation | What remains unproven |
| --- | --- | --- |
| `0x8040` write 8 | Park a peer at the reviewed CPU-halt sites; wake on reviewed notification | Exact PEN-F clock/sleep/wake behavior |
| IRQ120 doorbells `0x99200308/0x99300308` and clears `...30c` | Latch a specific request; clear only after native acknowledgement; deliver at guarded scheduling boundaries | Hardware latency, arbitrary preemption and all interrupt sources |
| `0x9bf00044` | Bulk completion progression for three pinned Alex descriptors | Peripheral execution and electrical interface |
| `0x98800050`, `0x98800100` | Scoped mux/PLL readback; native calculations and writes run | Physical clock lock and timing |
| `0x9b000500/0x9b000504` | Enable latch and write-mask-to-clear, inferred from paired acquire/release | True hardware register specification |
| RAM aliases | Coherent cached/uncached views | Real cache/DMA coherence under concurrent use |
| NAND/settings | Pinned logical image bytes, explicit synthetic metadata and erased banks | ECC, raw NAND failures, actual calibration/settings and power-loss behavior |

The latest connected frontier leaves USTART1 running, section 3 constructors pending, and SD95/FIRMUP19/application 64–65 dormant in that schedule. Other bounded fixtures reach those services independently. Neither evidence set identifies the physical OK+power edge, establishes an earlier USB recovery route, or supplies the missing reset/BOOT code.

## Reproducing address-level evidence

The retained [boot emulator](../../../tools/penf_boot_emulator.py) and [camera-unit continuation](../../../tools/penf_boot_camera_units.py) implement the connected models. [Emulator contracts](../../tooling/EMULATOR.md) explain pinned inputs, memory assumptions and strict stops. The [disassembly window inventory](../../../provenance/disassembly-windows.json) supports local regeneration from owned firmware; bulk firmware listings are not distributed here.
