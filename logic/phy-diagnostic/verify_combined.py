"""Independent validation of the written combined image; no builder imports."""
import hashlib,json,lzma,struct,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    dst=ROOT/'combined'
    original=(ROOT.parent/'uimage.bin').read_bytes()
    base=(ROOT.parent/'security/preupload-hardening/main-preupload.NOT-FLASHABLE.bin').read_bytes()
    phy=(ROOT/'original-baseline/main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
    data=(dst/'secure-ui-phy.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    main=(dst/'main-secure-ui-phy.NOT-FLASHABLE.bin').read_bytes()
    sha=lambda b:hashlib.sha256(b).hexdigest()
    assert sha(base)=='2675629b6ccda9c91436cf4eb62089ed1b090db6920a4c7f5b9acc23f890ab88'
    assert sha(phy)=='825021509d72ab5fcd9d41fa115890afa1a5a83f49ed07c50260f5feabc5f1f6'
    assert sha(data)=='c2948bec9931d02837ccfe09b5f53aaf55b4e4cd00c1e6060c310f48a68b175a'
    assert sha(main)=='5b8797c162d21db877a546b66f3927954348497b3c3ad43fdf154e8081e0072d'
    assert len(data)==718108 and len(main)==2174360
    h=bytearray(data[:64]);crc=struct.unpack_from('>I',h,4)[0];h[4:8]=bytes(4)
    assert zlib.crc32(h)==crc and zlib.crc32(data[64:])==struct.unpack_from('>I',data,24)[0]
    assert all(a==b for i,(a,b) in enumerate(zip(data[:64],original[:64])) if i not in list(range(4,8))+list(range(24,28)))
    assert data[64:64+0x2440]==original[64:64+0x2440]
    raw=data[64+0x2440:];decoder=lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    assert decoder.decompress(raw,max_length=2174361)==main and decoder.eof
    compressed=len(raw)-len(decoder.unused_data)
    assert compressed==655726 and decoder.unused_data==b'\xff'*53038
    ranges=[(0x16d34,0x16d3c),(0x11207c,0x112080),(0x19ecc2,0x19f140),(0x211ff0,0x211ff4)]
    diff=[i for i,(a,b) in enumerate(zip(base,main)) if a!=b]
    assert len(diff)==499 and all(any(lo<=i<hi for lo,hi in ranges) for i in diff)
    assert all(main[lo:hi]==phy[lo:hi] for lo,hi in ranges)
    assert struct.unpack_from('<I',main,0x11207c)[0]==0x0c067c69
    report=dict(status='PASS: independent combined artifact verification; not installed',
                uimage_sha256=sha(data),main_sha256=sha(main),uimage_bytes=len(data),main_bytes=len(main),
                compressed_bytes=compressed,headroom_bytes=len(decoder.unused_data),
                crc_valid=True,original_loader_unchanged=True,changed_bytes_relative_to_secure_ui=len(diff),
                secure_ui_bytes_preserved_outside_four_diagnostic_ranges=True,
                diagnostic_bytes_match_working_v2=True,hardware_validated=False)
    (dst/'verification-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
