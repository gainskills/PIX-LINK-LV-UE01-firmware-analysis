"""Offline firmware web patch. Never accesses a device or writes flash."""
from pathlib import Path
import hashlib
import json
import lzma
import struct
import subprocess
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAIN = (ROOT / 'main-decompressed.bin').read_bytes()
BASE = 0x80000400
NODE = __import__('os').environ.get('NODE', 'node')
subprocess.run([NODE, str(HERE / 'minify.cjs')], check=True)
assets = []
data_offset = 0x19ecc2
for entry in range(0x1ede4c, 0x1ee3a8, 28):
    name_addr, handler, size, *_ = struct.unpack_from('<7I', MAIN, entry)
    assert BASE <= name_addr < BASE + len(MAIN)
    name_offset = name_addr - BASE
    name = MAIN[name_offset:MAIN.index(b'\0', name_offset)].decode()
    assets.append({'path': name, 'offset': data_offset, 'size': size, 'handler': hex(handler), 'name_offset': name_offset})
    data_offset += size
assert assets[-1]['path'] == '/wl_wps.htm'
assert len(assets) == 49
by_name = {a['path']: a for a in assets}
assert by_name['/lan.htm']['offset'] == 0x1d3b97
assert by_name['/js/jquery.js']['offset'] == 0x1ad83c
patched = bytearray(MAIN)
changes = []

def write(offset, data, why):
    before = bytes(patched[offset:offset + len(data)])
    assert len(before) == len(data)
    patched[offset:offset + len(data)] = data
    changes.append({'offset': hex(offset), 'bytes': len(data), 'purpose': why,
                    'before_sha256': hashlib.sha256(before).hexdigest(),
                    'after_sha256': hashlib.sha256(data).hexdigest()})

default = b'WLN_WscConfMode=7\n'
assert MAIN.count(default) == 1
write(MAIN.index(default) + len(default) - 2, b'0', 'WPS factory default off')
images = [a for a in assets if a['path'].startswith('/img/') or a['path'] == '/favicon.ico']
assert len(images) == 18 and sum(a['size'] for a in images) == 41127
assert images[-1]['offset'] + images[-1]['size'] == by_name['/index.htm']['offset']
for asset in images:
    # Keep the resource table and every following address intact. Repeated zero
    # bytes cost almost nothing in the compressed stream; do not shift code/data.
    write(asset['offset'], bytes(asset['size']), 'Remove old image payload: ' + asset['path'])
    handler = int(asset['handler'], 16) - BASE
    assert struct.unpack_from('<3I', MAIN, handler) == (
        0x00003021, 0x080047bc, 0x24070000 | asset['size'])
    write(handler + 8, struct.pack('<I', 0x24070000), 'Empty image response: ' + asset['path'])
    asset['response_bytes'] = 0
html = (HERE / 'lan.htm').read_bytes()
assert b'<img' not in html.lower() and b'url(' not in html.lower() and b'/img/' not in html.lower()
# Existing callbacks receive (context, resource_data). Tail-call the existing
# raw HTTP writer instead of injecting values at the old HTML byte offsets.
canonical = by_name['/index.htm']
assert len(html) <= canonical['size']
for path, prologue in [('/index.htm', 0x27bdffd0), ('/lan.htm', 0x27bdffe8)]:
    asset = by_name[path]
    body = html if path == '/index.htm' else b''
    write(asset['offset'], body.ljust(asset['size'], b' '), 'New image-free dashboard storage: ' + path)
    handler_offset = int(asset['handler'], 16) - BASE
    assert MAIN[handler_offset:handler_offset + 4] == struct.pack('<I', prologue)
    stub = struct.pack('<III', 0x00003021, 0x08000000 | ((0x80011ef0 >> 2) & 0x03ffffff),
                       0x24070000 | len(html))
    if path == '/lan.htm':
        address = BASE + canonical['offset']
        stub = struct.pack('<II', 0x3c050000 | (address >> 16), 0x34a50000 | (address & 65535)) + stub
    write(handler_offset, stub, 'Raw page callback; preserve caller stack and RA: ' + path)
    asset['response_bytes'] = len(html)
    asset['response_offset'] = canonical['offset']
