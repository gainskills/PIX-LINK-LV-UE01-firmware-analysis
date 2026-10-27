"""Independent written-artifact validation; does not import builder/patch modules."""
import hashlib,json,lzma,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=0x80000400

def need(ok,message):
    if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def inspect_artifacts(source,original,main,image,blob,manifest):
    need(sha(source)=='43ef36588e9f3c08b302583a60fc30bcb8fd374953a82a88eb64fcef2714c243','Unknown source container')
    need(sha(original)=='2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe','Unknown original baseline')
    need(len(image)==718108 and len(main)==2174360,'Invalid fixed container/main length')
    need(manifest.get('baseline_kind')=='original','Manifest is not original-baseline')
    need(manifest.get('base_main_sha256')==sha(original),'Manifest baseline fingerprint mismatch')
    h=bytearray(image[:64]);wanted=struct.unpack_from('>I',h,4)[0];h[4:8]=bytes(4)
    need(zlib.crc32(h)==wanted,'Header CRC mismatch')
    need(zlib.crc32(image[64:])==struct.unpack_from('>I',h,24)[0],'Payload CRC mismatch')
    need(all(a==b for i,(a,b) in enumerate(zip(image[:64],source[:64])) if i not in range(4,8) and i not in range(24,28)),'Non-CRC header fields changed')
    need(image[64:64+0x2440]==source[64:64+0x2440],'Original loader changed')
    raw=image[64+0x2440:]
    need(raw[:5]==source[64+0x2440:64+0x2445],'LZMA properties changed')
    need(struct.unpack_from('<Q',raw,5)[0]==2174360,'LZMA decompressed length changed')
    decoder=lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    decoded=decoder.decompress(raw,max_length=2174361)
    need(decoder.eof and decoded==main,'LZMA data does not match complete main')
    size=len(raw)-len(decoder.unused_data)
    need(0<size<=708764 and decoder.unused_data==b'\xff'*(708764-size),'Invalid compressed boundary or padding')
    need(manifest.get('compressed_bytes')==size and manifest.get('headroom_bytes')==708764-size,'Manifest compression size mismatch')
    need(sha(main)=='825021509d72ab5fcd9d41fa115890afa1a5a83f49ed07c50260f5feabc5f1f6','Isolated main fingerprint mismatch')
    need(sha(blob)=='cd096b1b0d0b956d4030fd7f0450bdcc2ee01031324176c193b24a7b216c711b' and len(blob)==780,'Diagnostic payload changed')
    for data,key in [(main,'main_sha256'),(image,'uimage_sha256'),(blob,'payload_sha256')]:need(sha(data)==manifest.get(key),'Manifest '+key+' mismatch')
    need(manifest.get('source_uimage_sha256')==sha(source),'Manifest source fingerprint mismatch')
    need(manifest.get('main_bytes')==len(main) and manifest.get('uimage_bytes')==len(image),'Manifest artifact lengths mismatch')
    allowed=[(0xa4b0,0xa4b4),(0x16d34,0x16d3c),(0x11207c,0x112080),(0x19ecc2,0x19f140),(0x211ff0,0x211ff4)]
    need(manifest.get('allowed_main_ranges')==[[hex(a),hex(b)] for a,b in allowed],'Manifest allowed ranges mismatch')
    changed=[i for i,(a,b) in enumerate(zip(original,main)) if a!=b]
    need(len(changed)==1067 and all(any(a<=i<b for a,b in allowed) for i in changed),'Changes outside isolated scope')
    need(struct.unpack_from('<I',main,0x11207c)[0]==0x0c067c69,'Telnet builtin reg call mismatch')
    need(main[0x19ecc4:0x19efd0]==blob,'Payload is not in favicon allocation')
    need(main[0x19ecc2:0x19ecc4]==bytes(2) and main[0x19efd0:0x19f140]==bytes(368),'Unused favicon bytes not cleared')
    need(struct.unpack_from('<I',main,0xa4b0)[0]==0x24070000,'Favicon response does not have zero length')
    need(struct.unpack_from('<I',main,0x211ff0)[0]==0x8019f1a4,'CLI callback mismatch')
    jump,nop=struct.unpack_from('<II',main,0x16d34)
    need(jump>>26==2 and nop==0 and (0x80000000|((jump&0x3ffffff)<<2))==0x8019f2e4,'Relink hook mismatch')
    need(main[0x8019f36c-BASE:0x8019f36c-BASE+8]==bytes(8),'Initial counters not zero')
    need(struct.unpack_from('<I',main,0x8019f32c-BASE)[0]==0x400b4800,'CP0 Count instruction mismatch')
    return {'status':'PASS: original-baseline offline artifact validation only','comparison_base':'Original firmware main',
            'main_bytes':len(main),'uimage_bytes':len(image),'changed_main_bytes':len(changed),
            'compressed_bytes':size,'headroom_bytes':708764-size,'uimage_sha256':sha(image),'main_sha256':sha(main),
            'header_crc_valid':True,'payload_crc_valid':True,'loader_unchanged':True,
            'original_pages_and_defaults_unchanged_except_favicon':True,'hardware_validated':False,
            'limits':['No candidate boot, real cache/MDIO timing, UART access or recovery tested.',
                      'BMSR reads can clear latched state; this is instrumentation, not a connectivity fix.',
                      'Small compression headroom is not evidence of hardware compatibility.']}

def verify():
    dst=ROOT/'original-baseline'
    result=inspect_artifacts((ROOT.parent/'uimage.bin').read_bytes(),(ROOT.parent/'main-decompressed.bin').read_bytes(),
                            (dst/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes(),
                            (dst/'phy-diagnostic.uimage.NOT-FOR-FLASHING.bin').read_bytes(),
                            (dst/'payload.bin').read_bytes(),json.loads((dst/'build-manifest.json').read_text()))
    # Dependencies are declared in requirements.txt.
    from capstone import Cs,CS_ARCH_MIPS,CS_MODE_MIPS32,CS_MODE_LITTLE_ENDIAN
    blob=(dst/'payload.bin').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
    instructions=list(md.disasm(blob[:680],0x8019f0c4));need(len(instructions)*4==680,'Incomplete code disassembly')
    (dst/'payload-disassembly.txt').write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():8} {i.mnemonic} {i.op_str}' for i in instructions)+'\n')
    result['payload_code_bytes']=680
    (dst/'verification-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':verify()
