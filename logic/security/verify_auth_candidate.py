"""Independent verification of the written authentication candidate."""
import hashlib
import json
import lzma
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'security/auth-hardening'
BASE = 0x80000400


def sha(data): return hashlib.sha256(data).hexdigest()


def verify():
    old_image = (ROOT / 'web-update/web-wps-jquery.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    old = (ROOT / 'web-update/main-web-update.NOT-FLASHABLE.bin').read_bytes()
    assert sha(old_image) == '75581dd659ed625e7547ce91b89803f0983df49b7a537c0ebb7e1302bdf1178f'
    assert sha(old) == '3385f574b110096a4446cf6beef365c95c63e41ac5be80d1cca5b5d8842d81b8'
    new = (OUT / 'main-auth.NOT-FLASHABLE.bin').read_bytes()
    image = (OUT / 'web-auth.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    manifest = json.loads((OUT / 'build-manifest.json').read_text())
    assert len(new) == len(old) == 2174360 and len(image) == len(old_image) == 718108
    assert image[64:64+0x2440] == old_image[64:64+0x2440]
    assert all(a == b for i, (a, b) in enumerate(zip(image[:64], old_image[:64]))
               if i not in range(4, 8) and i not in range(24, 28))
    header = bytearray(image[:64]); hcrc = struct.unpack_from('>I', header, 4)[0]
    header[4:8] = bytes(4)
    assert zlib.crc32(header) == hcrc
    assert zlib.crc32(image[64:]) == struct.unpack_from('>I', image, 24)[0]
    stream = image[64+0x2440:]
    assert stream[:5] == old_image[64+0x2440:64+0x2445]
    assert struct.unpack_from('<Q', stream, 5)[0] == len(new)
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    assert decoder.decompress(stream, max_length=len(new)+1) == new and decoder.eof
    compressed = len(stream) - len(decoder.unused_data)
    assert decoder.unused_data == b'\xff' * (708764-compressed)
    ranges = [(0xe024, 0xe0e0), (0xe160, 0xe164)]
    changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    assert len(changed) == 164
    assert all(any(lo <= i < hi for lo, hi in ranges) for i in changed)
    assert struct.unpack_from('<4I', new, 0xe160) == (0x24020001, 0, 0x1040006a, 0x00002021)
    code = new[0xe024:0xe024+156]
    assert new[0xe024+156:0xe0e0] == bytes(32)
    # Dependencies are declared in requirements.txt.
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
    instructions = list(Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN).disasm(code, 0x8000e424))
    assert len(instructions) == 39
    calls = [i for i in instructions if i.mnemonic == 'jal']
    assert len(calls) == 3 and all(i.op_str == '0x8015c59c' for i in calls)
    for i in instructions:
        if i.mnemonic.startswith('b'):
            target = int(i.op_str.split(',')[-1].strip(), 16)
            assert 0x8000e424 <= target < 0x8000e424+156
        if i.mnemonic == 'sw': assert '($sp)' in i.op_str
    for address, name in [(0x8016718c, b'/login.htm'), (0x801670bc, b'/js/app.js'), (0x80166f68, b'/favicon.ico')]:
        assert new[address-BASE:].split(b'\0', 1)[0] == name
        # Three immediate address loads point to canonical strings after '/'.
        target = address + 1
        pair = struct.pack('<II', 0x3c050000 | target >> 16, 0x34a50000 | (target & 65535))
        assert code.count(pair) == 1
    for key, value in [('source_uimage_sha256', sha(old_image)), ('base_main_sha256', sha(old)),
                       ('main_sha256', sha(new)), ('uimage_sha256', sha(image)),
                       ('compressed_bytes', compressed), ('headroom_bytes', 708764-compressed)]:
        assert manifest[key] == value, key
    result = dict(status='PASS: independent authentication artifact verification',
                  changed_main_bytes=len(changed), uimage_sha256=sha(image),
                  compressed_bytes=compressed, headroom_bytes=708764-compressed,
                  upload_before_auth_fixed=False, hardware_validated=False)
    (OUT / 'public-gate-disassembly.txt').write_text('\n'.join(
        f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in instructions)+'\n')
    (OUT / 'verification-results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': verify()
