#!/usr/bin/env python3
"""Build OM-3 HSL (B) on top of a feature-patched decoded main.

Assembles patches/hsl/om-3 sources, applies them to the baseline main, and
re-encodes a flashable OLY container. Does not require PEN-F release equality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from oly_container import parse, reconstruct, replace_payload  # noqa: E402

BASE = 0x60021020
STOCK = ROOT / "firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN"
STOCK_SHA = "8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d"
DEFAULT_MAIN = ROOT / "generated/om3-db-ring-wifi-shutter-slots123-final-menufix/main.decoded.bin"
AS = ROOT / "toolchains/mn103-gas-ld-build/gas/as-new.exe"
LD = ROOT / "toolchains/mn103-gas-ld-build/ld/ld-new.exe"
OBJCOPY = ROOT / "toolchains/mn103-objdump-build/install/bin/mn10300-elf-objcopy.exe"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(msg)


def assemble_group(group: dict, out_dir: Path, assembler: Path, linker: Path, objcopy: Path) -> dict[str, bytes]:
    folder = out_dir / "assembly" / group["name"]
    folder.mkdir(parents=True, exist_ok=True)
    objects = []
    for source in group["sources"]:
        obj = folder / (Path(source).stem + ".o")
        subprocess.run([str(assembler), "-o", str(obj), str(HERE / source)], check=True)
        objects.append(str(obj))
    elf = folder / "patch.elf"
    subprocess.run(
        [str(linker), "--no-relax", "-T", str(HERE / group["linker"]), "-o", str(elf), *objects],
        check=True,
    )
    blobs: dict[str, bytes] = {}
    for name in group["sections"]:
        output = folder / f"{name}.bytes"
        subprocess.run(
            [str(objcopy), "-O", "binary", f"--only-section=.{name}", str(elf), str(output)],
            check=True,
        )
        data = output.read_bytes()
        require(len(data) > 0, f"empty section {name}")
        blobs[name] = data
        (folder / f"{name}.sha256").write_text(sha(data) + "\n", encoding="utf-8")
    return blobs


def main() -> None:
    msys = Path(r"C:\msys64\usr\bin")
    if msys.is_dir():
        import os

        os.environ["PATH"] = str(msys) + os.pathsep + os.environ.get("PATH", "")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, default=DEFAULT_MAIN)
    ap.add_argument("--stock", type=Path, default=STOCK)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--as", dest="assembler", type=Path, default=AS)
    ap.add_argument("--ld", dest="linker", type=Path, default=LD)
    ap.add_argument("--objcopy", type=Path, default=OBJCOPY)
    ap.add_argument("--skip-groups", nargs="*", default=[], help="group names to skip")
    args = ap.parse_args()

    require(args.assembler.is_file(), f"missing assembler {args.assembler}")
    require(args.linker.is_file(), f"missing linker {args.linker}")
    require(args.objcopy.is_file(), f"missing objcopy {args.objcopy}")
    require(args.main.is_file(), f"missing baseline main {args.main}")
    require(args.stock.is_file(), f"missing stock {args.stock}")
    require(not args.out.exists(), f"refusing to overwrite {args.out}")

    spec = json.loads((HERE / "patch.json").read_text(encoding="utf-8"))
    amap = json.loads((HERE / "address_map.json").read_text(encoding="utf-8"))
    stock = args.stock.read_bytes()
    require(sha(stock) == STOCK_SHA, "stock container hash mismatch")
    main = bytearray(args.main.read_bytes())
    baseline_sha = sha(main)

    args.out.mkdir(parents=True)
    applied_sections = []
    for group in spec["groups"]:
        if group["name"] in args.skip_groups:
            continue
        blobs = assemble_group(group, args.out, args.assembler, args.linker, args.objcopy)
        for name, address in group["sections"].items():
            addr = int(address, 16)
            data = blobs[name]
            off = addr - BASE
            require(0 <= off < off + len(data) <= len(main), f"section OOB {name}")
            # Allow overwriting FF caves or exact declared before bytes
            before = bytes(main[off : off + len(data)])
            row = next((r for r in spec.get("main_ranges", []) if r["name"] == name), None)
            if row:
                require(len(data) == row["bytes"], f"{name} size {len(data)} != {row['bytes']}")
                if "before_sha256" in row:
                    require(sha(before) == row["before_sha256"], f"{name} before mismatch")
                elif row.get("before_is_ff_cave"):
                    require(all(b == 0xFF for b in before), f"{name}: expected FF cave")
            else:
                require(
                    before == data or all(b == 0xFF for b in before),
                    f"{name}: refusing non-FF overwrite at {hex(addr)}",
                )
            main[off : off + len(data)] = data
            applied_sections.append({"name": name, "address": hex(addr), "bytes": len(data), "sha256": sha(data)})

    # Keep stock COLOR schemas at factory ±5 so UI and clamps match.
    schema_applied = []

    for edit in spec.get("data_edits", []):
        addr = int(edit["address"], 16)
        after = bytes.fromhex(edit["after"])
        off = addr - BASE
        before = bytes(main[off : off + len(after)])
        if "before" in edit:
            require(before.hex() == edit["before"], f"data_edit before mismatch {edit['name']}")
        main[off : off + len(after)] = after
        applied_sections.append({"name": edit["name"], "address": hex(addr), "bytes": len(after), "sha256": sha(after)})

    blocks = parse(stock)
    package = reconstruct([replace_payload(blocks[0], bytes(main)), *blocks[1:]])
    require(parse(package)[0].payload == bytes(main), "container round-trip failed")

    (args.out / "main.decoded.bin").write_bytes(main)
    (args.out / "OLY_E_147_1100_patched_lab.bin").write_bytes(package)
    report = {
        "release": spec.get("release", "om3-hsl-b"),
        "baseline_main_sha256": baseline_sha,
        "main_sha256": sha(main),
        "container_sha256": sha(package),
        "stock_sha256": STOCK_SHA,
        "value_range": "±5 (stock UI schemas, clamped in HSL paths)",
        "schema_edits": schema_applied,
        "sections": applied_sections,
        "skipped_groups": args.skip_groups,
        "camera_access": False,
        "scope": "B-stack-on-feature-pack",
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("main_sha256", "container_sha256", "value_range")}, indent=2))


if __name__ == "__main__":
    main()
