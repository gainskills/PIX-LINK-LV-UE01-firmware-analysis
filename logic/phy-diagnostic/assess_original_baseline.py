"""In-memory layout/compression feasibility only. Emits JSON, never firmware binaries."""
import hashlib,json,lzma,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 original=(ROOT.parent/'main-decompressed.bin').read_bytes()
 diag=(ROOT/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
 assert sha(original)=='2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
 assert sha(diag)=='98d017b3db1975d51f684f012b61a68c4ac1d104f8e13541d3c7138ffcb7f6cc'
 lo,hi,callback=0x19ecc2,0x19f140,0xa4b0
 assert hi-lo==1150 and struct.unpack_from('<I',original,callback)[0]==0x2407047e
 trial=bytearray(original);trial[lo:hi]=bytes(hi-lo)
 trial[callback:callback+4]=struct.pack('<I',0x24070000)
 diagnostic_ranges=[(0x19ecc4,0x19efd0),(0x16d34,0x16d3c),(0x211ff0,0x211ff4)]
 for a,b in diagnostic_ranges:trial[a:b]=diag[a:b]
 allowed=[(lo,hi),(callback,callback+4),*diagnostic_ranges]
 assert len(trial)==len(original)
 assert all(any(a<=i<b for a,b in allowed) for i,(x,y) in enumerate(zip(original,trial)) if x!=y)
 assert sha(trial)=='0ccb104d36fe70b0c5411979eda687519c0395642efb6ff22a168b40ec5251fe'
 source=(ROOT.parent/'uimage.bin').read_bytes()
 properties=source[64+0x2440:64+0x2445]
 attempts=[]
 for nice in [128,273,64]:
  compressed=lzma.compress(bytes(trial),format=lzma.FORMAT_ALONE,filters=[dict(id=lzma.FILTER_LZMA1,dict_size=8*1024*1024,lc=3,lp=0,pb=2,mode=lzma.MODE_NORMAL,nice_len=nice,mf=lzma.MF_BT4)])
  compressed=compressed[:5]+struct.pack('<Q',len(trial))+compressed[13:]
  assert compressed[:5]==properties
  assert lzma.decompress(compressed,format=lzma.FORMAT_ALONE)==trial
  attempts.append({'nice_len':nice,'compressed_bytes':len(compressed),'headroom':708764-len(compressed)})
 best=min(attempts,key=lambda x:x['compressed_bytes'])
 result={'scope':'In-memory original-baseline diagnostic layout/size feasibility only; no image emitted',
         'original_main_sha256':sha(original),'modeled_main_sha256':sha(trial),
         'favicon_offset':hex(lo),'favicon_storage_bytes':hi-lo,'favicon_callback_instruction_offset':hex(callback),
         'diagnostic_payload_bytes':780,'main_bytes_unchanged':len(trial),'main_changed_bytes':sum(x!=y for x,y in zip(original,trial)),
         'compression_attempts':attempts,'best_nice_len':best['nice_len'],'compressed_bytes':best['compressed_bytes'],
         'budget':708764,'headroom':best['headroom'],'fits_original_container':best['compressed_bytes']<=708764,
         'original_wps_factory_default_preserved':True,
         'limits':['Only original favicon storage/response instruction plus existing diagnostic ranges changed in memory.',
                   'No firmware image created or applied; this is a design/packing experiment.',
                   'Original UI and defaults preserved except empty favicon response in model.',
                   'Placement execution/cache, hardware timing, startup and recovery remain unverified.']}
 (ROOT/'original-baseline-feasibility.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
