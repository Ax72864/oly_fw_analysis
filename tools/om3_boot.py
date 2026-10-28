#!/usr/bin/env python3
"""OM-3 startup harness for offline debugging (stock 1100 main).

Loads the pinned OM-3 main image and executes from analysis entry 0x60021020.
This is a debugging front-end: it can auto-stub unmodeled MMIO/RAM so a long
run reaches a stable budget stop. Auto-stubs are logged; they are not silicon
measurements and are not a PEN-F peer/IRQ port.

Modes:
  prefix   – stop at the first unmodeled access (no auto-stub)
  run      – explicit models only (optional --auto-stub)
  advance  – keep auto-stubbing peripheral/RAM faults until budget / breakpoint
  idle     – same as advance with a large default budget; reports stable_under_budget
             when no fault remains inside the budget (not a claimed RTOS idle)

Examples:
  python tools/om3_boot.py prefix --out generated/om3-boot-prefix
  python tools/om3_boot.py advance --limit 2000000 --out generated/om3-boot-advance
  python tools/om3_boot.py idle --out generated/om3-boot-idle
  python tools/om3_boot.py run --breakpoint 0x600216b1 --out generated/om3-boot-bp
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
import struct
import sys

from oly_container import sha256
from penf_emulator import ENGINE, INITIAL_SP, Region, ROOT, STACK, execute

BASE = 0x60021020
STOCK_MAIN = ROOT / 'analysis/om3_1100/00_0100_50000020.decoded.bin'
STOCK_MAIN_SHA = '5e8d376e9111a44ac0352f26030d7c1b17026d42c45f3600cfa02a0e8c5b7d59'
HOOK_RETURN = 0x18030000
MAIN_END = BASE + 33554368  # stock main payload length


def require(value, message):
    if not value:
        raise ValueError(message)


def load_main(path=STOCK_MAIN):
    data = path.read_bytes()
    require(sha256(data) == STOCK_MAIN_SHA, f'Unexpected OM-3 main at {path}')
    return data


def parse_addrs(values):
    return [int(item, 0) for item in (values or [])]


def fault_dict(fault):
    if not fault:
        return None
    out = dict(fault)
    for key in ('pc', 'address'):
        if key in out and isinstance(out[key], int):
            out[key + '_hex'] = hex(out[key])
    return out


class OM3BootState:
    """Cooperative OM-3 main-image boot state with explicit + auto stubs."""

    def __init__(self, image, *, strap_bits=7):
        self.image = image
        self.regions = [
            Region('main_image', BASE, image, 'rx'),
            Region('incoming_stack', STACK, bytes(0x4000), 'rw', True),
            Region('return_trampoline', HOOK_RETURN, b'\xcb' * 8, 'rx'),
        ]
        self.regs = {'pc': BASE, 'sp': INITIAL_SP, 'psw': 0}
        self.events = []
        self.steps = 0
        self.models = []
        self.auto_stubs = []
        self._install_seed_models(strap_bits)

    def _install_seed_models(self, strap_bits):
        # Writable mirrors / helper RAM used by early entry.
        self.ram('entry_status_mirror', 0x628ac680, bytes(0x100))
        self.ram('early_workspace', 0x6181e340, bytes(0x4000))
        # Match PEN-F layout: 2 KiB stack then 6 KiB reloc helper (no overlap).
        self.ram('internal_stack', 0x47000000, bytes(0x800), aliases=False)
        self.ram('reloc_helper', 0x47000800, b'\xa5' * 0x1800, aliases=False, executable=True)
        self.ram('shared_kernel_flags', 0x8ff00000, bytes(0x400), aliases=False)
        self.ram('private_lock_bytes', 0x8fe00000, bytes(0x10), aliases=False)

        # OM-3 observed entry + PEN-F-analogue early controller/clock/IRQ shadows.
        seeds = [
            (0x98e0009c, 'rw', strap_bits & 7, 'entry_controller_word'),
            (0x98e00060, 'r', strap_bits & 7, 'boot_status_analogue'),
            (0x98e00058, 'r', 0, 'controller_58_analogue'),
            (0x8070, 'rw', 0, 'core_config_8070'),
            (0x8050, 'r', 0, 'cpu_index_0'),
            (0x98100008, 'w', 0, 'early_write_98100008'),
            (0x988004a0, 'rw', 0, 'clock_gate_988004a0'),
            (0x988004a4, 'rw', 0, 'clock_gate_988004a4'),
            (0x9880004c, 'r', 1, 'clock_mux_hypothesis'),
            (0x98800008, 'r', 0, 'clock_divider_hypothesis'),
            (0x988000fc, 'r', 0x200000, 'serial_clock_word_hypothesis'),
            (0x988000c8, 'r', 0, 'clock_status_c8'),
            (0x98800020, 'r', 0, 'clock_status_20'),
            (0x98800008, 'r', 0, 'clock_status_08'),
        ]
        for address, perms, value, name in seeds:
            self.register(address, perms, value)
            self.models.append({
                'name': name, 'address': hex(address), 'permissions': perms,
                'value': value, 'kind': 'seed',
                'assumption': 'Synthetic early MMIO; not measured on OM-3 silicon',
            })

        # Interrupt / timer / UART-style pages borrowed as empty shadows from PEN-F boot.
        for address in (0x98900000, 0x98900004, 0x98900024, 0x98900028, 0x9890002c,
                        0x9890004c, 0x98900078):
            self.register(address, 'rw', 0)
        for address in (0x98700000, 0x98700014, 0x98700018, 0x9870001c, 0x98700028):
            self.register(address, 'rw', 1 if address == 0x9870001c else 0)
        for address in (0x8000 + i for i in range(0, 0x20, 4)):
            self.register(address, 'w', 0)
        for address in (0x8940, 0x8944, 0x8948, 0x894c, 0x8950, 0x8954, 0x8958):
            self.register(address, 'rw', 0)
        # Early BSS/SRAM (entry probes 0x97f00080..9f; clear walks through 0x97f01fff).
        sram = bytearray(0x2000)
        for offset in range(0x80, 0xa0, 4):
            struct.pack_into('<I', sram, offset, 0x01010101 if offset >= 0x90 else 0)
        self.regions.append(Region('early_sram_97f00000', 0x97f00000, bytes(sram), 'rw', True))
        # Early memcpy/DMA engine at 0x9bc00000: firmware polls bit0 of +0x04 (setlb/lne
        # at 0x60021530 / 0x600215e9). Keep the status word ready so boot can proceed.
        dma = bytearray(0x100)
        struct.pack_into('<I', dma, 0x04, 1)
        self.regions.append(Region('dma_engine_9bc00000', 0x9bc00000, bytes(dma), 'rw', True))
        # Neighbor clock-gate page touched just before the historical 0x988004a0 frontier.
        self.regions.append(Region('clock_page_98800300', 0x98800300, bytes(0x100), 'rw', True))
        # Secondary stack + early relocated helpers (SP switch at 0x600210a0; later
        # execute hits e.g. 0x50002900, so this window is rwx).
        self.regions.append(Region('secondary_stack_50000000', 0x50000000, bytes(0x10000), 'rwx', True))
        self.models.append({
            'name': 'penf_analogue_irq_uart_clock_pages',
            'kind': 'seed_batch',
            'assumption': 'Empty/ready shadows inspired by penf_boot_emulator early maps; not OM-3-qualified',
        })
        self.models.append({
            'name': 'dma_engine_9bc00004_ready',
            'address': '0x9bc00004',
            'value': 1,
            'kind': 'seed',
            'assumption': 'Synthetic DMA/copy completion bit; observed poll at 0x60021530',
        })
        self.models.append({
            'name': 'secondary_stack_50000000',
            'address': '0x50000000',
            'bytes': 0x10000,
            'kind': 'seed',
            'assumption': 'Stack window for post-switch entry at 0x600210c5; size chosen for debugging headroom',
        })

    def read(self, address, size):
        for region in self.regions:
            if region.address <= address and address + size <= region.address + len(region.data):
                offset = address - region.address
                return bytes(region.data[offset:offset + size])
        raise ValueError(f'Unmapped harness read {address:#x}+{size:#x}')

    def write(self, address, data):
        """Write into a capture/root region and keep uncached aliases in sync."""
        data = bytes(data)
        for region in self.regions:
            rend = region.address + len(region.data)
            if region.address <= address and address + len(data) <= rend:
                root = region.alias_of or region.name
                backing = next(item for item in self.regions if item.name == root)
                offset = address - region.address
                blob = backing.data[:offset] + data + backing.data[offset + len(data):]
                self.regions = [
                    replace(item, data=blob) if item.name == root or item.alias_of == root else item
                    for item in self.regions
                ]
                return
        raise ValueError(f'Unmapped harness write {address:#x}+{len(data):#x}')

    def ram(self, name, address, data, *, aliases=True, executable=False):
        address = address - 0x40000000 if 0xa0000000 <= address < 0xc0000000 else address
        end = address + len(data)
        rebuilt = []
        for region in self.regions:
            rend = region.address + len(region.data)
            if address < rend and region.address < end:
                if region.alias_of or region.capture:
                    if region.address <= address and end <= rend:
                        self.write(address, data)
                        return
                    raise ValueError(f'RAM extent overlaps mutable region: {name}, {region.name}')
                if region.address < address:
                    rebuilt.append(replace(region, name=region.name + '_lo',
                                           data=region.data[:address - region.address]))
                if end < rend:
                    rebuilt.append(replace(region, name=region.name + '_hi', address=end,
                                           data=region.data[end - region.address:]))
            else:
                # Drop stale uncached aliases whose root was split away.
                if region.alias_of and any(
                        item.name == region.alias_of and
                        address < item.address + len(item.data) and item.address < end
                        for item in self.regions):
                    continue
                rebuilt.append(region)
        perms = 'rwx' if executable else 'rw'
        blob = bytes(data)
        rebuilt.append(Region(name, address, blob, perms, True))
        if aliases and 0x60000000 <= address < 0x80000000:
            rebuilt.append(Region(name + '_uncached', address + 0x40000000, blob, perms, False, name))
        self.regions = rebuilt

    def register(self, address, permissions, value=0, size=4):
        # Avoid duplicate exact mappings.
        for region in self.regions:
            if region.address == address and len(region.data) == size:
                return
        if self.covered(address, size):
            return
        if size == 2:
            data = struct.pack('<H', value & 0xffff)
        elif size == 1:
            data = bytes((value & 0xff,))
        else:
            data = struct.pack('<I', value & 0xffffffff)
        self.regions.append(Region(f'reg_{address:08x}', address, data,
                                   permissions, 'w' in permissions))

    def covered(self, address, size=4):
        end = address + size
        for region in self.regions:
            rend = region.address + len(region.data)
            if region.address <= address and end <= rend:
                return True
        return False

    def map_mmio_page(self, address, span=0x100):
        page = address & ~(span - 1)
        if self.covered(page, span):
            return page, False
        # Drop any exact small stubs that sit inside the new page.
        self.regions = [
            region for region in self.regions
            if not (page <= region.address and region.address + len(region.data) <= page + span)
        ]
        blob = bytearray(span)
        # Heuristic: many OM-3/PEN-F status words sit at +0x04 / +0x1c and are polled
        # for bit0. Prefill those so auto-stubbed pages do not livelock in setlb/lne.
        if span >= 0x20:
            struct.pack_into('<I', blob, 0x04, 1)
            struct.pack_into('<I', blob, 0x1c, 1)
        self.regions.append(Region(f'mmio_{page:08x}', page, bytes(blob), 'rw', True))
        return page, True

    def stub_span_for(self, address):
        """Choose an auto-stub granule. Large clears get big windows to stay under region caps."""
        if 0x97f00000 <= address < 0x98000000:
            return 0x2000
        if 0x50000000 <= address < 0x51000000:
            return 0x10000
        if 0x98000000 <= address < 0x9c000000:
            return 0x100
        return 0x100

    def stub_fault(self, fault):
        """Install a logged stub for an unmodeled access. Return True if stubbed."""
        if not fault or fault.get('kind') != 1:
            return False
        raw = fault['address'] & ~3
        # Uncached DRAM mirror 0xa0000000..0xc0000000 → cached 0x60000000..0x80000000.
        address = raw - 0x40000000 if 0xa0000000 <= raw < 0xc0000000 else raw
        access = {0: 'read', 1: 'write', 2: 'execute'}.get(fault.get('map'), 'unknown')
        size = max(4, fault.get('size') or 4)

        # Main-image window via cached or uncached alias: promote a page so both
        # views exist (flat main is mapped cached-only at load).
        if BASE <= address < MAIN_END and access in ('read', 'write'):
            page = address & ~0xfff
            offset = page - BASE
            self.ram(f'promoted_main_{page:08x}', page, self.image[offset:offset + 0x1000])
            self.auto_stubs.append({
                'kind': 'promote_main_page', 'address': hex(page), 'bytes': 0x1000,
                'pc': hex(fault.get('pc', 0)), 'raw': hex(raw), 'access': access,
            })
            return True

        # Runtime DRAM around / above the main image (cached or via uncached alias).
        if access in ('read', 'write') and 0x61000000 <= address < 0x70000000:
            page = address & ~0xfff
            if not self.covered(page, 0x1000):
                self.ram(f'runtime_ram_{page:08x}', page, bytes(0x1000))
                self.auto_stubs.append({
                    'kind': 'runtime_ram_page', 'address': hex(page), 'bytes': 0x1000,
                    'pc': hex(fault.get('pc', 0)), 'raw': hex(raw), 'access': access,
                })
                return True
            # Covered cached but fault was on uncached alias: add alias via re-ram.
            if raw != address and not self.covered(raw, size):
                # Find backing data and re-install with aliases.
                for region in self.regions:
                    if region.address <= page and page + 0x1000 <= region.address + len(region.data):
                        if region.alias_of:
                            continue
                        offset = page - region.address
                        self.ram(f'runtime_ram_{page:08x}', page, region.data[offset:offset + 0x1000])
                        self.auto_stubs.append({
                            'kind': 'runtime_ram_uncached_alias', 'address': hex(page),
                            'bytes': 0x1000, 'pc': hex(fault.get('pc', 0)), 'raw': hex(raw),
                            'access': access,
                        })
                        return True
                return False

        # Secondary / loader window after the 0x600210a0 SP switch (stack + helpers).
        if 0x50000000 <= address < 0x51000000 and access in ('read', 'write', 'execute'):
            page = address & ~0xffff
            if not self.covered(page, 0x10000):
                self.regions.append(Region(f'secondary_{page:08x}', page, bytes(0x10000), 'rwx', True))
                self.auto_stubs.append({
                    'kind': 'secondary_stack', 'address': hex(page), 'bytes': 0x10000,
                    'pc': hex(fault.get('pc', 0)), 'raw': hex(raw), 'access': access,
                })
                return True
            # Covered but not executable: replace with rwx.
            for region in list(self.regions):
                if region.address <= address < region.address + len(region.data):
                    if 'x' not in region.permissions:
                        data = region.data
                        self.regions = [item for item in self.regions if item.name != region.name]
                        self.regions.append(Region(region.name + '_x', region.address, data, 'rwx', True))
                        self.auto_stubs.append({
                            'kind': 'secondary_make_executable', 'address': hex(region.address),
                            'bytes': len(data), 'pc': hex(fault.get('pc', 0)), 'raw': hex(raw),
                            'access': access,
                        })
                        return True
                    break
            return False

        # Peripheral / shared windows.
        if (0x8000 <= address < 0x10000 or
                0x80000000 <= address < 0xa0000000 or
                0x97000000 <= address < 0x9c000000 or
                0x47000000 <= address < 0x48000000):
            span = self.stub_span_for(address)
            if self.covered(address, size):
                page, created = self.map_mmio_page(address, span=span)
                if not created:
                    return False
            else:
                page, _ = self.map_mmio_page(address, span=span)
            self.auto_stubs.append({
                'kind': 'mmio_page', 'address': hex(page), 'bytes': span,
                'pc': hex(fault.get('pc', 0)), 'raw': hex(raw), 'access': access,
                'assumption': 'Auto-stubbed peripheral/shared window; status +0x04/+0x1c prefills bit0',
            })
            return True

        # Last-resort: zero-page for wild data pointers (e.g. 0x5245505b from an
        # uninitialized peripheral table). Not executable; debugging only.
        if access in ('read', 'write') and 0x1000 <= address < 0x80000000:
            page = address & ~0xfff
            if not self.covered(page, 0x1000):
                self.regions.append(Region(f'wild_{page:08x}', page, bytes(0x1000), 'rw', True))
                self.auto_stubs.append({
                    'kind': 'wild_pointer_page', 'address': hex(page), 'bytes': 0x1000,
                    'pc': hex(fault.get('pc', 0)), 'raw': hex(raw), 'access': access,
                    'assumption': 'Zero-filled catch-all for non-canonical data pointer',
                })
                return True
        return False

    def _ensure_peer_cpu_objects(self):
        """Wire dummy peer CPU objects into 0x97f00008..14 if still NULL.

        Clone CPU0's object (table[0]) as a template, then point +0x14c at a
        shared -1 word so 0x60031cc9..ccd takes the skip path.
        """
        try:
            cpu0 = struct.unpack('<I', self.read(0x97f00004, 4))[0]
        except ValueError:
            return
        if not cpu0:
            return
        base = 0x632be000
        if not self.covered(base, 0x1000):
            self.ram('synthetic_peer_cpu_objects', base, bytes(0x1000))
        sentinel = base
        self.write(sentinel, struct.pack('<I', 0xffffffff))
        try:
            template = self.read(cpu0, 0x200)
        except ValueError:
            template = bytes(0x200)
        for cpu in (1, 2, 3):
            slot = 0x97f00004 + cpu * 4
            current = struct.unpack('<I', self.read(slot, 4))[0]
            obj = base + 0x40 + cpu * 0x200
            if current and current != obj:
                continue
            self.write(obj, template)
            self.write(obj + 0x14c, struct.pack('<I', sentinel))
            self.write(slot, struct.pack('<I', obj))

    def service_mmio(self):
        """Apply synthetic device completions so poll loops can retire.

        OM-3 storage kicks 0x98d002f0=1 then btst/bne until bit0 clears
        (0x60022e99). DMA copy polls 0x9bc00004 bit0 for ready (0x60021530).
        These are debugging completions, not measured silicon timings.
        """
        completions = (
            (0x98d002f0, 0),   # storage/NAND busy clear
            (0x98d00200, 0),   # storage kick latch
            (0x9bc00004, 1),   # DMA/copy ready
            (0x98e000f4, 0),   # controller cmd word; poll-until-zero at 0x6007063c
            (0x98e0009c, 7),   # restore entry strap after page restubs
        )
        for address, value in completions:
            try:
                self.write(address, struct.pack('<I', value))
            except ValueError:
                pass
        # Peer/IRQ doorbell: PEN-F and OM-3 both poll 0x8958 bit4 (see 0x600335fa).
        try:
            old = struct.unpack('<H', self.read(0x8958, 2))[0]
            self.write(0x8958, struct.pack('<H', old | 0x10))
        except ValueError:
            pass
        # Multi-core kernel-ready mask at 0x97f00000 (OM-3 analogue of PEN-F 0x8ff00000).
        # CPU0 sets its bit then waits for (1<<core_count)-1 at 0x600333e9; OM-3 uses
        # core_count=4 → mask 0xf. Assume peer CPUs have published their ready bits.
        try:
            ready = struct.unpack('<H', self.read(0x97f00000, 2))[0]
            if ready and ready != 0xffff:
                self.write(0x97f00000, struct.pack('<H', ready | 0xf))
        except ValueError:
            pass
        # Peer present bytes polled by 0x60021705..1f (caller 0x6004dd97). Early SRAM
        # clear zeroes them; keep the three flags asserted for debugging progress.
        try:
            self.write(0x97f00095, b'\x01\x01\x01')
        except ValueError:
            pass
        # Peer CPU object pointer table at 0x97f00004 (walked by 0x60031cc7). Without
        # real peer cores the slots stay NULL and 0x60031cc9 faults on (0x14c,a0).
        # Plant dummy objects whose +0x14c word is -1 (the "skip" sentinel).
        try:
            self._ensure_peer_cpu_objects()
        except ValueError:
            pass

    def run_once(self, *, limit, breakpoints=(), stop_pc=0xffffffff):
        require(ENGINE.is_file(), f'MN103 engine missing at {ENGINE}')
        result = execute(
            self.regions, self.regs, stop_pc,
            breakpoints=list(breakpoints),
            limit=limit, trace_limit=40, trace_tail=True, timeout=180,
            changed_captures=True,
        )
        for item in result['memory']:
            region = self.regions[item['index']]
            data = bytes.fromhex(item['hex'])
            self.write(region.address, data)
        self.service_mmio()
        self.regs = result['registers']
        self.steps += result['completed']
        self.events.append({'kind': 'execution', 'result': {
            'status': result['status'],
            'completed': result['completed'],
            'pc': hex(result['registers']['pc']),
            'sp': hex(result['registers']['sp']),
            'fault': fault_dict(result['fault']),
        }})
        return result

    def advance(self, *, limit, breakpoints=(), max_stubs=400):
        remaining = limit
        while remaining > 0:
            chunk = min(remaining, 50000)
            result = self.run_once(limit=chunk, breakpoints=breakpoints)
            remaining = limit - self.steps
            if result['status'] == 'breakpoint':
                return result, 'breakpoint'
            if result['status'] == 'returned':
                return result, 'returned'
            if result['status'] == 'instruction_limit' and remaining <= 0:
                return result, 'stable_under_budget'
            if result['status'] == 'instruction_limit':
                continue
            if result['status'] != 'memory_fault':
                return result, result['status']
            if len(self.auto_stubs) >= max_stubs:
                return result, 'stub_budget_exhausted'
            if not self.stub_fault(result['fault']):
                return result, 'unhandled_fault'
            # Continue from the faulting PC with the new mapping.
        return result, 'stable_under_budget'


def summarize(result, state, mode, outcome=None):
    return {
        'model': 'OM-3',
        'build': '1100',
        'mode': mode,
        'outcome': outcome or result['status'],
        'main_sha256': STOCK_MAIN_SHA,
        'cpu_base': hex(BASE),
        'entry': hex(BASE),
        'engine': str(ENGINE.relative_to(ROOT)),
        'status': result['status'],
        'instructions_total': state.steps,
        'instructions_last_chunk': result['completed'],
        'pc': hex(result['registers']['pc']),
        'sp': hex(result['registers']['sp']),
        'fault': fault_dict(result.get('fault')),
        'seed_models': state.models,
        'auto_stub_count': len(state.auto_stubs),
        'auto_stubs_tail': state.auto_stubs[-20:],
        'how_to_debug': {
            'prefix': 'python tools/om3_boot.py prefix --out generated/om3-boot-prefix',
            'advance': 'python tools/om3_boot.py advance --limit 2000000 --out generated/om3-boot-advance',
            'idle': 'python tools/om3_boot.py idle --out generated/om3-boot-idle',
            'breakpoint': 'python tools/om3_boot.py run --breakpoint 0xADDR --out generated/om3-boot-bp',
        },
        'limits': [
            'Starts at downloaded main entry, not hardware reset/ROM.',
            'Auto-stubs zero-fill unmodeled MMIO/RAM; they enable debugging progress, not hardware fidelity.',
            'No ISP, NAND physics, Wi-Fi, USB gadget, or proven multi-core idle schedule.',
            'stable_under_budget means the instruction budget completed without an unhandled fault; not a claimed UI idle.',
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    def add_common(p, default_limit):
        p.add_argument('--main', type=Path, default=STOCK_MAIN)
        p.add_argument('--out', type=Path, help='new directory for the JSON report')
        p.add_argument('--limit', type=int, default=default_limit)
        p.add_argument('--breakpoint', action='append', default=[])
        p.add_argument('--strap-bits', type=int, default=7)
        p.add_argument('--max-stubs', type=int, default=400)
        return p

    add_common(sub.add_parser('prefix', help='stop at first unmodeled access'), 20000)
    run_p = add_common(sub.add_parser('run', help='single chunk; optional auto-stub loop off by default'), 200000)
    run_p.add_argument('--auto-stub', action='store_true', help='stub faults and continue within --limit')
    add_common(sub.add_parser('advance', help='auto-stub until budget/breakpoint/unhandled fault'), 2_000_000)
    add_common(sub.add_parser('idle', help='large advance; seek stable_under_budget'), 5_000_000)
    args = ap.parse_args(argv)

    image = load_main(args.main)
    state = OM3BootState(image, strap_bits=args.strap_bits)
    breakpoints = parse_addrs(args.breakpoint)

    if args.command == 'prefix':
        result = state.run_once(limit=args.limit, breakpoints=breakpoints)
        outcome = result['status']
    elif args.command == 'run' and not args.auto_stub:
        result = state.run_once(limit=args.limit, breakpoints=breakpoints)
        outcome = result['status']
    else:
        result, outcome = state.advance(
            limit=args.limit, breakpoints=breakpoints, max_stubs=args.max_stubs)

    report = summarize(result, state, args.command, outcome)
    text = json.dumps(report, indent=2) + '\n'
    if args.out:
        require(not args.out.exists(), 'Use a new output directory')
        args.out.mkdir(parents=True)
        (args.out / 'om3-boot.json').write_text(text)
        (args.out / 'auto-stubs.json').write_text(json.dumps(state.auto_stubs, indent=2) + '\n')
        (args.out / 'events.json').write_text(json.dumps(state.events[-50:], indent=2) + '\n')
    # Compact stdout for large runs.
    print(json.dumps({
        'outcome': outcome,
        'status': result['status'],
        'instructions_total': state.steps,
        'pc': hex(result['registers']['pc']),
        'sp': hex(result['registers']['sp']),
        'auto_stub_count': len(state.auto_stubs),
        'fault': fault_dict(result.get('fault')),
        'out': str(args.out) if args.out else None,
    }, indent=2))
    if outcome in ('breakpoint', 'returned', 'stable_under_budget'):
        return 0
    return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit(f'error: {exc}')
