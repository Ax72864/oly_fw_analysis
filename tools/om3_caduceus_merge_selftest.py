#!/usr/bin/env python3
"""Offline acceptance checks for Caduceus + ring/wifi/shutter merged OM-3 firmware."""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from oly_container import parse, sha256

BASE = 0x60021020
NEW_RING_CAVE = 0x60339660
RING_CAVE_SIZE = 1448
SECTION1_END_GETTER = 0x60045E84


def u32(img: bytes, addr: int) -> int:
    return struct.unpack_from("<I", img, addr - BASE)[0]


def dc_tgt(img: bytes, addr: int) -> int:
    off = addr - BASE
    if img[off] != 0xDC:
        raise AssertionError(f"no dc at {addr:#x}")
    rel = struct.unpack_from("<i", img, off + 1)[0]
    return addr + rel


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--main",
        type=Path,
        default=ROOT / "generated/om3-caduceus-ring-wifi-shutter-slots123/main.decoded.bin",
    )
    ap.add_argument(
        "--pkg",
        type=Path,
        default=ROOT
        / "generated/om3-sd-install/caduceus-v022-ring-wifi-shutter-slots123/DCOLYMP/E1479999.BIN",
    )
    ap.add_argument(
        "--pre-wav-main",
        type=Path,
        default=ROOT / "generated/om3-caduceus-ring-wifi-shutter/main.decoded.bin",
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")

    img = args.main.read_bytes()
    pre = args.pre_wav_main.read_bytes()
    pkg = args.pkg.read_bytes()
    checks: dict = {}

    # Ring cave survives WAV injection and is inside section-1 load
    off = NEW_RING_CAVE - BASE
    checks["ring_cave_intact_after_wav"] = pre[off : off + RING_CAVE_SIZE] == img[off : off + RING_CAVE_SIZE]
    checks["ring_cave_not_ff"] = set(img[off : off + 8]) != {0xFF}
    end1 = u32(img, SECTION1_END_GETTER)
    checks["section1_end"] = hex(end1)
    checks["ring_cave_inside_section1"] = NEW_RING_CAVE + RING_CAVE_SIZE <= end1

    # Caduceus colour base
    checks["caduceus_ext1_present"] = img[0x6031E920 - BASE] != 0xFF
    checks["facade_getvalue_caduceus"] = u32(img, 0x60E57480) == 0x6031EB32
    checks["facade_count_caduceus"] = u32(img, 0x60E57490) == 0x6031EEF4
    checks["facade_vbi_caduceus"] = u32(img, 0x60E57494) == 0x6031EF27

    # Shutter write facade; Caduceus owns get/cnt/vbi/sel with miss→shutter chain (v0.26.2 sites)
    checks["facade_config_write_shutter"] = u32(img, 0x60E57478) == 0x6031FA9F
    checks["facade_getvalue_caduceus"] = u32(img, 0x60E57480) == 0x60F4A814
    checks["facade_blocked_caduceus_sl_sel"] = u32(img, 0x60E5749C) == 0x60F4AB30
    checks["chain_ed_get"] = dc_tgt(img, 0x6031EC6A) == 0x6031FA67
    checks["chain_pf_cnt"] = dc_tgt(img, 0x6031EF1D) == 0x6031FA00
    checks["chain_pf_vbi"] = dc_tgt(img, 0x6031EF58) == 0x6031FA1B
    checks["chain_sl_sel"] = dc_tgt(img, 0x60F4AC4D) == 0x6031FA43

    # Ring hooks (optional full packs): dc = insn_addr + rel
    checks["ring_identity_hook"] = dc_tgt(img, 0x602F946B) == NEW_RING_CAVE + 242
    checks["ring_parser_hook"] = dc_tgt(img, 0x602FC5ED) == NEW_RING_CAVE + 101
    checks["ring_request_hook"] = dc_tgt(img, 0x603049F6) == NEW_RING_CAVE + 0
    checks["ring_selected_av"] = dc_tgt(img, 0x605AC5F1) == NEW_RING_CAVE + 929

    # WAV slots
    for name, addr in (
        ("slot1", 0x60820000),
        ("slot2", 0x603244B0),
        ("slot3", 0x617E4800),
    ):
        checks[f"{name}_riff"] = img[addr - BASE : addr - BASE + 4] == b"RIFF"

    # No overlap: ring cave outside slot2 WAV
    slot2_end = 0x603244B0 + 86444
    checks["ring_outside_slot2_wav"] = NEW_RING_CAVE >= slot2_end or (
        NEW_RING_CAVE + RING_CAVE_SIZE <= 0x603244B0
    )

    # Package integrity
    blocks = parse(pkg)
    checks["pkg_main_matches"] = blocks[0].payload == img
    checks["pkg_sha256"] = sha256(pkg)
    checks["main_sha256"] = sha256(img)
    checks["pkg_size"] = len(pkg)
    checks["om3mod_guides"] = (
        ROOT
        / "generated/om3-sd-install/caduceus-v022-ring-wifi-shutter-slots123/OM3MOD/GUIDES.BIN"
    ).is_file()
    checks["om3mod_labels"] = (
        ROOT
        / "generated/om3-sd-install/caduceus-v022-ring-wifi-shutter-slots123/OM3MOD/LABELS.BIN"
    ).is_file()

    bools = {k: v for k, v in checks.items() if isinstance(v, bool)}
    failed = [k for k, v in bools.items() if not v]
    passed = not failed

    # Optional: stock firmup sim (needs native MN103 engine). Missing engine ≠ merge failure.
    firmup = None
    try:
        from om3_firmup_sim import main as firmup_main

        code = firmup_main(["--scenario", "both"])
        firmup = {"passed": code == 0, "exit": code}
    except Exception as exc:  # noqa: BLE001
        firmup = {"passed": False, "error": str(exc), "skipped_reason": "native_engine_unavailable_or_error"}

    report = {
        "passed": passed,
        "merge_checks_passed": passed,
        "failed_checks": failed,
        "checks": checks,
        "firmup_sim_stock": firmup,
        "limits": [
            "Does not flash a camera",
            "om3_firmup_sim / preflash_validate refuse patched mains by design; firmup_sim tried on stock only",
            "Native MN103 engine may be unavailable on this host; merge structural checks are authoritative here",
            "Colour UI / ring / shutter behaviour still need body confirmation",
        ],
    }
    args.out.mkdir(parents=True)
    (args.out / "selftest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "failed_checks": failed,
                "firmup_sim_stock": firmup,
                "out": str(args.out),
            },
            indent=2,
        )
    )
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
