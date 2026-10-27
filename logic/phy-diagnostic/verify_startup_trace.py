"""Independent fixed-hash pre-upload validation; no device operations."""
import hashlib,json,lzma,struct,zlib
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent;dst=root/'startup-trace'
    image=(dst/'startup-trace.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    main=(dst/'main-startup-trace.NOT-FLASHABLE.bin').read_bytes()
    before=(root/'combined/main-secure-ui-phy.NOT-FLASHABLE.bin').read_bytes()
    sha=lambda b:hashlib.sha256(b).hexdigest()
    assert sha(image)=='81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377'
    assert sha(main)=='f6125ff8b27b50a5d0c0f7d4414c47a787d3c02e2abfb78e30a10c69318c1996'
    assert sha(before)=='5b8797c162d21db877a546b66f3927954348497b3c3ad43fdf154e8081e0072d'
    assert len(image)==718108 and len(main)==len(before)==2174360
    assert main[:0x19ecc4]==before[:0x19ecc4] and main[0x19f33c:]==before[0x19f33c:]
    assert image[64:64+0x2440]==(root.parent/'uimage.bin').read_bytes()[64:64+0x2440]
    header=bytearray(image[:64]);crc=struct.unpack_from('>I',header,4)[0];header[4:8]=bytes(4)
    assert zlib.crc32(header)==crc
    assert zlib.crc32(image[64:])==struct.unpack_from('>I',image,24)[0]
    assert lzma.decompress(image[64+0x2440:],format=lzma.FORMAT_ALONE)==main
    assert image[64+0x2440+655910:]==b'\xff'*52854
    tests=json.loads((dst/'test-results.json').read_text())
    assert tests['status']=='PASS' and tests['tests']==31 and tests['candidate_sha256']==sha(image)
    result=dict(status='PASS: fixed hashes, byte scope, loader, CRCs, decompression, padding and test evidence',
                candidate_sha256=sha(image),main_sha256=sha(main),image_bytes=len(image),compressed_bytes=655910,headroom_bytes=52854)
    (dst/'verification-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
