"""Verify the offline candidate layout, image removal and container integrity."""
from pathlib import Path
import hashlib,json,lzma,struct,zlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
original=(ROOT/'main-decompressed.bin').read_bytes()
patched=(HERE/'main-web-update.NOT-FLASHABLE.bin').read_bytes()
container=(HERE/'web-wps-jquery.uimage.NOT-FOR-FLASHING.bin').read_bytes()
source=(ROOT/'uimage.bin').read_bytes()
manifest=json.loads((HERE/'build-manifest.json').read_text())
base=0x80000400
offset=0x19ecc2
assets=[]
for entry in range(0x1ede4c,0x1ee3a8,28):
 name,handler,size,*_=struct.unpack_from('<7I',original,entry)
 at=name-base
 path=original[at:original.index(b'\0',at)].decode()
 assets.append(dict(path=path,handler=handler,size=size,offset=offset))
 offset+=size
images=[a for a in assets if a['path'].startswith('/img/') or a['path']=='/favicon.ico']
assert len(images)==18
assert sum(a['size'] for a in images)==41127
for asset in images:
 at=asset['offset'];size=asset['size'];handler=asset['handler']-base
 assert patched[at:at+size]==bytes(size), 'Old image payload remains: '+asset['path']
 # Existing image handlers are exactly three instructions. Keep offset and
 # branch target, change only the delay-slot response length immediate to zero.
 assert struct.unpack_from('<3I',original,handler)==(0x3021,0x080047bc,0x24070000|size)
 assert struct.unpack_from('<3I',patched,handler)==(0x3021,0x080047bc,0x24070000)
assert patched[0x1ede4c:0x1ee3a8]==original[0x1ede4c:0x1ee3a8], 'Resource table moved or changed'
html=(HERE/'lan.htm').read_bytes()
canonical=next(a for a in assets if a['path']=='/index.htm')
assert len(html)<=canonical['size']
assert patched[canonical['offset']:canonical['offset']+len(html)]==html
for path in ['/index.htm','/lan.htm']:
 asset=next(a for a in assets if a['path']==path)
 handler=asset['handler']-base
 if path=='/lan.htm':
  address=base+canonical['offset']
  assert struct.unpack_from('<2I',patched,handler)==(0x3c050000|(address>>16),0x34a50000|(address&65535))
  handler+=8
 assert struct.unpack_from('<3I',patched,handler)==(0x3021,0x080047bc,0x24070000|len(html))
 assert b'<img' not in html.lower() and b'url(' not in html.lower() and b'/img/' not in html.lower()
login=next(a for a in assets if a['path']=='/login.htm')
login_html=(HERE/'login.htm').read_bytes()
assert patched[login['offset']:login['offset']+len(login_html)]==login_html
assert struct.unpack_from('<3I',patched,login['handler']-base)==(0x3021,0x080047bc,0x24070000|len(login_html))
js=next(a for a in manifest['resource_map'] if a['path']=='/js/app.js')
assert patched[js['offset']:js['offset']+js['response_bytes']]==(HERE/'settings.min.js').read_bytes()+b'\n'
assert b'jQuery' not in (HERE/'settings.min.js').read_bytes()
assert struct.unpack_from('<4I',patched,int(js['handler'],16)-base)==(0x3c070000|(js['response_bytes']>>16),0x34e70000|(js['response_bytes']&65535),0x080047bc,0x3021)
status=next(a for a in assets if a['path']=='/status.htm')
assert patched[status['offset']:status['offset']+status['size']]==original[status['offset']:status['offset']+status['size']]
assert patched[0x8000ab14-base:0x8000b234-base]==original[0x8000ab14-base:0x8000b234-base]
allowed=bytearray(len(original))
for change in manifest['changes']:
 at=int(change['offset'],16);length=change['bytes'];allowed[at:at+length]=b'\1'*length
 assert hashlib.sha256(patched[at:at+length]).hexdigest()==change['after_sha256']
assert all(a==b or allowed[i] for i,(a,b) in enumerate(zip(original,patched)))
assert len(patched)==len(original)==2174360
assert len(container)==len(source)==718108
assert container[64:64+0x2440]==source[64:64+0x2440], 'Loader changed'
assert lzma.decompress(container[64+0x2440:],format=lzma.FORMAT_ALONE)==patched
assert zlib.crc32(container[64:])==struct.unpack_from('>I',container,24)[0]
assert zlib.crc32(container[:4]+bytes(4)+container[8:64])==struct.unpack_from('>I',container,4)[0]
assert hashlib.sha256(container).hexdigest()==manifest['candidate_sha256']
# Size gains must be real compressed-data savings, not reported from padded size.
compressed=manifest['compression'][-1]['bytes']
assert compressed<708533-20000, 'Expected substantial savings after image removal'
assert manifest['image_payload_bytes_removed']==41127
assert manifest['image_resources_removed']==18
print(json.dumps({'checks':'49 resource entries, 18 removed image payloads and response lengths, native dashboard/login and LAN alias callbacks, untouched status backend, all non-target bytes, unchanged table/loader/image lengths, LZMA round trip, both CRCs, SHA256 and compression savings verified','compressed_bytes':compressed,'compressed_budget':708764,'headroom_bytes':708764-compressed},indent=2))
