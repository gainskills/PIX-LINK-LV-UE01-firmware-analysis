"""Native auth regression tests; synthetic accounts, no HTTP/device access."""
import argparse
import base64
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
from unicorn import mips_const as mc

ROOT = Path(__file__).resolve().parent.parent


def run(main, path, authorization=None, cookie=False, default=True, early=False, method=1, early_entry=0x800103f8):
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0, 0x400000)
    u.mem_write(0x400, main)
    reg = lambda n: getattr(mc, 'UC_MIPS_REG_' + n.upper())
    def put(a, v): u.mem_write(a & 0x1fffffff, struct.pack('<I', v))
    def text(a, s): u.mem_write(a & 0x1fffffff, s.encode() + b'\0')
    request, stack, end = 0x80300000, 0x803f0000, 0x803e0000
    if early: request = stack + 4
    put(request + 4, 0x0101a8c0)
    put(request + 0x28, request + 0x200)
    put(request + 0x20, method)
    if early: put(stack + 0x20, 0x1234)
    text(request + 0x200, path)
    if authorization is not None:
        put(request + (0x58 if cookie else 0x4c), request + 0x400)
        text(request + 0x400, ('Authorization=' if cookie else '') + authorization)
    put(0x801ed300, 1)
    text(0x8025e214, 'admin')
    text(0x8025e224, 'admin' if default else 'fixture-pass')
    put(0x8025e238, 100)
    u.reg_write(reg('a0'), request)
    u.reg_write(reg('sp'), stack)
    u.reg_write(reg('ra'), end)
    if early:
        u.reg_write(reg('v0'), method)
        u.reg_write(reg('v1'), 3)
    reached = []
    outcome = []
    def returned(v=0):
        u.reg_write(reg('v0'), v)
        u.reg_write(reg('pc'), u.reg_read(reg('ra')))
    def hook(uc, pc, size, data):
        if early and pc in (0x80010400, 0x8001075c, 0x8000fe30):
            if pc == 0x80010400:
                assert u.reg_read(reg('v1')) == 0x1234
                outcome.append('body')
            elif pc == 0x8001075c: outcome.append('normal_nonpost')
            else: outcome.append('cleanup')
            u.emu_stop()
        elif early and pc == 0x8000f838:
            outcome.append(u.reg_read(reg('a1')))
            # Execute the native response wrapper, intercept only its I/O backends.
        elif early and pc == 0x8000ebb8:
            assert u.reg_read(reg('a1')) == 401
            returned()
        elif early and pc == 0x8000f6ac:
            assert u.reg_read(reg('a1')) == 401
            assert bytes(u.mem_read(u.reg_read(reg('a3')) & 0x1fffffff, 13)) == b'Unauthorized\0'
            returned()
        elif pc == 0x80007728:
            key, dest = u.reg_read(reg('a0')), u.reg_read(reg('a1'))
            assert key in (0x01040100, 0x010b0200, 0x01010200), hex(key)
            if key == 0x01040100: put(dest, 0)
            else: text(dest, 'admin' if default or key == 0x010b0200 else 'fixture-pass')
            returned()
        elif pc == 0x8015d8e0: returned(1000)
        elif pc == 0x801172d0: returned(request + 0x600)
        elif pc == 0x80005028: returned()
        elif pc in (0x80015268, 0x80015660, 0x80006614):
            raise AssertionError('Unexpected Flash backend')
        elif pc in (0x8000e398, 0x80117ba0): reached.append(hex(pc))
    u.hook_add(UC_HOOK_CODE, hook)
    u.emu_start(early_entry if early else 0x8000e4e0, end, timeout=3000000, count=100000)
    if not early: assert u.reg_read(reg('pc')) == end
    else: assert outcome and outcome[-1] in ('body', 'normal_nonpost', 'cleanup'), outcome
    assert u.reg_read(reg('sp')) == stack
    return (outcome if early else u.reg_read(reg('v0'))), reached


def cases(main):
    basic = lambda s: 'Basic ' + base64.b64encode(s.encode()).decode()
    inputs = [
        ('anonymous_config', '/profile.bin', None, False, True, 401),
        ('wrong_password', '/profile.bin', basic('admin:wrong'), False, True, 401),
        ('valid_default_credentials', '/profile.bin', basic('admin:admin'), False, True, 0),
        ('valid_changed_credentials', '/profile.bin', basic('admin:fixture-pass'), False, False, 0),
        ('anonymous_changed_credentials', '/profile.bin', None, False, False, 401),
        ('valid_cookie', '/index.htm', basic('admin:admin') + '; other=1', True, True, 0),
        ('wrong_cookie', '/index.htm', basic('admin:wrong'), True, True, 401),
        ('login_public', '/login.htm', None, False, True, 0),
        ('app_script_public', '/js/app.js', None, False, False, 0),
        ('favicon_public', '/favicon.ico', None, False, False, 0),
        ('substring_not_public', '/profile.bin/login', None, False, False, 401),
        ('app_suffix_not_public', '/js/app.js.extra', None, False, False, 401),
        ('normalized_login_public', 'login.htm', None, False, False, 0),
        ('normalized_script_public', 'js/app.js', None, False, False, 0),
        ('normalized_favicon_public', 'favicon.ico', None, False, False, 0),
        ('normalized_config_private', 'profile.bin', None, False, True, 401),
        ('normalized_wrong_password', 'profile.bin', basic('admin:wrong'), False, True, 401),
        ('normalized_valid_cookie', 'index.htm', basic('admin:admin'), True, True, 0),
        ('double_slash_not_public', '//login.htm', None, False, False, 401),
        ('login_suffix_not_public', 'login.htm.extra', None, False, False, 401),
    ]
    results = []
    for name, path, auth, cookie, default, expected in inputs:
        actual, reached = run(main, path, auth, cookie, default)
        results.append(dict(case=name, expected=expected, actual=actual,
                            passed=actual == expected, native_helpers_entered=reached))
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--main', type=Path, default=ROOT / 'main-decompressed.bin')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = cases(args.main.read_bytes())
    if args.report: args.report.write_text(json.dumps(result, indent=2) + '\n')
    for item in result: print(json.dumps(item))
    raise SystemExit(0 if all(r['passed'] for r in result) else 1)
