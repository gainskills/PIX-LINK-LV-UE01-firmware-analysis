"""Offline speed-path references and previously captured POA fields; no AP access."""
import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
B = (ROOT.parent / 'main-decompressed.bin').read_bytes()
SHA = '2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
assert hashlib.sha256(B).hexdigest() == SHA
SOURCE = ROOT.parent/'references/esw_rt3050-upstream.c'
source = SOURCE.read_text()
for name, value in [('LINK', 25), ('DUPLEX', 9), ('SPD', 0), ('FC', 16)]:
    assert re.search(r'#define\s+RT305X_ESW_' + name + r'_S\s+' + str(value) + r'\b', source)

calls = []
for offset in range(0, 0x163000, 4):
    word = struct.unpack_from('<I', B, offset)[0]
    if word >> 26 in (2, 3):
        target = 0x80000000 | ((word & 0x3ffffff) << 2)
        if target in (0x8001593c, 0x800159e0):
            caller = 0x80000400 + offset
            group = ('initialization' if 0x80015a88 <= caller < 0x80015c98 else
                     'active_relink' if 0x80017134 <= caller < 0x80017210 else 'other')
            calls.append({'address': hex(caller), 'target': hex(target),
                          'instruction': 'jal' if word >> 26 == 3 else 'j', 'group': group})
assert calls, 'No direct MDIO references found'
assert len(calls) == 32 and all(c['group'] != 'other' for c in calls)

strings = []
for value in (b'long_loop_thread', b'port#%d switch to 10M setting',
              b'port#%d switch to 100M normal setting'):
    offset = B.index(value)
    address = 0x80000400 + offset
    pointers = [hex(i) for i in range(0, len(B) - 3, 4)
                if struct.unpack_from('<I', B, i)[0] == address]
    strings.append({'string': value.decode(), 'address': hex(address),
                    'aligned_absolute_pointer_offsets': pointers})

samples = []
pattern = re.compile(r'Address = 0xb0110080, Value = 0x([ 0-9a-fA-F]+)')
for path in sorted((ROOT / 'cold-start-captures').glob('*-cli.json')):
    data = json.loads(path.read_text())
    # Only previously sanitized CLI output; never expose other fields or raw profiles.
    for match in pattern.finditer(data.get('output', '')):
        value = int(match.group(1).replace(' ', ''), 16)
        up = bool((value >> 25) & 1)
        samples.append({'capture': path.name, 'poa': hex(value), 'port': 0, 'link_up': up,
                        'reference_speed_mbps': (100 if value & 1 else 10) if up else None,
                        'reference_full_duplex': bool((value >> 9) & 1) if up else None,
                        'reference_flow_control': bool((value >> 16) & 1) if up else None})
assert samples, 'No historical POA samples parsed'
report = {
    'source_sha256': SHA, 'scan_file_range': ['0x0', '0x163000'],
    'direct_mdio_calls': calls, 'speed_related_strings': strings,
    'reference_source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'historical_poa_samples': samples,
    'summary': {'direct_mdio_call_count': len(calls),
                'parsed_samples': len(samples), 'link_up_samples': sum(s['link_up'] for s in samples),
                'link_up_reference_modes': sorted(set(
                    (s['reference_speed_mbps'], s['reference_full_duplex'], s['reference_flow_control'])
                    for s in samples if s['link_up']))},
    'limits': [
        'Raw aligned J/JAL scan is not a full control-flow or indirect-call proof.',
        'Absent absolute string pointers does not prove strings/code are unreachable.',
        'No periodic speed compensation thread has been established.',
        'Speed/duplex/flow fields use the local OpenWrt reference, not a matched MT7628KN SDK.',
        'Only link decoding has also been cross-checked in original native code.',
        'Link-down speed/duplex fields are omitted as invalid or stale.',
        'Historical point samples cannot exclude changes between samples or establish peer agreement.',
        'Flow-control bit is status, not a count or evidence of pause frames causing loss.',
        'No device access, packets, writes, configuration changes or new firmware images.']}
(ROOT / 'speed-path-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report['summary'], indent=2))
