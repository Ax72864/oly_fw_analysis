#!/usr/bin/env python3
"""Build the OM-3 lever/function-button default-bit patch (decoded main)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from oly_container import sha256  # noqa: E402
from om3_probe import BASE, STOCK_MAIN, load_stock_main  # noqa: E402
from om3_preflash_validate import (  # noqa: E402
    GET_CHANGE_FUNCTION_BUTTON,
    install_common_fixtures,
    run_with_stubs,
)
from om3_probe import OM3Probe  # noqa: E402


def require(cond, msg):
    if not cond:
        raise ValueError(msg)


def get_change(image, key, settings_value):
    state = OM3Probe(
        image, GET_CHANGE_FUNCTION_BUTTON, mask=0xC0, frame=0x14, registers={"d0": key}
    )
    install_common_fixtures(state, image, settings_value=settings_value)
    # When probing patched image defaults, read the image word unless overridden.
    if settings_value is None:
        # Re-install from image bytes already in main; promote page as-is.
        page = 0x60366E58 & ~0xFF
        off = page - BASE
        state.ram("settings_bank_page", page, image[off : off + 0x100])
    return run_with_stubs(state, limit=20000)


def build(args):
    spec = json.loads((HERE / "patch.json").read_text(encoding="utf-8"))
    require(sha256(args.main.read_bytes()) == spec["stock_main_sha256"], "Wrong stock main")
    image = bytearray(load_stock_main(args.main))
    restore = bytes(image)
    applied = []
    for row in spec["main_ranges"]:
        at = int(row["address"], 16) - BASE
        size = row["bytes"]
        before = bytes(image[at : at + size])
        require(sha256(before) == row["before_sha256"], f"Original bytes differ: {row['name']}")
        after = bytes.fromhex(row["after_hex"])
        require(len(after) == size, f"Bad after length: {row['name']}")
        image[at : at + size] = after
        applied.append(
            {
                "name": row["name"],
                "address": row["address"],
                "before_sha256": row["before_sha256"],
                "after_sha256": sha256(after),
            }
        )
    args.out.mkdir(parents=True, exist_ok=False)
    patched = bytes(image)
    (args.out / "patched-main.bin").write_bytes(patched)
    (args.out / "restore-main.bin").write_bytes(restore)

    # Acceptance: image default word already has bit0; fixture must load from image.
    k11 = get_change(patched, 11, settings_value=1)
    k16 = get_change(patched, 16, settings_value=1)  # bit0 only → key16 still 0
    expect = spec["acceptance"]
    ok = (
        k11.get("status") == "returned"
        and k11.get("d0") == expect["getChangeFunctionButton_key11"]
        and k16.get("status") == "returned"
        and k16.get("d0") == expect["getChangeFunctionButton_key16_default"]
    )
    acceptance = {
        "passed": ok,
        "key11": k11,
        "key16": k16,
        "settings_selectors": spec["settings_selectors"],
    }
    (args.out / "acceptance.json").write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
    report = {
        "model": "OM-3",
        "build": "1100",
        "stock_main_sha256": spec["stock_main_sha256"],
        "patched_main_sha256": sha256(patched),
        "restore_main_sha256": sha256(restore),
        "applied": applied,
        "acceptance": acceptance,
    }
    (args.out / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "acceptance_passed": ok, "patched_sha256": sha256(patched)}, indent=2))
    return 0 if ok else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, default=STOCK_MAIN)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        return build(args)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
