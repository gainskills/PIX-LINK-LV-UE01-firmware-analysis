"""Offline audit of diagnostic inheritance; never builds or uploads firmware."""
import hashlib,json,lzma,struct,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ORIGINAL='2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
UI='3385f574b110096a4446cf6beef365c95c63e41ac5be80d1cca5b5d8842d81b8'
DIAG='98d017b3db1975d51f684f012b61a68c4ac1d104f8e13541d3c7138ffcb7f6cc'
def sha(b):return hashlib.sha256(b).hexdigest()
def mask(ranges,length):
 out=bytearray(length)
 for lo,hi in ranges:
  assert 0<=lo<hi<=length
  out[lo:hi]=b'\1'*(hi-lo)
 return out
def compare(a,b,allowed):
 assert len(a)==len(b)
 different=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
 assert all(allowed[i] for i in different),'Difference outside declared ranges'
 return {'changed_bytes':len(different),'outside_declared_ranges':0}
def main():
 original=(ROOT.parent/'main-decompressed.bin').read_bytes()
 ui=(ROOT.parent/'web-update/main-web-update.NOT-FLASHABLE.bin').read_bytes()
 diag=(ROOT/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
 assert (sha(original),sha(ui),sha(diag))==(ORIGINAL,UI,DIAG)
 w=json.loads((ROOT.parent/'web-update/build-manifest.json').read_text())
 d=json.loads((ROOT/'build-manifest.json').read_text())
 wr=[(int(c['offset'],16),int(c['offset'],16)+c['bytes']) for c in w['changes']]
 dr=[tuple(int(x,16) for x in pair) for pair in d['allowed_main_ranges']]
 comparisons={'original_to_ui':compare(original,ui,mask(wr,len(original))),
              'ui_to_diagnostic':compare(ui,diag,mask(dr,len(original))),
              'original_to_diagnostic':compare(original,diag,mask(wr+dr,len(original)))}
 assert [comparisons[k]['changed_bytes'] for k in comparisons]==[152822,496,152845]
 assert len(wr)==46 and sum(hi-lo for lo,hi in wr)==160360
 for image,expected_main in [(ROOT.parent/'uimage.bin',original),(ROOT.parent/'web-update/web-wps-jquery.uimage.NOT-FOR-FLASHING.bin',ui),(ROOT/'phy-diagnostic.uimage.NOT-FOR-FLASHING.bin',diag)]:
  blob=image.read_bytes();header=bytearray(blob[:64]);payload=blob[64:]
  assert len(blob)==718108
  wanted=struct.unpack_from('>I',header,4)[0];header[4:8]=bytes(4)
  assert zlib.crc32(header)==wanted and zlib.crc32(payload)==struct.unpack_from('>I',header,24)[0]
  assert lzma.decompress(payload[0x2440:],format=lzma.FORMAT_ALONE)==expected_main
 checked=[]
 for name,lo,hi in [('native_mdio_read',0x8001593c,0x800159e0),('native_mdio_write',0x800159e0,0x80015a88),('phy_init',0x80015a88,0x80015c98),('relink_after_entry_hook',0x8001713c,0x80017200),('physical_link_interrupt',0x80016ef0,0x80016fb0),('upstream_transition_helper',0x8014de44,0x8014df3c),('upstream_status_callback',0x8014df3c,0x8014dff4),('upstream_monitor',0x8014e1f8,0x8014e3c8)]:
  a,b=lo-0x80000400,hi-0x80000400
  assert original[a:b]==ui[a:b]==diag[a:b]
  checked.append({'name':name,'runtime_range':[hex(lo),hex(hi)],'unchanged_from_original':True})
 result={'status':'PASS: combined-image scope, not diagnostic isolation from original',
         'original_main_sha256':ORIGINAL,'ui_main_sha256':UI,'diagnostic_main_sha256':DIAG,
         'comparisons':comparisons,'inherited_web_declared_ranges':len(wr),
         'inherited_web_allocated_bytes':sum(b-a for a,b in wr),'incremental_diagnostic_ranges':len(dr),
         'native_ranges_checked':checked,
         'inherited_scope':['WPS factory default 7 to 0; not proof of live saved configuration change.',
                            '18 image payloads and corresponding response lengths.',
                            'Dashboard/index/LAN/login pages and HTTP callbacks.',
                            'Management controller replaces jQuery; resource name and response length.'],
         'limits':['Three diagnostic ranges apply relative to UI candidate, not original firmware.',
                   'Unchanged native ranges do not prove unchanged behavior under different UI/configuration actions.',
                   'Offline CRC/decompression checks do not prove bootability or recovery.',
                   'No AP access, configuration actions, firmware builds or binary artifact writes.']}
 (ROOT/'candidate-scope-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'comparisons':comparisons,'native_ranges_checked':len(checked)},indent=2))
if __name__=='__main__':main()
