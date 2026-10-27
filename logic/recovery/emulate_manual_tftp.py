"""Bounded native TFTP command experiment, with network/cache/environment stubs.

Not a loader tool or a validated hardware procedure. No device access.
"""
import json
from emulate_boot_paths import ROOT, SHA, STACK, machine, reg, put, string, UC_HOOK_CODE


def run_case(autostart, dirty, network_result):
    u = machine()
    events = []
    end = 0x802d0000
    u.reg_write(reg('t9'), 0xbc00c020)
    u.reg_write(reg('ra'), end)
    u.reg_write(reg('a0'), 0)
    u.reg_write(reg('a1'), 0)
    u.reg_write(reg('a2'), 1)
    u.reg_write(reg('a3'), 0x802e0000)
    put(u, 0x802e0000, 0x802e0100)
    u.mem_write(0x2e0100, b'tftpboot\0')
    u.mem_write(0x2e0200, (autostart or '').encode() + b'\0')
    put(u, 0xbc017040, dirty)
    put(u, 0xbc0160e0, 0x80100000)
    put(u, 0xbc046dcc, max(network_result, 0))
    for address in (0xbc017168, 0xbc01716c, 0xbc046da4, 0xbc046da8, 0xbc017164):
        put(u, address, 0)
    for address in (0xbc017124, 0xbc0170e4, 0xbc017144):
        u.mem_write(address & 0x1fffffff, b'\0')
    u.mem_write(0x1c045b54, b'OFFLINE-ONLY.bin\0')

    def returned(value=0):
        u.reg_write(reg('v0'), value & 0xffffffff)
        u.reg_write(reg('pc'), u.reg_read(reg('ra')))

    def code(uc, address, size, unused):
        if address == 0xbc00d73c:
            key = string(u, u.reg_read(reg('a0')))
            assert key in ('loadaddr', 'autostart'), key
            events.append({'operation': 'getenv_model', 'key': key})
            returned(0x802e0200 if key == 'autostart' and autostart is not None else 0)
        elif address == 0xbc005048:
            assert u.reg_read(reg('a0')) == 3
            events.append({'operation': 'network_model', 'result': network_result})
            returned(network_result)
        elif address == 0xbc012418:
            assert u.reg_read(reg('a0')) == 0x80100000
            assert u.reg_read(reg('a1')) == network_result
            events.append({'operation': 'cache_model'})
            returned()
        elif address == 0xbc00d674:
            events.append({'operation': 'setenv_model', 'key': string(u, u.reg_read(reg('a0')))})
            returned()
        elif address == 0xbc010300:
            events.append({'operation': 'environment_save_intercepted'})
            returned()
        elif address == 0xbc00ad44:
            events.append({'operation': 'bootm_intercepted'})
            returned()
        elif address == 0xbc00dffc:
            returned()
        elif address in (0xbc009488, 0xbc008db8):
            raise AssertionError('Unexpected direct Flash write/erase entry')

    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(0xbc00c020, end, timeout=3000000, count=10000)
    assert u.reg_read(reg('pc')) == end
    assert u.reg_read(reg('sp')) == STACK
    boot_count = sum(e['operation'] == 'bootm_intercepted' for e in events)
    save_count = sum(e['operation'] == 'environment_save_intercepted' for e in events)
    assert boot_count == int(network_result > 0 and autostart == 'yes')
    assert save_count == int(network_result > 0 and autostart == 'yes' and dirty != 0)
    result = u.reg_read(reg('v0'))
    assert result == int(network_result < 0)
    return {'modeled_autostart': autostart, 'modeled_dirty_flag': dirty,
            'modeled_network_result': network_result, 'command_return': result,
            'bootm_calls': boot_count, 'environment_save_calls': save_count,
            'events': events, 'stack_restored': True}


if __name__ == '__main__':
    cases = [run_case(a, d, n) for a in (None, 'no', 'yes')
             for d in (0, 1) for n in (-1, 0, 718108)]
    report = {'status': 'PASS: eighteen original manual TFTP command models',
              'boot_prefix_sha256': SHA, 'cases': cases,
              'limits': [
                  'Runs original TFTP command, not menu caller, environment editor or bootm.',
                  'Network return, address, environment and dirty flag are synthetic inputs.',
                  'Cache, environment save and bootm backends are intercepted; no transfer occurs.',
                  'Absent/no autostart returns without saving or booting in these models only.',
                  'Zero-length network return also returns command success; return code alone is insufficient.',
                  'Does not validate serial access, live environment, RAM overlap or real recovery.',
                  'Failure return must be checked by a future operator; GPIO caller remains unsafe.',
                  'No device access, packets, AP changes, Flash operations or new firmware images.']}
    (ROOT / 'manual-tftp-experiment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])
