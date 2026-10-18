# IDA 4.9 and the MN103 module

IDA is useful for browsing functions, adding names and following references.
The verified combination is **IDA 4.9 Free with the historical MN103 processor
module**. This is a specific old combination, not a claim that every IDA Free
version supports camera processors.

Most analysis in this repository uses GNU disassembly and the MN103 emulator.
IDA supplied an independent check and a navigable database. It is optional:
neither the research probes nor the HSL build require it. This module does not
provide an MN103 C decompiler.

## Install the tools

Obtain the [IDA 4.9 freeware installer](https://archive.org/details/idafree49)
and [MN103 module](https://pentax-hack.info/firmware/pan/mn103.zip) separately.
The installer SHA-256 is
`7745833d4376ed029ccd2990da66536d568f239e37ad5149bd0a0218ed68b4a9`.
The tested `mn103.w32` hash is
`3400dd7cc5727f34ab6a924cf3b9dc1842d27979ec02723cb19f49429711c080`.
These identify the inspected copies, not a publisher signature.

1. Install IDA 4.9 on Windows, or in an initialized 32-bit Wine prefix on Linux.
   Complete its ordinary first-run dialogs interactively.
2. Put `mn103.w32` in IDA's processor directory (`procs` in the tested install)
   and `mn103.cfg` in `cfg`.
3. Select the MN103 processor. Create the image segment at its runtime address;
   do not accept an unrelated default ROM region from the module configuration.
4. For PEN-F 3101, load decoded main at `0x60021020`. Its 21,364,672 bytes end
   at `0x61480fe0`. The container's flash address is a different address space.

The installer/module sources and the separate historical module source tree
are described by the [module authors' tools page](https://hitmen.c02.at/html/tools_ida.html).
Compatibility with another IDA version must be checked independently.

## What Wine and IDC do

Wine supplies the Windows APIs needed by IDA on Linux. It does not emulate the
camera. IDC is IDA's own scripting language. The supplied Python tool generates
an IDC script that loads the image, decodes selected windows, exports bytes and
instructions, checks a call reference and saves an IDA database.

The optional Linux runner uses Xvfb for a virtual screen. Its small driver clicks
only the normal freeware About dialog; it does not complete license dialogs.
Bubblewrap isolates the installation and output directory and disables network
access. Use a dedicated Wine prefix and run one exporter at a time.

## Prepare an export

From the repository root, after decoding the matching stock firmware:

```bash
python3 tools/ida/prepare.py \
  --image analysis/penf_3.1/00_0100_403a0020.decoded.bin \
  --out generated/ida-pen-f
```

The output contains `input.bin`, `export.idc` and the model description. The
[PEN-F model file](../../../tools/ida/models/pen-f-3101.json) pins the input hash,
base, three windows and a known call reference. Another model needs its own
verified descriptor; changing the camera name is insufficient.

On Windows, pass `--windows-directory C:/research/ida-pen-f` when preparing the
files, put the output at that path, and run IDA there:

```text
idag.exe -A -a -pmn103 -Sexport.idc -omain.idb input.bin
```

The Linux runner expects an installation directory containing
`extracted/app/idag.exe` and an initialized `prefix/`. A system 32-bit Wine,
Xvfb, Bubblewrap, xwininfo and XTest are needed. An extracted Wine runtime under
`runtime/` is also supported; the tested one was Wine 6.0.3.

```bash
python3 tools/ida/prepare.py \
  --image analysis/penf_3.1/00_0100_403a0020.decoded.bin \
  --out generated/ida-pen-f-run \
  --run --installation /path/to/ida49
```

Linux systems that disallow user namespaces cannot use this wrapper. Manual
IDA use and the GNU tooling remain available. This wrapper is not needed on
Windows.

## Interpreting the result

`listing.txt` should end with `COMPLETE` and contain
`XREF 60021029 -> 600210E9`. `main.idb` is the database. The verified export
covers 143 instructions in the entry, checksum and COLOR-builder windows:
addresses, lengths, bytes and mnemonic names agree with GNU. This is not a whole-image
function analysis or an automated comparison of operand semantics.

The exporter intentionally avoids whole-image recursive analysis. Mixed code
and data can produce plausible but false instructions. Decoding a window does
not prove that startup reaches it, and `udf00` names alone do not explain the
custom instruction semantics.
