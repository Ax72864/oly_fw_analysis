#!/usr/bin/env python3
"""Place three OM-3 electronic-shutter WAV slots into a patched main image.

Loads multi_sound / sound_bank_fit from the pinned db.firmware 0.3.1 PYZ
(requires CPython 3.12 — matching the archive bytecode). Offline only.
A slots-injected container was SD-flashed on OM-3 (2026-11-04); see
docs/boot/om-3/FLASH_WORKFLOW.md.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import subprocess
import sys
import types
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_UPSTREAM = ROOT / "third_party/zh-om-c-firmware/tools"
EXE = ROOT / "third_party/zh-om-c-firmware/upstream-releases/db.firmware.0.3.1.exe"
FAKE = ROOT / "third_party/zh-om-c-firmware"
STOCK_SHA = "8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d"
BASE = 0x60021020

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(TOOLS_UPSTREAM))


def ensure_python312() -> None:
    if sys.version_info[:2] == (3, 12):
        return
    cmd = ["py", "-3.12", str(Path(__file__).resolve()), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as wav:
        info = {
            "path": str(path),
            "channels": wav.getnchannels(),
            "sampwidth": wav.getsampwidth(),
            "framerate": wav.getframerate(),
            "nframes": wav.getnframes(),
            "duration_ms": round(1000.0 * wav.getnframes() / wav.getframerate(), 3),
            "comptype": wav.getcomptype(),
        }
    data = path.read_bytes()
    info["bytes"] = len(data)
    info["sha256"] = sha256(data)
    info["ok"] = (
        info["channels"] == 2
        and info["sampwidth"] == 2
        and info["framerate"] == 48000
        and info["comptype"] == "NONE"
        and data[:4] == b"RIFF"
    )
    return info


def load_pyz_modules():
    from pyinstaller_archive import Archive, Pyz

    if not EXE.is_file():
        raise SystemExit(f"missing {EXE}")
    archive = Archive(EXE)
    pyz = Pyz(archive.read("PYZ.pyz"))
    # Materialize assets the modules resolve via Path(__file__).
    for entry in archive.entries:
        rel = str(entry[0]).replace("\\", "/")
        if not rel.startswith("assets/shutter/"):
            continue
        dest = FAKE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = archive.read(entry[0])
        if not dest.exists() or dest.read_bytes() != data:
            dest.write_bytes(data)

    import numpy  # noqa: F401

    loaded: dict[str, types.ModuleType] = {}

    def load(name: str) -> types.ModuleType:
        if name in loaded:
            return loaded[name]
        code = pyz.read(name)
        mod = types.ModuleType(name)
        # Upstream layout: modules sit next to assets/ as repo-root siblings.
        mod.__file__ = str(FAKE / f"{name}.py")
        loaded[name] = mod
        sys.modules[name] = mod
        exec(code, mod.__dict__)
        return mod

    for name in (
        "om1_sound_menu",
        "om1_sound_drive",
        "om1_sound",
        "om1_sound_bank",
        "sound_bank_fit",
        "multi_sound",
    ):
        load(name)
    return loaded


def bank_end_u32(blob: bytes) -> int:
    if len(blob) < 6 or blob[:2] != b"\xfc\xcc":
        raise ValueError(f"not a bank-end stub: {blob.hex()}")
    return struct.unpack_from("<I", blob, 2)[0]


def apply_patches(image: bytearray, patches: list[dict]) -> list[dict]:
    applied: list[dict] = []
    for patch in patches:
        label = str(patch.get("label") or "")
        old = base64.b64decode(patch["old"])
        new = base64.b64decode(patch["new"])
        off = int(patch["offset"])
        cur = bytes(image[off : off + max(len(old), len(new))])
        if cur[: len(new)] == new:
            applied.append({"label": label, "offset": off, "bytes": len(new), "action": "already"})
            continue
        if cur[: len(old)] == old:
            image[off : off + len(new)] = new
            applied.append({"label": label, "offset": off, "bytes": len(new), "action": "exact"})
            continue
        # Empty caves: stock FF, or prior zeroed state block.
        if set(old) <= {0xFF} and (set(cur[: len(old)]) <= {0xFF} or set(cur[: len(old)]) <= {0x00}):
            image[off : off + len(new)] = new
            applied.append({"label": label, "offset": off, "bytes": len(new), "action": "cave"})
            continue
        # Ring already moved bank-1 end; extend further for PCM if needed.
        if label.startswith("shutter_bank_end_") and len(old) == 6 and len(new) == 6 and len(cur) >= 6:
            try:
                cur_end = bank_end_u32(cur[:6])
                new_end = bank_end_u32(new)
            except ValueError as exc:
                raise SystemExit(f"{label} parse failed: {exc}") from exc
            if cur_end >= new_end:
                applied.append(
                    {
                        "label": label,
                        "offset": off,
                        "bytes": 6,
                        "action": "bank_end_keep",
                        "end": hex(cur_end),
                    }
                )
                continue
            image[off : off + 6] = new
            applied.append(
                {
                    "label": label,
                    "offset": off,
                    "bytes": 6,
                    "action": "bank_end_extend",
                    "from": hex(cur_end),
                    "to": hex(new_end),
                }
            )
            continue
        # Option-dependent runtime stubs already present but not byte-identical:
        # force-replace when current was a filled cave (not stock).
        if label in {"runtime_menu", "runtime_controls", "runtime_state"} and set(old) <= {0xFF}:
            image[off : off + len(new)] = new
            applied.append({"label": label, "offset": off, "bytes": len(new), "action": "replace"})
            continue
        raise SystemExit(
            f"patch conflict label={label} offset={off}: "
            f"cur={cur[:12].hex()} old={old[:12].hex()} new={new[:12].hex()}"
        )
    return applied


def validate_slots(image: bytes, report: dict) -> list[dict]:
    rows = []
    state_off = 3149792  # runtime_state from om3 multibody template
    state = image[state_off : state_off + 320]
    range_count = struct.unpack_from("<I", state, 80)[0]
    if range_count != 3:
        raise SystemExit(f"expected 3 PCM ranges in state, got {range_count}")
    slots = report.get("slots") or []
    if len(slots) != 3:
        raise SystemExit(f"expected 3 compose slots, got {len(slots)}")
    for i, slot in enumerate(slots):
        assets = slot["assets"]
        primary = assets[0]
        addr = int(primary["address"])
        expect_sha = primary["sha256"]
        # descriptor pair (slow/fast) at state+160
        for j in range(2):
            d_addr, d_len = struct.unpack_from("<II", state, 160 + i * 16 + j * 8)
            if d_addr != addr:
                raise SystemExit(f"slot{i+1} rate{j} descriptor addr {hex(d_addr)} != {hex(addr)}")
        off = addr - BASE
        # data length from range table (payload after 44-byte WAV header)
        r0, r1 = struct.unpack_from("<II", state, 84 + i * 8)
        payload_len = r1 - r0
        # full WAV bytes = header(44) + payload, but placed blob may be raw PCM+header from compose
        # Read length from descriptor
        _d_addr, wav_len = struct.unpack_from("<II", state, 160 + i * 16)
        blob = image[off : off + wav_len]
        if len(blob) != wav_len:
            raise SystemExit(f"slot{i+1} truncated at {hex(addr)}")
        if blob[:4] != b"RIFF":
            raise SystemExit(f"slot{i+1} missing RIFF at {hex(addr)}")
        got = sha256(blob)
        if got != expect_sha:
            raise SystemExit(f"slot{i+1} sha mismatch: got {got} want {expect_sha}")
        rows.append(
            {
                "slot": i + 1,
                "address": hex(addr),
                "offset": off,
                "wav_len": wav_len,
                "payload_len": payload_len,
                "duration_ms": primary.get("duration_ms"),
                "sample_rate": primary.get("sample_rate"),
                "bank": primary.get("bank"),
                "sha256": got,
                "riff_ok": True,
            }
        )
    return rows


def main() -> None:
    ensure_python312()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, required=True, help="already code-patched OM-3 main.decoded.bin")
    ap.add_argument(
        "--stock",
        type=Path,
        default=ROOT / "firmware_archive/reference/OM-3/1.1/OLY_E_147_1100_0000_0000.BIN",
    )
    ap.add_argument("--slot1", type=Path, required=True)
    ap.add_argument("--slot2", type=Path, required=True)
    ap.add_argument("--slot3", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--speed-enabled", action="store_true", help="create slow/fast pitched pair per slot")
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")

    from oly_container import encode, parse, replace_payload

    slots = [args.slot1, args.slot2, args.slot3]
    checks = [inspect_wav(p) for p in slots]
    bad = [c for c in checks if not c["ok"]]
    if bad:
        raise SystemExit("WAV format check failed: " + json.dumps(bad, ensure_ascii=False, indent=2))

    mods = load_pyz_modules()
    ms = mods["multi_sound"]
    options = {
        "slots": [
            {
                "path": str(p.resolve()),
                "start_ms": 0,
                "end_ms": 0,
                "normalize": True,
                "onset_boost": True,
                "auto_fit": True,
                "speed_enabled": bool(args.speed_enabled),
                "slow_rate": 90,
                "fast_rate": 110,
                "gain": 100,
            }
            for p in slots
        ],
        "burst_hz": 50,
        "burst_policy": "restart",
    }
    profile = {
        "id": "om3-1.1",
        "source_sha256": STOCK_SHA,
        "size": args.stock.stat().st_size,
    }
    _features, patches, report = ms.compose([], profile, ["shutter-sound"], options)

    image = bytearray(args.main.read_bytes())
    applied = apply_patches(image, patches)
    main_bytes = bytes(image)
    slot_rows = validate_slots(main_bytes, report)

    args.out.mkdir(parents=True)
    (args.out / "main.decoded.bin").write_bytes(main_bytes)
    stock = args.stock.read_bytes()
    if sha256(stock) != STOCK_SHA:
        raise SystemExit(f"stock sha mismatch: {sha256(stock)}")
    blocks = parse(stock)
    container = b"".join(
        b.header + encode(b.payload) + b.trailer
        for b in [replace_payload(blocks[0], main_bytes), *blocks[1:]]
    )
    (args.out / "OLY_E_147_1100_patched_lab.bin").write_bytes(container)
    (args.out / "report.json").write_text(
        json.dumps(
            {
                "wav_checks": checks,
                "compose_report": {k: v for k, v in report.items() if k != "slots"},
                "compose_slots": report.get("slots"),
                "applied_patches": applied,
                "validated_slots": slot_rows,
                "main_sha256": sha256(main_bytes),
                "container_sha256": sha256(container),
                "slot_paths": [str(p) for p in slots],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "wav_ok": True,
                "validated_slots": slot_rows,
                "applied": sum(1 for a in applied if a["action"] not in {"already", "bank_end_keep"}),
                "main_sha256": sha256(main_bytes),
                "container_sha256": sha256(container),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
