"""Offline byte-range exercise; never emits a flash image or uses device I/O."""
import hashlib
import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_image(data):
    assert len(data) >= 64
    magic, hcrc, _, size, _, _, dcrc = struct.unpack_from('>7I', data)
    assert magic == 0x27051956 and len(data) == size + 64
    header = bytearray(data[:64])
    header[4:8] = bytes(4)
    assert zlib.crc32(header) == hcrc
    assert zlib.crc32(data[64:]) == dcrc


def main():
    private = ROOT / 'private-captures/full-2m-readonly-nc'
    original = (private / 'flash-2m-copy0.bin').read_bytes()
    assert original == (private / 'flash-2m-copy1.bin').read_bytes()
    assert len(original) == 0x200000
    assert digest(original) == 'b3413627600d69787c731355827d633bee30407062886df0fc7489d6aa704f9a'
    stock = (ROOT.parent / 'uimage.bin').read_bytes()
    candidate = (ROOT.parent / 'phy-diagnostic/original-baseline/phy-diagnostic.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    assert digest(candidate) == '64421c4fada9034e9622b0a839745a758534dc75d77ad79dd6da9b71bdbf3706'
    check_image(stock)
    check_image(candidate)
    start, end = 0x50000, 0x50000 + len(candidate)
    assert len(stock) == len(candidate) == 718108
    assert original[start:end] == stock and end == 0xff51c
    proposed = bytearray(original)
    proposed[start:end] = candidate
    assert proposed[:start] == original[:start] and proposed[end:] == original[end:]
    models = []
    for alignment in (0x1000, 0x10000):
        lower = start // alignment * alignment
        upper = (end + alignment - 1) // alignment * alignment
        # Model erase/rewrite with all out-of-image bytes explicitly preserved.
        applied = bytearray(original)
        applied[lower:upper] = b'\xff' * (upper - lower)
        applied[lower:upper] = proposed[lower:upper]
        assert applied == proposed
        rolled_back = bytearray(applied)
        rolled_back[lower:upper] = b'\xff' * (upper - lower)
        rolled_back[lower:upper] = original[lower:upper]
        assert rolled_back == original
        # Also include the known GPIO-upgrade environment erase as a hazard model.
        hazard = bytearray(applied)
        hazard[0x30000:0x40000] = b'\xff' * 0x10000
        hazard[lower:upper] = original[lower:upper]
        residual = sum(a != b for a, b in zip(hazard, original))
        assert residual > 0 and hazard != original
        hazard[0x30000:0x40000] = original[0x30000:0x40000]
        assert hazard == original
        tail = original[end:upper]
        models.append({
            'assumed_alignment_bytes': alignment,
            'erase_span_half_open': [hex(lower), hex(upper)],
            'blocks_in_span': (upper - lower) // alignment,
            'out_of_image_prefix_bytes': start - lower,
            'out_of_image_tail_bytes': len(tail),
            'out_of_image_tail_non_ff_bytes': sum(v != 255 for v in tail),
            'memory_apply_exact': True, 'memory_rollback_exact': True,
            'rollback_sha256': digest(rolled_back),
            'image_only_rollback_after_environment_erase_exact': False,
            'remaining_changed_bytes_in_environment_hazard_model': residual,
            'memory_rollback_including_environment_exact': True,
        })
    report = {
        'status': 'PASS: offline layout and rollback byte exercises; hardware recovery unverified',
        'backup_sha256': digest(original), 'stock_uimage_sha256': digest(stock),
        'candidate_uimage_sha256': digest(candidate),
        'image_span_half_open': [hex(start), hex(end)],
        'image_bytes': len(candidate),
        'changed_image_bytes': sum(a != b for a, b in zip(stock, candidate)),
        'outside_image_unchanged_in_replacement_model': True,
        'alignment_models': models,
        'limits': [
            '4 KiB and 64 KiB are hypothetical alignment models, not measured erase geometry.',
            'Memory replacement is not a simulation of Flash timing, partial writes or power loss.',
            'Environment hazard models the separately located boot upgrade erase call; no hardware backend executes.',
            'Backup is a historical sequential capture; restoring its environment may revert later settings.',
            'No flashable whole-chip file, device command, network access or hardware operation is produced.',
            'Original/candidate CRC validity and byte reversibility do not establish safe upgrade or recovery.',
        ],
    }
    (ROOT / 'rollback-layout-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
