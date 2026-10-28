#!/usr/bin/env python3
"""Bounded OM-3 main-image probe harness.

Loads the pinned OM-3 1100 main payload into the shared MN103 emulator regions
without requiring the PEN-F stock image. This is not a full camera boot: hardware
models stay explicit and unknown MMIO stops the run. Suitable for section-end /
loader smoke checks and as the base class used by om3_code_space_audit.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

from oly_container import sha256
from penf_boot_emulator import HOOK_RETURN
from penf_emulator import ENGINE, Region, ROOT
from penf_probe import BUFFER, CALLER, RESULT, ProbeState

BASE = 0x60021020
STOCK_MAIN = ROOT / "analysis/om3_1100/00_0100_50000020.decoded.bin"
STOCK_MAIN_SHA = "5e8d376e9111a44ac0352f26030d7c1b17026d42c45f3600cfa02a0e8c5b7d59"
END_GETTER = 0x60045e6c


class OM3Probe(ProbeState):
    """Native call fixture whose main region is the supplied OM-3 image."""

    def __init__(self, image, target, mask=0, frame=0, registers=None):
        # Construct regions directly: ProbeState.__init__ would load PEN-F main.
        caller = b"\xdd" + struct.pack("<i", target - CALLER) + bytes((mask, frame)) + b"\xcb"
        self.regions = [
            Region("main", BASE, image, "rx"),
            Region("caller", CALLER, caller, "rx"),
            Region("stack", 0x18010000, bytes(0x10000), "rw", True),
            Region("result", RESULT, bytes(16), "rw", True),
            Region("return_trampoline", HOOK_RETURN, b"\xcb" * 8, "rx"),
            Region("input_package", BUFFER, bytes(128), "rw", True),
        ]
        self.regs = dict(pc=CALLER, sp=0x18018000, psw=0)
        self.regs.update(registers or {})
        self.events = []
        self.steps = 0
        self.cpu = 0


def require(value, message):
    if not value:
        raise ValueError(message)


def load_stock_main(path=STOCK_MAIN):
    data = path.read_bytes()
    require(sha256(data) == STOCK_MAIN_SHA, f"Unexpected OM-3 main at {path}")
    return data


def call(state, target, mask=0, frame=0, **registers):
    state.write(
        CALLER,
        b"\xdd" + struct.pack("<i", target - CALLER) + bytes((mask, frame)) + b"\xcb",
    )
    state.regs = dict(pc=CALLER, sp=0x18018000, psw=0, **registers)


def section_end(image, section_id):
    state = OM3Probe(image, END_GETTER, registers={"d0": section_id})
    result = state.run({CALLER + 7}, limit=100)
    require(
        result["status"] == "breakpoint" and state.regs["pc"] == CALLER + 7,
        "End getter must return natively",
    )
    require(state.regs["sp"] == 0x18018000, "End getter stack")
    return {
        "section_id": section_id,
        "end_exclusive": hex(state.regs["d0"]),
        "status": result["status"],
        "completed_instructions": result.get("completed"),
        "event_kinds": [event.get("kind") for event in state.events],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, default=STOCK_MAIN)
    ap.add_argument("--section-id", type=int, default=1)
    ap.add_argument("--out", type=Path, help="optional new directory for the smoke report")
    args = ap.parse_args(argv)
    require(ENGINE.is_file(), f"MN103 engine missing at {ENGINE}; build tools/build_mn103_emulator.py")
    image = load_stock_main(args.main)
    row = section_end(image, args.section_id)
    report = {
        "model": "OM-3",
        "build": "1100",
        "main_sha256": STOCK_MAIN_SHA,
        "main_bytes": len(image),
        "cpu_base": hex(BASE),
        "engine": str(ENGINE.relative_to(ROOT)),
        "smoke": "section_end_getter",
        "result": row,
        "limits": [
            "Not a full OM-3 startup or ISP/Wi-Fi simulation.",
            "OM3Probe replaces only the main image; peripheral models remain explicit.",
        ],
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        require(not args.out.exists(), "Use a new output directory")
        args.out.mkdir(parents=True)
        (args.out / "om3-probe-smoke.json").write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit(f"error: {exc}")
