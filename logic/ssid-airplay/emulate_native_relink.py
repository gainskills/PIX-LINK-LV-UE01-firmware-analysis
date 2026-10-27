"""Offline original-code experiment; no sockets, device commands or image writes.

MMIO is a deliberately simple model, not a hardware timing simulation.
Native relink and native MDIO write machine code are executed unchanged.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import mips_const as mc
ROOT = Path(__file__).resolve().parent
IMAGE = (ROOT.parent / 'main-decompressed.bin').read_bytes()
SHA = '2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
assert hashlib.sha256(IMAGE).hexdigest() == SHA, 'Unexpected original firmware'
START = 0x80017134
RETURN = 0x802f1000
GPIO = 0x10000060
PCR0 = 0x101100c0
PCR1 = 0x101100c4
POA = 0x10110080

def reg(name):
    return getattr(mc, 'UC_MIPS_REG_' + name.upper())

def word(value):
    return struct.pack('<I', value & 0xffffffff)

def trial(name, link_up, complete_after):
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0, 0x300000)
    u.mem_map(GPIO & ~4095, 4096)
    u.mem_map(PCR0 & ~4095, 4096)
    u.mem_write(0x400, IMAGE)
    u.reg_write(reg('sp'), 0x802f0000)
    u.reg_write(reg('ra'), RETURN)
    u.reg_write(reg('cp0_status'), 0x1000ff01)
    u.mem_write(GPIO, word(0x80))
    u.mem_write(POA, word(0x83818301 if link_up else 0x81808100))
    commands = []
    prints = []
    delays = []
    counters = {'completion_polls': 0, 'current_polls': 0, 'poa_reads': 0}
    def read(uc, access, address, size, value, unused):
        physical = address & 0x1fffffff
        if physical == POA:
            counters['poa_reads'] += 1
        if physical == PCR1:
            assert not uc.reg_read(reg('cp0_status')) & 1
            counters['completion_polls'] += 1
            counters['current_polls'] += 1
            done = complete_after is not None and counters['current_polls'] > complete_after
            uc.mem_write(PCR1, word(1 if done else 0))
    def write(uc, access, address, size, value, unused):
        physical = address & 0x1fffffff
        if physical == PCR0:
            assert not uc.reg_read(reg('cp0_status')) & 1
            commands.append({'phy': value & 31, 'register': (value >> 8) & 31,
                             'value': value >> 16, 'operation': hex(value & 0x6000)})
            counters['current_polls'] = 0
    def code(uc, address, size, unused):
        if address == 0x8014fca8:
            assert uc.reg_read(reg('cp0_status')) & 1
            pointer = uc.reg_read(reg('a0')) & 0x1fffffff
            fmt = bytes(uc.mem_read(pointer, 100)).split(b'\0')[0].decode('ascii')
            prints.append({'format': fmt, 'phy': uc.reg_read(reg('a2'))})
            uc.reg_write(reg('v0'), 0x1234)
            uc.reg_write(reg('pc'), uc.reg_read(reg('ra')))
        elif address == 0x80150478:
            assert uc.reg_read(reg('cp0_status')) & 1
            delays.append(uc.reg_read(reg('a0')))
            uc.reg_write(reg('v0'), 0)
            uc.reg_write(reg('pc'), uc.reg_read(reg('ra')))
    u.hook_add(UC_HOOK_MEM_READ, read)
    u.hook_add(UC_HOOK_MEM_WRITE, write)
    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(START, RETURN, timeout=3000000, count=100000)
    returned = u.reg_read(reg('pc')) == RETURN
    if complete_after is not None:
        expected = [(p, 0, value) for value in [0x3900, 0x3300] for p in range(5)]
        assert [(x['phy'], x['register'], x['value']) for x in commands] == expected
        assert all(x['operation'] == '0x2000' for x in commands)
        assert returned and delays == [300] and len(prints) == 10
        assert sum('link Up' in x['format'] for x in prints) == 5
        assert counters['poa_reads'] == 0
        assert u.reg_read(reg('sp')) == 0x802f0000
        assert u.reg_read(reg('cp0_status')) == 0x1000ff01
        assert struct.unpack('<I', u.mem_read(GPIO, 4))[0] == 0x80
    else:
        assert not returned and len(commands) == 1 and not prints and not delays
        assert 0x80015a44 <= u.reg_read(reg('pc')) <= 0x80015a50
        assert not u.reg_read(reg('cp0_status')) & 1
    return {'case': name, 'simulated_link_up': link_up,
            'simulated_completion_after_polls': complete_after,
            'returned_within_instruction_budget': returned,
            'commands': commands, 'prints': prints, 'delay_arguments': delays,
            'counters': counters, 'final_pc': hex(u.reg_read(reg('pc'))),
            'final_interrupt_enable': bool(u.reg_read(reg('cp0_status')) & 1)}

if __name__ == '__main__':
    cases = [trial('link_down_completion_immediate', False, 0),
             trial('link_up_completion_immediate', True, 0),
             trial('link_down_completion_delayed', False, 20),
             trial('controller_never_completes', False, None)]
    # Only physical link state differs in the first two models; observed behavior must match.
    for key in ['commands', 'prints', 'delay_arguments', 'counters']:
        assert cases[0][key] == cases[1][key], key
    result = {'status': 'PASS: four original-code experiments; not a device test',
              'source_sha256': SHA, 'relink_entry': hex(START),
              'native_write_entry': '0x800159e0', 'cases': cases,
              'limits': ['MMIO is simulated; no hardware timing or PHY analog behavior is modeled.',
                         'printf and sleep are intercepted; sleep argument 300 has no confirmed wall-clock unit.',
                         'Up/Down in this helper are operation logs, not link-state measurements.',
                         'The never-completes case hits an emulator instruction budget; the original polling loop has no counter.',
                         'No proof that this helper or controller stall caused the X99 fault.',
                         'No network access, firmware modification, flashing or AP configuration changes.']}
    (ROOT / 'native-relink-experiment.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'cases': len(cases),
                      'link_state_changes_helper_behavior': False,
                      'noncompletion_returned': cases[-1]['returned_within_instruction_budget'],
                      'noncompletion_interrupts_enabled': cases[-1]['final_interrupt_enable']}, indent=2))
