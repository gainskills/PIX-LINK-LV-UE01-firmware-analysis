"""Independent inspection of written artifacts, not builder helper reuse."""
import hashlib,json,lzma,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
from capstone import Cs,CS_ARCH_MIPS,CS_MODE_MIPS32,CS_MODE_LITTLE_ENDIAN

def digest(b):return hashlib.sha256(b).hexdigest()
def verify():
    manifest=json.loads((ROOT/'build-manifest.json').read_text())
    source=(ROOT.parent/'uimage.bin').read_bytes()
    base=(ROOT.parent/'web-update/main-web-update.NOT-FLASHABLE.bin').read_bytes()
    ui=(ROOT.parent/'web-update/web-wps-jquery.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    main=(ROOT/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
    image=(ROOT/'phy-diagnostic.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    blob=(ROOT/'payload.bin').read_bytes()
    assert digest(source)=='43ef36588e9f3c08b302583a60fc30bcb8fd374953a82a88eb64fcef2714c243'
    assert digest(base)=='3385f574b110096a4446cf6beef365c95c63e41ac5be80d1cca5b5d8842d81b8'
    assert digest(ui)=='75581dd659ed625e7547ce91b89803f0983df49b7a537c0ebb7e1302bdf1178f'
    assert len(image)==718108 and len(main)==2174360
    for data,key in [(main,'main_sha256'),(image,'uimage_sha256'),(blob,'payload_sha256')]:assert digest(data)==manifest[key]
    h=bytearray(image[:64]);want=struct.unpack_from('>I',h,4)[0];h[4:8]=bytes(4)
    assert zlib.crc32(h)==want
    assert zlib.crc32(image[64:])==struct.unpack_from('>I',h,24)[0]
    # Only header/data CRC words can differ in the U-Boot header.
    assert all(a==b for i,(a,b) in enumerate(zip(image[:64],source[:64])) if i not in range(4,8) and i not in range(24,28))
    assert image[64:64+0x2440]==source[64:64+0x2440]
    size=manifest['compressed_bytes'];compressed=image[64+0x2440:64+0x2440+size]
    assert len(compressed)<=708764
    assert manifest['headroom_bytes']==708764-size
    assert lzma.decompress(compressed,format=lzma.FORMAT_ALONE)==main
    assert struct.unpack_from('<Q',compressed,5)[0]==2174360
    assert image[64+0x2440+size:]==b'\xff'*(708764-size)
    allowed=[(0x19ecc4,0x19ecc4+len(blob)),(0x16d34,0x16d3c),(0x211ff0,0x211ff4)]
    assert main[0x19ecc4:0x19ecc4+len(blob)]==blob
    assert base[0x19ecc4:0x19ecc4+len(blob)]==bytes(len(blob))
    changes=[i for i,(a,b) in enumerate(zip(main,base)) if a!=b]
    assert all(any(lo<=i<hi for lo,hi in allowed) for i in changes)
    symbols={k:int(v,16) for k,v in manifest['symbols'].items()}
    assert struct.unpack_from('<I',main,0x211ff0)[0]==symbols['wrapper']
    jump,nop=struct.unpack_from('<II',main,0x16d34)
    assert jump>>26==2 and nop==0 and (0x80000000|((jump&0x3ffffff)<<2))==symbols['trace']
    assert main[symbols['counter']-0x80000400:symbols['counter']-0x80000400+8]==bytes(8)
    assert struct.unpack_from('<I',main,symbols['read_count']-0x80000400)[0]==0x400b4800 # mfc0 t3, CP0 Count
    dis=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
    end=symbols['code_end']-0x8019f0c4
    insns=list(dis.disasm(blob[:end],0x8019f0c4))
    assert len(insns)*4==end
    (ROOT/'payload-disassembly.txt').write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():8} {i.mnemonic} {i.op_str}' for i in insns)+'\n')
    result={'status':'PASS: offline artifact checks only','checks':['Known source and unchanged UI candidate hashes','Fixed outer/main sizes and loader bytes','Independent header/data CRC checks','LZMA roundtrip and fixed decompressed-size header','Only three diagnostic ranges changed relative to the UI main','Actual CLI pointer, relink jump, zero data and CP0 Count opcode','Capstone decoded every payload code word'],'compressed_bytes':size,'headroom_bytes':708764-size,'payload_code_bytes':end,'payload_total_bytes':len(blob),'changed_main_bytes':len(changes),'comparison_base':'UI candidate main; whole image also inherits UI/default changes','uimage_sha256':digest(image),'hardware_validated':False}
    (ROOT/'verification-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':verify()
