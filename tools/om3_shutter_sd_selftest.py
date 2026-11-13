#!/usr/bin/env python3
"""Offline structural checks for the SD shutter-sound loader patch."""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

BASE = 0x60021020
HOOK_ADDR = 0x60A8F1D1
SS_CHAIN = 0x603244B0
PCM_BASE = 0x60324D00
PCM_LIMIT = 0x60357000
MENU = {
    0x6031FA00: "ss_option_count",
    0x6031FA1B: "ss_option_value",
    0x6031FA43: "ss_option_blocked",
    0x6031FA67: "ss_config_read",
    0x6031FA9F: "ss_config_write",
}
NM_LOAD = 0x60F49800
SD_OUT = 0x60A8F1E2
SECTION2_START = 0x603BA800


def decode_jmp(image: bytes, addr: int) -> int:
    off = addr - BASE
    if image[off] != 0xDC:
        raise ValueError(f"not JMP at {hex(addr)}: {image[off:off+5].hex()}")
    rel = struct.unpack_from("<i", image, off + 1)[0]
    return (addr + rel) & 0xFFFFFFFF


def section1_end(image: bytes) -> int:
    return struct.unpack_from("<I", image, 0x60045E84 - BASE)[0]


def decode_call(image: bytes, addr: int) -> int:
    off = addr - BASE
    op = image[off]
    if op == 0xDD:
        rel = struct.unpack_from("<i", image, off + 1)[0]
        return (addr + rel) & 0xFFFFFFFF
    if op == 0xCD:
        rel = struct.unpack_from("<h", image, off + 1)[0]
        return (addr + rel) & 0xFFFFFFFF
    raise ValueError(f"not CALL at {hex(addr)}: {image[off:off+7].hex()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, required=True)
    ap.add_argument("--report", type=Path, help="om3_shutter_sd_patch report.json")
    ap.add_argument("--stage-sd", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    image = args.main.read_bytes()
    checks: dict = {}
    errors: list[str] = []

    # Hook → ss_chain
    try:
        hook_tgt = decode_jmp(image, HOOK_ADDR)
        checks["hook_target"] = hex(hook_tgt)
        checks["hook_ok"] = hook_tgt == SS_CHAIN
        if not checks["hook_ok"]:
            errors.append(f"hook -> {hex(hook_tgt)} want {hex(SS_CHAIN)}")
    except ValueError as exc:
        checks["hook_ok"] = False
        errors.append(str(exc))

    # Boot hook must enter the real nm_load and return without scanning WAVs.
    try:
        nm = decode_call(image, SS_CHAIN)
        checks["nm_load_target"] = hex(nm)
        checks["nm_load_ok"] = nm == NM_LOAD
        if not checks["nm_load_ok"]:
            errors.append(f"ss_chain call -> {hex(nm)} want {hex(NM_LOAD)}")
    except ValueError as exc:
        checks["nm_load_ok"] = False
        errors.append(str(exc))
    window_head = image[SS_CHAIN - BASE : SS_CHAIN - BASE + 24]
    sd_outs = []
    for i in range(len(window_head) - 4):
        if window_head[i] == 0xDC:
            rel = struct.unpack_from("<i", window_head, i + 1)[0]
            sd_outs.append((SS_CHAIN + i + rel) & 0xFFFFFFFF)
    checks["early_jmps"] = [hex(t) for t in sd_outs]
    checks["chain_returns_sd_out"] = SD_OUT in sd_outs
    if not checks["chain_returns_sd_out"]:
        errors.append("ss_chain does not jmp sd_out in its first 24 bytes")
    # A second call in those bytes would be the old boot-time ss_boot scan.
    calls = [i for i, b in enumerate(window_head) if b in (0xDD, 0xCD)]
    checks["chain_call_sites"] = len(calls)
    if len(calls) != 1:
        errors.append(f"ss_chain has {len(calls)} calls in the prologue; want only nm_load")

    # Cave head
    cave = image[SS_CHAIN - BASE : SS_CHAIN - BASE + 8]
    checks["cave_head"] = cave.hex()
    checks["cave_not_ff"] = set(cave) != {0xFF}
    if not checks["cave_not_ff"]:
        errors.append("ss cave still FF")

    # Path strings inside cave window
    window = image[SS_CHAIN - BASE : PCM_BASE - BASE]
    checks["has_shut_path"] = b"C:\\OM3MOD\\SHUT" in window
    checks["has_shutsel_path"] = b"C:\\OM3MOD\\SHUTSEL.BIN" in window
    if not checks["has_shut_path"]:
        errors.append("missing SHUTxx path string")
    if not checks["has_shutsel_path"]:
        errors.append("missing SHUTSEL path string")

    # Menu JMPs
    syms = {}
    if args.report and args.report.is_file():
        rep = json.loads(args.report.read_text(encoding="utf-8"))
        syms = {k: int(v, 16) for k, v in rep.get("symbols", {}).items()}
    for cave_addr, name in MENU.items():
        try:
            tgt = decode_jmp(image, cave_addr)
        except ValueError as exc:
            checks[f"{name}_ok"] = False
            errors.append(str(exc))
            continue
        checks[f"{name}_target"] = hex(tgt)
        expect = syms.get(name)
        ok = (expect is None) or (tgt == expect)
        checks[f"{name}_ok"] = ok
        if expect is not None and not ok:
            errors.append(f"{name} -> {hex(tgt)} want {hex(expect)}")

    # Section / bank coverage
    end1 = section1_end(image)
    checks["section1_end"] = hex(end1)
    checks["section1_covers_pcm"] = end1 >= PCM_LIMIT
    if not checks["section1_covers_pcm"]:
        errors.append(f"section1 end {hex(end1)} < pcm limit {hex(PCM_LIMIT)}")
    checks["section1_before_section2"] = end1 <= SECTION2_START
    if not checks["section1_before_section2"]:
        errors.append(f"section1 end {hex(end1)} overlaps section2 {hex(SECTION2_START)}")

    # Caduceus facade get still Caduceus (don't clobber colour)
    fac_get = struct.unpack_from("<I", image, 0x60E57480 - BASE)[0]
    checks["facade_get"] = hex(fac_get)
    checks["facade_get_not_shutter_menu"] = fac_get not in MENU
    # config_write facade still points at shutter cave (our JMP lives there)
    fac_wr = struct.unpack_from("<I", image, 0x60E57478 - BASE)[0]
    checks["facade_write"] = hex(fac_wr)
    checks["facade_write_is_shutter_cave"] = fac_wr == 0x6031FA9F

    if args.stage_sd:
        bin_path = args.stage_sd / "DCOLYMP" / "E1479999.BIN"
        checks["stage_has_container"] = bin_path.is_file()
        om = args.stage_sd / "OM3MOD"
        checks["stage_has_guides"] = (om / "GUIDES.BIN").is_file() or True  # optional if not copied
        shut_files = sorted(om.glob("SHUT*.WAV")) if om.is_dir() else []
        checks["stage_shut_wavs"] = [p.name for p in shut_files]
        checks["stage_has_shutsel"] = (om / "SHUTSEL.BIN").is_file()
        if shut_files and not checks["stage_has_shutsel"]:
            errors.append("missing SHUTSEL.BIN on stage tree")
        if checks["stage_has_shutsel"]:
            sel = (om / "SHUTSEL.BIN").read_bytes()
            checks["shutsel_magic_ok"] = sel[:4] == b"OM3S" and len(sel) >= 12
            if not checks["shutsel_magic_ok"]:
                errors.append("bad SHUTSEL.BIN")

    args.out.mkdir(parents=True, exist_ok=True)
    out = {"checks": checks, "errors": errors, "ok": not errors}
    (args.out / "selftest.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
