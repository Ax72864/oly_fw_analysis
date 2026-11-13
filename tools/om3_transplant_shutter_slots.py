#!/usr/bin/env python3
"""Transplant shutter WAV slot deltas from a verified slots build onto another main.

Used when CPython 3.12 (required by om3_shutter_slots.py / db.firmware PYZ) is unavailable.
Diffs donor_before → donor_after and applies the changed spans onto --target main.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from oly_container import encode, parse, replace_payload, sha256

BASE = 0x60021020
STOCK = ROOT / "firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN"
STOCK_SHA = "8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d"
SECTION1_END_GETTER = 0x60045E84
# Must match om3_caduceus_feature_merge.NEW_RING_CAVE / RING_CAVE_SIZE.
NEW_RING_CAVE = 0x60339660
RING_CAVE_SIZE = 1448


def bank_end_u32(blob: bytes) -> int | None:
    if len(blob) < 6 or blob[:2] != b"\xfc\xcc":
        return None
    return struct.unpack_from("<I", blob, 2)[0]


def ensure_section1_covers_ring(image: bytearray) -> dict | None:
    """Keep section-1 end high enough for the relocated ring cave after WAV transplant."""
    off = SECTION1_END_GETTER - BASE
    cur = struct.unpack_from("<I", image, off)[0]
    needed = NEW_RING_CAVE + RING_CAVE_SIZE
    aligned = (needed + 0x7FF) & ~0x7FF
    if cur >= aligned:
        return None
    struct.pack_into("<I", image, off, aligned)
    return {"action": "extend_section1_end", "from": hex(cur), "to": hex(aligned)}


def changed_spans(before: bytes, after: bytes, min_gap: int = 16) -> list[tuple[int, int]]:
    if len(before) != len(after):
        raise ValueError("donor before/after length mismatch")
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(before)
    while i < n:
        if before[i] == after[i]:
            i += 1
            continue
        start = i
        while i < n and before[i] != after[i]:
            i += 1
        end = i
        if spans and start - spans[-1][1] <= min_gap:
            spans[-1] = (spans[-1][0], end)
        else:
            spans.append((start, end))
    return spans


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target-main", type=Path, required=True)
    ap.add_argument(
        "--donor-before",
        type=Path,
        default=ROOT / "generated/om3-db-ring-wifi-shutter/main.decoded.bin",
        help="feature-pack main before WAV injection",
    )
    ap.add_argument(
        "--donor-after",
        type=Path,
        default=ROOT / "generated/om3-db-ring-wifi-shutter-slots123-final/main.decoded.bin",
        help="same feature-pack main after WAV injection",
    )
    ap.add_argument("--stock", type=Path, default=STOCK)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--write-container", action="store_true")
    ap.add_argument("--stage-sd", type=Path)
    ap.add_argument("--om3mod", type=Path, help="copy OM3MOD from this tree into --stage-sd")
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")

    before = args.donor_before.read_bytes()
    after = args.donor_after.read_bytes()
    target = bytearray(args.target_main.read_bytes())
    if len(target) != len(after):
        raise SystemExit(f"target length {len(target)} != donor {len(after)}")
    had_ring_cave = set(target[NEW_RING_CAVE - BASE : NEW_RING_CAVE - BASE + 8]) != {0xFF}

    spans = changed_spans(before, after)
    applied = []
    conflicts = []
    for lo, hi in spans:
        # Prefer applying wherever target still matches donor-before (safe transplant).
        # If target already differs (Caduceus/ring relocation), still apply WAV payload
        # when donor-after looks like RIFF/bank data or when before was FF/zero cave.
        tgt_slice = bytes(target[lo:hi])
        before_slice = before[lo:hi]
        after_slice = after[lo:hi]
        if tgt_slice == after_slice:
            applied.append({"offset": lo, "runtime": hex(BASE + lo), "bytes": hi - lo, "action": "already"})
            continue
        # Section-1 end imm32 (and fc-cc bank-end stubs): never shrink a higher end.
        end_imm_lo = SECTION1_END_GETTER - BASE
        end_imm_hi = end_imm_lo + 4
        if lo < end_imm_hi and hi > end_imm_lo:
            cur_end = struct.unpack_from("<I", target, end_imm_lo)[0]
            new_end = struct.unpack_from("<I", after, end_imm_lo)[0]
            keep = max(cur_end, new_end)
            if had_ring_cave:
                keep = max(keep, NEW_RING_CAVE + RING_CAVE_SIZE)
            keep = (keep + 0x7FF) & ~0x7FF
            struct.pack_into("<I", target, end_imm_lo, keep)
            applied.append(
                {
                    "offset": end_imm_lo,
                    "runtime": hex(SECTION1_END_GETTER),
                    "bytes": 4,
                    "action": "section1_end_max",
                    "from_target": hex(cur_end),
                    "from_donor": hex(new_end),
                    "to": hex(keep),
                }
            )
            continue
        if hi - lo == 6 and before_slice[:2] == b"\xfc\xcc" and after_slice[:2] == b"\xfc\xcc":
            cur_end = bank_end_u32(tgt_slice)
            new_end = bank_end_u32(after_slice)
            if cur_end is not None and new_end is not None:
                if cur_end >= new_end:
                    applied.append(
                        {
                            "offset": lo,
                            "runtime": hex(BASE + lo),
                            "bytes": 6,
                            "action": "bank_end_keep",
                            "end": hex(cur_end),
                        }
                    )
                    continue
                target[lo:hi] = after_slice
                applied.append(
                    {
                        "offset": lo,
                        "runtime": hex(BASE + lo),
                        "bytes": 6,
                        "action": "bank_end_extend",
                        "from": hex(cur_end),
                        "to": hex(new_end),
                    }
                )
                continue
        if tgt_slice == before_slice:
            target[lo:hi] = after_slice
            applied.append({"offset": lo, "runtime": hex(BASE + lo), "bytes": hi - lo, "action": "transplant"})
            continue
        # WAV / bank payloads: only force when the target span is still empty FF
        # (Caduceus/ring may have occupied former feature-pack free space).
        if after_slice[:4] == b"RIFF" or before_slice[:2] == b"\xfc\xcc" or set(before_slice) <= {0xFF}:
            if set(tgt_slice) <= {0xFF}:
                target[lo:hi] = after_slice
                applied.append(
                    {
                        "offset": lo,
                        "runtime": hex(BASE + lo),
                        "bytes": hi - lo,
                        "action": "force_payload_ff",
                        "note": "target was FF; wrote donor WAV/bank payload",
                    }
                )
                continue
            conflicts.append(
                {
                    "offset": lo,
                    "runtime": hex(BASE + lo),
                    "bytes": hi - lo,
                    "reason": "WAV/bank span would clobber non-FF target (relocate ring/other cave)",
                    "target_head": tgt_slice[:12].hex(),
                    "after_head": after_slice[:12].hex(),
                }
            )
            continue
        conflicts.append(
            {
                "offset": lo,
                "runtime": hex(BASE + lo),
                "bytes": hi - lo,
                "target_head": tgt_slice[:12].hex(),
                "before_head": before_slice[:12].hex(),
                "after_head": after_slice[:12].hex(),
            }
        )

    if conflicts:
        raise SystemExit("transplant conflicts:\n" + json.dumps(conflicts, indent=2))

    # Only enforce ring-cave residency when the pre-WAV target already carried one.
    if had_ring_cave:
        end_fix = ensure_section1_covers_ring(target)
        if end_fix:
            applied.append(end_fix)

    # Validate RIFF at known slot addresses from donor report if present
    report_path = args.donor_after.parent / "report.json"
    slot_rows = []
    if report_path.is_file():
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        for slot in rep.get("compose_slots") or rep.get("slots") or []:
            assets = slot.get("assets") or [slot]
            primary = assets[0]
            addr = int(primary["address"])
            off = addr - BASE
            # find length via nearby state descriptors if present; else search RIFF size
            if target[off : off + 4] != b"RIFF":
                raise SystemExit(f"slot at {hex(addr)} missing RIFF after transplant")
            wav_len = struct.unpack_from("<I", target, off + 4)[0] + 8
            blob = bytes(target[off : off + wav_len])
            slot_rows.append(
                {
                    "address": hex(addr),
                    "wav_len": wav_len,
                    "sha256": sha256(blob),
                    "riff_ok": True,
                }
            )

    if had_ring_cave:
        cave = bytes(target[NEW_RING_CAVE - BASE : NEW_RING_CAVE - BASE + RING_CAVE_SIZE])
        if set(cave[:8]) <= {0xFF}:
            raise SystemExit(f"ring cave missing at {NEW_RING_CAVE:#x} after transplant")
        end1 = struct.unpack_from("<I", target, SECTION1_END_GETTER - BASE)[0]
        if NEW_RING_CAVE + RING_CAVE_SIZE > end1:
            raise SystemExit(
                f"ring cave {NEW_RING_CAVE:#x}+{RING_CAVE_SIZE:#x} past section-1 end {end1:#x}"
            )

    main_bytes = bytes(target)
    args.out.mkdir(parents=True)
    (args.out / "main.decoded.bin").write_bytes(main_bytes)
    container = None
    if args.write_container or args.stage_sd:
        stock = args.stock.read_bytes()
        if sha256(stock) != STOCK_SHA:
            raise SystemExit("stock SHA mismatch")
        # Prefer rebuilding from an existing Caduceus-based lab container if present next to target
        lab = args.target_main.parent / "OLY_E_147_1100_caduceus_features_lab.bin"
        if lab.is_file():
            pkg = lab.read_bytes()
            blocks = parse(pkg)
            container = b"".join(
                b.header + encode(b.payload) + b.trailer
                for b in [replace_payload(blocks[0], main_bytes), *blocks[1:]]
            )
        else:
            blocks = parse(stock)
            container = b"".join(
                b.header + encode(b.payload) + b.trailer
                for b in [replace_payload(blocks[0], main_bytes), *blocks[1:]]
            )
        (args.out / "OLY_E_147_1100_patched_lab.bin").write_bytes(container)

    summary = {
        "target_main": str(args.target_main),
        "donor_before": str(args.donor_before),
        "donor_after": str(args.donor_after),
        "span_count": len(spans),
        "changed_bytes": sum(hi - lo for lo, hi in spans),
        "applied": applied,
        "slots": slot_rows,
        "main_sha256": sha256(main_bytes),
        "container_sha256": sha256(container) if container else None,
    }
    (args.out / "report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if args.stage_sd:
        if args.stage_sd.exists():
            raise SystemExit(f"refusing to overwrite {args.stage_sd}")
        assert container is not None
        for sub in ("DCOLYMP", "OM3MOD", "restore"):
            (args.stage_sd / sub).mkdir(parents=True)
        (args.stage_sd / "DCOLYMP" / "E1479999.BIN").write_bytes(container)
        (args.stage_sd / "restore" / "E1479999.BIN").write_bytes(args.stock.read_bytes())
        if args.om3mod and args.om3mod.is_dir():
            import shutil

            for p in args.om3mod.iterdir():
                if p.is_file():
                    shutil.copyfile(p, args.stage_sd / "OM3MOD" / p.name)
        (args.stage_sd / "MANIFEST.json").write_text(
            json.dumps(
                {
                    "container_sha256": sha256(container),
                    "main_sha256": sha256(main_bytes),
                    "wav_injected": True,
                    "method": "transplant_from_verified_slots_build",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "out": str(args.out),
                "span_count": len(spans),
                "changed_bytes": summary["changed_bytes"],
                "main_sha256": summary["main_sha256"],
                "container_sha256": summary["container_sha256"],
                "slots": slot_rows,
                "stage_sd": str(args.stage_sd) if args.stage_sd else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
