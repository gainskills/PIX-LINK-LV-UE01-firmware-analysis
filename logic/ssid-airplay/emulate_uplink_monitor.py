"""Offline monitor control-flow experiment; dependencies are explicit stubs.

Executes original monitor bytes. No sockets, AP actions or firmware writes.
"""
import hashlib
import json
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
from unicorn import mips_const as mc
ROOT = Path(__file__).resolve().parent
B = (ROOT.parent / 'main-decompressed.bin').read_bytes()
SHA = '2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
assert hashlib.sha256(B).hexdigest() == SHA
FLAG = 0x80212ca0
STATE = 0x802551d0

def reg(name): return getattr(mc, 'UC_MIPS_REG_' + name.upper())
def put(u, address, value): u.mem_write(address & 0x1fffffff, int(value & 0xffffffff).to_bytes(4, 'little'))
def get(u, address): return int.from_bytes(u.mem_read(address & 0x1fffffff, 4), 'little')

def trial(mode, configured, state, pending, requeue=False):
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0, 0x300000); u.mem_write(0x400, B)
    u.reg_write(reg('sp'), 0x802f0000)
    for a in [FLAG, STATE, 0x802551d4, 0x802551e0, 0x802551e4]: put(u, a, 0)
    put(u, FLAG, pending); put(u, STATE, state)
    # AP-mode-associated interface byte; kept false to avoid a distinct transition path.
    u.mem_write(0x25e4e9, b'\0')
    calls = []; iterations = [0]; final = {}
    def returned(value=0):
        u.reg_write(reg('v0'), value & 0xffffffff)
        u.reg_write(reg('pc'), u.reg_read(reg('ra')))
    def code(uc, address, size, unused):
        if address == 0x8014e280:
            iterations[0] += 1
            if iterations[0] == 3:
                final['pending_after_two_iterations'] = get(u, FLAG)
                u.emu_stop()
        elif address == 0x800082cc:
            assert u.reg_read(reg('a0')) == 0x011a0100
            u.mem_write(u.reg_read(reg('a1')) & 0x1fffffff, str(mode).encode() + b'\0')
            returned()
        elif address == 0x8015b5a8:
            pointer = u.reg_read(reg('a0')) & 0x1fffffff
            assert bytes(u.mem_read(pointer, 2)) == str(mode).encode() + b'\0'
            returned(mode)
        elif address == 0x80007728:
            assert u.reg_read(reg('a0')) == 0x04f20100
            put(u, u.reg_read(reg('a1')), configured); returned()
        elif address == 0x80150478:
            calls.append({'call': 'sleep', 'argument': u.reg_read(reg('a0'))}); returned()
        elif address == 0x80017134:
            calls.append({'call': 'relink', 'pending_on_entry': get(u, FLAG), 'state': get(u, STATE)})
            if requeue: put(u, FLAG, 1)
            # Deliberately return a negative-looking word: monitor does not interpret it.
            returned(0xffffffff)
        elif address == 0x8014de44:
            calls.append({'call': 'transition_notification'}); put(u, FLAG, 1); returned()
        elif address in [0x8014dcc0, 0x8014dc34, 0x8014dba4, 0x8014dff4, 0x8014e190]:
            calls.append({'call': hex(address), 'argument': u.reg_read(reg('a0'))}); returned()
    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(0x8014e1f8, 0x802f1000, timeout=3000000, count=100000)
    assert iterations[0] == 3, 'Monitor did not reach next iteration twice'
    relinks = [c for c in calls if c['call'] == 'relink']
    expected = 1 if mode == 1 and pending == 1 else 0
    assert len(relinks) == expected, (mode, configured, state, pending, calls)
    if mode == 1: assert final['pending_after_two_iterations'] == 0
    else: assert final['pending_after_two_iterations'] == pending
    return {'mode_numeric': mode, 'configured': configured, 'upstream_state_numeric': state,
            'initial_pending': pending, 'simulated_requeue_during_relink': requeue,
            'relink_calls': len(relinks), **final, 'calls': calls}

