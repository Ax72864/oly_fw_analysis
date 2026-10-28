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
# Synthetic deeper-idle site: firmware idle callback lands here and bra-selfs.
# Encoding mirrors stock 0x60036a13 (`ca 00` as disassembled self-branch).
SYNTH_APP_IDLE = 0x50003000
SYNTH_APP_IDLE_BYTES = b'\xca\x00'
FIRMWARE_HALTS = (0x60036a13, 0x60036a2b)


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
        self.halt_diverts = 0
        self.milestones = []
        self.beyond_halt = True
        self.max_halt_diverts = 8  # only intentional park escapes; not fault thrash
        self.app_ready_armed = False
        self.stack_pc_recovers = 0
        self._install_seed_models(strap_bits)

    def _install_seed_models(self, strap_bits):
        # Writable mirrors / helper RAM used by early entry.
        self.ram('entry_status_mirror', 0x628ac680, bytes(0x100))
        self.ram('early_workspace', 0x6181e340, bytes(0x4000))
        # Match PEN-F layout: 2 KiB stack then 6 KiB reloc helper (no overlap).
        self.ram('internal_stack', 0x47000000, bytes(0x800), aliases=False)
        self.ram('reloc_helper', 0x47000800, b'\xa5' * 0x1800, aliases=False, executable=True)
        # Shared kernel flags, then PEN-F-analogue display state at 0x8ff001a4.
        self.ram('shared_kernel_flags', 0x8ff00000, bytes(0x1a4), aliases=False)
        self.regions.append(Region('display_shared_state', 0x8ff001a4, bytes(12), 'rw', True))
        self.ram('private_lock_bytes', 0x8fe00000, bytes(0x10), aliases=False)
        # Extra GPIO / ADC-style shadows used later in bring-up (PEN-F analogues).
        for address in (0x98d00140, 0x98d00144, 0x98d01104, 0x98d01108):
            self.register(address, 'rw', 0x2000 if address == 0x98d01104 else 0)
        for address in (0x99200310, 0x99300310, 0x99b00310):
            self.register(address, 'w', 0)

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
        # execute hits e.g. 0x50002900, so this window is rwx). Plant synthetic
        # app-idle trampoline at SYNTH_APP_IDLE for beyond-halt deeper steady state.
        secondary = bytearray(0x10000)
        secondary[SYNTH_APP_IDLE - 0x50000000:SYNTH_APP_IDLE - 0x50000000 + 2] = SYNTH_APP_IDLE_BYTES
        self.regions.append(Region('secondary_stack_50000000', 0x50000000, bytes(secondary), 'rwx', True))
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
        self.models.append({
            'name': 'synth_app_idle',
            'address': hex(SYNTH_APP_IDLE),
            'kind': 'seed',
            'assumption': 'Synthetic deeper-idle bra-self; stands in for missing app scheduler callback',
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
            # Mark peer objects application-ready like CPU0 after arming.
            self.write(obj + 360, struct.pack('<I', 1))
            self.write(slot, struct.pack('<I', obj))

    def _promote_for_write(self, address, size=4):
        if BASE <= address < MAIN_END:
            page = address & ~0xfff
            if not any(r.address == page and 'w' in r.permissions and r.capture
                       for r in self.regions):
                offset = page - BASE
                self.ram(f'promoted_main_{page:08x}', page, self.image[offset:offset + 0x1000])

    def _arm_application_ready(self):
        """Mark CPU0 app-ready (+0x168=1) and point idle callback at SYNTH_APP_IDLE.

        Firmware parks at 0x60036a13 when +0x168 != 1; with +0x168 == 1 the idle
        path calls *(obj+0x134). Stock value is an empty retf; we install the
        synthetic bra-self trampoline so the run can settle in deeper_idle.
        """
        try:
            cpu0 = struct.unpack('<I', self.read(0x97f00004, 4))[0]
        except ValueError:
            return False
        if not cpu0:
            return False
        self._promote_for_write(cpu0 + 360)
        self._promote_for_write(cpu0 + 308)
        try:
            self.write(cpu0 + 360, struct.pack('<I', 1))
            self.write(cpu0 + 308, struct.pack('<I', SYNTH_APP_IDLE))
        except ValueError:
            return False
        try:
            if self.read(0x8ff001a4, 4) == bytes(4):
                self.write(0x8ff001a4, struct.pack('<I', 0x3070))
        except ValueError:
            pass
        if not self.app_ready_armed:
            self.app_ready_armed = True
            note = {
                'kind': 'app_ready_armed',
                'cpu0': hex(cpu0),
                'idle_fn': hex(SYNTH_APP_IDLE),
                'assumption': 'Synthetic app-ready flag + idle trampoline; not stock scheduler',
            }
            self.milestones.append(note)
            self.events.append({'kind': 'model', 'result': note})
        return True

    def _neutralize_callback_list(self):
        """Clear first pending fn so accidental walks of 0x6003330b return."""
        try:
            cpu0 = struct.unpack('<I', self.read(0x97f00004, 4))[0]
            head = struct.unpack('<I', self.read(cpu0 + 196, 4))[0]
            if head:
                self._promote_for_write(head + 8)
                self.write(head + 8, struct.pack('<I', 0))
        except ValueError:
            pass

    def at_deeper_idle(self, pc=None):
        pc = self.regs.get('pc', 0) if pc is None else pc
        return SYNTH_APP_IDLE <= pc < SYNTH_APP_IDLE + 4

    def service_control_flow(self, *, reason='halt'):
        """Escape firmware bra-self parks into SYNTH_APP_IDLE (no wild PC thrash)."""
        if not self.beyond_halt:
            return False
        pc = self.regs.get('pc', 0)
        if self.at_deeper_idle(pc):
            return False  # already at deeper steady state
        if pc not in FIRMWARE_HALTS:
            return False
        if self.halt_diverts >= self.max_halt_diverts:
            return False
        self.halt_diverts += 1
        self._arm_application_ready()
        self._neutralize_callback_list()
        # 0x60036a13 → enter stock call site 0x60036a15 (calls *+0x134 = trampoline).
        # 0x60036a2b → already after call; jump straight to trampoline.
        dest = SYNTH_APP_IDLE if pc == 0x60036a2b else 0x60036a15
        self.regs['pc'] = dest
        note = {
            'kind': 'halt_divert',
            'from': hex(pc),
            'to': hex(dest),
            'divert': self.halt_diverts,
            'reason': reason,
            'assumption': 'Leave stock bra-self for synthetic app idle; not a physical wake',
        }
        self.milestones.append(note)
        self.events.append({'kind': 'model', 'result': note})
        return True

    def recover_corrupt_pc(self, reason):
        """One-shot recovery if PC lands in kernel stack / non-code (beyond2 failure mode)."""
        if not self.beyond_halt or self.stack_pc_recovers >= 2:
            return False
        pc = self.regs.get('pc', 0)
        in_stack = 0x62e00000 <= pc < 0x63000000
        in_break = pc == 0x60038ba6  # known 0xff padding after bad call
        if not (in_stack or in_break):
            return False
        self.stack_pc_recovers += 1
        self._arm_application_ready()
        self._neutralize_callback_list()
        self.regs['pc'] = SYNTH_APP_IDLE
        note = {
            'kind': 'corrupt_pc_recover',
            'from': hex(pc),
            'to': hex(SYNTH_APP_IDLE),
            'reason': reason,
            'recover': self.stack_pc_recovers,
            'assumption': 'PC left code space; return to synthetic idle once',
        }
        self.milestones.append(note)
        self.events.append({'kind': 'model', 'result': note})
        return True

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
            (0x98d01104, 0x2000),  # storage ready analogue
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
        try:
            ready = struct.unpack('<H', self.read(0x97f00000, 2))[0]
            if ready and ready != 0xffff:
                self.write(0x97f00000, struct.pack('<H', ready | 0xf))
        except ValueError:
            pass
        try:
            self.write(0x97f00095, b'\x01\x01\x01')
        except ValueError:
            pass
        try:
            self._ensure_peer_cpu_objects()
        except ValueError:
            pass
        # Arm as soon as CPU0 object exists so firmware prefers the ready idle path.
        if self.beyond_halt and not self.app_ready_armed:
            self._arm_application_ready()
        self.service_control_flow()

    def classify_outcome(self, result):
        pc = result['registers']['pc']
        if self.at_deeper_idle(pc) and self.app_ready_armed:
            return 'deeper_idle'
        if pc in FIRMWARE_HALTS and not self.beyond_halt:
            return 'self_halt'
        if pc in FIRMWARE_HALTS and self.halt_diverts >= self.max_halt_diverts:
            return 'parked_after_diverts'
        if pc in FIRMWARE_HALTS:
            return 'self_halt'
        return 'stable_under_budget'

    def run_once(self, *, limit, breakpoints=(), stop_pc=0xffffffff):
        require(ENGINE.is_file(), f'MN103 engine missing at {ENGINE}')
        self.service_control_flow()
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
        self.regs = result['registers']
        self.service_mmio()
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
        result = None
        while remaining > 0:
            chunk = min(remaining, 50000)
            result = self.run_once(limit=chunk, breakpoints=breakpoints)
            remaining = limit - self.steps
            if result['status'] == 'breakpoint':
                return result, 'breakpoint'
            if result['status'] == 'returned':
                return result, 'returned'
            if result['status'] == 'instruction_limit' and remaining <= 0:
                return result, self.classify_outcome(result)
            if result['status'] == 'instruction_limit':
                # Settled on trampoline early: keep burning budget there (success path).
                if self.at_deeper_idle():
                    continue
                continue
            if result['status'] == 'instruction_fault':
                if self.recover_corrupt_pc('instruction_fault'):
                    continue
                return result, 'instruction_fault'
            if result['status'] != 'memory_fault':
                return result, result['status']
            if len(self.auto_stubs) >= max_stubs:
                return result, 'stub_budget_exhausted'
            if not self.stub_fault(result['fault']):
                # Do not thrash divert on every fault (beyond2 lesson); recover only
                # if PC itself left code space.
                if self.recover_corrupt_pc('unhandled_fault'):
                    continue
                return result, 'unhandled_fault'
        return result, self.classify_outcome(result)


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
        'halt_diverts': state.halt_diverts,
        'stack_pc_recovers': state.stack_pc_recovers,
        'app_ready_armed': state.app_ready_armed,
        'synth_app_idle': hex(SYNTH_APP_IDLE),
        'milestones_tail': state.milestones[-20:],
        'beyond_halt': state.beyond_halt,
        'success_criteria': {
            'deeper_idle': (
                'outcome==deeper_idle AND pc in synth_app_idle AND app_ready_armed '
                'AND fault is null — synthetic app-schedulable steady state after '
                'clearing 0x988004a0 frontier, peer mask, and stock bra-self parks'
            ),
        },
        'how_to_debug': {
            'prefix': 'python tools/om3_boot.py prefix --out generated/om3-boot-prefix',
            'advance': 'python tools/om3_boot.py advance --limit 2000000 --out generated/om3-boot-advance',
            'idle': 'python tools/om3_boot.py idle --out generated/om3-boot-idle',
            'fullchain': 'python tools/om3_boot.py idle --limit 5000000 --out generated/om3-boot-fullchain',
            'breakpoint': 'python tools/om3_boot.py run --breakpoint 0xADDR --out generated/om3-boot-bp',
            'stay_halted': 'python tools/om3_boot.py idle --no-beyond-halt --out generated/om3-boot-halt',
        },
        'limits': [
            'Starts at downloaded main entry, not hardware reset/ROM.',
            'Auto-stubs zero-fill unmodeled MMIO/RAM; they enable debugging progress, not hardware fidelity.',
            'deeper_idle uses a synthetic bra-self trampoline as the app idle callback; not GUI/RTOS proof.',
            'No ISP, NAND physics, Wi-Fi, USB gadget, GUI, or real multi-core task schedule.',
            'stable_under_budget means the instruction budget completed without an unhandled fault; not a claimed UI idle.',
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    def add_common(p, default_limit):
        p.add_argument('--main', type=Path, default=STOCK_MAIN)
        p.add_argument('--out', type=Path,
                       help='report directory (created if missing; re-run overwrites om3-boot.json / auto-stubs.json / events.json)')
        p.add_argument('--limit', type=int, default=default_limit)
        p.add_argument('--breakpoint', action='append', default=[])
        p.add_argument('--strap-bits', type=int, default=7)
        p.add_argument('--max-stubs', type=int, default=400)
        p.add_argument('--beyond-halt', dest='beyond_halt', action='store_true', default=True,
                       help='leave bra-self parks and re-enter init (default on)')
        p.add_argument('--no-beyond-halt', dest='beyond_halt', action='store_false',
                       help='stay on 0x60036a13/0x60036a2b self-halt')
        p.add_argument('--max-halt-diverts', type=int, default=80)
        return p

    add_common(sub.add_parser('prefix', help='stop at first unmodeled access'), 20000)
    run_p = add_common(sub.add_parser('run', help='single chunk; optional auto-stub loop off by default'), 200000)
    run_p.add_argument('--auto-stub', action='store_true', help='stub faults and continue within --limit')
    add_common(sub.add_parser('advance', help='auto-stub until budget/breakpoint/unhandled fault'), 2_000_000)
    idle_p = add_common(sub.add_parser('idle', help='large advance; seek deeper_idle / stable_under_budget'), 5_000_000)
    idle_p.set_defaults(max_stubs=2500, max_halt_diverts=8)
    args = ap.parse_args(argv)

    image = load_main(args.main)
    state = OM3BootState(image, strap_bits=args.strap_bits)
    state.beyond_halt = bool(args.beyond_halt)
    state.max_halt_diverts = args.max_halt_diverts
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
        if args.out.exists() and not args.out.is_dir():
            raise ValueError(f'--out must be a directory, not a file: {args.out}')
        args.out.mkdir(parents=True, exist_ok=True)
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
        'halt_diverts': state.halt_diverts,
        'app_ready_armed': state.app_ready_armed,
        'fault': fault_dict(result.get('fault')),
        'out': str(args.out) if args.out else None,
    }, indent=2))
    if outcome in ('breakpoint', 'returned', 'stable_under_budget',
                   'self_halt', 'parked_after_diverts', 'deeper_idle'):
        return 0
    return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit(f'error: {exc}')
