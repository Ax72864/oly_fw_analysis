#!/usr/bin/env python3
"""OM-3 native firmup simulation: SD read → validate → FIRMUP_SRV-class trap.

Offline only. Models filesystem / timers / logs; traps flash-backend writes.
Does not access a camera, write an SD card, or program device flash.

Pipeline (build 1100 main):
  1) SD firmup client  0x6106b87a  — pattern walk via path helper 0x6106be34
  2) After E147????BIN hit — bounded post-hit load (loop-detect, no brick path)
  3) Check_FirmwareUpdate / Execute_FirmwareUpdate log sites — flash backends trapped
  4) FIRMUP_SRV-class service body — same validate site with flash traps; RTOS
     task schedule is not claimed complete (name landmark 0x602ee307)

PEN-F analogue: tools/penf_sd_path_probe.py (full client↔service queues).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from oly_container import sha256
from om3_probe import OM3Probe, BASE, STOCK_MAIN, STOCK_MAIN_SHA, load_stock_main, require
from penf_probe import CALLER, LOGS
from penf_update_probe import synthetic_block

SD_CLIENT = 0x6106B87A
PATH_HELPER = 0x6106BE34
EXECUTE_FW_UPDATE = 0x60D41EA8
# Check_FirmwareUpdate string use @ 0x60d42032 lives inside the same body as Execute
# (mid-function entry faults); landmark only — do not call 0x60d42020 as an entry.
CHECK_FW_STRING = 0x60EF7793
CHECK_FW_XREF = 0x60D42032
FIRMUP_SRV_NAME = 0x602EE307
FIRMUP_SRV_CLASS = EXECUTE_FW_UPDATE  # service-class body until task entry is pinned

# Fixed leaf stubs (return value). Keep flash backends OUT of this set — trap them.
FIXED_RETURNS = {
    0x60023C05: 0,  # timebase wrapper
    0x60023C0D: 0,
    0x6106BDC0: 0,  # early gate → take mount_ok path
    0x6106D821: 0,
    0x6106BBD9: 0,
    0x6106BE04: 1,  # treat as mount success status
    0x6106BDC4: 1,
    0x60023D68: 0,  # firmup log helper (also loop sentinel)
    0x60023F59: 0,
    0x600254CB: 0,
    0x60AE7412: 0,  # UI/log
    0x60AE7469: 0,
    0x60AE769F: 0,
    0x60AE773B: 1,
    0x60AE75CD: 0,
    0x60AE75AF: 0,
    0x6040D06F: 0,
    0x6040D4B7: 0,
    0x6040D51A: 0,
    0x6040D103: 0,
    0x6040D196: 0,
    0x50002A15: 0,
    0x60022EE7: 0,
    0x60AE796B: 0,
    0x60AE794E: 0,
    0x60AE795E: 0,
    0x60031581: 0,  # post-search helper (peer/status)
    0x60031591: 0,  # mid-helper (null-deref if entered raw)
    0x60030899: 0,  # peer ready probe
    0x600772D7: 0,
    0x6106D62E: 0,
    0x6004D171: 0,  # FS open/read family — modeled absent / nop
    0x6004D087: 0,
    0x6106BAE9: 0,
    0x604174C5: 0,
    0x6041803A: 0,
    0x60430F79: 0,
}

# If these are reached, treat as flash-backend / program requests and trap.
FLASH_TRAP = {
    0x60022402,  # erase/program family
    0x60021E3E,
    0x600224C2,
    0x60025B1B,  # near [firmup]Write Progress — may not be callable entry
}

E147_PATTERN = "E147????BIN"
DCOLYMP = "DCOLYMP"
LOOP_SENTINEL = 0x60023D68
POST_HIT_LOOP_LIMIT = 12
POST_HIT_STUB_BUDGET = 80


def _seed_mmio(state: OM3Probe) -> None:
    for base in (0x98E00000, 0x98900000, 0x98100000, 0x98800000):
        try:
            state.ram(f"mmio_{base:x}", base, bytes(0x1000), aliases=False)
        except ValueError:
            pass
    state.ram("firmup_bss", 0x62B00000, bytes(0x20000), aliases=False)
    # Peer/CPU objects for 0x60030899 (reads *(table[cpu])+0x1c).
    state.ram("cpu_index", 0x8050, struct.pack("<I", 0), aliases=False)
    peer = bytearray(0x2000)
    cpu_obj = 0x97F00100
    status = 0x97F00200
    struct.pack_into("<I", peer, 0, cpu_obj)
    struct.pack_into("<I", peer, 4, cpu_obj)
    # Object header + status pointer so mid-helper does not immediately null-deref.
    struct.pack_into("<I", peer, cpu_obj - 0x97F00000, status)
    struct.pack_into("<I", peer, cpu_obj - 0x97F00000 + 0x1C, status)
    peer[status - 0x97F00000] = 1
    peer[status - 0x97F00000 + 1] = 1
    state.ram("peer_page", 0x97F00000, bytes(peer), aliases=False)
    state.ram("fs_out", 0x19103000, bytes(0x200), aliases=False)
    state.ram("fs_file", 0x19105000, bytes(0x8000), aliases=False)


def _read_cstring(state: OM3Probe, addr: int, limit: int = 12) -> str | None:
    try:
        raw = state.read(addr, limit)
    except ValueError:
        return None
    if not all((32 <= b < 127) or b == 0x3F for b in raw):
        return None
    return raw.split(b"\x00")[0].decode("ascii")


def _model_path_helper(state: OM3Probe, package: bytes | None, searches: list) -> str:
    """Model 0x6106be34: pattern walk expects size/hit on match, 0xe00/0xe0c on miss."""
    a2 = state.regs.get("a2", 0) & 0xFFFFFFFF
    nam = None
    try:
        pat = struct.unpack("<I", state.read(a2, 4))[0]
        nam = _read_cstring(state, pat, 11)
    except (ValueError, struct.error):
        nam = None
    if nam is None:
        sp = state.regs.get("sp", 0) & 0xFFFFFFFF
        for off in range(0, 0x60, 4):
            try:
                cand = struct.unpack("<I", state.read(sp + off, 4))[0]
            except ValueError:
                continue
            nam = _read_cstring(state, cand, 11)
            if nam and "BIN" in nam:
                break
    if not nam:
        nam = "?"
    searches.append(nam)
    found = package is not None and nam == E147_PATTERN
    if found:
        n = min(len(package), 0x2000)
        state.write(0x19105000, package[:n])
        a0 = state.regs.get("a0", 0) & 0xFFFFFFFF
        try:
            state.write(a0, struct.pack("<I", n))
        except ValueError:
            pass
        state.return_from_model(n if n else 1)
        return f"path_helper:{nam}:hit:{n}"
    state.return_from_model(0xE00)
    return f"path_helper:{nam}:miss"


def _e147_hit(events: list) -> bool:
    return any(
        isinstance(e, dict) and "E147????BIN:hit" in str(e.get("detail", ""))
        for e in events
    )


def _handle_auto_map(state: OM3Probe, result: dict, events: list, budget: list) -> dict | None:
    """Return a terminal report dict on hard fault; None to continue after auto-map."""
    fault = result.get("fault") or {}
    addr = int(fault.get("address") or 0) & 0xFFFFFFFF
    page = addr & ~0xFFF
    if page < 0x1000:
        return {
            "status": "memory_fault",
            "pc": hex(state.regs["pc"] & 0xFFFFFFFF),
            "fault": fault,
        }
    try:
        state.ram(f"auto_{page:x}", page, bytes(0x1000), aliases=False)
        budget[0] += 1
        events.append({"kind": "auto_map", "page": hex(page)})
        if budget[0] > 200:
            return {
                "status": "auto_map_exhaustion",
                "pc": hex(state.regs["pc"] & 0xFFFFFFFF),
            }
        return None
    except ValueError as exc:
        return {
            "status": "memory_fault",
            "pc": hex(state.regs["pc"] & 0xFFFFFFFF),
            "fault": fault,
            "error": str(exc),
        }


def run_sd_client(image: bytes, package: bytes | None) -> dict:
    """Card search (+ bounded post-hit load). Stops cleanly after E147 hit + loop."""
    state = OM3Probe(image, SD_CLIENT, mask=0xF0, frame=0x98, registers={})
    _seed_mmio(state)
    stops = {CALLER + 7, *FIXED_RETURNS, *FLASH_TRAP, *LOGS, PATH_HELPER}
    searches: list[str] = []
    events: list[dict] = []
    flash_traps: list[dict] = []
    auto_budget = [0]
    post_hit_stubs = 0
    loop_counts: Counter[int] = Counter()
    hit_step = None

    for _ in range(1500):
        result = state.run(stops, limit=100000)
        pc = state.regs["pc"] & 0xFFFFFFFF

        if result["status"] == "memory_fault":
            terminal = _handle_auto_map(state, result, events, auto_budget)
            if terminal is None:
                continue
            terminal.update(
                {
                    "searches": searches,
                    "e147_sought": E147_PATTERN in searches,
                    "e147_hit": _e147_hit(events),
                    "events": events[-60:],
                    "instructions": state.steps,
                    "auto_maps": auto_budget[0],
                }
            )
            return terminal

        if result["status"] != "breakpoint":
            return {
                "status": result.get("status"),
                "pc": hex(pc),
                "fault": result.get("fault"),
                "searches": searches,
                "e147_sought": E147_PATTERN in searches,
                "e147_hit": _e147_hit(events),
                "events": events[-60:],
                "instructions": state.steps,
            }

        if pc == CALLER + 7:
            return {
                "status": "returned",
                "d0": state.regs.get("d0", 0) & 0xFFFFFFFF,
                "searches": searches,
                "e147_sought": E147_PATTERN in searches,
                "e147_hit": _e147_hit(events),
                "dcolymp_seen": any(DCOLYMP in s for s in searches),
                "load_phase": "client_returned",
                "flash_traps": flash_traps,
                "auto_maps": auto_budget[0],
                "events": events[-80:],
                "instructions": state.steps,
                "package_sha256": None
                if package is None
                else hashlib.sha256(package).hexdigest(),
            }

        if pc in LOGS:
            try:
                state.diagnostic()
            except Exception:
                state.return_from_model(0)
            events.append({"kind": "log", "pc": hex(pc)})
            continue

        if pc in FLASH_TRAP:
            row = {
                "pc": hex(pc),
                "d0": state.regs.get("d0", 0) & 0xFFFFFFFF,
                "a0": state.regs.get("a0", 0) & 0xFFFFFFFF,
                "a1": state.regs.get("a1", 0) & 0xFFFFFFFF,
            }
            flash_traps.append(row)
            events.append({"kind": "flash_trap", **row})
            state.return_from_model(0)
            continue

        if pc == PATH_HELPER:
            note = _model_path_helper(state, package, searches)
            events.append({"kind": "fs_model", "detail": note})
            if "E147????BIN:hit" in note:
                hit_step = state.steps
                events.append({"kind": "milestone", "name": "e147_card_hit", "steps": hit_step})
            continue

        if pc in FIXED_RETURNS:
            state.return_from_model(FIXED_RETURNS[pc])
            events.append({"kind": "stub", "pc": hex(pc), "d0": FIXED_RETURNS[pc]})
            sought = E147_PATTERN in searches
            hit = _e147_hit(events)
            if sought:
                post_hit_stubs += 1
                loop_counts[pc] += 1
                # Log helper spins when RTOS service is not co-scheduled (hit or miss).
                if (
                    loop_counts[LOOP_SENTINEL] >= POST_HIT_LOOP_LIMIT
                    or post_hit_stubs >= POST_HIT_STUB_BUDGET
                ):
                    return {
                        "status": "load_ready" if hit else "search_complete",
                        "reason": "post_search_loop_detect"
                        if loop_counts[LOOP_SENTINEL] >= POST_HIT_LOOP_LIMIT
                        else "post_search_stub_budget",
                        "searches": searches,
                        "e147_sought": True,
                        "e147_hit": hit,
                        "dcolymp_seen": any(DCOLYMP in s for s in searches),
                        "load_phase": "ready_for_service" if hit else "no_package",
                        "flash_traps": flash_traps,
                        "auto_maps": auto_budget[0],
                        "post_hit_stubs": post_hit_stubs,
                        "loop_pc_counts": {
                            hex(k): v for k, v in loop_counts.most_common(8)
                        },
                        "events": events[-80:],
                        "instructions": state.steps,
                        "package_sha256": hashlib.sha256(package).hexdigest()
                        if package is not None
                        else None,
                    }
            continue

        state.return_from_model(0)
        events.append({"kind": "unknown_stub", "pc": hex(pc)})
        if E147_PATTERN in searches:
            post_hit_stubs += 1

    return {
        "status": "step_exhaustion",
        "searches": searches,
        "e147_sought": E147_PATTERN in searches,
        "e147_hit": _e147_hit(events),
        "events": events[-40:],
        "instructions": state.steps,
        "auto_maps": auto_budget[0],
    }


def _run_fw_site(image: bytes, package: bytes, target: int, label: str) -> dict:
    """Call into Check/Execute FirmwareUpdate region; trap flash backends."""
    state = OM3Probe(
        image,
        target,
        mask=0xA0,
        frame=0x14,
        registers={"d0": 0, "a0": 0x19204000, "a2": 0x19208000},
    )
    _seed_mmio(state)
    state.ram("pkg_buf", 0x19204000, package + bytes(0x100), aliases=False)
    state.ram("ctx_obj", 0x19208000, bytes(0x800), aliases=False)
    stops = {CALLER + 7, *FIXED_RETURNS, *FLASH_TRAP, *LOGS}
    events: list[dict] = []
    flash_traps: list[dict] = []
    auto_budget = [0]
    nested = 0
    for _ in range(500):
        result = state.run(stops, limit=80000)
        pc = state.regs["pc"] & 0xFFFFFFFF
        if result["status"] == "memory_fault":
            terminal = _handle_auto_map(state, result, events, auto_budget)
            if terminal is None:
                continue
            terminal.update(
                {
                    "label": label,
                    "entry": hex(target),
                    "events": events[-40:],
                    "flash_traps": flash_traps,
                    "instructions": state.steps,
                }
            )
            return terminal
        if result["status"] != "breakpoint":
            return {
                "status": result.get("status"),
                "label": label,
                "entry": hex(target),
                "pc": hex(pc),
                "fault": result.get("fault"),
                "events": events[-40:],
                "flash_traps": flash_traps,
                "instructions": state.steps,
            }
        if pc == CALLER + 7:
            return {
                "status": "returned",
                "label": label,
                "entry": hex(target),
                "d0": state.regs.get("d0", 0) & 0xFFFFFFFF,
                "flash_traps": flash_traps,
                "flash_programmed": False,
                "events": events[-50:],
                "instructions": state.steps,
            }
        if pc in LOGS:
            try:
                state.diagnostic()
            except Exception:
                state.return_from_model(0)
            events.append({"kind": "log", "pc": hex(pc)})
            continue
        if pc in FLASH_TRAP:
            row = {"pc": hex(pc)}
            flash_traps.append(row)
            events.append({"kind": "flash_trap", **row})
            state.return_from_model(0)
            continue
        if pc in FIXED_RETURNS:
            state.return_from_model(FIXED_RETURNS[pc])
            continue
        state.return_from_model(0)
        nested += 1
        events.append({"kind": "nested_stub", "pc": hex(pc)})
        if nested > 120:
            return {
                "status": "nested_stub_budget",
                "label": label,
                "entry": hex(target),
                "flash_traps": flash_traps,
                "flash_programmed": False,
                "events": events[-40:],
                "instructions": state.steps,
            }
    return {
        "status": "step_exhaustion",
        "label": label,
        "entry": hex(target),
        "events": events[-30:],
        "flash_traps": flash_traps,
        "instructions": state.steps,
    }


def run_validate_trap(image: bytes, package: bytes) -> dict:
    row = _run_fw_site(image, package, EXECUTE_FW_UPDATE, "Execute_FirmwareUpdate")
    row["check_firmware_update_string"] = hex(CHECK_FW_STRING)
    row["check_firmware_update_xref"] = hex(CHECK_FW_XREF)
    row["check_note"] = (
        "Check_FirmwareUpdate xref sits in the Execute body; "
        "not invoked as a separate mid-function entry"
    )
    return row


def run_firmup_srv_class(image: bytes, package: bytes) -> dict:
    """FIRMUP_SRV-class path: validate body + flash traps.

    Task entry PC is not yet pinned from the OM-3 name table (string @ 0x602ee307).
    This exercises the same native update body the service eventually reaches,
    with flash backends trapped — analogous to penf_sd_path_probe's service half
    without claiming full RTOS queue delivery.
    """
    body = _run_fw_site(image, package, FIRMUP_SRV_CLASS, "FIRMUP_SRV_class_body")
    body["firmup_srv_name"] = hex(FIRMUP_SRV_NAME)
    body["task_entry_pinned"] = False
    body["limit"] = (
        "Service-class body via Execute_FirmwareUpdate site; "
        "RTOS task entry / client↔service queues not fully reconstructed"
    )
    return body


def _accept_sd(probe: dict, expect_hit: bool) -> bool:
    if expect_hit:
        return bool(probe.get("e147_hit")) and probe.get("status") in (
            "load_ready",
            "returned",
        )
    # Absent package: must seek E147 and must not hit.
    return (
        bool(probe.get("e147_sought"))
        and not bool(probe.get("e147_hit"))
        and probe.get("status") in ("search_complete", "returned", "load_ready")
    )


def _accept_validate(probe: dict) -> bool:
    return probe.get("status") in ("returned", "nested_stub_budget") and not probe.get(
        "flash_programmed", False
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, default=STOCK_MAIN)
    ap.add_argument("--out", type=Path, help="new report directory")
    ap.add_argument(
        "--scenario",
        choices=("absent", "e147", "validate", "srv", "both"),
        default="both",
    )
    args = ap.parse_args(argv)
    image = load_stock_main(args.main)
    package = synthetic_block(kind=0x100, model=0x1470, address=0x403A0000, size=4032)

    probes: dict = {}
    if args.scenario in ("absent", "both"):
        probes["sd_client_absent"] = run_sd_client(image, None)
    if args.scenario in ("e147", "both"):
        probes["sd_client_e147"] = run_sd_client(image, package)
    if args.scenario in ("validate", "both"):
        probes["execute_firmware_update_trap"] = run_validate_trap(image, package)
    if args.scenario in ("srv", "both"):
        probes["firmup_srv_class"] = run_firmup_srv_class(image, package)

    e147 = probes.get("sd_client_e147") or {}
    absent = probes.get("sd_client_absent") or {}
    validate = probes.get("execute_firmware_update_trap") or {}
    srv = probes.get("firmup_srv_class") or {}

    if args.scenario == "absent":
        passed = _accept_sd(absent, expect_hit=False)
    elif args.scenario == "e147":
        passed = _accept_sd(e147, expect_hit=True)
    elif args.scenario == "validate":
        passed = _accept_validate(validate)
    elif args.scenario == "srv":
        passed = _accept_validate(srv)
    else:  # both
        passed = (
            _accept_sd(absent, expect_hit=False)
            and _accept_sd(e147, expect_hit=True)
            and _accept_validate(validate)
            and _accept_validate(srv)
        )

    report = {
        "model": "OM-3",
        "build": "1100",
        "main_sha256": STOCK_MAIN_SHA,
        "purpose": (
            "Native firmup simulation: SD client read/search → validate → "
            "FIRMUP_SRV-class trap; no device I/O"
        ),
        "entries": {
            "sd_client": hex(SD_CLIENT),
            "path_helper": hex(PATH_HELPER),
            "execute_firmware_update": hex(EXECUTE_FW_UPDATE),
            "check_firmware_update_string": hex(CHECK_FW_STRING),
            "check_firmware_update_xref": hex(CHECK_FW_XREF),
            "firmup_srv_name": hex(FIRMUP_SRV_NAME),
            "firmup_srv_class_body": hex(FIRMUP_SRV_CLASS),
            "e147_pattern": E147_PATTERN,
            "dcolymp": DCOLYMP,
        },
        "probes": probes,
        "passed": passed,
        "limits": [
            "Physical OK+power selector is outside this fixture",
            "FIRMUP_SRV RTOS task entry PC is not pinned; class body is used",
            "Client↔service RTOS queues are not fully reconstructed",
            "Flash backends are trapped; no programming occurs",
            "Does not write a camera or SD card",
            "Does not suggest or perform intentional brick / failure flash tests",
        ],
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        require(not args.out.exists(), "Use a new output directory")
        args.out.mkdir(parents=True)
        (args.out / "om3-firmup-sim.json").write_text(text, encoding="utf-8")
    summary = {
        "passed": passed,
        "sd_absent_status": (probes.get("sd_client_absent") or {}).get("status"),
        "sd_absent_sought": (probes.get("sd_client_absent") or {}).get("e147_sought"),
        "sd_absent_hit": (probes.get("sd_client_absent") or {}).get("e147_hit"),
        "sd_e147_status": (probes.get("sd_client_e147") or {}).get("status"),
        "sd_e147_searches": (probes.get("sd_client_e147") or {}).get("searches"),
        "sd_e147_hit": (probes.get("sd_client_e147") or {}).get("e147_hit"),
        "validate_status": (probes.get("execute_firmware_update_trap") or {}).get(
            "status"
        ),
        "srv_status": (probes.get("firmup_srv_class") or {}).get("status"),
        "srv_flash_traps": len(
            (probes.get("firmup_srv_class") or {}).get("flash_traps") or []
        ),
        "out": None if not args.out else str(args.out),
    }
    print(json.dumps(summary, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, AssertionError) as exc:
        raise SystemExit(f"error: {exc}") from exc
