"""Offline check of original driver memdump handler; no device/network access."""
import json
import struct
from emulate_native_relink import IMAGE, SHA, ROOT, reg, Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE

ENTRY = 0x80079f50
RETURN = 0x802f1000
TARGET = 0x8025e740
assert struct.unpack_from('<II', IMAGE, 0x1ef5b0) == (0x801718b8, ENTRY)
assert IMAGE[0x1714b8:0x1714c0] == b'memdump\0'


def trial(argument):
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0, 0x300000)
    u.mem_write(0x400, IMAGE)
    u.reg_write(reg('sp'), 0x802f0000)
    u.reg_write(reg('ra'), RETURN)
    u.reg_write(reg('cp0_status'), 0x1000ff01)
    u.reg_write(reg('a0'), 0x802c0000)  # modeled adapter pointer
    u.reg_write(reg('a1'), 0 if argument is None else 0x802e0000)
    if argument is not None:
        u.mem_write(0x2e0000, argument.encode() + b'\0')
    evidence = {'argument': argument, 'parser_calls': 0, 'printf_calls': 0,
                'target_reads': 0, 'writes_outside_stack': []}
    recent = []

    def read(uc, access, address, size, value, unused):
        if (address & 0x1fffffff) < (TARGET & 0x1fffffff) + 4 and (
                address & 0x1fffffff) + size > (TARGET & 0x1fffffff):
            evidence['target_reads'] += 1

    def write(uc, access, address, size, value, unused):
        physical = address & 0x1fffffff
        if not 0x2ef000 <= physical < 0x2f0000:
            evidence['writes_outside_stack'].append(hex(address))

    def code(uc, address, size, unused):
        recent.append(hex(address))
        del recent[:-12]
        if address == 0x800fe9ac:
            evidence['parser_calls'] += 1
            assert uc.reg_read(reg('a1')) == 0 and uc.reg_read(reg('a2')) == 16
            uc.reg_write(reg('v0'), 0 if argument is None else int(argument, 16))
            uc.reg_write(reg('pc'), uc.reg_read(reg('ra')))
        elif address == 0x8014fca8:
            evidence['printf_calls'] += 1
            uc.reg_write(reg('v0'), 0)
            uc.reg_write(reg('pc'), uc.reg_read(reg('ra')))

    u.hook_add(UC_HOOK_CODE, code)
    u.hook_add(UC_HOOK_MEM_READ, read)
    u.hook_add(UC_HOOK_MEM_WRITE, write)
    try:
        u.emu_start(ENTRY, RETURN, timeout=3000000, count=10000)
    except Exception as error:
        raise RuntimeError(f'argument={argument!r}, pc={u.reg_read(reg("pc")):#x}, recent={recent}') from error
    assert u.reg_read(reg('pc')) == RETURN
    assert u.reg_read(reg('sp')) == 0x802f0000
    assert u.reg_read(reg('v0')) == 1
    assert evidence['parser_calls'] == 1
    assert evidence['printf_calls'] == int(argument is None)
    assert evidence['target_reads'] == 0
    assert evidence['writes_outside_stack'] == []
    return evidence


if __name__ == '__main__':
    cases = [trial(value) for value in ('8025e740', '0', None)]
    report = {'status': 'PASS: three original memdump handler experiments',
              'source_sha256': SHA, 'handler': hex(ENTRY), 'table_offset': '0x1ef5b0',
              'cases': cases,
              'conclusion': 'Handler parses input then returns 1 without reading the requested address.',
              'limits': ['Invokes handler directly; does not test full iwpriv transport/dispatch.',
                         'Numeric parser and null-argument warning printf are modeled/intercepted.',
                         'Native parser execution raised a local emulator CPU exception; not a device finding.',
                         'No MMIO is mapped; hardware register access would fail the experiment.',
                         'Does not rule out other undocumented RAM/PHY access paths.',
                         'No AP access, commands, packets, image generation or firmware changes.']}
    (ROOT / 'memdump-entry-experiment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])
