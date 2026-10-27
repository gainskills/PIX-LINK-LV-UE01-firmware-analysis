"""Offline authentication patch on the fixed web candidate. Never accesses AP."""
import hashlib
import json
import lzma
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'security/auth-hardening'
BASE = 0x80000400
START = 0x8000e424


def sha(b): return hashlib.sha256(b).hexdigest()


def public_gate(addresses, deny_post=False, deny_query=False):
    words, fixups, labels = [], [], {}
    def emit(w): words.append(w)
    def branch(op, rs, rt, label):
        fixups.append((len(words), label))
        emit(op << 26 | rs << 21 | rt << 16)
        emit(0)
    # Native O32-compatible subset: preserve s0 and ra across strcmp calls.
    emit(0x27bdffe0)  # addiu sp,sp,-32
    emit(0xafbf001c)
    emit(0xafb00018)
    if deny_post:
        emit(0x8c820020)  # request method (HTTP frame +0x24, request at +4)
        emit(0x24030003)
        branch(4, 2, 3, 'reject')
    if deny_query:
        emit(0x8c82002c)  # raw query pointer; parsed table may still be lazy
        branch(4, 2, 0, 'query_done')
        emit(0x90420000)
        branch(5, 2, 0, 'reject')
        labels['query_done'] = len(words)
    emit(0x8c900028)  # lw s0,0x28(a0)
    emit(0x92020000)  # lbu v0,0(s0)
    emit(0x2403002f)  # li v1,'/'
    branch(5, 2, 3, 'compare')
    emit(0x26100001)  # remove at most one leading slash
    labels['compare'] = len(words)
    for address in addresses:
        address += 1  # compare canonical names after their resource-table slash
        emit(0x02002021)  # move a0,s0
        emit(0x3c050000 | address >> 16)
        emit(0x34a50000 | (address & 65535))
        emit(0x0c000000 | ((0x8015c59c >> 2) & 0x3ffffff))
        emit(0)
        branch(4, 2, 0, 'accept')
    labels['reject'] = len(words)
    if deny_query:
        branch(4, 0, 0, 'return')
        words[-1] = 0x24020000  # return zero in the branch delay slot
    else:
        emit(0x24020000)
        branch(4, 0, 0, 'return')
    labels['accept'] = len(words)
    emit(0x24020001)
    labels['return'] = len(words)
    epilogue=(0x8fbf001c,0x8fb00018,0x03e00008,0x27bd0020) if deny_query else (0x8fbf001c,0x8fb00018,0x27bd0020,0x03e00008,0)
    for w in epilogue:emit(w)
    for index, label in fixups:
        words[index] |= (labels[label] - index - 1) & 65535
    code = struct.pack('<' + 'I' * len(words), *words)
    assert len(code) <= 0x8000e4e0 - START
    return code.ljust(0x8000e4e0 - START, b'\0'), len(code)


def main():
    web = ROOT / 'web-update'
    source = (web / 'web-wps-jquery.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    assert sha(source) == '75581dd659ed625e7547ce91b89803f0983df49b7a537c0ebb7e1302bdf1178f'
    before = (web / 'main-web-update.NOT-FLASHABLE.bin').read_bytes()
    assert lzma.decompress(source[64 + 0x2440:], format=lzma.FORMAT_ALONE) == before
    meta = json.loads((web / 'build-manifest.json').read_text())
    names = ('/login.htm', '/js/app.js', '/favicon.ico')
    addresses = []
    for name in names:
        item = next(a for a in meta['resource_map'] if a['path'] == name)
        address = BASE + item['name_offset']
        assert before[item['name_offset']:].split(b'\0', 1)[0].decode() == name
        addresses.append(address)
    patched = bytearray(before)
    offset = 0x8000e560 - BASE
    expected = 0x0c000000 | ((0x8000e398 >> 2) & 0x3ffffff)
    assert struct.unpack_from('<2I', before, offset) == (expected, 0)
    struct.pack_into('<I', patched, offset, 0x24020001)
    gate, code_bytes = public_gate(addresses)
    patched[START - BASE:0x8000e4e0 - BASE] = gate
    ranges = [(START - BASE, 0x8000e4e0 - BASE), (offset, offset + 4)]
    assert all(a == b or any(lo <= i < hi for lo, hi in ranges)
               for i, (a, b) in enumerate(zip(before, patched)))
    compressed = lzma.compress(bytes(patched), format=lzma.FORMAT_ALONE, filters=[{
        'id': lzma.FILTER_LZMA1, 'dict_size': 8 * 1024 * 1024, 'lc': 3,
        'lp': 0, 'pb': 2, 'mode': lzma.MODE_NORMAL, 'nice_len': 128, 'mf': lzma.MF_BT4}])
    compressed = compressed[:5] + struct.pack('<Q', len(patched)) + compressed[13:]
    budget = 708764
    assert len(compressed) <= budget
    payload = source[64:64 + 0x2440] + compressed + b'\xff' * (budget - len(compressed))
    header = bytearray(source[:64])
    struct.pack_into('>I', header, 24, zlib.crc32(payload))
    struct.pack_into('>I', header, 4, 0)
    struct.pack_into('>I', header, 4, zlib.crc32(header))
    image = bytes(header) + payload
    assert len(image) == len(source) == 718108
    assert lzma.decompress(image[64 + 0x2440:], format=lzma.FORMAT_ALONE) == patched
    OUT.mkdir(exist_ok=True)
    (OUT / 'main-auth.NOT-FLASHABLE.bin').write_bytes(patched)
    (OUT / 'web-auth.uimage.NOT-FOR-FLASHING.bin').write_bytes(image)
    report = dict(status='offline authentication candidate; upload-before-auth remains unresolved',
                  source_uimage_sha256=sha(source), base_main_sha256=sha(before),
                  main_sha256=sha(patched), uimage_sha256=sha(image),
                  main_bytes=len(patched), uimage_bytes=len(image),
                  compressed_bytes=len(compressed), headroom_bytes=budget-len(compressed),
                  allowed_main_ranges=[[hex(a), hex(b)] for a, b in ranges],
                  public_paths=list(names), public_path_addresses=[hex(a) for a in addresses],
                  public_gate_code_bytes=code_bytes,
                  changed_main_bytes=sum(a != b for a, b in zip(before, patched)),
                  hardware_validated=False)
    (OUT / 'build-manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
