#!/usr/bin/env python3
"""Make Caduceus v0.26.2 embedded shutter slots resident and playable offline.

Body evidence (2026-11-12):
  descfix copied v0.22 wav_descriptors/ranges but still failed. Slot 1/3
  reboot on select; slot 2 is selectable and silent.

Two byte-level causes, both checked against the body-proven v0.22 pack:

  1. Section-3 end stays at 0x60820000 and section-8 end at 0x617e4800, so the
     RIFF payloads that start on those exact addresses are never loaded.
     v0.22 raises those fc-cc immediates to 0x608272b0 and 0x617fd520.
     The WAV transplant never copied them: the donor feature-pack already had
     the raised ends, so they were not part of the WAV delta.

  2. descfix runtime_menu (0x6031fa00) and runtime_controls (0x6031fe00) are
     the unverified native-commit / menu_error_propagation overlays. The
     body-proven image still has the multibody bodies. Capture hooks, gain
     sites, WAV bytes and the slot-2 descriptor match; this overlay is the
     only shutter-code difference left, and it runs on select/commit/preview.

This script restores those two bodies from v0.22 and raises only the two
section ends. Section 6 stays at the v0.26.2 Caduceus value 0x60f59800.
"""
from __future__ import annotations

import json
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from oly_container import encode, parse, replace_payload, sha256

BASE = 0x60021020
STOCK = ROOT / "firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN"
STOCK_SHA = "8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d"
V022_PKG = (
    ROOT
    / "generated/om3-sd-ready/caduceus-v022-shutter-only-blog-looks/DCOLYMP/E1479999.BIN"
)
DESC_PKG = (
    ROOT
    / "generated/om3-sd-ready/caduceus-v0262-shutter-only-descfix/DCOLYMP/E1479999.BIN"
)
DESC_SHA = "09ddf208458535fc971361f5a19254396d6a4cb18e454d5e572964fd6644a2ac"

# Proven multibody bodies. Spans are exactly the v0.22-vs-descfix cave diffs.
RESTORE_SPANS = (
    (0x6031FA82, 0x6031FA83),
    (0x6031FAAA, 0x6031FAAB),
    (0x6031FAAE, 0x6031FAAF),
    (0x6031FAB7, 0x6031FAB8),
    (0x6031FACC, 0x6031FAF2),
    (0x6031FE52, 0x6031FE53),
    (0x6031FE5B, 0x6031FE7A),
    (0x6031FE88, 0x6031FE89),
    (0x6031FE8C, 0x6031FE8D),
    (0x6031FE94, 0x6031FE95),
    (0x6031FEA1, 0x6031FED3),
)
# fc-cc imm32 operands. Do not touch section 6 (Caduceus sliders, 0x60f59800).
SECTION_ENDS = {
    0x60045E84: 0x60339800,  # s1, already covers slot 2; keep
    0x60045EC4: 0x608272B0,  # s3, cover slot 1
    0x60045EBC: 0x617FD520,  # s8, cover slot 3
    0x60045E9C: 0x60F59800,  # s6, Caduceus v0.26.2, must not shrink
}
NEXT_SECTION = {
    0x60045EC4: 0x60828000,  # s4
    0x60045EBC: 0x61809000,  # s9
}
SLOTS = (
    (1, 0x60820000, 29352, 0x6082002C, 0x608272A8),
    (2, 0x603244B0, 86444, 0x603244DC, 0x6033965C),
    (3, 0x617E4800, 101652, 0x617E482C, 0x617FD514),
)
CHAIN = (
    (0x6031EC6A, 0x6031FA67),
    (0x6031EF1D, 0x6031FA00),
    (0x6031EF58, 0x6031FA1B),
    (0x60F4AC4D, 0x6031FA43),
)
FACADE = {
    0x60E57478: 0x6031FA9F,
    0x60E57480: 0x60F4A814,
    0x60E57490: 0x60F4A91A,
    0x60E57494: 0x60F4AA16,
    0x60E5749C: 0x60F4AB30,
}
EXT_TAILS = (
    (0x6031E920, 0x6031F000),  # ext1, Caduceus
    (0x6081FE00, 0x60820000),  # ext3, immediately before slot 1
    (0x617E45E0, 0x617E4800),  # ext8, immediately before slot 3
    (0x60F49800, 0x60F59800),  # section-6 extension used by v0.26.2
)


