"""Offline-only, hash-guarded packaging. Never uploads or flashes images."""
import hashlib,json,lzma,struct,zlib
from pathlib import Path
import patch
ROOT=Path(__file__).resolve().parent
SOURCE_SHA='43ef36588e9f3c08b302583a60fc30bcb8fd374953a82a88eb64fcef2714c243'
ORIGINAL_MAIN_SHA='2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
MAIN_SHA='3385f574b110096a4446cf6beef365c95c63e41ac5be80d1cca5b5d8842d81b8'
BUDGET=708764
MAIN_NAME='main-phy-diagnostic.NOT-FOR-FLASHING.bin'
IMAGE_NAME='phy-diagnostic.uimage.NOT-FOR-FLASHING.bin'
def sha(data):return hashlib.sha256(data).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def ranges(baseline='ui'):
    if baseline=='original':return [(0xa4b0,0xa4b4),(0x16d34,0x16d3c),(0x11207c,0x112080),(0x19ecc2,0x19f140),(0x211ff0,0x211ff4)]
    require(baseline=='ui','Unknown baseline')
    blob,sym=patch.assemble()
    return [(patch.START-patch.BASE,patch.START-patch.BASE+len(blob)),(patch.RELINK-patch.BASE,patch.RELINK-patch.BASE+8),(patch.CALLBACK-patch.BASE,patch.CALLBACK-patch.BASE+4)]
def patch_main(main):
    baseline='original' if sha(main)==ORIGINAL_MAIN_SHA else 'ui'
    require(sha(main) in [MAIN_SHA,ORIGINAL_MAIN_SHA],'Unknown main image; refusing patch')
    blob,sym=patch.assemble();out=bytearray(main)
    lo=patch.START-patch.BASE
    if baseline=='original':
        require(main[0xa4a8:0xa4b4]==struct.pack('<III',0x3021,0x080047bc,0x2407047e),'Original favicon callback mismatch')
        require(0x19ecc2<=lo and lo+len(blob)<=0x19f140,'Payload exceeds original favicon allocation')
        out[0x19ecc2:0x19f140]=bytes(1150)
        out[0xa4b0:0xa4b4]=struct.pack('<I',0x24070000)
        require(main[0x11207c:0x112080]==struct.pack('<I',0x0c044a58),'Telnet builtin reg call mismatch')
        out[0x11207c:0x112080]=struct.pack('<I',0x0c000000|((sym['wrapper']>>2)&0x3ffffff))
    require(lo+len(blob)<=0x1a8d69,'Payload exceeds retired resource space')
    require(out[lo:lo+len(blob)]==bytes(len(blob)),'Retired resource space is not zero')
    entry=patch.RELINK-patch.BASE;callback=patch.CALLBACK-patch.BASE
    require(main[entry:entry+8]==struct.pack('<II',0x27bdffe8,0x3c028017),'Relink prologue mismatch')
    require(main[callback:callback+4]==struct.pack('<I',patch.REG_HANDLER),'CLI callback mismatch')
    out[lo:lo+len(blob)]=blob
    out[entry:entry+8]=struct.pack('<II',0x08000000|((sym['trace']>>2)&0x3ffffff),0)
    out[callback:callback+4]=struct.pack('<I',sym['wrapper'])
    require(len(out)==len(main),'Main length changed')
    allowed=ranges(baseline)
    require(all(any(a<=i<b for a,b in allowed) for i,(x,y) in enumerate(zip(main,out)) if x!=y),'Unreviewed byte changed')
    return bytes(out)
