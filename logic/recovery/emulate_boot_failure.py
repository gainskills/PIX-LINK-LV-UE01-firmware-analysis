"""Offline original Upgrade Mode failure flow; no network/device/Flash access.

Execute the real TFTP command and caller, replacing NetLoop and I/O backends.
The negative NetLoop result and download-size globals are synthetic inputs.
"""
import json
from emulate_boot_paths import ROOT, SHA, STACK, machine, reg, put, string, UC_HOOK_CODE


def failed_download(download_size, write_result):
    u = machine()
    calls = []
    command_returns = []
    u.reg_write(reg('s4'), 0)
    u.reg_write(reg('s5'), STACK + 0x38)
    u.reg_write(reg('s2'), 5)
    put(u, STACK + 0x3c, 0x802e0000)
    put(u, STACK + 0x40, 0x802e0100)
    u.mem_write(0x2e0000, b'80100000\0')
    u.mem_write(0x2e0100, b'OFFLINE-ONLY.bin\0')
    put(u, 0xbc046dcc, download_size)

    def returned(value=0):
        u.reg_write(reg('v0'), value & 0xffffffff)
        u.reg_write(reg('pc'), u.reg_read(reg('ra')))

    def code(uc, address, size, unused):
        if address == 0xbc00c020:
            calls.append({'operation': 'original_tftp_command_entered'})
        elif address == 0xbc00d73c:  # getenv: model absent loadaddr override
            assert string(u, u.reg_read(reg('a0'))) == 'loadaddr'
            returned(0)
        elif address == 0xbc010a20:
            assert string(u, u.reg_read(reg('a0'))) == '80100000'
            returned(0x80100000)
        elif address == 0xbc004e54:  # bounded filename copy backend
            target = u.reg_read(reg('a0'))
            value = string(u, u.reg_read(reg('a1'))).encode() + b'\0'
            assert len(value) <= u.reg_read(reg('a2'))
            u.mem_write(target & 0x1fffffff, value)
            returned(target)
        elif address == 0xbc005048:
            assert u.reg_read(reg('a0')) == 3
            calls.append({'operation': 'NetLoop_stub', 'result': -1})
            returned(-1)
        elif address == 0xbc002308:
            command_returns.append(u.reg_read(reg('v0')))
        elif address == 0xbc009488:
            source, offset, length = [u.reg_read(reg(n)) for n in ('a0', 'a1', 'a2')]
            assert (source, offset, length) == (0x80100000, 0x50000, download_size)
            calls.append({'operation': 'flash_write_stub', 'offset': hex(offset),
                          'length': length, 'result': write_result})
            returned(write_result)
        elif address == 0xbc008db8:
            offset, length = [u.reg_read(reg(n)) for n in ('a0', 'a1')]
            assert (offset, length) == (0x30000, 0x10000)
            calls.append({'operation': 'flash_erase_stub', 'offset': hex(offset), 'length': length})
            returned()
        elif address in (0xbc00dffc, 0xbc003f40):
            returned()
        elif address == 0xbc011394:
            assert string(u, u.reg_read(reg('a1'))) == '0x%X'
            u.mem_write(u.reg_read(reg('a0')) & 0x1fffffff,
                        ('0x%X' % u.reg_read(reg('a2'))).encode() + b'\0')
            returned()
        elif address == 0xbc00ad44:
            calls.append({'operation': 'bootm_intercepted'})
            u.emu_stop()

    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(0xbc0022ec, 0xbc002b00, timeout=3000000, count=10000)
    assert command_returns == [1], command_returns
    assert [c['operation'] for c in calls] == [
        'original_tftp_command_entered', 'NetLoop_stub', 'flash_write_stub',
        'flash_erase_stub', 'bootm_intercepted'], calls
    assert u.reg_read(reg('sp')) == STACK
    return {'modeled_download_size': download_size, 'modeled_write_result': write_result,
            'observed_tftp_command_return': command_returns[0], 'calls': calls}


if __name__ == '__main__':
    cases = [failed_download(length, result) for length in (0, 718108) for result in (0, -1)]
    report = {
        'status': 'PASS: four original TFTP failure-return and Upgrade Mode caller experiments',
        'boot_prefix_sha256': SHA, 'cases': cases,
        'limits': [
            'NetLoop -1, download-size globals and Flash backend results are modeled inputs.',
            'Does not prove a missing server/file or timeout returns rather than retries forever.',
            'Flash write and erase backends are intercepted; actual Flash effects are not emulated.',
            'A stale nonzero size is hypothetical, not observed on the device.',
            'Not the Ethernet failure root cause or a firmware fix.',
            'No device access, packets, reboots, firmware images or Flash operations.']}
    (ROOT / 'boot-failure-experiment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'tftp_failure_return': 1,
                      'erase_backend_reached_in_all_cases': True, 'device_access': False}, indent=2))