def u32(img: bytes, addr: int) -> int:
    return struct.unpack_from("<I", img, addr - BASE)[0]


def dc_target(img: bytes, addr: int) -> int:
    off = addr - BASE
    if img[off] != 0xDC:
        raise SystemExit(f"expected dc at {addr:#x}, got {img[off]:02x}")
    return addr + struct.unpack_from("<i", img, off + 1)[0]


def load_main(path: Path) -> bytes:
    return parse(path.read_bytes())[0].payload


def apply_fix(desc: bytes, good: bytes) -> bytearray:
    image = bytearray(desc)
    for lo, hi in RESTORE_SPANS:
        off = lo - BASE
        if desc[off:hi - BASE] == good[off:hi - BASE]:
            raise SystemExit(f"restore span {lo:#x} already matches v0.22; source moved")
        image[off : hi - BASE] = good[off : hi - BASE]
    for addr, end in SECTION_ENDS.items():
        off = addr - BASE
        if image[off - 2 : off] != b"\xfc\xcc":
            raise SystemExit(f"section end at {addr:#x} is not fc-cc")
        struct.pack_into("<I", image, off, end)
    return image


def check(image: bytes, desc: bytes, good: bytes) -> dict:
    checks: dict = {}
    for addr, end in SECTION_ENDS.items():
        checks[f"end_{addr:08x}"] = hex(u32(image, addr))
        checks[f"end_{addr:08x}_ok"] = u32(image, addr) == end
        nxt = NEXT_SECTION.get(addr)
        if nxt is not None:
            checks[f"end_{addr:08x}_before_next"] = end < nxt
    # Code + every PCM byte is inside its section.
    checks["code_inside_s1"] = 0x603244AC <= u32(image, 0x60045E84)
    for slot, addr, ln, pcm0, pcm1 in SLOTS:
        off = addr - BASE
        riff = image[off : off + 4] == b"RIFF"
        size = struct.unpack_from("<I", image, off + 4)[0] + 8 if riff else None
        checks[f"slot{slot}_riff"] = riff and size == ln
        checks[f"slot{slot}_matches_v022"] = image[off : off + ln] == good[off : off + ln]
        d_addr, d_len = struct.unpack_from("<II", image, 0x603220A0 - BASE + (slot - 1) * 16)
        checks[f"slot{slot}_desc"] = d_addr == addr and d_len == ln
        r0, r1 = struct.unpack_from("<II", image, 0x60322054 - BASE + (slot - 1) * 8)
        checks[f"slot{slot}_range"] = (r0, r1) == (pcm0, pcm1) and (r1 - r0) == (ln - 44)
        if slot == 1:
            loaded = u32(image, 0x60045EC4) >= pcm1
        elif slot == 2:
            loaded = u32(image, 0x60045E84) >= pcm1
        else:
            loaded = u32(image, 0x60045EBC) >= pcm1
        checks[f"slot{slot}_pcm_loaded"] = loaded
    checks["range_count"] = u32(image, 0x60322050) == 3
    for jmp, tgt in CHAIN:
        checks[f"chain_{jmp:08x}"] = dc_target(image, jmp) == tgt
    for addr, expect in FACADE.items():
        checks[f"facade_{addr:08x}"] = u32(image, addr) == expect
    for lo, hi in EXT_TAILS:
        checks[f"caduceus_{lo:08x}_intact"] = image[lo - BASE : hi - BASE] == desc[lo - BASE : hi - BASE]
    # Proven bodies restored; nothing else in the shutter cave moved.
    cave_lo, cave_hi = 0x6031F000 - BASE, 0x603244B0 - BASE
    drifted = []
    i = cave_lo
    while i < cave_hi:
        if image[i] == good[i]:
            i += 1
            continue
        s = i
        while i < cave_hi and image[i] != good[i]:
            i += 1
        drifted.append((BASE + s, BASE + i))
    checks["cave_matches_v022"] = not drifted
    checks["cave_drift"] = [f"{a:#x}..{b:#x}" for a, b in drifted]
    # Capture / gain hook sites stay on the proven bytes.
    for addr, n in ((0x60BC2026, 16), (0x60BC22BB, 16), (0x60BAED63, 16), (0x60ADC465, 16)):
        off = addr - BASE
        checks[f"hook_{addr:08x}"] = image[off : off + n] == good[off : off + n] == desc[off : off + n]
    bools = {k: v for k, v in checks.items() if isinstance(v, bool)}
    failed = [k for k, v in bools.items() if not v]
    return {"passed": not failed, "failed": failed, "checks": checks}


