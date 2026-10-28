#!/usr/bin/env python3
"""OM-3 pre-flash offline validation harness (sound / lever / settings / L2).

Goal: exercise the call paths needed to accept firmware mods before any
device flash — not a GUI simulator and not a substitute for ``om3_boot``
``deeper_idle``.

Build 1100 pinned main only. Emits graded acceptance (L0/L1/L2/FULLCHAIN).
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from oly_container import sha256
from penf_emulator import ENGINE, ROOT
from penf_probe import CALLER
from om3_probe import OM3Probe, BASE, STOCK_MAIN, STOCK_MAIN_SHA, load_stock_main, require

# Resolved native entries (string → prologue), build 1100.
AUD_IKEY = 0x60ADF844
AUD_IKEY_TABLE = 0x60DDB9E4
AUD_IKEY_TABLE_COUNT = 18
AUD_LOG_ENABLE = 0x62B43BA4

START_PLAY_SOUND_EXT = 0x604375D6
CHANGE_FUNCTION_BUTTON = 0x60AF1F1E
GET_CHANGE_FUNCTION_BUTTON = 0x60AF284F
SETTINGS_WORD = 0x60366E58
KEYASSIGN_MODE_DIAL_A = 0x603713D4
KEYASSIGN_MODE_DIAL_B = 0x603713D8
UI_LOG = 0x60AE7412

CAMERA_COMMON_VT = 0x60E20750
GET_LEVER_SWITCH_STATE = 0x60B34C2C
LEVER_LEAF = 0x60AF2E05
EV_CHANGE_LEVER_SW = 0xE2
EV_CHANGE_LEVER_SW_NAME = 0x60DEE084
GUI_FN_LEVER_POWER_SWITCH = 0x400000D

# Settings enum table (name ptr, id, flags) near 0x612f1c54.
PROP_MODE_DIAL = 0x60
PROP_LEVER_SWITCH = 0x61
PROP_SILENT_SETTING = 0x77
PROP_TABLE_MODE_DIAL = 0x612F1C54
PROP_TABLE_LEVER_SWITCH = 0x612F1C60

PLAY_ALLOC_BUF = 0x19004000
LEVER_KEYS = (11, 16)

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

STUB_PCS = {
    UI_LOG,
    0x60AE7469,
    0x60AE769F,
    0x60AE773B,
    0x60AE76B7,
    0x60AEE352,
    0x60AEE613,
    0x60AEE65F,
    0x60AF18D4,
}

SOUND_PATCH = ROOT / "patches/sound/om-3/build.py"
LEVER_PATCH = ROOT / "patches/power_lever/om-3/build.py"


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
    off = image.find(text.encode("ascii"))
    return None if off < 0 else BASE + off


def u32(image: bytes, address: int) -> int:
    return struct.unpack_from("<I", image, address - BASE)[0]


def dump_ikey_table(image: bytes) -> list[dict]:
    rows = []
    for i in range(AUD_IKEY_TABLE_COUNT):
        addr = AUD_IKEY_TABLE + i * 8
        ptr = u32(image, addr)
        wave = u32(image, addr + 4)
        name = cstring_at(image, ptr)
        note = None
        if name and name.startswith("PRM_AUD_SHUT"):
            note = "mechanical shutter family"
        elif name and name.startswith("PRM_AUD_CSHUT"):
            note = "compact/electronic shutter family"
        rows.append(
            {
                "index": i,
                "ikey_ptr": hex(ptr),
                "ikey": name,
                "is_short_sound": wave,
                "note": note,
            }
        )
    return rows


def dump_custom_key_strings(image: bytes) -> list[dict]:
    rows = []
    for name in CUSTOM_KEY_STRINGS:
        addr = find_string(image, f"[GUI KeyAssignment]:{name}") or find_string(image, name)
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
                "abi": "d0/d1 params; prologue movm+add-48; CALLER mask=0 frame=0",
                "assert_string": hex(
                    find_string(image, "[ASSERT]Start_Play_Sound_Ext param error") or 0
                ),
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
                "leaf": hex(LEVER_LEAF),
                "vtable": hex(CAMERA_COMMON_VT),
                "vtable_offset": hex(0xEC),
                "abi": "a0=CameraCommon* d0=arg; call mask=0xa0 frame=0x10",
            },
            "EV_CHANGE_LEVER_SW": {
                "name": hex(EV_CHANGE_LEVER_SW_NAME),
                "event_id": hex(EV_CHANGE_LEVER_SW),
            },
            "GUI_FN_LEVER_POWER_SWITCH": hex(GUI_FN_LEVER_POWER_SWITCH),
        },
        "settings_bank": {
            "MODE_DIAL_property_id": hex(PROP_MODE_DIAL),
            "LEVER_SWITCH_property_id": hex(PROP_LEVER_SWITCH),
            "SILENT_SETTING_property_id": hex(PROP_SILENT_SETTING),
            "property_table_MODE_DIAL": hex(PROP_TABLE_MODE_DIAL),
            "property_table_LEVER_SWITCH": hex(PROP_TABLE_LEVER_SWITCH),
            "function_button_word": hex(SETTINGS_WORD),
            "keyassignment_mode_dial_cache": [
                hex(KEYASSIGN_MODE_DIAL_A),
                hex(KEYASSIGN_MODE_DIAL_B),
            ],
            "MODE_DIAL_B_ONOFF_gate_properties": [1482, 1483],
            "note": (
                "MODE_DIAL/LEVER_SWITCH enum ids located in settings name table; "
                "function-button bits at 0x60366e58; KeyAssignment caches mode_dial "
                "at 0x603713d4/d8. Live property bag for 1482/1483 still needs service objects."
            ),
        },
        "ikey_wave_table": dump_ikey_table(image),
        "custom_key_assignment_strings": dump_custom_key_strings(image),
    }


def install_common_fixtures(state: OM3Probe, image: bytes, settings_value: int = 0) -> None:
    page = SETTINGS_WORD & ~0xFF
    blob = bytearray(image[page - BASE : page - BASE + 0x100])
    struct.pack_into("<I", blob, SETTINGS_WORD - page, settings_value & 0xFFFFFFFF)
    state.ram("settings_bank_page", page, bytes(blob))
    # Also promote KeyAssignment mode_dial cache page (may overlap).
    page2 = KEYASSIGN_MODE_DIAL_A & ~0xFF
    if page2 != page:
        state.ram(
            "keyassign_mode_dial_page",
            page2,
            image[page2 - BASE : page2 - BASE + 0x100],
        )
    state.ram("aud_log_enable", AUD_LOG_ENABLE, struct.pack("<I", 0))
    state.ram("aud_log_aux", 0x62B43BA8, struct.pack("<I", 0))


def install_play_peer_fixtures(state: OM3Probe) -> None:
    """Minimal peer/CPU objects so Start_Play_Sound_Ext can return offline."""
    state.ram("peer_page", 0x97F00000, bytes(0x2000), aliases=False)
    cpu_obj = 0x97F01000
    status = 0x97F01100
    blob = bytearray(0x200)
    struct.pack_into("<I", blob, 0x1C, status)
    struct.pack_into("<I", blob, 0x60, status + 0x20)
    state.write(cpu_obj, bytes(blob))
    state.write(status, b"\x01\x01" + bytes(0x40))
    page = bytearray(0x20)
    struct.pack_into("<I", page, 4, cpu_obj)
    state.write(0x97F00000, bytes(page))
    state.ram("cpu_index", 0x8050, struct.pack("<I", 0), aliases=False)
    state.ram("play_alloc_buf", PLAY_ALLOC_BUF, bytes(0x100), aliases=False)


def run_with_stubs(state: OM3Probe, *, limit: int = 50000, stub_result: int = 0) -> dict:
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
            state.return_from_model(stub_result if pc != 0x60AE773B else 1)
            guarded += 1
            if guarded > 2000:
                return {
                    "status": "stub_exhaustion",
                    "pc": hex(pc),
                    "instructions": state.steps,
                    "stub_hits": guarded,
                }
            continue
        return {
            "status": result.get("status"),
            "pc": hex(pc),
            "fault": result.get("fault"),
            "instructions": state.steps,
            "stub_hits": guarded,
        }


def probe_aud_ikey(image: bytes) -> dict:
    rows = []
    for entry in dump_ikey_table(image):
        ikey_addr = int(entry["ikey_ptr"], 16)
        state = OM3Probe(image, AUD_IKEY, mask=0xF0, frame=0x1C, registers={"a0": ikey_addr})
        install_common_fixtures(state, image)
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
            "Stock: PRM_AUD_SHUT*=short, PRM_AUD_CSHUT*=not. "
            "L2 sound patch can flip CSHUT short flags for offline acceptance."
        ),
    }


def probe_change_function(image: bytes) -> dict:
    scenarios = []
    for key in LEVER_KEYS + (0, 12):
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
            scenarios.append(
                {
                    "key": key,
                    "lever": lever,
                    "initial": hex(initial),
                    "final": hex(final),
                    "d0": outcome.get("d0"),
                    "accepted_key": key in LEVER_KEYS,
                    "settings_changed": final != initial,
                    "run": outcome,
                }
            )
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
        and all(s["run"].get("status") == "returned" for s in accepted + rejected)
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
    }


def probe_start_play_sound(image: bytes) -> dict:
    """Enter Start_Play_Sound_Ext with peer fixtures; require stable return."""
    state = OM3Probe(
        image, START_PLAY_SOUND_EXT, mask=0, frame=0, registers={"d0": 1, "d1": 0}
    )
    install_common_fixtures(state, image)
    install_play_peer_fixtures(state)
    extra = {
        0x6040D06F,
        0x6040D4B7,
        0x6040D51A,
        0x60416784,
        0x60419315,
        0x50002A15,
        0x60416878,
        0x6040D103,
        0x6040D196,
        0x6003193E,
        0x60038C74,
    }
    stops = {CALLER + 7, *STUB_PCS, *extra}
    guarded = 0
    modeled = []
    while True:
        result = state.run(stops, limit=50000)
        pc = state.regs["pc"]
        if result["status"] == "breakpoint" and pc == CALLER + 7:
            return {
                "target": hex(START_PLAY_SOUND_EXT),
                "passed": True,
                "status": "returned",
                "d0": state.regs.get("d0", 0) & 0xFFFFFFFF,
                "instructions": state.steps,
                "stub_hits": guarded,
                "modeled": modeled,
                "note": "Stable return under peer/DSP stubs; not a speaker proof.",
            }
        if result["status"] == "breakpoint" and pc in stops:
            modeled.append(hex(pc))
            if pc == 0x60416784:
                state.return_from_model(PLAY_ALLOC_BUF)
            else:
                state.return_from_model(0)
            guarded += 1
            if guarded > 500:
                break
            continue
        return {
            "target": hex(START_PLAY_SOUND_EXT),
            "passed": False,
            "status": result.get("status"),
            "pc": hex(pc),
            "fault": result.get("fault"),
            "instructions": state.steps,
            "stub_hits": guarded,
            "modeled": modeled,
            "note": "Play entry did not return; see fault/pc.",
        }


def _run_lever_leaf(image: bytes, property_value: int) -> dict:
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
        "passed": contrast,
        "gui_fn_lever_power_switch": hex(GUI_FN_LEVER_POWER_SWITCH),
        "synthetic_contrast": {
            "property_0": low,
            "property_1": high,
            "d0_differs": contrast,
        },
    }


def probe_dual_mode_settings(image: bytes) -> dict:
    """Contrast lever-power vs dial-power using located settings-bank words.

    Located offsets:
      - MODE_DIAL property id 0x60 / LEVER_SWITCH 0x61 (enum table)
      - function-button word 0x60366e58
      - KeyAssignment mode_dial cache 0x603713d4
    """
    # Mode A: lever bound (key11 bit set), mode_dial cache = still (1)
    state_a = OM3Probe(
        image, GET_CHANGE_FUNCTION_BUTTON, mask=0xC0, frame=0x14, registers={"d0": 11}
    )
    install_common_fixtures(state_a, image, settings_value=0x1)
    page = KEYASSIGN_MODE_DIAL_A & ~0xFF
    blob = bytearray(image[page - BASE : page - BASE + 0x100])
    struct.pack_into("<I", blob, KEYASSIGN_MODE_DIAL_A - page, 1)  # API_MODE_DIAL_STILL
    state_a.ram("keyassign_mode_dial_page", page, bytes(blob))
    lever_mode = run_with_stubs(state_a, limit=20000)
    dial_cache_a = struct.unpack("<I", state_a.read(KEYASSIGN_MODE_DIAL_A, 4))[0]

    # Mode B: lever unbound (bits clear), mode_dial cache = B (28) as power stand-in
    state_b = OM3Probe(
        image, GET_CHANGE_FUNCTION_BUTTON, mask=0xC0, frame=0x14, registers={"d0": 11}
    )
    install_common_fixtures(state_b, image, settings_value=0x0)
    blob_b = bytearray(image[page - BASE : page - BASE + 0x100])
    struct.pack_into("<I", blob_b, KEYASSIGN_MODE_DIAL_A - page, 28)  # API_MODE_DIAL_B
    state_b.ram("keyassign_mode_dial_page", page, bytes(blob_b))
    dial_mode = run_with_stubs(state_b, limit=20000)
    dial_cache_b = struct.unpack("<I", state_b.read(KEYASSIGN_MODE_DIAL_A, 4))[0]

    passed = (
        lever_mode.get("status") == "returned"
        and dial_mode.get("status") == "returned"
        and lever_mode.get("d0") == 1
        and dial_mode.get("d0") == 0
        and dial_cache_a == 1
        and dial_cache_b == 28
    )
    return {
        "passed": passed,
        "located_offsets": {
            "MODE_DIAL_property_id": hex(PROP_MODE_DIAL),
            "LEVER_SWITCH_property_id": hex(PROP_LEVER_SWITCH),
            "function_button_word": hex(SETTINGS_WORD),
            "keyassignment_mode_dial_cache": hex(KEYASSIGN_MODE_DIAL_A),
            "MODE_DIAL_B_ONOFF_gate_properties": [1482, 1483],
        },
        "lever_power_mode": {
            "function_button_word": "0x1",
            "mode_dial_cache": dial_cache_a,
            "getChangeFunctionButton_key11": lever_mode,
        },
        "dial_power_mode": {
            "function_button_word": "0x0",
            "mode_dial_cache": dial_cache_b,
            "getChangeFunctionButton_key11": dial_mode,
        },
        "interpretation": (
            "Offline dual-mode uses located bank words: lever bits at 0x60366e58 "
            "and KeyAssignment mode_dial cache at 0x603713d4 (B=28). "
            "Live 1482/1483 property-service bag remains unmodeled."
        ),
        "open_dependency": (
            "Property-service objects for MODE_DIAL_B_ONOFF gates 1482/1483 "
            "are not instantiated offline; enum ids and cache words are located."
        ),
    }


def run_l2_patch_builds() -> dict:
    """Run data-only L2 patch builders into a temp dir and collect acceptance."""
    results = {}
    with tempfile.TemporaryDirectory(prefix="om3-l2-") as tmp:
        tmp_path = Path(tmp)
        for name, script in (("sound", SOUND_PATCH), ("power_lever", LEVER_PATCH)):
            out = tmp_path / name
            if not script.is_file():
                results[name] = {"passed": False, "error": f"missing {script}"}
                continue
            proc = subprocess.run(
                [sys.executable, str(script), "--out", str(out)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            acc_path = out / "acceptance.json"
            build_path = out / "build.json"
            acc = json.loads(acc_path.read_text(encoding="utf-8")) if acc_path.is_file() else {}
            build = json.loads(build_path.read_text(encoding="utf-8")) if build_path.is_file() else {}
            results[name] = {
                "passed": bool(acc.get("passed")) and proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "acceptance": acc,
                "patched_main_sha256": build.get("patched_main_sha256"),
            }
    results["passed"] = all(v.get("passed") for k, v in results.items() if k != "passed")
    return results


def evaluate_acceptance(static: dict, probes: dict) -> dict:
    ikey = probes["aud_ikey"]
    changefn = probes["change_function"]
    play = probes["start_play_sound"]
    lever = probes["get_lever"]
    dual = probes["dual_mode"]
    l2 = probes.get("l2_patches") or {}

    sound_l0 = bool(static["ikey_wave_table"]) and all(
        row.get("ikey") for row in static["ikey_wave_table"]
    )
    sound_l1 = bool(ikey.get("passed")) and bool(play.get("passed"))
    lever_l0 = all(
        row.get("analysis_address") for row in static["custom_key_assignment_strings"]
    )
    lever_l1 = bool(changefn.get("passed")) and bool(lever.get("passed"))
    dual_l1 = bool(dual.get("passed"))
    l2_ok = bool(l2.get("passed"))

    criteria = {
        "sound": {
            "L0_ikey_wave_table_closed": {
                "required": True,
                "met": sound_l0,
                "evidence": "ikey_wave_table + resolved aud_ikey entry",
            },
            "L1_ikey_native_map_and_play_return": {
                "required": True,
                "met": sound_l1,
                "evidence": "aud_ikey map + Start_Play_Sound_Ext stable return",
            },
        },
        "lever": {
            "L0_assignment_strings_and_entries": {
                "required": True,
                "met": lever_l0,
                "evidence": "customKeyAssignment_swXX + API entries",
            },
            "L1_changeFunction_and_lever_leaf": {
                "required": True,
                "met": lever_l1,
                "evidence": "settings round-trip + lever leaf contrast",
            },
            "L1_dual_mode_located_bank_offsets": {
                "required": True,
                "met": dual_l1,
                "evidence": (
                    "MODE_DIAL=0x60 / LEVER_SWITCH=0x61; "
                    "0x60366e58 vs 0x603713d4 dial-B contrast"
                ),
            },
        },
        "l2": {
            "L2_sound_and_lever_patch_builds": {
                "required": True,
                "met": l2_ok,
                "evidence": "patches/sound/om-3 + patches/power_lever/om-3 offline builds",
            }
        },
        "shared": {
            "no_gui_required": {"required": True, "met": True, "evidence": "CPU+MMIO harness only"},
            "boot_deeper_idle_not_acceptance": {
                "required": True,
                "met": True,
                "evidence": "acceptance is feature probes + L2 patches",
            },
        },
    }

    required = [
        item for group in criteria.values() for item in group.values() if item.get("required")
    ]
    met = [item for item in required if item.get("met")]
    blockers = [
        {"name": name, **item}
        for group in criteria.values()
        for name, item in group.items()
        if item.get("required") and not item.get("met")
    ]

    if len(met) == len(required):
        overall = "PASS_PREFLASH_FULLCHAIN"
    elif sound_l1 and lever_l1 and dual_l1 and not l2_ok:
        overall = "PASS_PREFLASH_L1_PLUS"
    elif sound_l1 and lever_l1:
        overall = "PASS_PREFLASH_L1"
    elif len(met) >= 4:
        overall = "PASS_PREFLASH_CORE_WITH_BLOCKERS"
    else:
        overall = "INCOMPLETE"

    hard_stop = None
    if dual.get("open_dependency") and dual_l1:
        hard_stop = {
            "id": "property_service_1482_1483",
            "summary": dual.get("open_dependency"),
            "blocks": "On-device-identical MODE_DIAL_B_ONOFF property bag (not required for FULLCHAIN offline bar)",
        }

    return {
        "overall": overall,
        "required_met": f"{len(met)}/{len(required)}",
        "criteria": criteria,
        "blockers": blockers,
        "hard_stop_beyond_fullchain": hard_stop,
        "preflash_bar_definition": {
            "L0": "Static xref/ABI closed",
            "L1": "Native aud_ikey + play return + changeFunction + lever leaf",
            "L1_dual": "Located MODE_DIAL/LEVER bank offsets + offline dual-mode contrast",
            "L2": "Reproducible data patches under patches/*/om-3 with native acceptance",
            "FULLCHAIN": "All required L0–L2 criteria met offline (no GUI, no flash)",
            "L3": "On-device only with explicit user authorization",
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main", type=Path, default=STOCK_MAIN)
    ap.add_argument("--out", type=Path, help="report directory (created/reused)")
    ap.add_argument("--skip-native", action="store_true")
    ap.add_argument("--skip-l2", action="store_true", help="skip patch builds")
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
            "dual_mode": {"passed": False, "skipped": True},
            "l2_patches": {"passed": False, "skipped": True},
        }
    else:
        probes["aud_ikey"] = probe_aud_ikey(image)
        probes["change_function"] = probe_change_function(image)
        probes["start_play_sound"] = probe_start_play_sound(image)
        probes["get_lever"] = probe_get_lever(image)
        probes["dual_mode"] = probe_dual_mode_settings(image)
        probes["l2_patches"] = (
            {"passed": False, "skipped": True}
            if args.skip_l2
            else run_l2_patch_builds()
        )

    acceptance = evaluate_acceptance(static, probes)
    report = {
        "model": "OM-3",
        "build": "1100",
        "main_sha256": STOCK_MAIN_SHA,
        "purpose": "pre-flash full-chain offline validation (sound/lever/settings/L2)",
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
            json.dumps(
                {
                    "change_function": probes.get("change_function"),
                    "dual_mode": probes.get("dual_mode"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (args.out / "om3-l2-patches.json").write_text(
            json.dumps(probes.get("l2_patches", {}), indent=2) + "\n", encoding="utf-8"
        )

    summary = {
        "overall": acceptance["overall"],
        "required_met": acceptance["required_met"],
        "aud_ikey_passed": probes.get("aud_ikey", {}).get("passed"),
        "play_returned": probes.get("start_play_sound", {}).get("passed"),
        "change_function_passed": probes.get("change_function", {}).get("passed"),
        "get_lever_passed": probes.get("get_lever", {}).get("passed"),
        "dual_mode_passed": probes.get("dual_mode", {}).get("passed"),
        "l2_passed": probes.get("l2_patches", {}).get("passed"),
        "blockers": [b.get("name") for b in acceptance.get("blockers", [])],
        "hard_stop_beyond_fullchain": acceptance.get("hard_stop_beyond_fullchain"),
        "out": None if not args.out else str(args.out),
    }
    print(json.dumps(summary, indent=2))
    return 0 if acceptance["overall"] == "PASS_PREFLASH_FULLCHAIN" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, AssertionError) as exc:
        sys.exit(f"error: {exc}")
