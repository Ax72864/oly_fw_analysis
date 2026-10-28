#!/usr/bin/env python3
"""Build the OM-3 CSHUT short-sound table patch (decoded main, offline)."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from oly_container import sha256  # noqa: E402
from om3_probe import BASE, STOCK_MAIN, STOCK_MAIN_SHA, load_stock_main  # noqa: E402
from om3_preflash_validate import probe_aud_ikey  # noqa: E402


def require(cond, msg):
    if not cond:
        raise ValueError(msg)


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
    # Native acceptance on patched image
    ikey = probe_aud_ikey(patched)
    expect = spec["acceptance"]["expect_ikey_short"]
    observed = {r["ikey"]: r["observed_d0"] for r in ikey.get("mapped", [])}
    ok = all(observed.get(k) == v for k, v in expect.items()) and bool(ikey.get("passed"))
    acceptance = {
        "passed": ok,
        "expect_ikey_short": expect,
        "observed": {k: observed.get(k) for k in expect},
        "aud_ikey_passed": ikey.get("passed"),
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
