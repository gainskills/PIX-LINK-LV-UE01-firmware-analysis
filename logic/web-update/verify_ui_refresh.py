"""Independent release/resource validation; read-only, no device access."""
import hashlib,lzma,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def verify(path):
    image=path.read_bytes();meta=__import__('json').loads(Path(str(path)+'.json').read_text())
    sha=lambda data:hashlib.sha256(data).hexdigest()
    baseline=(ROOT/'firmware/intermediates/phy-diagnostic/startup-trace/startup-trace.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    assert sha(baseline)=='81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377'
    assert sha(image)==meta['uimage_sha256'] and len(image)==718108
    header=bytearray(image[:64]);crc=struct.unpack_from('>I',header,4)[0];header[4:8]=bytes(4)
    assert struct.unpack_from('>I',header)[0]==0x27051956 and zlib.crc32(header)==crc
    assert struct.unpack_from('>I',header,12)[0]==len(image)-64
    assert zlib.crc32(image[64:])==struct.unpack_from('>I',header,24)[0]
    assert image[64:64+0x2440]==baseline[64:64+0x2440]
    decoder=lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    main=decoder.decompress(image[64+0x2440:],max_length=2174361)
    before=lzma.decompress(baseline[64+0x2440:],format=lzma.FORMAT_ALONE)
    assert decoder.eof and len(main)==2174360 and sha(main)==meta['main_sha256']
    assert decoder.unused_data==b'\xff'*meta['headroom_bytes']
    assert len(image)-64-0x2440-len(decoder.unused_data)==meta['compressed_bytes']
    allowed=[(0x1ad83c,0x1ad83c+95786),(0xae40,0xae50),(0x1a8d69,0x1ab6a1),(0x8d7c,0x8d80),(0xa4e8,0xa4ec)]
    if meta.get('native_status_renderer_changed'):
        allowed.extend([(0xa868,0xa86c),(0x19f340,0x19f358)])
        assert struct.unpack_from('<I',main,0xa868)[0]==0x0c000000|((0x8019f740>>2)&0x3ffffff)
        assert struct.unpack_from('<6I',main,0x19f340)==(0x3c068025,0x8cc651d0,0x3c058016,0x24a56aac,0x0800479d,0)
    # Fixed allocation sizes come from the original resource table, not the new manifest.
    assert all(any(lo<=i<hi for lo,hi in allowed) for i,(a,b) in enumerate(zip(before,main)) if a!=b)
    html=(Path(__file__).parent/'lan.htm').read_bytes();js=(Path(__file__).parent/'settings.min.js').read_bytes()+b'\n'
    assert len(html)<=10552 and main[0x1a8d69:0x1a8d69+10552]==html.ljust(10552,b' ')
    assert main[0x1ad83c:0x1ad83c+95786]==js.ljust(95786,b' ')
    assert struct.unpack_from('<I',main,0x8d7c)[0]==0x24070000|len(html)
    assert struct.unpack_from('<I',main,0xa4e8)[0]==0x24070000|len(html)
    assert struct.unpack_from('<4I',main,0xae40)==(0x3c070000|(len(js)>>16),0x34e70000|(len(js)&65535),0x080047bc,0x3021)
    print('PASS: hashes, container size, CRCs, loader, bounded decompression, padding, fixed byte scope and embedded resources')
if __name__=='__main__':verify(Path(sys.argv[1]))
