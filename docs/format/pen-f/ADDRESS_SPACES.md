# Address spaces and loaded sections

File offsets, container addresses, logical flash addresses and CPU runtime
addresses are different. Record which one a number refers to before following
references or building a patch.

## PEN-F 3101 mapping

The decoded main uses analysis base `0x60021020`. The component's container
payload address is `0x403a0020`; that is not a disassembler load address.
Some code and initialized data are copied again during startup.

For application section 3:

| Property | Address or length |
| --- | --- |
| Section descriptor | `60026d94` |
| Logical flash source | `407b1800` |
| Runtime destination | `60432800` |
| Runtime end, exclusive | `6069b800` |
| Length | 2,527,232 bytes |
| Native load callback | `600421e1` |

The storage read uses source alias `807b1800` and destination alias `a0432800`.
The harness supplies coherent aliases; this does not model physical cache
coherency, NAND timing or ECC.

Native load tests start with poisoned destination RAM, copy the specified
section, and verify all bytes. Changed padding survives load and reload without
an additional checksum decision in the executed upper loader. The lower storage
service is modeled; earlier or lower integrity checks are not excluded.

## Why an FF-filled gap can be misleading

A large FF run in the flat image may contain:

- Alignment padding inside a loaded section.
- File bytes outside that section's actual load boundary.
- A runtime destination whose initial contents come from a different file range.

For example, startup copies `0x648` bytes from `6002f020` to `61170fe0`, including
small-bank descriptors. Reading only the flat image at the destination would
misidentify initialized data as unused space.

Startup also copies 6 KiB of helper code into `47000800..47002000`. Those copy/fill
routines are relocated main-image code, not evidence of an independent ROM.

## Flash and runtime ownership

The loader uses fixed logical offsets and lengths; it does not spontaneously
shift a table during installation. NAND bad-block mapping can change physical
placement without changing those logical addresses.

Code inserted into a loaded section executes from RAM. A successful load proves
its initial contents, not that another subsystem can never overwrite or reuse
that RAM. Code-space qualification therefore needs section bounds, initializer
and table bounds, references and runtime ownership—not only an FF scan.
See [code-space examples](../../safety/CODE_SPACE.md).