def notification_trial(driver_return):
    """Execute the original transition helper, with driver/printf/memset stubs."""
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0, 0x300000); u.mem_write(0x400, B)
    u.reg_write(reg('sp'), 0x802f0000); u.reg_write(reg('ra'), 0x802f1000)
    put(u, FLAG, 0)
    calls = []
    def string(address):
        return bytes(u.mem_read(address & 0x1fffffff, 128)).split(b'\0')[0].decode('ascii')
    def returned(value):
        u.reg_write(reg('v0'), value & 0xffffffff)
        u.reg_write(reg('pc'), u.reg_read(reg('ra')))
    def code(uc, address, size, unused):
        if address == 0x8014fef8:
            target, fill, length = [u.reg_read(reg(n)) for n in ['a0','a1','a2']]
            assert fill == 0 and length == 60
            u.mem_write(target & 0x1fffffff, bytes(length)); returned(target)
        elif address == 0x8014fca8:
            assert string(u.reg_read(reg('a0'))) == 'iwpriv %s %s %s \n'
            assert [string(u.reg_read(reg(n))) for n in ['a1','a2','a3']] == ['ra0','set','DisConnectAllSta=1']
            returned(0)
        elif address == 0x8011258c:
            assert u.reg_read(reg('a0')) == 3
            argv = u.reg_read(reg('a1'))
            args = [string(get(u, argv + i * 4)) for i in range(3)]
            assert args == ['ra0','set','DisConnectAllSta=1']
            calls.append(args); returned(driver_return)
    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(0x8014de44, 0x802f1000, timeout=3000000, count=10000)
    assert u.reg_read(reg('pc')) == 0x802f1000 and get(u, FLAG) == 1
    assert u.reg_read(reg('sp')) == 0x802f0000 and len(calls) == 1
    return {'modeled_driver_return': driver_return, 'driver_arguments': calls[0],
            'pending_after_return': get(u, FLAG)}

def repeated_status_trial(status):
    """Two repeated notifications; consuming the request is modeled explicitly."""
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0, 0x300000); u.mem_write(0x400, B)
    put(u, FLAG, 0); put(u, STATE, status); put(u, 0x802551d4, 0)
    driver_calls = []
    def returned(value=0):
        u.reg_write(reg('v0'), value & 0xffffffff)
        u.reg_write(reg('pc'), u.reg_read(reg('ra')))
    def string(address):
        return bytes(u.mem_read(address & 0x1fffffff, 128)).split(b'\0')[0].decode('ascii')
    def code(uc, address, size, unused):
        if address == 0x8014fef8:
            target, fill, length = [u.reg_read(reg(n)) for n in ['a0','a1','a2']]
            assert fill == 0 and length == 60
            u.mem_write(target & 0x1fffffff, bytes(length)); returned(target)
        elif address == 0x8014fca8: returned()
        elif address == 0x8014dcc0: returned()
        elif address == 0x8011258c:
            assert u.reg_read(reg('a0')) == 3
            argv = u.reg_read(reg('a1'))
            args = [string(get(u, argv + i * 4)) for i in range(3)]
            assert args == ['ra0','set','DisConnectAllSta=1']
            driver_calls.append(args); returned()
    u.hook_add(UC_HOOK_CODE, code)
    observations = []
    for i in range(2):
        u.reg_write(reg('sp'), 0x802f0000); u.reg_write(reg('ra'), 0x802f1000)
        u.reg_write(reg('a0'), status)
        u.emu_start(0x8014df3c, 0x802f1000, timeout=3000000, count=10000)
        assert u.reg_read(reg('pc')) == 0x802f1000
        assert u.reg_read(reg('sp')) == 0x802f0000
        expected_pending = int(status in [0, 2])
        assert get(u, FLAG) == expected_pending and get(u, STATE) == status
        observations.append({'notification_number': i + 1, 'state_after': get(u, STATE),
                             'pending_after': get(u, FLAG)})
        put(u, FLAG, 0)  # Modeled consumer, not native monitoring or hardware execution.
    assert len(driver_calls) == (2 if status in [0, 2] else 0)
    return {'initial_and_repeated_status': status, 'requests_consumed_between_callbacks': True,
            'driver_calls': len(driver_calls), 'observations': observations}

if __name__ == '__main__':
    cases = [trial(1, configured, state, pending)
             for configured in [0, 1] for state in [0, 1, 2] for pending in [0, 1]]
    cases += [trial(mode, 1, 2, 1) for mode in [0, 2]]
    cases += [trial(1, 1, 2, 1, requeue=True)]
    notifications = [notification_trial(value) for value in [0, -1]]
    repeated = [repeated_status_trial(value) for value in [0, 1, 2]]
    result = {'status': 'PASS: 15 monitor, 2 transition-helper and 3 repeated-status cases; dependencies stubbed',
              'source_sha256': SHA, 'entry': '0x8014e1f8', 'cases': cases, 'notification_cases': notifications, 'repeated_status_cases': repeated,
              'limits': ['Executes two iterations with constant modeled state/configuration.',
                         'Config readers, conversion, sleep, notification, GPIO helpers and relink are stubbed.',
                         'Negative-looking relink return is synthetic; native helper has no defined success/error result.',
                         'Requeue is a synthetic interleaving, not proof of actual concurrent setter execution.',
                         'No full driver emulation, physical PHY state, fault reproduction or recovery testing.',
                         'Repeated notifications are injected; this does not prove callers emit duplicates in a stable connection.',
                         'No AP access or firmware/configuration writes.']}
    (ROOT / 'uplink-monitor-experiment.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'repeater_matrix_cases': 12, 'repeated_status_cases': len(repeated), 'transition_helper_cases': len(notifications),
                      'other_mode_cases': 2, 'requeue_cases': 1,
                      'requeue_after_two_iterations': cases[-1]['pending_after_two_iterations']}, indent=2))
