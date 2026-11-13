#!/usr/bin/env python3
"""Regenerate patch.json from baseline + assembled section sizes."""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = 0x60021020
MAIN = ROOT / "generated/om3-db-ring-wifi-shutter-slots123-final-menufix/main.decoded.bin"
AS = ROOT / "toolchains/mn103-gas-ld-build/gas/as-new.exe"
LD = ROOT / "toolchains/mn103-gas-ld-build/ld/ld-new.exe"
OBJCOPY = ROOT / "toolchains/mn103-objdump-build/install/bin/mn10300-elf-objcopy.exe"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def assemble_sizes(group: dict, work: Path) -> dict[str, int]:
    folder = work / group["name"]
    folder.mkdir(parents=True, exist_ok=True)
    objects = []
    for source in group["sources"]:
        obj = folder / (Path(source).stem + ".o")
        subprocess.run([str(AS), "-o", str(obj), str(HERE / source)], check=True)
        objects.append(str(obj))
    elf = folder / "patch.elf"
    subprocess.run([str(LD), "--no-relax", "-T", str(HERE / group["linker"]), "-o", str(elf), *objects], check=True)
    sizes = {}
    for name in group["sections"]:
        out = folder / f"{name}.bytes"
        subprocess.run(
            [str(OBJCOPY), "-O", "binary", f"--only-section=.{name}", str(elf), str(out)],
            check=True,
        )
        sizes[name] = out.stat().st_size
        require = sizes[name] > 0
        if not require:
            raise SystemExit(f"empty section {name}")
    return sizes


def main() -> None:
    main_bin = MAIN.read_bytes()
    groups = [
        {
            "name": "image_parameters",
            "sources": ["src/image_parameters/image_parameters.s"],
            "linker": "src/image_parameters/layout.ld",
            "sections": {"color_hook": "0x60518615", "extension": "0x607187a4"},
        },
        {
            "name": "editor_storage",
            "sources": [
                "src/editor_storage/editor.s",
                "src/editor_storage/settings.s",
                "src/editor_storage/settings_lifecycle.s",
                "src/editor_storage/wheel.s",
                "src/editor_storage/image_transport.s",
                "src/editor_storage/raw_development.s",
                "src/editor_storage/orf_metadata.s",
            ],
            "linker": "src/editor_storage/layout.ld",
            "sections": {
                "hsl_set_hook": "0x60b8798b",
                "hsl_get_pointer": "0x60e57480",
                "hsl_default_pointer": "0x60e57510",
                "hsl_axis": "0x6071cf00",
                "hsl_dispatch_hook": "0x610f5f9e",
                "hsl_ui": "0x607189a4",
                "wheel_color1_hook": "0x60b1d0c7",
                "wheel_color3_hook": "0x60b1d219",
                "wheel_color4_hook": "0x60b1d2c2",
                "hsl_wheel": "0x60b1d170",
                "wheel2_color1_hook": "0x60cce97e",
                "wheel2_color3_hook": "0x60cceac8",
                "wheel2_else_hook": "0x60cceb77",
                "hsl_wheel2": "0x60ccea23",
                "persist_boot_hook": "0x603f0301",
                "persist_commit_hook": "0x60419d4f",
                "persist_refresh_hook": "0x604040ff",
                "hsl_cells": "0x60718da4",
                "hsl_persist": "0x60718f40",
                "persist_source": "0x60719e00",
                "capture_acquire": "0x603e7f34",
                "capture_to_job": "0x608abbcd",
                "recording_to_job": "0x6054fd82",
                "transport": "0x6071a000",
                "transport_rows": "0x6071a400",
                "raw_acquire_hook": "0x618e28ab",
                "raw_acquire": "0x6071b000",
                "native_orf_hook": "0x60550363",
                "native_orf_export": "0x6071b100",
            },
        },
        {
            "name": "settings_backup",
            "sources": ["src/settings_backup/settings_backup.s"],
            "linker": "src/settings_backup/layout.ld",
            "sections": {
                "backup_export_hook": "0x619fd0f8",
                "backup_header_hook": "0x619fd7e1",
                "backup_line_hook": "0x619fd859",
                "backup_footer_hook": "0x619fd8f2",
                "backup_export": "0x619f5108",
                "backup_lifecycle": "0x619f5300",
                "backup_import": "0x619f5380",
                "backup_data": "0x619f5700",
            },
        },
    ]

    work = HERE / "_gen_asm"
    if work.exists():
        import shutil

        shutil.rmtree(work)
    work.mkdir()

    ranges = []
    for group in groups:
        sizes = assemble_sizes(group, work)
        for name, address in group["sections"].items():
            va = int(address, 16)
            n = sizes[name]
            off = va - BASE
            b = main_bin[off : off + n]
            row = {"name": name, "address": address, "bytes": n, "before_hex": b.hex()}
            if all(x == 0xFF for x in b):
                row["before_is_ff_cave"] = True
            else:
                row["before_sha256"] = sha(b)
            ranges.append(row)
            group["sections"][name] = address

    spec = {
        "model": "OM-3",
        "firmware": "1.1 build 1100",
        "release": "om3-hsl-b-pm5-20261105",
        "cpu_base": "0x60021020",
        "baseline_main_sha256": sha(main_bin),
        "groups": groups,
        "main_ranges": ranges,
        "schema_edits": [],
        "data_edits": [],
        "value_range": "±5",
        "known_gaps": [
            "Wi-Fi HSL1 intentionally omitted.",
            "±7 range / wheel-encode / value-label OSD intentionally omitted; clamps and stock schemas stay ±5.",
            "compact_acquire / compact_to_job not hooked (no in-range trampoline).",
            "ORF: packed owner+37694 only; Workspace Adjust Color H/L will not appear (no CMIO tables).",
            "Wheel paint/update hooks unavailable; axis fill via COLOR expand paths only.",
        ],
        "abandoned": ["wifi_hsl1", "range_wheel_encode", "range_value_label", "pm7_schemas"],
    }
    (HERE / "patch.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print("groups", len(groups), "ranges", len(ranges), "schemas", 0)


if __name__ == "__main__":
    # Ensure MSYS DLLs resolve when invoked outside bash.
    import os

    msys = Path(r"C:\msys64\usr\bin")
    if msys.is_dir():
        os.environ["PATH"] = str(msys) + os.pathsep + os.environ.get("PATH", "")
    main()
