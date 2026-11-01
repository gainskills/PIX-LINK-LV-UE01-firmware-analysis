"""Refresh bounded dashboard/controller resources in the exact tested startup-trace image; offline."""
import hashlib,json,lzma,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'logic/phy-diagnostic'))
import builder
import status_telemetry

def build():
    release=ROOT/'firmware/releases'
    baseline=(ROOT/'firmware/intermediates/phy-diagnostic/startup-trace/startup-trace.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    assert builder.sha(baseline)=='81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377'
    before=lzma.decompress(baseline[64+0x2440:],format=lzma.FORMAT_ALONE)
    assert builder.sha(before)=='f6125ff8b27b50a5d0c0f7d4414c47a787d3c02e2abfb78e30a10c69318c1996'
    original=(ROOT/'firmware/original/main-decompressed.bin').read_bytes()
    offset=0x19ecc2;assets={}
    for entry in range(0x1ede4c,0x1ee3a8,28):
        addr,handler,size,*_=struct.unpack_from('<7I',original,entry)
        pos=addr-0x80000400
        name=original[pos:original.index(b'\0',pos)].decode()
        assets[name]=(offset,size,handler-0x80000400)
        offset+=size
    offset,size,h=assets['/js/jquery.js']
    assert offset==0x1ad83c
    old_stub=struct.unpack_from('<4I',before,h)
    old_len=((old_stub[0]&65535)<<16)|(old_stub[1]&65535)
    assert old_stub==(0x3c070000|(old_len>>16),0x34e70000|(old_len&65535),0x080047bc,0x3021)
    js=(Path(__file__).parent/'settings.min.js').read_bytes()+b'\n'
    assert len(js)<=size
    after=bytearray(before)
    after[offset:offset+size]=js.ljust(size,b' ')
    after[h:h+16]=struct.pack('<4I',0x3c070000|(len(js)>>16),0x34e70000|(len(js)&65535),0x080047bc,0x3021)
    allowed=[[offset,offset+size],[h,h+16]]
    html=(Path(__file__).parent/'lan.htm').read_bytes()
    page,page_size,index_handler=assets['/index.htm']
    _,_,lan_handler=assets['/lan.htm']
    assert page==0x1a8d69 and len(html)<=page_size and len(html)<65536
    # Preserve the installed raw callbacks and /lan.htm canonical-data pointer.
    assert struct.unpack_from('<2I',before,index_handler)==(0x3021,0x080047bc)
    assert struct.unpack_from('<4I',before,lan_handler)==(0x3c05801a,0x34a59169,0x3021,0x080047bc)
    old_html_len=struct.unpack_from('<I',before,index_handler+8)[0]
    assert old_html_len>>16==0x2407 and struct.unpack_from('<I',before,lan_handler+16)[0]==old_html_len
    after[page:page+page_size]=html.ljust(page_size,b' ')
    allowed.append([page,page+page_size])
    for immediate in [index_handler+8,lan_handler+16]:
        struct.pack_into('<I',after,immediate,0x24070000|len(html))
        allowed.append([immediate,immediate+4])
    assert all(any(lo<=i<hi for lo,hi in allowed) for i,(a,b) in enumerate(zip(before,after)) if a!=b)
    after,native_ranges=status_telemetry.apply(after)
    allowed.extend(native_ranges)
    image,compressed=builder.package((ROOT/'firmware/original/uimage.bin').read_bytes(),bytes(after))
    # Independently check final container and decoded resource.
    header=bytearray(image[:64]);crc=struct.unpack_from('>I',header,4)[0];header[4:8]=bytes(4)
    assert zlib.crc32(header)==crc
    assert zlib.crc32(image[64:])==struct.unpack_from('>I',image,24)[0]
    assert image[64:64+0x2440]==baseline[64:64+0x2440]
    decoded=lzma.decompress(image[64+0x2440:],format=lzma.FORMAT_ALONE)
    assert decoded==after and decoded[offset:offset+len(js)]==js
    assert decoded[page:page+len(html)]==html
    assert image[64+0x2440+compressed:]==b'\xff'*(builder.BUDGET-compressed)
    digest=builder.sha(image);name=f'lv-ue01-repeater-{digest[:8]}.uimage.bin'
    dest=release/name
    if dest.exists():assert dest.read_bytes()==image
    else:dest.write_bytes(image)
    manifest=dict(status='OFFLINE VERIFIED; NOT FLASHED OR BOOT TESTED',file=name,uimage_sha256=digest,
        baseline_sha256=builder.sha(baseline),main_sha256=builder.sha(decoded),controller_sha256=builder.sha(js),
        image_bytes=len(image),compressed_bytes=compressed,headroom_bytes=builder.BUDGET-compressed,
        allowed_main_ranges=allowed,dashboard_bytes=len(html),dashboard_capacity_bytes=page_size,dashboard_sha256=builder.sha(html),
        changes='Allow upstream management port changes through the active upstream URL, with verified save and post-reboot redirect including port 80; retain numeric upstream status, prior mode-switch and layout changes.',
        native_status_renderer_changed=True,driver_changed=False,phy_diagnostics_changed=False,factory_reset_tested=False,ethernet_fix_confirmed=False)
    (release/(name+'.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    sums=release/'SHA256SUMS';line=f'{digest}  {name}\n'
    if line not in sums.read_text():sums.write_text(sums.read_text()+line)
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':build()
