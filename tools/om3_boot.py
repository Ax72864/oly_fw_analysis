#!/usr/bin/env python3
"""OM-3 startup harness for offline debugging (stock 1100 main).

Loads the pinned OM-3 main image and executes from analysis entry 0x60021020.
This is a debugging front-end, not a claim of complete TruePic / board fidelity.

Modes:
  prefix  – stop at the first unmodeled access (default entry probe)
  run     – continue with explicit modeled MMIO/RAM until limit, breakpoint, or fault
  idle    – reserved name for a future connected idle schedule; currently reports the
            still-missing model boundary instead of inventing PEN-F peers

Breakpoints are absolute analysis addresses. Unknown accesses stop with a retained
fault report so you can extend the model deliberately.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

from dataclasses import replace

from oly_container import sha256
from penf_emulator import ENGINE, INITIAL_SP, Region, ROOT, STACK, execute

BASE = 0x60021020
STOCK_MAIN = ROOT / 'analysis/om3_1100/00_0100_50000020.decoded.bin'
STOCK_MAIN_SHA = '5e8d376e9111a44ac0352f26030d7c1b17026d42c45f3600cfa02a0e8c5b7d59'
HOOK_RETURN = 0x18030000


def require(value, message):
    if not value:
        raise ValueError(message)


def load_main(path=STOCK_MAIN):
    data = path.read_bytes()
    require(sha256(data) == STOCK_MAIN_SHA, f'Unexpected OM-3 main at {path}')
    return data


def parse_addrs(values):
    out = []
    for item in values or []:
        out.append(int(item, 0))
    return out


class OM3BootState:
    """Minimal cooperative boot state for OM-3 main-image debugging."""

    def __init__(self, image, *, strap_bits=7):
        self.image = image
        self.regions = [
            Region('main_image', BASE, image, 'rx'),
            Region('incoming_stack', STACK, bytes(0x1100), 'rw', True),
            Region('return_trampoline', HOOK_RETURN, b'\xcb' * 8, 'rx'),
        ]
        self.regs = {'pc': BASE, 'sp': INITIAL_SP, 'psw': 0}
        self.events = []
        self.steps = 0
        self.models = []
        # Promote slices of the flat image to writable RAM. Convenience only until
        # OM-3 section constructors / data initializers are qualified.
        self.ram('entry_status_mirror', 0x628ac680, bytes(0x40))
        self.ram('early_workspace', 0x6181e340, bytes(0x2000))
        self.ram('internal_stack', 0x47000000, bytes(0x800), aliases=False)
        self.ram('reloc_helper', 0x47000800, b'\xa5' * 0x1800, aliases=False, executable=True)
        # First native entry helper at 0x600210b5 reads 0x98e0009c then stores into
        # image RAM at 0x628ac680. 0x8070 is touched by the companion helper.
        self.register(0x98e0009c, 'r', strap_bits & 7)
        self.register(0x8070, 'rw', 0)
        self.register(0x98100008, 'w', 0)
        self.models.extend([
            {
                'name': 'entry_controller_word',
                'address': '0x98e0009c',
                'value': strap_bits & 7,
                'assumption': 'Synthetic word for the first OM-3 entry helper read; not measured on silicon',
                'code': '0x600210b5',
            },
            {
                'name': 'cpu_index_or_control_8070',
                'address': '0x8070',
                'assumption': 'Read-modify-write shadow used by 0x600210aa; semantics unqualified',
            },
            {
                'name': 'early_write_98100008',
                'address': '0x98100008',
                'assumption': 'Write-only shadow at entry 0x60021046; same address appears in PEN-F early boot',
            },
        ])

    def ram(self, name, address, data, *, aliases=True, executable=False):
        address = address - 0x40000000 if 0xa0000000 <= address < 0xc0000000 else address
        end = address + len(data)
        rebuilt = []
        for region in self.regions:
            rend = region.address + len(region.data)
            if address < rend and region.address < end:
                if region.alias_of or region.capture:
                    raise ValueError(f'RAM extent overlaps mutable region: {name}, {region.name}')
                if region.address < address:
                    rebuilt.append(replace(region, name=region.name + '_lo',
                                           data=region.data[:address - region.address]))
                if end < rend:
                    rebuilt.append(replace(region, name=region.name + '_hi', address=end,
                                           data=region.data[end - region.address:]))
            else:
                rebuilt.append(region)
        perms = 'rwx' if executable else 'rw'
        rebuilt.append(Region(name, address, bytes(data), perms, True))
        if aliases and 0x60000000 <= address < 0x80000000:
            rebuilt.append(Region(name + '_uncached', address + 0x40000000,
                                  bytes(data), perms, False, name))
        self.regions = rebuilt

    def register(self, address, permissions, value=0):
        self.regions.append(Region(f'reg_{address:08x}', address,
                                   struct.pack('<I', value & 0xffffffff), permissions, 'w' in permissions))

    def run(self, *, limit, breakpoints=(), stop_pc=0xffffffff):
        require(ENGINE.is_file(), f'MN103 engine missing at {ENGINE}')
        result = execute(
            self.regions, self.regs, stop_pc,
            breakpoints=list(breakpoints),
            limit=limit, trace_limit=40, trace_tail=True, timeout=180,
            changed_captures=True,
        )
        # Apply captured writable buffers back into regions for follow-on steps.
        for item in result['memory']:
            region = self.regions[item['index']]
            data = bytes.fromhex(item['hex'])
            for index, current in enumerate(self.regions):
                if current.name == region.name:
                    self.regions[index] = replace(current, data=data)
                    break
        self.regs = result['registers']
        self.steps += result['completed']
        self.events.append({'kind': 'execution', 'result': {
            'status': result['status'],
            'completed': result['completed'],
            'pc': hex(result['registers']['pc']),
            'sp': hex(result['registers']['sp']),
            'fault': result['fault'],
            'diagnostics': result.get('diagnostics', ''),
        }})
        return result


def summarize(result, state, mode):
    fault = result.get('fault')
    return {
        'model': 'OM-3',
        'build': '1100',
        'mode': mode,
        'main_sha256': STOCK_MAIN_SHA,
        'cpu_base': hex(BASE),
        'entry': hex(BASE),
        'engine': str(ENGINE.relative_to(ROOT)),
        'status': result['status'],
        'instructions_completed': result['completed'],
        'pc': hex(result['registers']['pc']),
        'sp': hex(result['registers']['sp']),
        'fault': fault,
        'models_supplied': state.models,
        'how_to_debug': {
            'rerun_with_breakpoint': 'python tools/om3_boot.py run --breakpoint 0xADDR --out generated/om3-boot-bp',
            'increase_limit': 'python tools/om3_boot.py run --limit 500000 --out generated/om3-boot-long',
            'interpret_fault': 'Extend OM3BootState.register/ram for the faulting address only after reviewing the surrounding code',
            'idle_status': 'Connected multi-core idle peers are not yet ported from penf_boot_*; stop at the current fault instead of inventing them',
        },
        'limits': [
            'Starts at downloaded main entry, not hardware reset/ROM.',
            'No ISP, NAND physics, Wi-Fi, or USB gadget stack.',
            'Early MMIO models (0x98e0009c / 0x8070 / 0x98100008) are synthetic; GPIO/ADC/power maps need OM-3-specific qualification.',
            'Not interchangeable with penf_boot_* peer/IRQ schedules.',
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    def add_common(p):
        p.add_argument('--main', type=Path, default=STOCK_MAIN)
        p.add_argument('--out', type=Path, help='new directory for the JSON report')
        p.add_argument('--limit', type=int, default=200000, help='instruction budget (default 200000)')
        p.add_argument('--breakpoint', action='append', default=[],
                       help='analysis address; repeatable (e.g. --breakpoint 0x600210ef)')
        p.add_argument('--strap-bits', type=int, default=7, help='synthetic boot_status low bits')
        return p

    add_common(sub.add_parser('prefix', help='entry probe; stop at first unmodeled access / budget'))
    add_common(sub.add_parser('run', help='continue under the current explicit models'))
    idle = sub.add_parser('idle', help='report missing idle-model status (no invented peers)')
    idle.add_argument('--out', type=Path, help='optional new directory for the JSON report')
    args = ap.parse_args(argv)

    if args.command == 'idle':
        report = {
            'model': 'OM-3',
            'mode': 'idle',
            'status': 'model_incomplete',
            'message': 'OM-3 connected idle (penf_boot_console_idle / core_idle peers) is not ported yet.',
            'next_steps': [
                'Use: python tools/om3_boot.py prefix --out generated/om3-boot-prefix',
                'Qualify each successive fault address against OM-3 disassembly',
                'Port only reviewed PEN-F peer hooks after address remapping evidence exists',
            ],
        }
        text = json.dumps(report, indent=2) + '\n'
        if args.out:
            require(not args.out.exists(), 'Use a new output directory')
            args.out.mkdir(parents=True)
            (args.out / 'om3-boot.json').write_text(text)
        print(text, end='')
        return 2

    image = load_main(args.main)
    state = OM3BootState(image, strap_bits=args.strap_bits)
    breakpoints = parse_addrs(args.breakpoint)
    # Prefix intentionally uses a modest limit so the first frontier is quick.
    limit = 5000 if args.command == 'prefix' and args.limit == 200000 else args.limit
    result = state.run(limit=limit, breakpoints=breakpoints)
    report = summarize(result, state, args.command)
    text = json.dumps(report, indent=2) + '\n'
    if args.out:
        require(not args.out.exists(), 'Use a new output directory')
        args.out.mkdir(parents=True)
        (args.out / 'om3-boot.json').write_text(text)
        (args.out / 'events.json').write_text(json.dumps(state.events, indent=2) + '\n')
    print(text, end='')
    return 0 if result['status'] in ('breakpoint', 'returned') else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit(f'error: {exc}')