def package(source,main,*,nice_len=128):
    require(sha(source)==SOURCE_SHA,'Unknown source container; refusing packaging')
    require(len(main)==2174360,'Main length mismatch')
    header=bytearray(source[:64]);payload=source[64:]
    require(zlib.crc32(payload)==struct.unpack_from('>I',header,24)[0],'Source payload CRC mismatch')
    wanted=struct.unpack_from('>I',header,4)[0];header[4:8]=bytes(4)
    require(zlib.crc32(header)==wanted,'Source header CRC mismatch')
    compressed=lzma.compress(main,format=lzma.FORMAT_ALONE,filters=[dict(id=lzma.FILTER_LZMA1,dict_size=8*1024*1024,lc=3,lp=0,pb=2,mode=lzma.MODE_NORMAL,nice_len=nice_len,mf=lzma.MF_BT4)])
    compressed=compressed[:5]+struct.pack('<Q',len(main))+compressed[13:]
    require(len(compressed)<=BUDGET,'Compressed payload exceeds container budget')
    require(lzma.decompress(compressed,format=lzma.FORMAT_ALONE)==main,'LZMA roundtrip mismatch')
    payload=payload[:0x2440]+compressed+b'\xff'*(BUDGET-len(compressed))
    struct.pack_into('>I',header,24,zlib.crc32(payload));struct.pack_into('>I',header,4,zlib.crc32(header))
    result=bytes(header)+payload;require(len(result)==len(source),'Container length changed')
    return result,len(compressed)
def build(baseline='ui'):
    require(baseline in ['ui','original'],'Unknown baseline')
    original=baseline=='original'
    dst=ROOT/'original-baseline' if original else ROOT
    main=(ROOT.parent/'main-decompressed.bin' if original else ROOT.parent/'web-update/main-web-update.NOT-FLASHABLE.bin').read_bytes()
    source=(ROOT.parent/'uimage.bin').read_bytes()
    require(sha(main)==(ORIGINAL_MAIN_SHA if original else MAIN_SHA),'Selected baseline does not match input fingerprint')
    result=patch_main(main);image,size=package(source,result,nice_len=64 if original else 128);blob,sym=patch.assemble()
    dst.mkdir(exist_ok=True)
    (dst/MAIN_NAME).write_bytes(result);(dst/IMAGE_NAME).write_bytes(image);(dst/'payload.bin').write_bytes(blob)
    scope=('Original UI/defaults retained; favicon storage/empty response plus diagnostic instrumentation only.' if original else 'Combined UI/default/diagnostic candidate; three diagnostic ranges are incremental relative to the UI main, not original firmware.')
    manifest={'status':'OFFLINE ONLY / NOT FOR FLASHING / NOT HARDWARE VALIDATED','baseline_kind':baseline,'baseline_scope':scope,
              'source_uimage_sha256':sha(source),'base_main_sha256':sha(main),'main_bytes':len(result),'main_sha256':sha(result),
              'uimage_bytes':len(image),'uimage_sha256':sha(image),'payload_bytes':len(blob),'payload_sha256':sha(blob),
              'compressed_bytes':size,'compressed_budget':BUDGET,'headroom_bytes':BUDGET-size,'compression_nice_len':64 if original else 128,
              'symbols':{k:hex(v) for k,v in sym.items()},'allowed_main_ranges':[[hex(a),hex(b)] for a,b in ranges(baseline)],
              'limits':['No boot, flash, cache execution, real MDIO timing or recovery validation.',
                        'Favicon/retired resource RAM placement has only offline validation.',
                        'BMSR reads may clear latched state; first and second values are logged in order.',
                        'CP0 Count is a wrapping raw tick value; not wall time.',
                        'Counter resets at boot, wraps modulo 2^32, counts entries to one known firmware relink function only.',
                        'Diagnostic reads are not an Ethernet fix; native PHY initialization remains unchanged.',
                        'Hardware recovery and candidate boot remain unverified; backup evidence is recorded separately under ../recovery/.']}
    if not original:manifest['base_ui_main_sha256']=sha(main)
    (dst/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['status','baseline_kind','payload_bytes','compressed_bytes','headroom_bytes','uimage_sha256']},indent=2))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',choices=['ui','original'],default='ui')
    build(parser.parse_args().baseline)
