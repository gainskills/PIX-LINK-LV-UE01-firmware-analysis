"""Build an OFFLINE ONLY candidate; this script never contacts or writes a device."""
from pathlib import Path
import hashlib
import json
import lzma
import struct
import zlib

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
main = (ROOT / 'main-decompressed.bin').read_bytes()
image = (ROOT / 'uimage.bin').read_bytes()
header, payload = image[:64], image[64:]
assert struct.unpack_from('>I', header)[0] == 0x27051956
assert struct.unpack_from('>I', header, 12)[0] == len(payload)
assert zlib.crc32(payload) == struct.unpack_from('>I', header, 24)[0]
zero_crc_header = header[:4] + bytes(4) + header[8:]
assert zlib.crc32(zero_crc_header) == struct.unpack_from('>I', header, 4)[0]
old, new = b'WLN_WscConfMode=7\n', b'WLN_WscConfMode=0\n'
assert main.count(old) == 1
offset = main.index(old)
patched = main[:offset] + new + main[offset + len(old):]
diff = [i for i, (a, b) in enumerate(zip(main, patched)) if a != b]
assert len(main) == len(patched) and diff == [offset + len(old) - 2]
(OUT / 'main-wps-default-off.NOT-FLASHABLE.bin').write_bytes(patched)
start = 0x2440
original_stream = payload[start:]
assert lzma.decompress(original_stream, format=lzma.FORMAT_ALONE) == main
budget = len(original_stream)
report = {
    'status': 'offline analysis only; upgrade format and device acceptance unverified',
    'source_uimage_sha256': hashlib.sha256(image).hexdigest(),
    'changed_main_offsets': [hex(x) for x in diff],
    'change': 'factory default WLN_WscConfMode=7 -> 0 only',
    'existing_configuration_changed': False,
    'button_or_runtime_enable_paths_patched': False,
    'compression_budget': budget,
    'attempts': [],
}
for nice, depth in [(273, 64), (128, 0), (273, 256), (192, 64), (64, 0), (96, 256)]:
    stream = lzma.compress(patched, format=lzma.FORMAT_ALONE, filters=[{
        'id': lzma.FILTER_LZMA1, 'dict_size': 8 * 1024 * 1024,
        'lc': 3, 'lp': 0, 'pb': 2, 'mode': lzma.MODE_NORMAL,
        'nice_len': nice, 'mf': lzma.MF_BT4, 'depth': depth,
    }])
    stream = stream[:5] + struct.pack('<Q', len(patched)) + stream[13:]
    assert stream[:5] == original_stream[:5]
    assert lzma.decompress(stream, format=lzma.FORMAT_ALONE) == patched
    report['attempts'].append({'nice_len': nice, 'depth': depth, 'bytes': len(stream)})
    print(report['attempts'][-1], flush=True)
    if len(stream) > budget:
        continue
    # Keep the custom loader, all payload addresses and hardcoded end unchanged.
    new_payload = payload[:start] + stream + b'\xff' * (budget - len(stream))
    new_header = bytearray(header)
    struct.pack_into('>I', new_header, 24, zlib.crc32(new_payload))
    struct.pack_into('>I', new_header, 4, 0)
    struct.pack_into('>I', new_header, 4, zlib.crc32(new_header))
    candidate = bytes(new_header) + new_payload
    assert len(candidate) == len(image)
    assert candidate[64:64 + start] == payload[:start]
    assert lzma.decompress(candidate[64 + start:], format=lzma.FORMAT_ALONE) == patched
    assert zlib.crc32(candidate[64:]) == struct.unpack_from('>I', candidate, 24)[0]
    assert zlib.crc32(candidate[:4] + bytes(4) + candidate[8:64]) == struct.unpack_from('>I', candidate, 4)[0]
    dest = OUT / 'wps-default-off.uimage.NOT-FOR-FLASHING.bin'
    dest.write_bytes(candidate)
    report['candidate'] = dest.name
    report['candidate_sha256'] = hashlib.sha256(candidate).hexdigest()
    report['roundtrip_and_crcs_verified'] = True
    break
else:
    report['candidate'] = None
    report['reason'] = 'compressed data did not fit original loader allocation; no loader patch attempted'
(OUT / 'wps-default-candidate.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'attempts'}, indent=2))
