#!/usr/bin/env python3
"""Merge Caduceus OM-3 with verified ring / wifi-5ghz / shutter-sound features.

Default Caduceus release: **v0.26.2** (body-oriented rebuild; shutter-only pack
was previously proven on v0.22).

Pipeline (offline, no camera I/O):
  1. Apply Caduceus release (colour / films / OM3MOD card files)
  2. Optionally wifi-5ghz / relocated ring-native
  3. Apply shutter-sound, skipping facade words Caduceus owns
  4. Chain Caduceus editor miss paths → shutter full entries (correct dc encoding)
  5. Extend section-1 end for shutter caves; WAV via transplant/slots tools

Caduceus v0.23+ routes facade get/cnt/vbi/sel through `sl_*` then `ed_get` /
`pf_cnt` / `pf_vbi` in ext1. Chain the **ext1 miss** (and `sl_sel` miss) sites,
not the `sl_*` entries themselves, so films/sliders keep priority.

MN103 `dc`: target = insn_addr + rel32 (NOT +5).
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "third_party/caduceus-om3/firmware"))

from oly_container import encode, parse, replace_payload, sha256  # noqa: E402

STOCK = ROOT / "firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN"
STOCK_SHA = "8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d"
STOCK_MAIN_SHA = "5e8d376e9111a44ac0352f26030d7c1b17026d42c45f3600cfa02a0e8c5b7d59"
PROFILE = ROOT / "third_party/zh-om-c-firmware/extracted/om3_profile_full.json"
SHUTTER_DIR = ROOT / "third_party/zh-om-c-firmware/extracted"
CADUCEUS = ROOT / "third_party/caduceus-om3"
CADUCEUS_RELEASE = CADUCEUS / "releases" / "v0.26.2"
BASE = 0x60021020

OLD_RING_CAVE = 0x6031E910
# Immediately after shutter slot-2 WAV (RIFF ends 0x6033965c). Must stay inside
# section-1 load end — 0x60388000 was past end 0x60339660 and caused bootloops.
NEW_RING_CAVE = 0x60339660
RING_CAVE_SIZE = 1448
SECTION1_END_GETTER = 0x60045E84  # mov imm32 operand; exclusive load end

# v0.26.2 facade owners (sl_*). Shutter must not overwrite these words.
SKIP_SHUTTER_FACADE = {
    0x60E57480,  # GetValue / sl_get
    0x60E57490,  # count / sl_cnt
    0x60E57494,  # vbi / sl_vbi
    0x60E5749C,  # selectable / sl_sel (was stock-only on v0.22)
}

# Expected Caduceus facade entry points after v0.26.2 apply (sanity markers).
CADUCEUS_FACADE = {
    0x60E57480: 0x60F4A814,  # sl_get
    0x60E57490: 0x60F4A91A,  # sl_cnt
    0x60E57494: 0x60F4AA16,  # sl_vbi
    0x60E5749C: 0x60F4AB30,  # sl_sel
}

# Ext1 / sl_sel miss (after restore) → shutter full entries → stock on non-match.
# Addresses are for Caduceus v0.26.2 (ext1 miss sites shifted +2 vs v0.22).
CHAIN_RETARGETS = (
    (0x6031EC6A, 0x6031FA67, "ed_get_miss->shutter_config_read"),
    (0x6031EF1D, 0x6031FA00, "pf_cnt_miss->shutter_option_count"),
    (0x6031EF58, 0x6031FA1B, "pf_vbi_miss->shutter_option_value"),
    (0x60F4AC4D, 0x6031FA43, "sl_sel_miss->shutter_option_blocked"),
)

# Stock full entries; used only when shutter chain is off.
STOCK_FALLTHROUGH = (
    (0x6031EC6A, 0x60B86DE7, "ed_get_miss->stock_get"),
    (0x6031EF1D, 0x60B86E09, "pf_cnt_miss->stock_cnt"),
    (0x6031EF58, 0x60B87031, "pf_vbi_miss->stock_vbi"),
    (0x60F4AC4D, 0x60B86A01, "sl_sel_miss->stock_sel"),
)


def b64(data: str) -> bytes:
    return base64.b64decode(data)


def apply_offset_patches(
    image: bytearray,
    patches: list[dict],
    stage: str,
    *,
    skip_runtime: set[int] | None = None,
    allow_relocate_cave: bool = False,
) -> list[dict]:
    rows = []
    skip_runtime = skip_runtime or set()
    for patch in patches:
        runtime = BASE + patch["offset"]
        if runtime in skip_runtime:
            rows.append(
                {
                    "stage": stage,
                    "label": patch.get("label"),
                    "runtime": hex(runtime),
                    "action": "skipped_facade_conflict",
                }
            )
            continue
        old, new = b64(patch["old"]), b64(patch["new"])
        if allow_relocate_cave and patch.get("label") == "payload_cave":
            rows.append(
                {
                    "stage": stage,
                    "label": "payload_cave",
                    "action": "deferred_relocate",
                    "old_runtime": hex(runtime),
                    "size": len(new),
                }
            )
            continue
        if len(new) < len(old):
            raise ValueError(f"{stage}: shrinking patch at {runtime:#x}")
        if len(new) > len(old):
            tail = bytes(image[patch["offset"] + len(old) : patch["offset"] + len(new)])
            if set(tail) - {0xFF}:
                raise ValueError(f"{stage}: growth at {runtime:#x} hits non-FF")
        cur = bytes(image[patch["offset"] : patch["offset"] + len(old)])
        if cur != old:
            raise ValueError(
                f"{stage}: old mismatch at {runtime:#x} "
                f"(got {cur[:12].hex()} want {old[:12].hex()})"
            )
        image[patch["offset"] : patch["offset"] + len(new)] = new
        rows.append(
            {
                "stage": stage,
                "label": patch.get("label"),
                "runtime": hex(runtime),
                "old_len": len(old),
                "new_len": len(new),
                "action": "applied",
            }
        )
    return rows


def apply_address_replace(
    image: bytearray, address: int, previous: bytes, data: bytes, stage: str
) -> dict:
    offset = address - BASE
    if offset < 0 or offset + len(data) > len(image):
        raise ValueError(f"{stage}: address {address:#x} out of main")
    if len(data) > len(previous):
        tail = bytes(image[offset + len(previous) : offset + len(data)])
        if set(tail) - {0xFF}:
            raise ValueError(f"{stage}: growth at {address:#x} hits non-FF")
    cur = bytes(image[offset : offset + len(previous)])
    if cur != previous:
        raise ValueError(f"{stage}: previous mismatch at {address:#x}")
    image[offset : offset + len(data)] = data
    return {
        "stage": stage,
        "address": hex(address),
        "old_len": len(previous),
        "new_len": len(data),
        "action": "applied",
    }


def encode_dc_jmp(from_addr: int, to_addr: int) -> bytes:
    """MN103 JMP (d32,PC): opcode DC + rel32, target = from_addr + rel.

    Empirically matches Caduceus `jmp stock_*` (editor.ld full entries) and
    shutter miss fallthroughs. The previous +5 form aimed 5 bytes early and
    bootlooped any facade chain / ring hook retarget.
    """
    rel = to_addr - from_addr
    return bytes([0xDC]) + struct.pack("<i", rel)


def decode_dc_target(image: bytes, addr: int) -> int:
    off = addr - BASE
    if image[off] != 0xDC:
        raise ValueError(f"expected dc at {addr:#x}, got {image[off]:02x}")
    rel = struct.unpack_from("<i", image, off + 1)[0]
    return addr + rel


def section1_end(image: bytes) -> int:
    return struct.unpack_from("<I", image, SECTION1_END_GETTER - BASE)[0]


def ensure_section1_end(image: bytearray, needed_exclusive: int) -> dict:
    """Raise section-1 exclusive load end if the cave/code would sit past it."""
    off = SECTION1_END_GETTER - BASE
    cur = struct.unpack_from("<I", image, off)[0]
    # Match stock/ring 2 KiB alignment habit when extending past the WAV tail.
    aligned = (needed_exclusive + 0x7FF) & ~0x7FF
    if cur >= aligned:
        return {
            "stage": "section1-end",
            "action": "keep",
            "end": hex(cur),
            "needed": hex(needed_exclusive),
        }
    struct.pack_into("<I", image, off, aligned)
    return {
        "stage": "section1-end",
        "action": "extend",
        "from": hex(cur),
        "to": hex(aligned),
        "needed": hex(needed_exclusive),
    }


def relocate_ring_cave(image: bytearray, cave_payload: bytes) -> list[dict]:
    """Place ring cave at NEW_RING_CAVE and rewrite exit dc+rel32 targets."""
    if len(cave_payload) != RING_CAVE_SIZE:
        raise ValueError(f"ring cave size {len(cave_payload)} != {RING_CAVE_SIZE}")
    new_off = NEW_RING_CAVE - BASE
    dest = bytes(image[new_off : new_off + RING_CAVE_SIZE])
    if set(dest) - {0xFF}:
        raise ValueError(f"NEW_RING_CAVE {NEW_RING_CAVE:#x} is not free FF")

    cave = bytearray(cave_payload)
    old_lo, old_hi = OLD_RING_CAVE, OLD_RING_CAVE + RING_CAVE_SIZE
    new_lo, new_hi = NEW_RING_CAVE, NEW_RING_CAVE + RING_CAVE_SIZE
    exit_fixes = []

    # Rewrite real dc exits whose targets lie outside the cave. Intra-cave rels
    # stay PIC. Bytes that merely look like dc+imm32 but decode to non-code
    # addresses are payload/data — rewriting them corrupts the cave (bootloop).
    CODE_LO, CODE_HI = 0x60000000, 0x62000000
    i = 0
    while i < len(cave) - 4:
        if cave[i] == 0xDC:
            rel = struct.unpack_from("<i", cave, i + 1)[0]
            old_insn = OLD_RING_CAVE + i
            old_tgt = old_insn + rel
            external = not (old_lo <= old_tgt < old_hi)
            plausible = CODE_LO <= old_tgt < CODE_HI
            if external and plausible:
                new_insn = NEW_RING_CAVE + i
                new_rel = old_tgt - new_insn
                struct.pack_into("<i", cave, i + 1, new_rel)
                exit_fixes.append(
                    {
                        "cave_offset": hex(i),
                        "old_insn": hex(old_insn),
                        "new_insn": hex(new_insn),
                        "target": hex(old_tgt),
                        "old_rel": rel,
                        "new_rel": new_rel,
                    }
                )
                i += 5
                continue
        i += 1

    image[new_off : new_off + RING_CAVE_SIZE] = cave
    rows = [
        {
            "stage": "ring-relocate",
            "action": "placed_cave",
            "old": hex(OLD_RING_CAVE),
            "new": hex(NEW_RING_CAVE),
            "size": RING_CAVE_SIZE,
            "exit_fixes": exit_fixes,
            "exit_fix_count": len(exit_fixes),
        }
    ]
    rows.append(ensure_section1_end(image, NEW_RING_CAVE + RING_CAVE_SIZE))
    return rows


def apply_ring_relocated(image: bytearray, feature: dict) -> list[dict]:
    rows: list[dict] = []
    cave_payload = None
    for patch in feature["patches"]:
        label = patch.get("label")
        old, new = b64(patch["old"]), b64(patch["new"])
        runtime = BASE + patch["offset"]
        if label == "payload_cave":
            cave_payload = new
            continue
        if label == "loader_patch" or not label:
            # exact apply (loader and any non-hook)
            cur = bytes(image[patch["offset"] : patch["offset"] + len(old)])
            if cur != old:
                raise ValueError(f"ring {label} mismatch at {runtime:#x}")
            image[patch["offset"] : patch["offset"] + len(new)] = new
            rows.append({"stage": "ring-native", "label": label, "runtime": hex(runtime), "action": "applied"})
            continue
        # hooks: rewrite dc target into relocated cave
        if new[0] != 0xDC:
            raise ValueError(f"ring hook {label} at {runtime:#x} is not dc jmp")
        old_rel = struct.unpack_from("<i", new, 1)[0]
        old_tgt = runtime + old_rel
        if not (OLD_RING_CAVE <= old_tgt < OLD_RING_CAVE + RING_CAVE_SIZE):
            raise ValueError(f"ring hook {label} target {old_tgt:#x} not in old cave")
        entry_off = old_tgt - OLD_RING_CAVE
        new_tgt = NEW_RING_CAVE + entry_off
        patched = encode_dc_jmp(runtime, new_tgt) + new[5:]
        if len(patched) != len(new):
            raise ValueError(f"ring hook {label} length drift")
        cur = bytes(image[patch["offset"] : patch["offset"] + len(old)])
        if cur != old:
            raise ValueError(f"ring hook {label} old mismatch at {runtime:#x}")
        image[patch["offset"] : patch["offset"] + len(patched)] = patched
        rows.append(
            {
                "stage": "ring-native",
                "label": label,
                "runtime": hex(runtime),
                "action": "retargeted",
                "old_target": hex(old_tgt),
                "new_target": hex(new_tgt),
                "cave_entry_offset": entry_off,
            }
        )
    if cave_payload is None:
        raise ValueError("ring-native missing payload_cave")
    rows.extend(relocate_ring_cave(image, cave_payload))
    return rows


def apply_shutter(image: bytearray) -> list[dict]:
    rows: list[dict] = []
    multibody = json.loads((SHUTTER_DIR / "assets__shutter__multibody__om3-1.1.json").read_text(encoding="utf-8"))
    remaining = json.loads((SHUTTER_DIR / "assets__shutter__remaining-021__om3-1.1.json").read_text(encoding="utf-8"))
    native = json.loads((SHUTTER_DIR / "assets__shutter__native-commit-v3__om3-1.1.json").read_text(encoding="utf-8"))
    if multibody["source"]["sha256"] != STOCK_SHA or remaining["source_sha256"] != STOCK_SHA:
        raise ValueError("shutter assets pin a different stock image")

    rows.extend(
        apply_offset_patches(
            image,
            multibody["patches"],
            "shutter-multibody",
            skip_runtime=SKIP_SHUTTER_FACADE,
        )
    )
    for frag in remaining.get("fragments", []):
        rows.append(
            apply_address_replace(
                image,
                frag["address"],
                b64(frag["previous_data"]),
                b64(frag["data"]),
                f"shutter-remaining:{frag['name']}",
            )
        )
    rows.extend(
        apply_offset_patches(image, remaining.get("additional_patches", []), "shutter-remaining-add")
    )
    rows.append(
        apply_address_replace(
            image,
            native["controls_address"],
            b64(native["previous_data"]),
            b64(native["data"]),
            "shutter-native-controls",
        )
    )
    rows.append(
        apply_address_replace(
            image,
            native["helper_address"],
            b"\xff" * len(b64(native["helper_data"])),
            b64(native["helper_data"]),
            "shutter-native-helper",
        )
    )
    for frag in native.get("wiring_fragments", []):
        rows.append(
            apply_address_replace(
                image,
                frag["address"],
                b64(frag["previous_data"]),
                b64(frag["data"]),
                f"shutter-wiring:{frag['name']}",
            )
        )
    return rows


def apply_caduceus_chain(image: bytearray) -> list[dict]:
    """Point Caduceus miss paths at shutter full entries (regs/stack already restored)."""
    rows = []
    for jmp_addr, shutter_tgt, label in CHAIN_RETARGETS:
        off = jmp_addr - BASE
        if image[off] != 0xDC:
            raise ValueError(f"chain {label}: no dc at {jmp_addr:#x}")
        old_tgt = decode_dc_target(image, jmp_addr)
        image[off : off + 5] = encode_dc_jmp(jmp_addr, shutter_tgt)
        rows.append(
            {
                "stage": "facade-chain",
                "label": label,
                "jmp": hex(jmp_addr),
                "old_target": hex(old_tgt),
                "new_target": hex(shutter_tgt),
                "action": "retargeted",
            }
        )
    return rows


def verify_stock_fallthrough(image: bytes) -> list[dict]:
    """Ensure Caduceus miss paths still tail-call stock full entries."""
    rows = []
    for jmp_addr, stock_tgt, label in STOCK_FALLTHROUGH:
        tgt = decode_dc_target(image, jmp_addr)
        ok = tgt == stock_tgt
        rows.append(
            {
                "stage": "facade-fallthrough",
                "label": label,
                "jmp": hex(jmp_addr),
                "target": hex(tgt),
                "expected": hex(stock_tgt),
                "action": "ok" if ok else "mismatch",
            }
        )
        if not ok:
            raise ValueError(f"{label}: miss path {tgt:#x} != stock {stock_tgt:#x}")
    return rows


def apply_caduceus_package(stock: bytes, release_dir: Path) -> tuple[bytes, dict]:
    """Use Caduceus patch.apply to build the colour package (includes white frames)."""
    import patch as cad_patch  # type: ignore  # noqa: PLC0415

    meta = json.loads((release_dir / "patch.json").read_text(encoding="utf-8"))
    pkg = cad_patch.apply(stock, meta)
    return pkg, meta


def rebuild_from_package(pkg: bytes, main: bytes) -> bytes:
    blocks = parse(pkg)
    patched = [replace_payload(blocks[0], main), *blocks[1:]]
    return b"".join(b.header + encode(b.payload) + b.trailer for b in patched)


# Shutter menu_payload ends at 0x603244ac; must be inside section-1 before WAV inject.
SHUTTER_CODE_END = 0x603244AC


def verify_markers(image: bytes, features: list[str] | None = None) -> dict:
    """Cheap structural checks that merged features are present."""
    features = features or []
    checks = {}
    end1 = section1_end(image)
    checks["section1_end"] = hex(end1)
    if "wifi-5ghz" in features:
        checks["wifi_site_a"] = image[0x618269FB - BASE : 0x618269FB - BASE + 4].hex()
        checks["wifi_site_a_not_ff"] = set(image[0x618269FB - BASE : 0x618269FB - BASE + 4]) != {0xFF}
    if "ring-native" in features:
        cave_head = bytes(image[NEW_RING_CAVE - BASE : NEW_RING_CAVE - BASE + 8])
        checks["ring_new_cave_not_ff"] = set(cave_head) != {0xFF}
        checks["ring_new_cave_head"] = cave_head.hex()
        checks["ring_cave_inside_section1"] = NEW_RING_CAVE + RING_CAVE_SIZE <= end1
        checks["ring_cave_inside_section1_ok"] = checks["ring_cave_inside_section1"]
    if "shutter-sound" in features:
        checks["shutter_code_inside_section1"] = SHUTTER_CODE_END <= end1
        checks["shutter_code_inside_section1_ok"] = checks["shutter_code_inside_section1"]
        checks["facade_config_write"] = hex(struct.unpack_from("<I", image, 0x60E57478 - BASE)[0])
        checks["facade_option_blocked"] = hex(struct.unpack_from("<I", image, 0x60E5749C - BASE)[0])
        checks["facade_config_write_is_shutter"] = (
            struct.unpack_from("<I", image, 0x60E57478 - BASE)[0] == 0x6031FA9F
        )
        # Blocked facade word stays Caduceus sl_sel; shutter reached via chain.
        checks["facade_blocked_is_caduceus_sl_sel"] = (
            struct.unpack_from("<I", image, 0x60E5749C - BASE)[0] == CADUCEUS_FACADE[0x60E5749C]
        )
        for jmp_addr, shutter_tgt, label in CHAIN_RETARGETS:
            tgt = decode_dc_target(image, jmp_addr)
            checks[f"chain_{label}"] = hex(tgt)
            checks[f"chain_{label}_ok"] = tgt == shutter_tgt
    for facade_addr, expect in CADUCEUS_FACADE.items():
        ptr = struct.unpack_from("<I", image, facade_addr - BASE)[0]
        key = f"facade_{facade_addr:08x}"
        checks[key] = hex(ptr)
        checks[f"{key}_is_caduceus"] = ptr == expect
    checks["facade_getvalue_is_caduceus"] = checks.get(
        f"facade_{0x60E57480:08x}_is_caduceus", False
    )
    # Caduceus ext1 still non-FF (colour code present)
    ext1 = bytes(image[0x6031E920 - BASE : 0x6031E920 - BASE + 16])
    checks["caduceus_ext1_present"] = set(ext1) != {0xFF}
    return checks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stock", type=Path, default=STOCK)
    ap.add_argument("--profile", type=Path, default=PROFILE)
    ap.add_argument("--caduceus-release", type=Path, default=CADUCEUS_RELEASE)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--features",
        nargs="+",
        default=["wifi-5ghz", "ring-native", "shutter-sound"],
        choices=["wifi-5ghz", "ring-native", "shutter-sound"],
    )
    ap.add_argument("--write-container", action="store_true")
    ap.add_argument("--stage-sd", type=Path, help="also write DCOLYMP/OM3MOD/restore tree here")
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite existing {args.out}")

    stock = args.stock.read_bytes()
    if sha256(stock) != STOCK_SHA:
        raise SystemExit("stock SHA-256 mismatch")

    pkg, cad_meta = apply_caduceus_package(stock, args.caduceus_release)
    blocks = parse(pkg)
    if sha256(blocks[0].payload) != cad_meta["main_sha256_after"]:
        raise SystemExit("Caduceus main digest mismatch after apply")
    image = bytearray(blocks[0].payload)
    applied: list[dict] = [
        {
            "stage": "caduceus",
            "version": cad_meta["version"],
            "main_sha256": cad_meta["main_sha256_after"],
            "pkg_sha256": cad_meta["result_sha256"],
            "action": "applied",
        }
    ]

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    feats = {f["id"]: f for f in profile["features"]}

    if "wifi-5ghz" in args.features:
        applied.extend(apply_offset_patches(image, feats["wifi-5ghz"]["patches"], "wifi-5ghz"))
    if "ring-native" in args.features:
        applied.extend(apply_ring_relocated(image, feats["ring-native"]))
    if "shutter-sound" in args.features:
        applied.extend(apply_shutter(image))
        applied.extend(apply_caduceus_chain(image))
        # Without ring loader_patch, stock/Caduceus end stays 0x6031f000 — extend so
        # shutter caves at 0x6031f000+ are actually loaded (WAV transplant may raise further).
        applied.append(ensure_section1_end(image, SHUTTER_CODE_END))

    main_bytes = bytes(image)
    markers = verify_markers(main_bytes, list(args.features))
    require_shutter = "shutter-sound" in args.features
    bad = [k for k, v in markers.items() if k.endswith("_ok") and v is False]
    bad += [k for k, v in markers.items() if k.endswith("_is_caduceus") and v is False]
    if require_shutter:
        bad += [k for k, v in markers.items() if k.endswith("_is_shutter") and v is False]
    else:
        bad = [k for k in bad if not k.endswith("_is_shutter")]
    bad += [k for k, v in markers.items() if k.endswith("_not_ff") and v is False]
    bad += [k for k, v in markers.items() if k.endswith("_present") and v is False]
    if bad:
        raise SystemExit(f"marker checks failed: {bad} full={json.dumps(markers, indent=2)}")

    merged_pkg = rebuild_from_package(pkg, main_bytes)
    again = parse(merged_pkg)
    if again[0].payload != main_bytes:
        raise SystemExit("merged container round-trip main mismatch")

    args.out.mkdir(parents=True)
    (args.out / "main.decoded.bin").write_bytes(main_bytes)
    report = {
        "stock_sha256": STOCK_SHA,
        "caduceus_release": args.caduceus_release.name,
        "caduceus_version": cad_meta["version"],
        "features": list(args.features),
        "ring_cave": (
            {"old": hex(OLD_RING_CAVE), "new": hex(NEW_RING_CAVE), "size": RING_CAVE_SIZE}
            if "ring-native" in args.features
            else None
        ),
        "main_sha256": sha256(main_bytes),
        "container_sha256": sha256(merged_pkg),
        "caduceus_pkg_sha256": cad_meta["result_sha256"],
        "markers": markers,
        "patch_count": len(applied),
        "patches": applied,
        "note": (
            f"Caduceus colour base + features {list(args.features)}. "
            "dc jmp uses insn_addr+rel; Caduceus miss chains to shutter full entries. "
            "WAV slots not yet injected when shutter-sound is selected."
        ),
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.write_container:
        (args.out / "OLY_E_147_1100_caduceus_features_lab.bin").write_bytes(merged_pkg)

    if args.stage_sd:
        if args.stage_sd.exists():
            raise SystemExit(f"refusing to overwrite existing {args.stage_sd}")
        for sub in ("DCOLYMP", "OM3MOD", "restore"):
            (args.stage_sd / sub).mkdir(parents=True)
        (args.stage_sd / "DCOLYMP" / "E1479999.BIN").write_bytes(merged_pkg)
        (args.stage_sd / "restore" / "E1479999.BIN").write_bytes(stock)
        for name in ("GUIDES.BIN", "LABELS.BIN"):
            src = args.caduceus_release / name
            if src.is_file():
                shutil.copyfile(src, args.stage_sd / "OM3MOD" / name)
        (args.stage_sd / "VERSION.txt").write_text(
            f"Caduceus {cad_meta['version']} + features={','.join(args.features)}\n"
            f"main_sha256={sha256(main_bytes)}\n"
            f"container_sha256={sha256(merged_pkg)}\n",
            encoding="utf-8",
        )
        (args.stage_sd / "MANIFEST.json").write_text(
            json.dumps(
                {
                    "container_sha256": sha256(merged_pkg),
                    "main_sha256": sha256(main_bytes),
                    "caduceus": cad_meta["version"],
                    "features": list(args.features),
                    "wav_injected": False,
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
                "features": args.features,
                "main_sha256": sha256(main_bytes),
                "container_sha256": sha256(merged_pkg),
                "patch_count": len(applied),
                "ring_cave": hex(NEW_RING_CAVE) if "ring-native" in args.features else None,
                "stage_sd": str(args.stage_sd) if args.stage_sd else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
