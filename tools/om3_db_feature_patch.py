#!/usr/bin/env python3
"""Recreate OM-3 db-firmware feature patches offline (no Korean, no camera I/O).

Applies ring-native + wifi-5ghz + shutter-sound sites extracted from the pinned
azqeurio/om-c-firmware 0.3.1 profile onto stock OLY_E_147_1100. Verifies
before/after digests where the upstream profile publishes them. Writes decoded
main + optional re-encoded container for lab use; does not flash a camera.
Physical SD firmup of a later slots-injected build is documented in
docs/boot/om-3/FLASH_WORKFLOW.md.
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
from pathlib import Path

from oly_container import encode, parse, replace_payload, sha256

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN"
STOCK_SHA = "8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d"
PROFILE = ROOT / "third_party/zh-om-c-firmware/extracted/om3_profile_full.json"
SHUTTER_DIR = ROOT / "third_party/zh-om-c-firmware/extracted"
BASE = 0x60021020
FEATURES = ("ring-native", "wifi-5ghz", "shutter-sound")


def b64(data: str) -> bytes:
    return base64.b64decode(data)


def apply_offset_patches(image: bytearray, patches: list[dict], stage: str) -> list[dict]:
    rows = []
    for patch in patches:
        old, new = b64(patch["old"]), b64(patch["new"])
        if len(new) < len(old):
            raise ValueError(f"{stage}: shrinking patch at {patch['offset']}")
        if len(new) > len(old):
            tail = bytes(image[patch["offset"] + len(old) : patch["offset"] + len(new)])
            if set(tail) - {0xFF}:
                raise ValueError(f"{stage}: growth at {patch['offset']} hits non-FF {tail.hex()}")
        cur = bytes(image[patch["offset"] : patch["offset"] + len(old)])
        if cur != old:
            raise ValueError(
                f"{stage}: old mismatch at {patch['offset']} "
                f"(got {cur[:12].hex()} want {old[:12].hex()})"
            )
        image[patch["offset"] : patch["offset"] + len(new)] = new
        rows.append(
            {
                "stage": stage,
                "label": patch.get("label"),
                "offset": patch["offset"],
                "old_len": len(old),
                "new_len": len(new),
            }
        )
    return rows


def apply_address_replace(image: bytearray, address: int, previous: bytes, data: bytes, stage: str) -> dict:
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
        "offset": offset,
        "old_len": len(previous),
        "new_len": len(data),
    }


def feature_map(profile: dict) -> dict:
    return {f["id"]: f for f in profile["features"]}


def apply_ring(image: bytearray, feature: dict) -> list[dict]:
    return apply_offset_patches(image, feature["patches"], "ring-native")


def apply_wifi(image: bytearray, feature: dict) -> list[dict]:
    return apply_offset_patches(image, feature["patches"], "wifi-5ghz")


def apply_shutter(image: bytearray) -> list[dict]:
    rows: list[dict] = []
    multibody = json.loads((SHUTTER_DIR / "assets__shutter__multibody__om3-1.1.json").read_text(encoding="utf-8"))
    remaining = json.loads((SHUTTER_DIR / "assets__shutter__remaining-021__om3-1.1.json").read_text(encoding="utf-8"))
    native = json.loads((SHUTTER_DIR / "assets__shutter__native-commit-v3__om3-1.1.json").read_text(encoding="utf-8"))
    if multibody["source"]["sha256"] != STOCK_SHA or remaining["source_sha256"] != STOCK_SHA:
        raise ValueError("shutter assets pin a different stock image")
    rows.extend(apply_offset_patches(image, multibody["patches"], "shutter-multibody"))
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
    rows.extend(apply_offset_patches(image, remaining.get("additional_patches", []), "shutter-remaining-add"))
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


def rebuild_container(stock: bytes, main: bytes) -> bytes:
    blocks = parse(stock)
    if sha256(blocks[0].payload) != "5e8d376e9111a44ac0352f26030d7c1b17026d42c45f3600cfa02a0e8c5b7d59":
        raise ValueError("stock block0 digest mismatch")
    patched = [replace_payload(blocks[0], main), *blocks[1:]]
    return b"".join(b.header + encode(b.payload) + b.trailer for b in patched)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stock", type=Path, default=STOCK)
    ap.add_argument("--profile", type=Path, default=PROFILE)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--features",
        nargs="+",
        default=list(FEATURES),
        choices=list(FEATURES),
        help="subset of non-Korean OM-3 features",
    )
    ap.add_argument("--write-container", action="store_true", help="also write re-encoded OLY .BIN")
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite existing {args.out}")
    stock = args.stock.read_bytes()
    if sha256(stock) != STOCK_SHA:
        raise SystemExit("stock SHA-256 mismatch")
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    if profile.get("source_sha256") != STOCK_SHA and profile.get("id") != "om3-1.1":
        # profile root uses source_sha256 field on OM-3 entry
        pass
    if profile["source_sha256"] != STOCK_SHA:
        raise SystemExit("profile source_sha256 mismatch")
    feats = feature_map(profile)
    image = bytearray(parse(stock)[0].payload)
    applied: list[dict] = []
    checks: dict = {"stock_sha256": STOCK_SHA, "features": list(args.features)}

    if "ring-native" in args.features:
        applied.extend(apply_ring(image, feats["ring-native"]))
        if args.features == ["ring-native"]:
            container = rebuild_container(stock, bytes(image))
            expect = feats["ring-native"]["expected_sha256"]
            checks["ring_only_container_sha256"] = sha256(container)
            checks["ring_only_expected_sha256"] = expect
            checks["ring_only_match"] = sha256(container) == expect
            if not checks["ring_only_match"]:
                raise SystemExit("ring-only container digest mismatch")

    if "wifi-5ghz" in args.features:
        applied.extend(apply_wifi(image, feats["wifi-5ghz"]))
    if "shutter-sound" in args.features:
        applied.extend(apply_shutter(image))

    main_bytes = bytes(image)
    container = rebuild_container(stock, main_bytes)
    # Round-trip container parse
    again = parse(container)
    if again[0].payload != main_bytes:
        raise SystemExit("container round-trip main mismatch")
    args.out.mkdir(parents=True)
    (args.out / "main.decoded.bin").write_bytes(main_bytes)
    (args.out / "report.json").write_text(
        json.dumps(
            {
                **checks,
                "main_sha256": sha256(main_bytes),
                "container_sha256": sha256(container),
                "runtime_base": hex(BASE),
                "korean_included": False,
                "patch_count": len(applied),
                "patches": applied,
                "note": "Offline reconstruction from upstream 0.3.1 sites; not a physical flash package endorsement.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if args.write_container:
        # Research artifact only; filename avoids implying an SD updater package.
        (args.out / "OLY_E_147_1100_patched_lab.bin").write_bytes(container)
    print(
        json.dumps(
            {
                "out": str(args.out),
                "features": args.features,
                "main_sha256": sha256(main_bytes),
                "container_sha256": sha256(container),
                "patch_count": len(applied),
                "ring_only_match": checks.get("ring_only_match"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