def stage(container: bytes, main: bytes, report: dict, out: Path, stage_sd: Path) -> None:
    if out.exists() or stage_sd.exists():
        raise SystemExit(f"refusing to overwrite {out} or {stage_sd}")
    out.mkdir(parents=True)
    (out / "main.decoded.bin").write_bytes(main)
    (out / "OLY_E_147_1100_patched_lab.bin").write_bytes(container)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    om3mod = ROOT / "generated/om3-sd-ready/caduceus-v0262-shutter-only/OM3MOD"
    for sub in ("DCOLYMP", "OM3MOD", "restore"):
        (stage_sd / sub).mkdir(parents=True)
    (stage_sd / "DCOLYMP" / "E1479999.BIN").write_bytes(container)
    (stage_sd / "restore" / "E1479999.BIN").write_bytes(STOCK.read_bytes())
    for p in om3mod.iterdir():
        if p.is_file():
            shutil.copyfile(p, stage_sd / "OM3MOD" / p.name)
    manifest = {
        "container_sha256": sha256(container),
        "main_sha256": sha256(main),
        "caduceus": "v0.26.2",
        "features": ["shutter-sound", "wav-slots123", "facade-chain", "section-resident"],
        "excluded": ["ring-native", "wifi-5ghz"],
        "body_status": "offline_only_not_body_tested",
        "do_not_treat_as_verified": True,
        "proven_alternative": "generated/om3-sd-ready/caduceus-v022-shutter-only-blog-looks/",
        "fix": "s3/s8 load ends from v0.22; restore proven runtime_menu/runtime_controls",
        "selftest_passed": report["passed"],
    }
    (stage_sd / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (stage_sd / "VERSION.txt").write_text(
        "Caduceus v0.26.2 + shutter/WAV resident fix (NO ring, NO wifi5G)\n"
        f"container={sha256(container)}\n"
        "body=NOT tested. Until a body pass, use caduceus-v022-shutter-only-blog-looks.\n",
        encoding="utf-8",
    )
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    desc_pkg = DESC_PKG.read_bytes()
    if sha256(desc_pkg) != DESC_SHA:
        raise SystemExit("descfix container SHA mismatch")
    stock = STOCK.read_bytes()
    if sha256(stock) != STOCK_SHA:
        raise SystemExit("stock SHA mismatch")
    desc = load_main(DESC_PKG)
    good = load_main(V022_PKG)
    image = apply_fix(desc, good)
    report = check(bytes(image), desc, good)
    if not report["passed"]:
        raise SystemExit("selftest failed:\n" + json.dumps(report, indent=2))
    blocks = parse(desc_pkg)
    container = b"".join(
        b.header + encode(b.payload) + b.trailer
        for b in [replace_payload(blocks[0], bytes(image)), *blocks[1:]]
    )
    again = parse(container)[0].payload
    if again != bytes(image):
        raise SystemExit("container round-trip mismatch")
    out = ROOT / "generated/om3-caduceus-shutter-only-resident"
    stage_sd = ROOT / "generated/om3-sd-ready/caduceus-v0262-shutter-only-resident"
    report["container_sha256"] = sha256(container)
    report["main_sha256"] = sha256(bytes(image))
    stage(container, bytes(image), report, out, stage_sd)
    print(
        json.dumps(
            {
                "passed": True,
                "container_sha256": report["container_sha256"],
                "main_sha256": report["main_sha256"],
                "stage_sd": str(stage_sd),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
