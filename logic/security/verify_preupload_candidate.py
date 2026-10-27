"""Written second-stage artifact check, independent of patch generation."""
import hashlib
import json
import lzma
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'security/preupload-hardening'
BASE = 0x80000400


def sha(b): return hashlib.sha256(b).hexdigest()


def main():
    parent = ROOT / 'security/auth-hardening'
    old = (parent/'main-auth.NOT-FLASHABLE.bin').read_bytes()
    source = (parent/'web-auth.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    assert sha(source) == 'a8d20ebf90669c86fb79ce85abf662b856f2d07a1c4fb40d5c0eb208f91951b0'
    assert sha(old) == 'dedd2ecce827c6e7604eb70d569c929ccec89d4dc2942e1904f27c4db6a8de70'
    new = (OUT/'main-preupload.NOT-FLASHABLE.bin').read_bytes()
    image = (OUT/'web-preupload.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    manifest = json.loads((OUT/'build-manifest.json').read_text())
    assert len(new) == len(old) == 2174360
    assert len(image) == len(source) == 718108
    assert image[64:64+0x2440] == source[64:64+0x2440]
    assert all(a == b for i,(a,b) in enumerate(zip(image[:64],source[:64]))
               if i not in range(4,8) and i not in range(24,28))
    h = bytearray(image[:64]); expected = struct.unpack_from('>I',h,4)[0]; h[4:8]=bytes(4)
    assert zlib.crc32(h) == expected
    assert zlib.crc32(image[64:]) == struct.unpack_from('>I',image,24)[0]
    data = image[64+0x2440:]
    assert data[:5] == source[64+0x2440:64+0x2445]
    assert struct.unpack_from('<Q',data,5)[0] == len(new)
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    assert dec.decompress(data,max_length=len(new)+1) == new and dec.eof
    compressed = len(data)-len(dec.unused_data)
    assert dec.unused_data == b'\xff'*(708764-compressed)
    allowed = [(0xdf98,0xe0e0),(0xfff8,0xfffc)]
    diff = [i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    assert len(diff)==264 and all(any(a<=i<b for a,b in allowed) for i in diff)
    assert struct.unpack_from('<2I',new,0xfff8)==(0x080038e6,0x8fa30020)
    assert struct.unpack_from('<I',new,0xe160)[0]==0x24020001
    assert new[0xdf98+84:0xe024]==bytes(56)
    assert new[0xe024:0xe0e0].count(struct.pack('<I',0x8c82002c))==1
    assert new[0xe024:0xe0e0].count(struct.pack('<I',0x90420000))==1
    # Dependencies are declared in requirements.txt.
    from capstone import Cs,CS_ARCH_MIPS,CS_MODE_MIPS32,CS_MODE_LITTLE_ENDIAN
    cs=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
    guard=list(cs.disasm(new[0xdf98:0xdf98+84],0x8000e398))
    gate=list(cs.disasm(new[0xe024:0xe0e0],0x8000e424))
    assert len(guard)==21 and len(gate)==47
    assert [i.op_str for i in guard if i.mnemonic=='jal']==['0x8000e4e0','0x8000f838']
    assert [i.op_str for i in guard if i.mnemonic=='j']==['0x8001075c','0x8000fe30','0x80010400']
    assert all(i.op_str=='0x8015c59c' for i in gate if i.mnemonic=='jal')
    for key,want in [('main_sha256',sha(new)),('uimage_sha256',sha(image)),
                     ('compressed_bytes',compressed),('headroom_bytes',708764-compressed)]:
        assert manifest[key]==want
    assert sha(new)=='2675629b6ccda9c91436cf4eb62089ed1b090db6920a4c7f5b9acc23f890ab88'
    # Anchor header frame initialization and native cleanup/error entry dependencies.
    assert struct.unpack_from('<I',new,0x8000fd0c-BASE)[0]==0xafa00094
    assert new[0x8000f838-BASE:0x8000f8a4-BASE]==old[0x8000f838-BASE:0x8000f8a4-BASE]
    result=dict(status='PASS: independent preupload artifact check',uimage_sha256=sha(image),
                changed_from_auth_stage_one=len(diff),compressed_bytes=compressed,
                headroom_bytes=708764-compressed,full_http_integration_verified=False,
                hardware_validated=False)
    (OUT/'guard-disassembly.txt').write_text('\n'.join(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in guard+gate)+'\n')
    (OUT/'verification-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
