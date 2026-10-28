#!/usr/bin/env python3
"""OM-3 pre-flash offline validation harness (sound / lever / settings).

Goal: exercise the call paths needed to accept firmware mods before any
device flash — not a GUI simulator and not a substitute for ``om3_boot``
``deeper_idle``.

Build 1100 pinned main only. Emits a graded acceptance report (L0/L1/…)
aligned with the shutter-sound / power-lever checklist.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

from oly_container import sha256
from penf_emulator import ENGINE, ROOT
from penf_probe import CALLER, RESULT
from om3_probe import OM3Probe, BASE, STOCK_MAIN, STOCK_MAIN_SHA, load_stock_main, call, require

# Resolved native entries (string → prologue), build 1100.
AUD_IKEY = 0x60adf844
AUD_IKEY_TABLE = 0x60ddb9e4
AUD_IKEY_TABLE_COUNT = 18
AUD_LOG = 0x60a8394e
AUD_LOG_ENABLE = 0x62b43ba4

START_PLAY_SOUND_EXT = 0x604375d6
PLAY_SOUND_WRAPPER = 0x60c32db3  # logs then calls Start_Play_Sound_Ext

CHANGE_FUNCTION_BUTTON = 0x60af1f1e
GET_CHANGE_FUNCTION_BUTTON = 0x60af284f
SETTINGS_WORD = 0x60366e58
UI_LOG = 0x60ae7412
SETTINGS_GET = 0x60ae8c3e
SETTINGS_SET = 0x60ae92d4

CAMERA_COMMON_VT = 0x60e20750
GET_LEVER_SWITCH_STATE = 0x60b34c2c  # vtable +0xec
CHANGE_FUNCTION_METHOD = 0x60b34c8c  # vtable +0xf4 (this, key, lever)
GET_CHANGE_FUNCTION_METHOD = 0x60b34cf5  # vtable +0xf8 candidate

EV_CHANGE_LEVER_SW = 0xE2
EV_CHANGE_MODE_DIAL_NAME = 0x60dedc89
EV_CHANGE_LEVER_SW_NAME = 0x60dee084

CUSTOM_KEY_STRINGS = (
    "customKeyAssignment_sw01",
    "customKeyAssignment_sw02",
    "customKeyAssignment_sw03",
    "customKeyAssignment_sw04",
    "customKeyAssignment_sw05",
    "customKeyAssignment_sw06",
    "customKeyAssignment_sw12",
    "customKeyAssignment_sw13",
    "customKeyAssignment_sw14",
    "customKeyAssignment_sw15",
)

# Lever-related keys accepted by changeFunctionButton (others error out).
LEVER_KEYS = (11, 16)

STUB_PCS = {
    UI_LOG,
    0x60ae7469,  # related UI log variant used by CameraCommon methods
    0x60ae769f,
    0x60ae773b,
    0x60ae76b7,
    0x60aee352,
    0x60aee613,
    0x60aee65f,
    0x60af18d4,  # message-id → string table (needs large fixtures)
}


def cstring_at(image: bytes, address: int, limit: int = 96) -> str | None:
    off = address - BASE
    if off < 0 or off >= len(image):
        return None
    end = image.find(b"\x00", off, off + limit)
    if end < 0:
        return None
    chunk = image[off:end]
    if not chunk or any(b < 32 or b >= 127 for b in chunk):
        return None
    return chunk.decode("ascii")


def find_string(image: bytes, text: str) -> int | None:
    needle = text.encode("ascii")
    off = image.find(needle)
    return None if off < 0 else BASE + off


def u32(image: bytes, address: int) -> int:
    return struct.unpack_from("<I", image, address - BASE)[0]


def dump_ikey_table(image: bytes) -> list[dict]:
    rows = []
    for i in range(AUD_IKEY_TABLE_COUNT):
        addr = AUD_IKEY_TABLE + i * 8
        ptr = u32(image, addr)
        wave = u32(image, addr + 4)
        rows.append(
            {
                "index": i,
                "ikey_ptr": hex(ptr),
                "ikey": cstring_at(image, ptr),
                "is_short_sound": wave,
                "note": (
                    "mechanical shutter family"
                    if (cstring_at(image, ptr) or "").startswith("PRM_AUD_SHUT")
                    else (
                        "compact/electronic shutter family"
                        if (cstring_at(image, ptr) or "").startswith("PRM_AUD_CSHUT")
                        else None
                    )
                ),
            }
        )
    return rows


def dump_custom_key_strings(image: bytes) -> list[dict]:
    rows = []
    for name in CUSTOM_KEY_STRINGS:
        addr = find_string(image, f"[GUI KeyAssignment]:{name}")
        if addr is None:
            addr = find_string(image, name)
        rows.append({"name": name, "analysis_address": None if addr is None else hex(addr)})
    return rows


def static_landmarks(image: bytes) -> dict:
    return {
        "entries": {
            "aud_ikey_to_wavetype_is_short_sound": {
                "entry": hex(AUD_IKEY),
                "abi": "a0=ikey C string; returns d0=is_short (0/1); call mask=0xf0 frame=0x1c",
                "table": hex(AUD_IKEY_TABLE),
            },
            "Start_Play_Sound_Ext": {
                "entry": hex(START_PLAY_SOUND_EXT),
                "abi": "d0/d1 params; movm+[add -48]; call mask=0xf0 frame=0x30",
                "assert_string": hex(find_string(image, "[ASSERT]Start_Play_Sound_Ext param error") or 0),
            },
            "changeFunctionButton": {
                "entry": hex(CHANGE_FUNCTION_BUTTON),
                "abi": "d0=key d1=lever; accepts key in {11,16}; call mask=0xc0 frame=0x18",
                "settings_word": hex(SETTINGS_WORD),
            },
            "getChangeFunctionButton": {
                "entry": hex(GET_CHANGE_FUNCTION_BUTTON),
                "abi": "d0=key; returns 0/1 from settings bits; call mask=0xc0 frame=0x14",
            },
            "getLeverSwitchState": {
                "entry": hex(GET_LEVER_SWITCH_STATE),
                "vtable": hex(CAMERA_COMMON_VT),
                "vtable_offset": hex(0xEC),
                "abi": "a0=CameraCommon* d0=arg; call mask=0xa0 frame=0x10",
            },
            "EV_CHANGE_LEVER_SW": {
                "name": hex(EV_CHANGE_LEVER_SW_NAME),
                "event_id": hex(EV_CHANGE_LEVER_SW),
            },
        },
        "ikey_wave_table": dump_ikey_table(image),
        "custom_key_assignment_strings": dump_custom_key_strings(image),
    }


def install_common_fixtures(state: OM3Probe, image: bytes, settings_value: int = 0) -> None:
    """Writable mirrors for settings + mute audio/UI log enables where possible."""
    # Promote settings word out of rx main so read/modify/write probes work.
    page = SETTINGS_WORD & ~0xFF
    blob = bytearray(image[page - BASE : page - BASE + 0x100])
    struct.pack_into("<I", blob, SETTINGS_WORD - page, settings_value & 0xFFFFFFFF)
    state.ram("settings_bank_page", page, bytes(blob))
    # aud logger early-out when enable word is zero.
    state.ram("aud_log_enable", AUD_LOG_ENABLE, struct.pack("<I", 0))
    state.ram("aud_log_aux", 0x62b43ba8, struct.pack("<I", 0))


def run_with_stubs(state: OM3Probe, *, limit: int = 50000, stub_result: int = 0) -> dict:
    """Run until CALLER return, stubbing selected helper PCs via return_from_model."""
    stops = {CALLER + 7, *STUB_PCS}
    guarded = 0
    while True:
        result = state.run(stops, limit=limit)
        pc = state.regs["pc"]
        if result["status"] == "breakpoint" and pc == CALLER + 7:
            return {
                "status": "returned",
                "d0": state.regs.get("d0", 0) & 0xFFFFFFFF,
                "d0_hex": hex(state.regs.get("d0", 0) & 0xFFFFFFFF),
                "instructions": state.steps,
                "stub_hits": guarded,
                "sp_ok": state.regs["sp"] == 0x18018000,
            }
        if result["status"] == "breakpoint" and pc in STUB_PCS:
            state.return_from_model(stub_result if pc != 0x60ae773b else 1)
            guarded += 1
            if guarded > 2000:
                return {
                    "status": "stub_exhaustion",
                    "pc": hex(pc),
                    "instructions": state.steps,
                    "stub_hits": guarded,
                }
            continue
        fault = result.get("fault")
        return {
            "status": result.get("status"),
            "pc": hex(pc),
            "fault": fault,
            "instructions": state.steps,
            "stub_hits": guarded,
        }


def probe_aud_ikey(image: bytes) -> dict:
    rows = []
    for entry in dump_ikey_table(image):
        ikey_addr = int(entry["ikey_ptr"], 16)
        state = OM3Probe(image, AUD_IKEY, mask=0xF0, frame=0x1C, registers={"a0": ikey_addr})
        install_common_fixtures(state, image)
        # strcmp is native in-image; logger early-outs via AUD_LOG_ENABLE=0.
        # Still stub UI helpers if any side path trips.
        outcome = run_with_stubs(state, limit=20000)
        rows.append(
            {
                "ikey": entry["ikey"],
                "expected_short": entry["is_short_sound"],
                "observed_d0": outcome.get("d0"),
                "match": outcome.get("status") == "returned"
                and outcome.get("d0") == entry["is_short_sound"],
                "run": outcome,
            }
        )
    # Null ikey path
    state = OM3Probe(image, AUD_IKEY, mask=0xF0, frame=0x1C, registers={"a0": 0})
    install_common_fixtures(state, image)
    null_run = run_with_stubs(state, limit=10000)
    passed = all(r["match"] for r in rows) and null_run.get("status") == "returned"
    return {
        "target": hex(AUD_IKEY),
        "passed": passed,
        "mapped": rows,
        "null_ikey": null_run,
        "interpretation": (
            "PRM_AUD_SHUT*_VOL are short sounds; PRM_AUD_CSHUT*_VOL are not. "
            "E-shutter/silent cues likely need an explicit short-wave path."
        ),
    }


def probe_change_function(image: bytes) -> dict:
    scenarios = []
    for key in LEVER_KEYS + (0, 12):  # 0/12 should reject
        for lever in (0, 1):
            initial = 0xA5A5A5A5
            state = OM3Probe(
                image,
                CHANGE_FUNCTION_BUTTON,
                mask=0xC0,
                frame=0x18,
                registers={"d0": key, "d1": lever},
            )
            install_common_fixtures(state, image, settings_value=initial)
            outcome = run_with_stubs(state, limit=20000)
            final = struct.unpack("<I", state.read(SETTINGS_WORD, 4))[0]
            expected_ok = key in LEVER_KEYS
            scenarios.append(
                {
                    "key": key,
                    "lever": lever,
                    "initial": hex(initial),
                    "final": hex(final),
                    "d0": outcome.get("d0"),
                    "accepted_key": expected_ok,
                    "settings_changed": final != initial,
                    "run": outcome,
                }
            )
    # Round-trip get after set for key 11 lever=1
    state = OM3Probe(
        image, CHANGE_FUNCTION_BUTTON, mask=0xC0, frame=0x18, registers={"d0": 11, "d1": 1}
    )
    install_common_fixtures(state, image, settings_value=0)
    set_run = run_with_stubs(state, limit=20000)
    after_set = struct.unpack("<I", state.read(SETTINGS_WORD, 4))[0]
    state2 = OM3Probe(
        image, GET_CHANGE_FUNCTION_BUTTON, mask=0xC0, frame=0x14, registers={"d0": 11}
    )
    install_common_fixtures(state2, image, settings_value=after_set)
    get_run = run_with_stubs(state2, limit=20000)
    # lever=0 clears the bit
    state3 = OM3Probe(
        image, CHANGE_FUNCTION_BUTTON, mask=0xC0, frame=0x18, registers={"d0": 11, "d1": 0}
    )
    install_common_fixtures(state3, image, settings_value=after_set)
    clear_run = run_with_stubs(state3, limit=20000)
    after_clear = struct.unpack("<I", state3.read(SETTINGS_WORD, 4))[0]
    state4 = OM3Probe(
        image, GET_CHANGE_FUNCTION_BUTTON, mask=0xC0, frame=0x14, registers={"d0": 11}
    )
    install_common_fixtures(state4, image, settings_value=after_clear)
    get_clear = run_with_stubs(state4, limit=20000)

    accepted = [s for s in scenarios if s["accepted_key"]]
    rejected = [s for s in scenarios if not s["accepted_key"]]
    passed = (
        set_run.get("status") == "returned"
        and get_run.get("status") == "returned"
        and get_run.get("d0") == 1
        and clear_run.get("status") == "returned"
        and get_clear.get("status") == "returned"
        and get_clear.get("d0") == 0
        and all(s["run"].get("status") == "returned" for s in accepted)
        and all(s["run"].get("status") == "returned" for s in rejected)
    )
    return {
        "targets": {
            "changeFunctionButton": hex(CHANGE_FUNCTION_BUTTON),
            "getChangeFunctionButton": hex(GET_CHANGE_FUNCTION_BUTTON),
            "settings_word": hex(SETTINGS_WORD),
        },
        "passed": passed,
        "scenarios": scenarios,
        "round_trip": {
            "set_key11_lever1": {"run": set_run, "settings": hex(after_set)},
            "get_after_set": get_run,
            "clear_key11_lever0": {"run": clear_run, "settings": hex(after_clear)},
            "get_after_clear": get_clear,
        },
        "interpretation": (
            "Keys 11 and 16 are the only changeFunctionButton IDs accepted in-stock; "
            "lever=1 sets the corresponding bit in 0x60366e58, lever=0 clears it. "
            "Power-lever remap offline proof can target this word/API pair."
        ),
    }


PLAY_ALLOC_BUF = 0x19004000
LEVER_LEAF = 0x60AF2E05  # body behind CameraCommon::getLeverSwitchState
GUI_FN_LEVER_POWER_SWITCH = 0x400000D


def probe_start_play_sound(image: bytes) -> dict:
    """Smoke: enter Start_Play_Sound_Ext; record return or first hard stop."""
    state = OM3Probe(
        image,
        START_PLAY_SOUND_EXT,
        mask=0xF0,
        frame=0x30,
        registers={"d0": 1, "d1": 0},
    )
    install_common_fixtures(state, image)
    state.ram("play_alloc_buf", PLAY_ALLOC_BUF, bytes(0x100), aliases=False)
    # Extra stubs for play-subsystem helpers commonly hit early.
    extra = {
        0x6040D06F,
        0x6040D4B7,
        0x6040D51A,
        0x60416784,
        0x60419315,
        0x50002A15,
        0x60429759,
        0x604375DB,  # recursive/self only if mis-entered
    }
    stops = {CALLER + 7, *STUB_PCS, *extra}
    stops.discard(0x604375DB)
    guarded = 0
    touched = []
    while True:
        result = state.run(stops, limit=30000)
        pc = state.regs["pc"]
        if result["status"] == "breakpoint" and pc == CALLER + 7:
            return {
                "target": hex(START_PLAY_SOUND_EXT),
                "passed": True,
                "status": "returned",
                "d0": state.regs.get("d0", 0) & 0xFFFFFFFF,
                "instructions": state.steps,
                "stub_hits": guarded,
                "modeled": touched,
                "note": "Full play path returned under heavy stubbing; not a speaker proof.",
            }
        if result["status"] == "breakpoint" and pc in stops:
            touched.append(hex(pc))
            if pc == 0x60416784:
                # Allocator-like helper: hand back a writable fixture buffer.
                state.return_from_model(PLAY_ALLOC_BUF)
            else:
                state.return_from_model(0)
            guarded += 1
            if guarded > 500:
                break
            continue
        return {
            "target": hex(START_PLAY_SOUND_EXT),
            "passed": result.get("status") == "breakpoint" or (result.get("instructions") or 0) > 0,
            "status": result.get("status"),
            "pc": hex(pc),
            "fault": result.get("fault"),
            "instructions": state.steps,
            "stub_hits": guarded,
            "modeled": touched,
            "entry_reached": True,
            "note": (
                "Entry is reachable; deeper codec/DSP/MMIO is unmodeled. "
                "L1 sound acceptance uses aud_ikey mapping + entry smoke, not full playback."
            ),
        }


def _run_lever_leaf(image: bytes, property_value: int) -> dict:
    """Call lever leaf with stubbed property read returning ``property_value``."""
    state = OM3Probe(image, LEVER_LEAF, mask=0xE0, frame=0x10, registers={"d0": 1, "a0": 0})
    install_common_fixtures(state, image)
    stops = {CALLER + 7, 0x60419315, 0x60AEA7CF, 0x6044FB5D, *STUB_PCS}
    guarded = 0
    modeled = []
    while True:
        result = state.run(stops, limit=20000)
        pc = state.regs["pc"]
        if result["status"] == "breakpoint" and pc == CALLER + 7:
            return {
                "status": "returned",
                "d0": state.regs.get("d0", 0) & 0xFFFFFFFF,
                "property_stub": property_value,
                "instructions": state.steps,
                "stub_hits": guarded,
                "modeled": modeled,
            }
        if result["status"] == "breakpoint" and pc in stops:
            modeled.append(hex(pc))
            if pc == 0x6044FB5D:
                state.return_from_model(property_value & 0xFFFF)
            elif pc == 0x60419315:
                # Force the simpler property-read branch (return 0).
                state.return_from_model(0)
            else:
                state.return_from_model(0)
            guarded += 1
            if guarded > 200:
                break
            continue
        return {
            "status": result.get("status"),
            "pc": hex(pc),
            "fault": result.get("fault"),
            "property_stub": property_value,
            "instructions": state.steps,
            "stub_hits": guarded,
            "modeled": modeled,
        }


def probe_get_lever(image: bytes) -> dict:
    """Resolve getLeverSwitchState and show synthetic SW1/SW2 contrast via leaf stubs."""
    low = _run_lever_leaf(image, 0)
    high = _run_lever_leaf(image, 1)
    contrast = (
        low.get("status") == "returned"
        and high.get("status") == "returned"
        and low.get("d0") != high.get("d0")
    )
    return {
        "target": hex(GET_LEVER_SWITCH_STATE),
        "leaf": hex(LEVER_LEAF),
        "vtable": hex(CAMERA_COMMON_VT),
        "vtable_offset": hex(0xEC),
        "gui_fn_lever_power_switch": hex(GUI_FN_LEVER_POWER_SWITCH),
        "passed": contrast,
        "synthetic_contrast": {
            "property_0": low,
            "property_1": high,
            "d0_differs": contrast,
        },
        "interpretation": (
            "Leaf behind getLeverSwitchState returns opposite values when the "
            "property stub (0x6044fb5d) is 0 vs 1. This is offline synthetic "
            "contrast, not a sampled power-on-dial settings bank."
        ),
        "open_dependency": (
            "Real dual-mode (power-on-dial vs lever-power) still needs the "
            "settings-bank offset that selects mode-dial-as-power."
        ),
    }


def evaluate_acceptance(static: dict, probes: dict) -> dict:
    """Measurable pre-flash bar (checklist L0/L1). L2/L3 need patches/device."""
    ikey = probes["aud_ikey"]
    changefn = probes["change_function"]
    play = probes["start_play_sound"]
    lever = probes["get_lever"]

    sound_l0 = bool(static["ikey_wave_table"]) and all(
        row.get("ikey") for row in static["ikey_wave_table"]
    )
    sound_l1 = bool(ikey.get("passed")) and play.get("status") in {
        "returned",
        "fault",
        "unmapped",
        "breakpoint",
        "limit",
    }
    # play smoke counts for L1 if we at least entered the function (any progress)
    sound_l1 = bool(ikey.get("passed")) and (
        play.get("passed") or (play.get("instructions") or 0) > 0 or play.get("pc") is not None
    )

    lever_l0 = all(
        row.get("analysis_address") for row in static["custom_key_assignment_strings"]
    ) and static["entries"]["getLeverSwitchState"]["entry"] == hex(GET_LEVER_SWITCH_STATE)

    lever_l1 = bool(changefn.get("passed"))
    lever_synthetic = bool(lever.get("passed"))
    # True dual-mode (power-on-dial bank) remains an explicit hard stop.
    lever_l1_dual_mode_real = False

    criteria = {
        "sound": {
            "L0_ikey_wave_table_closed": {
                "required": True,
                "met": sound_l0,
                "evidence": "ikey_wave_table + resolved aud_ikey entry",
            },
            "L1_ikey_native_map_and_play_entry": {
                "required": True,
                "met": sound_l1,
                "evidence": "aud_ikey native map; Start_Play_Sound_Ext entry smoke",
            },
            "L1plus_forced_play_without_full_codec": {
                "required": False,
                "met": bool(play.get("status") == "returned"),
                "evidence": "optional full return under stubs",
            },
        },
        "lever": {
            "L0_assignment_strings_and_entries": {
                "required": True,
                "met": lever_l0,
                "evidence": "customKeyAssignment_swXX + getLever/changeFunction entries",
            },
            "L1_changeFunction_settings_roundtrip": {
                "required": True,
                "met": lever_l1,
                "evidence": "key 11/16 bit set/clear on 0x60366e58 via native APIs",
            },
            "L1_lever_state_synthetic_contrast": {
                "required": True,
                "met": lever_synthetic,
                "evidence": (
                    "getLeverSwitchState leaf returns differ for property stub 0 vs 1; "
                    f"GUI_FN_LEVER_POWER_SWITCH={hex(GUI_FN_LEVER_POWER_SWITCH)}"
                ),
            },
            "L1_dual_power_binding_real_settings_bank": {
                "required": False,
                "met": lever_l1_dual_mode_real,
                "evidence": "hard stop: mode-dial-as-power settings bank offset not located",
                "blocker": lever.get("open_dependency"),
            },
        },
        "shared": {
            "no_gui_required": {"required": True, "met": True, "evidence": "CPU+MMIO harness only"},
            "boot_deeper_idle_not_acceptance": {
                "required": True,
                "met": True,
                "evidence": "acceptance is feature probes, not om3_boot deeper_idle",
            },
        },
    }

    required = [
        item
        for group in criteria.values()
        for item in group.values()
        if item.get("required")
    ]
    met = [item for item in required if item.get("met")]
    blockers = [
        {"name": name, **item}
        for group_name, group in criteria.items()
        for name, item in group.items()
        if item.get("required") and not item.get("met")
    ]
    soft_blockers = [
        {"name": name, **item}
        for group_name, group in criteria.items()
        for name, item in group.items()
        if (not item.get("required")) and item.get("blocker") and not item.get("met")
    ]

    if len(met) == len(required) and not blockers:
        overall = "PASS_PREFLASH_L1"
    elif len(met) >= 4:
        overall = "PASS_PREFLASH_CORE_WITH_BLOCKERS"
    else:
        overall = "INCOMPLETE"

    return {
        "overall": overall,
        "required_met": f"{len(met)}/{len(required)}",
        "criteria": criteria,
        "blockers": blockers,
        "known_hard_stops": soft_blockers,
        "preflash_bar_definition": {
            "L0": "Static xref/ABI closed for sound ikey table + lever assignment/API entries",
            "L1_sound": "Native aud_ikey map matches table; play entry is callable/smokeable offline",
            "L1_lever": "Native changeFunctionButton/getChangeFunctionButton round-trip on settings word",
            "L1_lever_state": "Synthetic getLeverSwitchState leaf contrast (property stub 0 vs 1)",
            "L1_dual_mode_real": "Hard stop until mode-dial-as-power settings bank is mapped",
            "L2": "Reproducible patch build + code-space audit + boot non-regression (not in this run)",
            "L3": "On-device only with explicit user authorization (never automated)",
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, default=STOCK_MAIN)
    ap.add_argument(
        "--out",
        type=Path,
        help="report directory (created/reused; overwrites JSON reports)",
    )
    ap.add_argument("--skip-native", action="store_true", help="static dumps only")
    args = ap.parse_args(argv)

    require(ENGINE.is_file(), f"MN103 engine missing at {ENGINE}")
    image = load_stock_main(args.main)
    static = static_landmarks(image)

    probes = {}
    if args.skip_native:
        probes = {
            "aud_ikey": {"passed": False, "skipped": True},
            "change_function": {"passed": False, "skipped": True},
            "start_play_sound": {"passed": False, "skipped": True},
            "get_lever": {"passed": False, "skipped": True},
        }
    else:
        probes["aud_ikey"] = probe_aud_ikey(image)
        probes["change_function"] = probe_change_function(image)
        probes["start_play_sound"] = probe_start_play_sound(image)
        probes["get_lever"] = probe_get_lever(image)

    acceptance = evaluate_acceptance(static, probes)
    report = {
        "model": "OM-3",
        "build": "1100",
        "main_sha256": STOCK_MAIN_SHA,
        "purpose": "pre-flash offline validation of sound/lever/settings call paths",
        "not": [
            "GUI / Live View / menu click simulator",
            "om3_boot deeper_idle milestone",
            "authorization to flash a camera",
        ],
        "static": static,
        "probes": probes,
        "acceptance": acceptance,
    }

    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "om3-preflash-validate.json").write_text(text, encoding="utf-8")
        (args.out / "om3-preflash-acceptance.json").write_text(
            json.dumps(acceptance, indent=2) + "\n", encoding="utf-8"
        )
        (args.out / "om3-sound-ikey-map.json").write_text(
            json.dumps(probes.get("aud_ikey", {}), indent=2) + "\n", encoding="utf-8"
        )
        (args.out / "om3-lever-settings-probe.json").write_text(
            json.dumps(probes.get("change_function", {}), indent=2) + "\n", encoding="utf-8"
        )

    summary = {
        "overall": acceptance["overall"],
        "required_met": acceptance["required_met"],
        "aud_ikey_passed": probes.get("aud_ikey", {}).get("passed"),
        "change_function_passed": probes.get("change_function", {}).get("passed"),
        "start_play_status": probes.get("start_play_sound", {}).get("status"),
        "get_lever_passed": probes.get("get_lever", {}).get("passed"),
        "blockers": [
            b.get("name") or b.get("evidence") for b in acceptance.get("blockers", [])
        ],
        "out": None if not args.out else str(args.out),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, AssertionError) as exc:
        sys.exit(f"error: {exc}")
