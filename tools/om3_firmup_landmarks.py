#!/usr/bin/env python3
"""Offline OM-3 firmup / SD-update landmarks from pinned build 1100 main.

Read-only analysis of the decoded main image. Does not open a camera, write an
SD card, or program flash.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from oly_container import sha256
from om3_probe import BASE, STOCK_MAIN, STOCK_MAIN_SHA, load_stock_main, require

STRINGS = (
    ("DCOLYMP", b"DCOLYMP"),
    ("E147_pattern", b"E147????BIN"),
    ("S147_pattern", b"S147????BIN"),
    ("api_firmup_c", b"api_firmup.c"),
    ("firmup_mount_ok", b"[firmup]mount_ok"),
    ("firmup_ld_img_st", b"[firmup]ld_img_st"),
    ("fupsrv_get_request", b"[fupsrv]Get request"),
    ("FIRMUP_SRV", b"FIRMUP_SRV"),
    ("Execute_FirmwareUpdate", b"Execute_FirmwareUpdate start"),
    ("Check_FirmwareUpdate", b"Check_FirmwareUpdate start"),
    ("FirmUp_BODY_start", b"FirmUp_Update_Firmware for BODY start"),
    ("TPCFirmup_GetMode", b"[TPCFirmup]GetFirmwareUpdateMode"),
    ("TPCFirmup_UpdateInitiate", b"[TPCFirmup]UpdateInitiate"),
    ("USR_FIRMUP_END", b"USR_FIRMUP_END"),
)

# Absolute pointer sites observed loading DCOLYMP (0x606253b5) into path builders.
DCOLYMP_CODE_SITES = (
    0x6041762F,
    0x604177A9,
    0x604178C3,
    0x60417987,
)

COMMUNITY_SD = {
    "directory": "DCOLYMP",
    "filename": "E1479999.BIN",
    "slot": 1,
    "activation": "hold OK while powering on (community report; physical edge not native-proven here)",
    "source": "iKenndac/om-1-manual-firmware-install (third-party; at own risk)",
}


def find_all(image: bytes, needle: bytes) -> list[int]:
    out: list[int] = []
    start = 0
    while True:
        off = image.find(needle, start)
        if off < 0:
            break
        out.append(BASE + off)
        start = off + 1
    return out


def ptr_refs(image: bytes, address: int, limit: int = 32) -> list[int]:
    raw = struct.pack("<I", address & 0xFFFFFFFF)
    return find_all(image, raw)[:limit]


def pattern_table(image: bytes) -> list[dict]:
    """Parse contiguous ????BIN labels near S147/E147 table."""
    anchor = image.find(b"S147????BIN")
    if anchor < 0:
        return []
    rows = []
    off = anchor
    end = min(len(image), anchor + 256)
    while off < end:
        chunk = image[off : off + 12]
        if len(chunk) < 11 or b"BIN" not in chunk:
            break
        text = bytes(b if 32 <= b < 127 else 0x2E for b in chunk).decode("ascii")
        if "BIN" not in text:
            break
        # Labels are 11-byte 8.3-ish + NUL padding in practice.
        label = text.split("\x00")[0].rstrip(".")
        if "BIN" not in label:
            break
        rows.append({"analysis_address": hex(BASE + off), "pattern": label[:11]})
        off += 12
        if len(rows) >= 16:
            break
    return rows


def collect(image: bytes) -> dict:
    strings = {}
    for name, needle in STRINGS:
        addrs = find_all(image, needle)
        strings[name] = {
            "count": len(addrs),
            "addresses": [hex(a) for a in addrs[:8]],
        }
    dcol = find_all(image, b"DCOLYMP")
    e147 = find_all(image, b"E147????BIN")
    return {
        "model": "OM-3",
        "build": "1100",
        "main_sha256": STOCK_MAIN_SHA,
        "cpu_base": hex(BASE),
        "strings": strings,
        "pattern_table": pattern_table(image),
        "dcolymp_pointer_refs": [hex(a) for a in ptr_refs(image, dcol[0])] if dcol else [],
        "e147_pointer_refs": [hex(a) for a in ptr_refs(image, e147[0])] if e147 else [],
        "dcolymp_code_sites": [hex(a) for a in DCOLYMP_CODE_SITES],
        "path_helper_call": hex(0x6106BE34),
        "community_sd_layout": COMMUNITY_SD,
        "scope": [
            "Offline string/pointer landmarks only",
            "Does not prove OK+power selection or flash-backend success",
            "Does not access a camera or write an SD card",
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, default=STOCK_MAIN)
    ap.add_argument("--out", type=Path, help="report directory (created)")
    args = ap.parse_args(argv)
    image = load_stock_main(args.main)
    report = collect(image)
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        require(not args.out.exists(), "Use a new output directory")
        args.out.mkdir(parents=True)
        (args.out / "om3-firmup-landmarks.json").write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
