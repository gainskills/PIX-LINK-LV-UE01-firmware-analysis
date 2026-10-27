"""Second-stage offline candidate: authenticate POST before multipart handling."""
import json
import lzma
import struct
import zlib
from build_auth_candidate import ROOT, BASE, public_gate, sha

OUT = ROOT / 'security/preupload-hardening'


def guard():
    words, labels, fixups = [], {}, []
    def emit(w): words.append(w)
    def jump(address, call=False):
        emit((0x0c000000 if call else 0x08000000) | ((address >> 2) & 0x3ffffff))
    def branch(label):
        fixups.append((len(words), label)); emit(0x10400000); emit(0)
    emit(0x8fa20024); emit(0x24030003)
    # beq v0,v1,post
    fixups.append((len(words), 'post')); emit(0x10430000); emit(0)
    jump(0x8001075c); emit(0)
    labels['post'] = len(words)
    jump(0x8000e4e0, True); emit(0x27a40004)
    branch('body')
    emit(0x00402821)  # a1=auth status
    emit(0x3c068016); emit(0x34c68bb0)  # Unauthorized
    emit(0x00c04021)  # t0=message
    emit(0x00003821)  # a3=0
    jump(0x8000f838, True); emit(0x27a40004)
    jump(0x8000fe30); emit(0)
    labels['body'] = len(words)
    jump(0x80010400); emit(0x8fa30020)  # replay overwritten/clobbered body offset load
    for i, label in fixups: words[i] |= (labels[label] - i - 1) & 65535
    code = struct.pack('<'+'I'*len(words), *words)
    assert len(code) <= 0x8c
    return code.ljust(0x8c, b'\0'), len(code)


def main():
    parent = ROOT / 'security/auth-hardening'
    old = (parent / 'main-auth.NOT-FLASHABLE.bin').read_bytes()
    image = (parent / 'web-auth.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    assert sha(image) == 'a8d20ebf90669c86fb79ce85abf662b856f2d07a1c4fb40d5c0eb208f91951b0'
    assert lzma.decompress(image[64+0x2440:], format=lzma.FORMAT_ALONE) == old
    patched = bytearray(old)
    # The former default-account helper is unused after stage one.
    call = struct.pack('<I', 0x0c000000 | ((0x8000e398 >> 2) & 0x3ffffff))
    original = (ROOT / 'main-decompressed.bin').read_bytes()
    assert [i for i in range(0, 0x164000, 4) if original[i:i+4] == call] == [0xe160]
    assert patched[0xe160:0xe164] == struct.pack('<I', 0x24020001)
    code, code_size = guard()
    patched[0x8000e398-BASE:0x8000e424-BASE] = code
    gate, gate_size = public_gate([0x8016718c, 0x801670bc, 0x80166f68], deny_post=True, deny_query=True)
    patched[0x8000e424-BASE:0x8000e4e0-BASE] = gate
    assert struct.unpack_from('<2I', old, 0x800103f8-BASE) == (0x144300d8, 0x8fa30020)
    struct.pack_into('<I', patched, 0x800103f8-BASE, 0x08000000 | ((0x8000e398 >> 2) & 0x3ffffff))
    ranges = [(0xdf98, 0xe0e0), (0xfff8, 0xfffc)]
    assert all(a == b or any(lo <= i < hi for lo, hi in ranges)
               for i, (a, b) in enumerate(zip(old, patched)))
    data = lzma.compress(bytes(patched), format=lzma.FORMAT_ALONE, filters=[{
        'id': lzma.FILTER_LZMA1, 'dict_size': 8388608, 'lc': 3, 'lp': 0, 'pb': 2,
        'mode': lzma.MODE_NORMAL, 'nice_len': 128, 'mf': lzma.MF_BT4}])
    data = data[:5] + struct.pack('<Q', len(patched)) + data[13:]
    assert len(data) <= 708764
    payload = image[64:64+0x2440] + data + b'\xff'*(708764-len(data))
    header = bytearray(image[:64]); struct.pack_into('>I', header, 24, zlib.crc32(payload))
    struct.pack_into('>I', header, 4, 0); struct.pack_into('>I', header, 4, zlib.crc32(header))
    result = bytes(header)+payload
    assert len(result) == 718108
    OUT.mkdir(exist_ok=True)
    (OUT/'main-preupload.NOT-FLASHABLE.bin').write_bytes(patched)
    (OUT/'web-preupload.uimage.NOT-FOR-FLASHING.bin').write_bytes(result)
    meta = dict(status='offline pre-body POST auth candidate; full HTTP integration unverified',
                parent_sha256=sha(image), base_main_sha256=sha(old), main_sha256=sha(patched),
                uimage_sha256=sha(result), compressed_bytes=len(data), headroom_bytes=708764-len(data),
                allowed_main_ranges=[[hex(a),hex(b)] for a,b in ranges],
                guard_code_bytes=code_size, public_gate_code_bytes=gate_size,
                changed_main_bytes=sum(a != b for a,b in zip(old,patched)), hardware_validated=False)
    (OUT/'build-manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2))


if __name__ == '__main__': main()
