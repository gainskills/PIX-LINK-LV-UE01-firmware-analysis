"""Offline composition of previously tested secure UI and working PHY v2.

Separate output; does not alter or install either source image.
"""
import hashlib
import json
import lzma
from pathlib import Path
import builder

ROOT=Path(__file__).resolve().parent
BASE_SHA='2675629b6ccda9c91436cf4eb62089ed1b090db6920a4c7f5b9acc23f890ab88'
BASE_IMAGE_SHA='481ed9575c53ff9ab6d5021638f225eb35cb6ac7b7839d4e0a65ec6a13ae4bb3'
PHY_SHA='825021509d72ab5fcd9d41fa115890afa1a5a83f49ed07c50260f5feabc5f1f6'
RANGES=[(0x16d34,0x16d3c),(0x11207c,0x112080),(0x19ecc2,0x19f140),(0x211ff0,0x211ff4)]


def make_main(base,phy):
    if hashlib.sha256(base).hexdigest()!=BASE_SHA:raise ValueError('Unknown secure UI baseline')
    if hashlib.sha256(phy).hexdigest()!=PHY_SHA:raise ValueError('Unknown or obsolete PHY diagnostic baseline')
    if len(base)!=2174360 or len(phy)!=len(base):raise ValueError('Unexpected main lengths')
    # UI already suppresses favicon; its retired image storage must be unused.
    if base[0x19ecc2:0x19f140]!=bytes(1150):raise ValueError('Diagnostic storage is occupied')
    result=bytearray(base)
    for lo,hi in RANGES:result[lo:hi]=phy[lo:hi]
    return bytes(result)


def main():
    base=(ROOT.parent/'security/preupload-hardening/main-preupload.NOT-FLASHABLE.bin').read_bytes()
    parent_image=(ROOT.parent/'security/preupload-hardening/web-preupload.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    if hashlib.sha256(parent_image).hexdigest()!=BASE_IMAGE_SHA:raise ValueError('Secure UI container changed')
    if lzma.decompress(parent_image[64+0x2440:],format=lzma.FORMAT_ALONE)!=base:raise ValueError('Secure UI container/main mismatch')
    phy=(ROOT/'original-baseline/main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
    result=make_main(base,phy)
    image,size=builder.package((ROOT.parent/'uimage.bin').read_bytes(),result,nice_len=128)
    destination=ROOT/'combined'
    destination.mkdir(exist_ok=True)
    names=['main-secure-ui-phy.NOT-FLASHABLE.bin','secure-ui-phy.uimage.NOT-FOR-FLASHING.bin']
    for name,body in zip(names,[result,image]):(destination/name).write_bytes(body)
    manifest=dict(status='OFFLINE COMBINED CANDIDATE; NOT INSTALLED',
                  secure_ui_main_sha256=BASE_SHA,secure_ui_image_sha256=BASE_IMAGE_SHA,
                  diagnostic_main_sha256=PHY_SHA,main_sha256=hashlib.sha256(result).hexdigest(),
                  uimage_sha256=hashlib.sha256(image).hexdigest(),main_bytes=len(result),uimage_bytes=len(image),
                  compressed_bytes=size,headroom_bytes=builder.BUDGET-size,
                  allowed_ranges_relative_to_secure_ui=[[hex(lo),hex(hi)] for lo,hi in RANGES],
                  changed_bytes_relative_to_secure_ui=sum(x!=y for x,y in zip(base,result)),
                  limits=['Offline integration only; combined candidate has not booted.',
                          'Includes original driver/network stack; no Ethernet stability fix or dependency upgrade.',
                          'PHY BMSR reads can clear latched state; preserves both results.',
                          'Hardware recovery remains unverified.'])
    (destination/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (destination/'SHA256SUMS').write_text(''.join(hashlib.sha256(body).hexdigest()+'  '+name+'\n' for name,body in zip(names,[result,image])))
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