login = by_name['/login.htm']
login_body = (HERE / 'login.htm').read_bytes()
assert len(login_body) <= login['size']
write(login['offset'], login_body.ljust(login['size'], b' '), 'Native image-free login page')
login_handler = int(login['handler'], 16) - BASE
assert MAIN[login_handler:login_handler+4] == struct.pack('<I', 0x27bdfff0)
write(login_handler, struct.pack('<III', 0x3021, 0x080047bc, 0x24070000 | len(login_body)), 'Raw native login callback')
login['response_bytes'] = len(login_body)
js = (HERE / 'settings.min.js').read_bytes() + b'\n'
resource = by_name['/js/jquery.js']
assert len(js) <= resource['size'], 'Scripts exceed fixed resource allocation'
assert len(js) <= 95786
write(resource['offset'], js.ljust(resource['size'], b' '), 'Native management controller; remove jQuery')
write(resource['name_offset'], b'/js/app.js\0'.ljust(len('/js/jquery.js')+1, b'\0'), 'Native controller resource name')
js_handler = int(resource['handler'], 16)-BASE
assert struct.unpack_from('<4I', MAIN, js_handler) == (0x3c070001,0x34e7762a,0x080047bc,0x3021)
write(js_handler, struct.pack('<4I',0x3c070000|(len(js)>>16),0x34e70000|(len(js)&65535),0x080047bc,0x3021), 'Native script actual response length')
resource['path'] = '/js/app.js'
resource['response_bytes'] = len(js)
assert len(patched) == len(MAIN)
# Every byte outside the reviewed patch ranges must remain identical.
expected = bytearray(len(MAIN))
for c in changes:
    offset = int(c['offset'], 16)
    expected[offset:offset + c['bytes']] = b'\1' * c['bytes']
assert all(a == b or expected[i] for i, (a, b) in enumerate(zip(MAIN, patched)))
(HERE / 'main-web-update.NOT-FLASHABLE.bin').write_bytes(patched)
preview = HERE / 'preview'
preview.mkdir(exist_ok=True)
# Remove the obsolete generated URL; source firmware/library backups stay intact.
old_script = preview / 'js/jquery.js'
if old_script.exists():
    old_script.unlink()
for asset in assets:
    if not asset['size']:
        continue
    dest = preview / asset['path'].lstrip('/')
    dest.parent.mkdir(parents=True, exist_ok=True)
    response_bytes = asset.get('response_bytes', asset['size'])
    response_offset = asset.get('response_offset', asset['offset'])
    dest.write_bytes(patched[response_offset:response_offset + response_bytes])

source = (ROOT / 'uimage.bin').read_bytes()
header, payload = source[:64], source[64:]
assert zlib.crc32(payload) == struct.unpack_from('>I', header, 24)[0]
assert zlib.crc32(header[:4] + bytes(4) + header[8:]) == struct.unpack_from('>I', header, 4)[0]
assert lzma.decompress(payload[0x2440:], format=lzma.FORMAT_ALONE) == MAIN
assert struct.unpack_from('>I', header, 12)[0] == len(payload)
budget = len(payload) - 0x2440
attempts = []
candidate = None
for nice in [128, 273, 64]:
    compressed = lzma.compress(bytes(patched), format=lzma.FORMAT_ALONE, filters=[{
        'id': lzma.FILTER_LZMA1, 'dict_size': 8 * 1024 * 1024, 'lc': 3,
        'lp': 0, 'pb': 2, 'mode': lzma.MODE_NORMAL, 'nice_len': nice, 'mf': lzma.MF_BT4}])
    compressed = compressed[:5] + struct.pack('<Q', len(patched)) + compressed[13:]
    assert compressed[:5] == payload[0x2440:0x2445]
    attempts.append({'nice_len': nice, 'bytes': len(compressed), 'budget': budget})
    print(attempts[-1], flush=True)
    if len(compressed) > budget:
        continue
    new_payload = payload[:0x2440] + compressed + b'\xff' * (budget - len(compressed))
    h = bytearray(header)
    struct.pack_into('>I', h, 24, zlib.crc32(new_payload))
    struct.pack_into('>I', h, 4, 0)
    struct.pack_into('>I', h, 4, zlib.crc32(h))
    candidate = bytes(h) + new_payload
    assert len(candidate) == len(source)
    assert candidate[64:64 + 0x2440] == payload[:0x2440]
    assert lzma.decompress(candidate[64 + 0x2440:], format=lzma.FORMAT_ALONE) == patched
    assert zlib.crc32(candidate[64:]) == struct.unpack_from('>I', candidate, 24)[0]
    assert zlib.crc32(candidate[:4] + bytes(4) + candidate[8:64]) == struct.unpack_from('>I', candidate, 4)[0]
    (HERE / 'web-wps-jquery.uimage.NOT-FOR-FLASHING.bin').write_bytes(candidate)
    break
report = {'status': 'offline candidate; not installed, device upgrade acceptance unverified',
          'main_length_preserved': True, 'changes': changes, 'compression': attempts,
          'image_resources_removed': len(images),
          'image_payload_bytes_removed': sum(a['size'] for a in images),
          'previous_compressed_bytes': 708533,
          'jquery': None, 'ui_script_bytes': len(js), 'ui_allocation': resource['size'],
          'candidate_sha256': hashlib.sha256(candidate).hexdigest() if candidate else None,
          'source_sha256': hashlib.sha256(source).hexdigest(), 'resource_map': assets}
(HERE / 'build-manifest.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k not in ['changes', 'resource_map']}, indent=2))
if candidate is None:
    raise SystemExit('No candidate fits original loader allocation; no address changes attempted')
