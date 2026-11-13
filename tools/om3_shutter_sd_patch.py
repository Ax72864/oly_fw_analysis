#!/usr/bin/env python3
"""Post-merge patch: Caduceus SDLOAD → SD shutter WAV loader + menu wrappers.

Preferred base (2026-11-13): body-verified resident pack main

  generated/om3-sd-ready/caduceus-v0262-shutter-only-resident/.../main
  or lab generated/om3-caduceus-shutter-only-resident/main.decoded.bin

That image already has correct section-3/8 load ends and v0.22 menu/controls.
This tool overwrites the slot-2 WAV cave with ss_sd, clears PCM arenas, hooks
sd_load, and installs 5-byte menu entry JMPs only (wrappers id-gate 6001/6002).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from oly_container import encode, parse, replace_payload  # noqa: E402

BASE = 0x60021020
STOCK = ROOT / "firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN"
STOCK_SHA = "8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d"

PATCH_DIR = ROOT / "patches/shutter_sd/om-3"
WORK = ROOT / "generated/om3-shutter-sd-work"
AS = ROOT / "toolchains/mn103-gas-ld-build/gas/.libs/as-new.exe"
LD = ROOT / "toolchains/mn103-gas-ld-build/ld/.libs/ld-new.exe"

# Caduceus v0.26.2 sd_load: call nm_load (7) + bra sd_out (2)
HOOK_ADDR = 0x60A8F1D1
HOOK_OLD = bytes.fromhex("dd2fa64b00f024ca0a")
SS_CHAIN = 0x603244B0
SS_BIN_MAX_END = 0x60324D00  # PCM starts here
PCM_BASE = 0x60324D00
PCM_LIMIT = 0x60357000

# Shutter menu caves (multibody)
MENU = {
    0x6031FA00: "ss_option_count",
    0x6031FA1B: "ss_option_value",
    0x6031FA43: "ss_option_blocked",
    0x6031FA67: "ss_config_read",
    0x6031FA9F: "ss_config_write",
}

BANK1_END_STUB = 0x60045E82  # fc cc + u32 end

# Embedded slot arenas in the resident/v0.22 layout (cleared when moving to SD).
SLOT_ARENAS = (
    (0x60820000, 29352),   # slot 1
    (0x603244B0, 86444),   # slot 2 — also ss_sd inject window (first SS_BIN_MAX_END-SS_CHAIN)
    (0x617E4800, 101652),  # slot 3
)

# Keep resident section ends; never shrink these when raising s1 for PCM.
KEEP_SECTION_ENDS = {
    0x60045EC4: 0x608272B0,  # cover former slot1 window / match resident
    0x60045EBC: 0x617FD520,  # cover former slot3 window / match resident
    0x60045E9C: 0x60F59800,  # Caduceus v0.26.2 section-6
}

DESC_ADDR = 0x603220A0
RANGE_COUNT = 0x60322050
SELECTED_SLOT = 0x60322000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_msys_path() -> None:
    msys = Path(r"C:\msys64\usr\bin")
    if msys.is_dir():
        os.environ["PATH"] = str(msys) + os.pathsep + os.environ.get("PATH", "")


def extract_text(elf: bytes) -> tuple[int, bytes]:
    assert elf[:4] == b"\x7fELF"
    e_shoff = struct.unpack_from("<I", elf, 32)[0]
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", elf, 46)
    shstr = e_shoff + e_shstrndx * e_shentsize
    str_off = struct.unpack_from("<I", elf, shstr + 16)[0]
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        name_off, _t, _f, addr, off, size = struct.unpack_from("<IIIIII", elf, o)
        name = elf[str_off + name_off : str_off + name_off + 32].split(b"\0", 1)[0]
        if name == b".text" and size:
            return addr, elf[off : off + size]
    raise SystemExit("no .text in ss_sd.elf")


def parse_map_symbols(map_text: str) -> dict[str, int]:
    syms: dict[str, int] = {}
    for line in map_text.splitlines():
        line = line.strip()
        if not line.startswith("0x"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            addr = int(parts[0], 16)
        except ValueError:
            continue
        name = parts[-1]
        if name.startswith("0x") or name in {"=", "*"}:
            continue
        if name.startswith("ss_") or name in MENU.values():
            syms[name] = addr
    return syms


def build_ss() -> tuple[bytes, dict[str, int]]:
    ensure_msys_path()
    WORK.mkdir(parents=True, exist_ok=True)
    obj = WORK / "ss_sd.o"
    elf = WORK / "ss_sd.elf"
    mp = WORK / "ss_sd.map"
    bin_path = WORK / "ss_sd.bin"
    cmd_as = [str(AS), "-o", str(obj), str(PATCH_DIR / "ss_sd.s")]
    cmd_ld = [str(LD), "-T", str(PATCH_DIR / "ss_sd.ld"), "-Map", str(mp), "-o", str(elf), str(obj)]
    for cmd in (cmd_as, cmd_ld):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"build failed: {cmd}\n{proc.stderr or proc.stdout}")
    addr, blob = extract_text(elf.read_bytes())
    if addr != SS_CHAIN:
        raise SystemExit(f"unexpected link address {hex(addr)}")
    if addr + len(blob) > SS_BIN_MAX_END:
        raise SystemExit(f"ss_sd.bin too large: ends {hex(addr + len(blob))}")
    bin_path.write_bytes(blob)
    syms = parse_map_symbols(mp.read_text(encoding="utf-8", errors="replace"))
    for need in ("ss_chain", "ss_option_count", "ss_option_value", "ss_option_blocked", "ss_config_read", "ss_config_write"):
        if need not in syms:
            raise SystemExit(f"missing symbol {need} in map")
    return blob, syms


def encode_jmp(insn_addr: int, target: int) -> bytes:
    """MN103 JMP (d32,PC): DC + (target - insn_addr) as signed i32."""
    rel = (target - insn_addr) & 0xFFFFFFFF
    return b"\xdc" + struct.pack("<I", rel)


def ensure_section1_end(image: bytearray, needed_exclusive: int) -> dict:
    off = 0x60045E84 - BASE
    cur = struct.unpack_from("<I", image, off)[0]
    aligned = (needed_exclusive + 0x7FF) & ~0x7FF
    if cur >= aligned:
        return {"label": "section1_end", "action": "keep", "end": hex(cur)}
    struct.pack_into("<I", image, off, aligned)
    return {"label": "section1_end", "action": "extend", "from": hex(cur), "to": hex(aligned)}


def ensure_bank1_end(image: bytearray, needed_exclusive: int) -> dict:
    off = BANK1_END_STUB - BASE
    stub = bytes(image[off : off + 6])
    if stub[:2] != b"\xfc\xcc":
        return {"label": "bank1_end", "action": "skip", "bytes": stub.hex()}
    cur = struct.unpack_from("<I", image, off + 2)[0]
    if cur >= needed_exclusive:
        return {"label": "bank1_end", "action": "keep", "end": hex(cur)}
    image[off : off + 6] = b"\xfc\xcc" + struct.pack("<I", needed_exclusive)
    return {"label": "bank1_end", "action": "extend", "from": hex(cur), "to": hex(needed_exclusive)}


def clear_embedded_slots(image: bytearray) -> list[dict]:
    """Remove resident PCM so ss_sd / pcm_base own the windows; SD loads WAVs later."""
    rows: list[dict] = []
    for va, size in SLOT_ARENAS:
        o = va - BASE
        image[o : o + size] = b"\xFF" * size
        rows.append({"label": "clear_slot_arena", "address": hex(va), "bytes": size, "action": "ff"})
    return rows


def sanitize_descriptors_off(image: bytearray) -> dict:
    """Safe cold state: no playable lengths until ss_load_slot arms desc0."""
    struct.pack_into("<I", image, SELECTED_SLOT - BASE, 0)
    struct.pack_into("<I", image, RANGE_COUNT - BASE, 0)
    # Zero three descriptor pairs (addr,len)×2 each → 12 u32 from DESC_ADDR
    for i in range(12):
        struct.pack_into("<I", image, DESC_ADDR - BASE + 4 * i, 0)
    return {"label": "sanitize_descriptors", "action": "off", "address": hex(DESC_ADDR)}


def preserve_resident_section_ends(image: bytearray) -> list[dict]:
    rows: list[dict] = []
    for imm_va, want in KEEP_SECTION_ENDS.items():
        off = imm_va - BASE
        cur = struct.unpack_from("<I", image, off)[0]
        if cur == want:
            rows.append({"label": "section_end", "address": hex(imm_va), "action": "keep", "end": hex(cur)})
            continue
        # Never shrink Caduceus s6 or resident-proven slot covers.
        keep = max(cur, want)
        struct.pack_into("<I", image, off, keep)
        rows.append(
            {
                "label": "section_end",
                "address": hex(imm_va),
                "action": "set",
                "from": hex(cur),
                "to": hex(keep),
            }
        )
    return rows


def apply_patch(image: bytearray, blob: bytes, syms: dict[str, int]) -> list[dict]:
    rows: list[dict] = []
    rows.extend(clear_embedded_slots(image))
    rows.append(sanitize_descriptors_off(image))

    # 1) inject code+state into former slot-2 head (may have been RIFF)
    off = SS_CHAIN - BASE
    image[off : off + len(blob)] = blob
    rows.append({"label": "inject_ss_sd", "address": hex(SS_CHAIN), "bytes": len(blob), "action": "wrote"})

    # Clear PCM window to zeros (silent until SD load). Overlaps tail of former slot-2.
    pcm_off = PCM_BASE - BASE
    pcm_len = PCM_LIMIT - PCM_BASE
    image[pcm_off : pcm_off + pcm_len] = b"\x00" * pcm_len
    rows.append({"label": "clear_pcm", "address": hex(PCM_BASE), "bytes": pcm_len, "action": "zero"})

    # 2) hook sd_load (resident still has stock Caduceus call)
    hoff = HOOK_ADDR - BASE
    have = bytes(image[hoff : hoff + len(HOOK_OLD)])
    already = encode_jmp(HOOK_ADDR, SS_CHAIN) + bytes([0xCB, 0xCB, 0xCB, 0xCB])
    if have not in (HOOK_OLD, already):
        raise SystemExit(f"hook site mismatch at {hex(HOOK_ADDR)}: {have.hex()} want {HOOK_OLD.hex()}")
    image[hoff : hoff + 9] = already
    rows.append({"label": "hook_sd_load", "address": hex(HOOK_ADDR), "action": "jmp_ss_chain", "to": hex(SS_CHAIN)})

    # 3) menu wrappers — 5-byte JMP at cave entries only (keep rest of multibody / controls)
    for cave, name in MENU.items():
        tgt = syms[name]
        j = encode_jmp(cave, tgt)
        o = cave - BASE
        image[o : o + 5] = j
        rows.append({"label": f"menu_{name}", "address": hex(cave), "to": hex(tgt), "action": "jmp"})

    rows.append(ensure_section1_end(image, PCM_LIMIT))
    rows.append(ensure_bank1_end(image, PCM_LIMIT))
    rows.extend(preserve_resident_section_ends(image))
    return rows


def stage_sd_tree(
    stage: Path,
    container: bytes,
    stock: bytes,
    om3mod_src: Path | None,
    wavs: list[Path],
) -> None:
    for sub in ("DCOLYMP", "OM3MOD", "restore"):
        (stage / sub).mkdir(parents=True, exist_ok=True)
    (stage / "DCOLYMP" / "E1479999.BIN").write_bytes(container)
    (stage / "restore" / "E1479999.BIN").write_bytes(stock)
    if om3mod_src and om3mod_src.is_dir():
        for p in om3mod_src.iterdir():
            if p.is_file():
                (stage / "OM3MOD" / p.name).write_bytes(p.read_bytes())
    # Example / user WAVs as SHUT01..
    for i, wav in enumerate(wavs[:99], start=1):
        dest = stage / "OM3MOD" / f"SHUT{i:02d}.WAV"
        dest.write_bytes(wav.read_bytes())
    # Default selection: slot 1 if this tree has any SHUT wav, else Off.
    staged_wavs = sorted((stage / "OM3MOD").glob("SHUT*.WAV"))
    selected = 1 if staged_wavs else 0
    ver = 1
    check = (selected ^ 0x9BDF) & 0xFFFF
    shutsel = b"OM3S" + struct.pack("<HHH", ver, selected, check) + b"\x00\x00"
    (stage / "OM3MOD" / "SHUTSEL.BIN").write_bytes(shutsel)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, help="merged main.decoded.bin (Caduceus+shutter)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--stock", type=Path, default=STOCK)
    ap.add_argument("--write-container", action="store_true")
    ap.add_argument("--stage-sd", type=Path)
    ap.add_argument("--om3mod", type=Path, help="copy Caduceus OM3MOD files from here")
    ap.add_argument("--wav", type=Path, action="append", default=[], help="WAV files → SHUT01.. (repeatable)")
    ap.add_argument("--rebuild-asm", action="store_true", help="force rebuild ss_sd.s")
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")

    stock = args.stock.read_bytes()
    if sha256(stock) != STOCK_SHA:
        raise SystemExit("stock SHA mismatch")

    bin_path = WORK / "ss_sd.bin"
    map_path = WORK / "ss_sd.map"
    if args.rebuild_asm or not bin_path.is_file() or not map_path.is_file():
        blob, syms = build_ss()
    else:
        blob = bin_path.read_bytes()
        syms = parse_map_symbols(map_path.read_text(encoding="utf-8", errors="replace"))
        for need in MENU.values():
            if need not in syms:
                blob, syms = build_ss()
                break

    if args.main:
        main_bytes = bytearray(args.main.read_bytes())
    else:
        # Build Caduceus+shutter-only via merge tool into a temp path under out parent
        merge_out = args.out.parent / (args.out.name + "-merge-tmp")
        if merge_out.exists():
            raise SystemExit(f"temp merge dir exists: {merge_out}")
        cmd = [
            sys.executable,
            str(ROOT / "tools/om3_caduceus_feature_merge.py"),
            "--features",
            "shutter-sound",
            "--out",
            str(merge_out),
            "--write-container",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(proc.stderr or proc.stdout or "merge failed")
        main_bytes = bytearray((merge_out / "main.decoded.bin").read_bytes())

    applied = apply_patch(main_bytes, blob, syms)
    main_out = bytes(main_bytes)

    args.out.mkdir(parents=True)
    (args.out / "main.decoded.bin").write_bytes(main_out)
    (args.out / "ss_sd.bin").write_bytes(blob)
    report = {
        "applied": applied,
        "symbols": {k: hex(v) for k, v in sorted(syms.items())},
        "hook": hex(HOOK_ADDR),
        "ss_chain": hex(SS_CHAIN),
        "pcm": [hex(PCM_BASE), hex(PCM_LIMIT)],
        "main_sha256": sha256(main_out),
    }

    container = None
    if args.write_container or args.stage_sd:
        blocks = parse(stock)
        container = b"".join(
            b.header + encode(b.payload) + b.trailer
            for b in [replace_payload(blocks[0], main_out), *blocks[1:]]
        )
        (args.out / "OLY_E_147_1100_patched_lab.bin").write_bytes(container)
        report["container_sha256"] = sha256(container)

    if args.stage_sd:
        assert container is not None
        wavs = list(args.wav)
        if not wavs:
            # fall back to known finals if present
            final = ROOT / "generated/om3-shutter-sounds/final"
            if final.is_dir():
                wavs = sorted(final.glob("*.wav"))[:3]
        stage_sd_tree(args.stage_sd, container, stock, args.om3mod, wavs)
        report["stage_sd"] = str(args.stage_sd)
        report["wav_count"] = len(wavs)

    (args.out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "main_sha256": report["main_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
