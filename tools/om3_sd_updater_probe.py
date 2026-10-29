#!/usr/bin/env python3
"""OM-3 SD updater surface probe (offline + optional MSC read-only).

What this does
  - Freeze firmup landmarks from pinned build 1100 main.
  - Optionally list a camera Storage volume read-only (no create/delete/write).
  - Optionally stage a *host-local* dry install tree under --stage-out from a
    stock container path (never targets a camera drive letter).

What this refuses
  - Flashing, formatting, writing the camera SD, changing camera settings.
  - Staging onto paths that look like the live OM-3 volume (e.g. H:\\).

This is not a port of penf_sd_path_probe's native client/service transaction.
Native OM-3 SD client → FIRMUP_SRV fixtures remain future work.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from oly_container import sha256
from om3_firmup_landmarks import COMMUNITY_SD, collect
from om3_probe import STOCK_MAIN, STOCK_MAIN_SHA, load_stock_main, require

STOCK_CONTAINER_SHA = "8c133084414533159f587bf46bfb4152714c4074312a47c8d8503e33d605696d"
FORBIDDEN_STAGE_NAMES = {"dcolymp", "e1479999.bin"}


def _is_probably_camera_root(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    # Windows drive roots and anything named like the live volume mount.
    if len(resolved.parts) <= 1:
        return True
    # Reject staging directly onto a volume that already looks like the camera card.
    if (resolved / "DCIM").is_dir() and (resolved / "ALBM").is_dir():
        return True
    return False


def scan_msc_root(root: Path) -> dict:
    """Read-only directory probe. Never opens files for write."""
    require(root.exists() and root.is_dir(), f"MSC root missing: {root}")
    entries = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        try:
            st = child.stat()
            entries.append(
                {
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "size": None if child.is_dir() else st.st_size,
                }
            )
        except OSError as exc:
            entries.append({"name": child.name, "error": str(exc)})

    def present(name: str) -> bool:
        return (root / name).exists()

    updater_hits = []
    dcol = root / "DCOLYMP"
    if dcol.is_dir():
        for child in sorted(dcol.iterdir(), key=lambda p: p.name.lower()):
            updater_hits.append(
                {
                    "path": str(child.relative_to(root)).replace("\\", "/"),
                    "size": None if child.is_dir() else child.stat().st_size,
                }
            )

    return {
        "root": str(root),
        "read_only": True,
        "root_entries": entries,
        "has_DCIM": present("DCIM"),
        "has_ALBM": present("ALBM"),
        "has_DCOLYMP": present("DCOLYMP"),
        "has_PRIVATE": present("PRIVATE"),
        "has_MISC": present("MISC"),
        "dcolymp_listing": updater_hits,
        "expected_community_file": COMMUNITY_SD["filename"],
        "community_package_present": any(
            h.get("path", "").upper().endswith(COMMUNITY_SD["filename"])
            for h in updater_hits
        ),
        "interpretation": (
            "Storage MSC shows the photo volume only. Presence of DCOLYMP is "
            "optional; absence is normal for day-to-day use. This scan does not "
            "activate OK+power firmup."
        ),
    }


def stage_host_layout(container: Path, stage_out: Path) -> dict:
    """Copy stock container into host-local DCOLYMP/E1479999.BIN (not camera)."""
    require(container.is_file(), f"Missing container {container}")
    digest = sha256(container.read_bytes())
    require(digest == STOCK_CONTAINER_SHA, "Refusing: container SHA is not pinned OM-3 1100 stock")
    require(not _is_probably_camera_root(stage_out), "Refusing to stage onto a camera/MSC-looking path")
    require(not stage_out.exists(), "Use a new --stage-out directory")
    dest_dir = stage_out / "DCOLYMP"
    dest_dir.mkdir(parents=True)
    dest = dest_dir / COMMUNITY_SD["filename"]
    shutil.copyfile(container, dest)
    return {
        "staged": True,
        "stage_out": str(stage_out),
        "install_relative": f"DCOLYMP/{COMMUNITY_SD['filename']}",
        "bytes": dest.stat().st_size,
        "container_sha256": digest,
        "note": (
            "Host-local dry tree only. Do not copy to the camera unless a human "
            "explicitly authorizes a separate session; this tool never writes the MSC volume."
        ),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, default=STOCK_MAIN)
    ap.add_argument("--out", type=Path, help="new report directory")
    ap.add_argument(
        "--msc-root",
        type=Path,
        help="optional camera Storage volume root for READ-ONLY listing (e.g. H:/)",
    )
    ap.add_argument(
        "--stage-out",
        type=Path,
        help="optional NEW host directory for dry DCOLYMP/E1479999.BIN (never the camera)",
    )
    ap.add_argument(
        "--container",
        type=Path,
        help="stock OLY_E_147_1100 container for --stage-out",
    )
    args = ap.parse_args(argv)

    # Hard refuse accidental flags that would imply device writes.
    for bad in ("--write", "--flash", "--format"):
        if bad in (argv or sys.argv[1:]):
            raise SystemExit(f"Refusing {bad}: this probe is read-only toward the camera")

    image = load_stock_main(args.main)
    landmarks = collect(image)
    msc = scan_msc_root(args.msc_root) if args.msc_root else None
    staged = None
    if args.stage_out:
        require(args.container is not None, "--stage-out requires --container")
        staged = stage_host_layout(args.container, args.stage_out)

    report = {
        "model": "OM-3",
        "build": "1100",
        "main_sha256": STOCK_MAIN_SHA,
        "purpose": "SD updater surface probe (landmarks + optional MSC read-only)",
        "not": [
            "camera flash / firmware install",
            "SD card write or format",
            "native FIRMUP_SRV transaction (see penf_sd_path_probe for PEN-F)",
            "OK+power activation proof",
        ],
        "landmarks": landmarks,
        "msc_read_only": msc,
        "host_stage": staged,
        "next_gap": (
            "Port a bounded OM-3 native SD client→FIRMUP_SRV fixture modeled on "
            "penf_sd_path_probe; keep flash backends trapped."
        ),
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        require(not args.out.exists(), "Use a new output directory")
        args.out.mkdir(parents=True)
        (args.out / "om3-sd-updater-probe.json").write_text(text, encoding="utf-8")
        (args.out / "om3-firmup-landmarks.json").write_text(
            json.dumps(landmarks, indent=2) + "\n", encoding="utf-8"
        )
        if msc:
            (args.out / "om3-msc-readonly.json").write_text(
                json.dumps(msc, indent=2) + "\n", encoding="utf-8"
            )

    summary = {
        "landmarks_ok": bool(landmarks["strings"]["E147_pattern"]["count"]),
        "msc_scanned": msc is not None,
        "msc_has_DCOLYMP": None if msc is None else msc["has_DCOLYMP"],
        "host_staged": bool(staged),
        "out": None if not args.out else str(args.out),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, AssertionError) as exc:
        raise SystemExit(f"error: {exc}") from exc
