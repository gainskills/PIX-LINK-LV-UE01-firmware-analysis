"""Offline evidence extractor. Reads binaries only; never connects to an AP."""
from pathlib import Path
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
# Reuse the analysis environment; no packages are installed by this script.
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN

main = (ROOT / 'main-decompressed.bin').read_bytes()
flash = (ROOT / 'flash.bin').read_bytes()
base = 0x80000400
cs = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)

def cstr(address):
    offset = address - base
    assert 0 <= offset < len(main)
    return main[offset:main.index(b'\0', offset)].decode('ascii')

def instructions(start, end):
    assert base <= start < end <= base + len(main)
    return list(cs.disasm(main[start-base:end-base], start))

def require(address, mnemonic, operands):
    ins = instructions(address, address + 4)
    assert len(ins) == 1 and (ins[0].mnemonic, ins[0].op_str) == (mnemonic, operands), hex(address)

# Anchor the observed branches to real instructions, not reconstructed source.
require(0x8000e54c, 'jal', '0x8000e424')
require(0x8000e558, 'beq', '$v0, $v1, 0x8000e714')
require(0x8000e560, 'jal', '0x8000e398')
require(0x8000e568, 'beqz', '$v0, 0x8000e714')
require(0x8000e4a4, 'jal', '0x8015cb50')
require(0x8000e794, 'lw', '$ra, 0x6c($sp)')
require(0x8000e798, 'addiu', '$a0, $zero, 0x191')
require(0x80010498, 'beqz', '$v0, 0x80010e3c')
require(0x800106b0, 'jal', '0x80006614')
require(0x80010784, 'jal', '0x8000e4e0')
require(0x800066ec, 'jal', '0x80015268')
require(0x80006724, 'jal', '0x80015660')
require(0x80014c44, 'addiu', '$a0, $zero, 0x9f')
require(0x80014cf4, 'move', '$s0, $s2')

config_ids = {}
for offset in [0x1ed228, 0x1ed1a0]:
    address = struct.unpack_from('<I', main, offset)[0]
    config_ids[cstr(address)] = hex(struct.unpack_from('<I', main, offset-4)[0])
assert config_ids == {'SYS_USERS': '0x10b0200', 'SYS_ADMPASS': '0x1010200'}
assert cstr(0x80168504) == 'admin'
public_tokens = [cstr(a) for a in [0x8016850c,0x80168514,0x8016851c,0x80181b10,0x80168524,0x801670b4,0x8016852c]]
assert public_tokens == ['login','favicon','lang_','live','jquery','gl.js','fctest.htm']
assert cstr(0x80168450) == 'SYS_UPG'

chips = []
for offset in range(0x1ee9dc, 0x1ee9dc + 11*16, 16):
    name, device, packed, geometry = struct.unpack_from('<4I', main, offset)
    count = packed >> 16
    size = 0
    regions = []
    for index in range(count):
        block_bytes, blocks = struct.unpack_from('<II', main, geometry-base+index*8)
        regions.append({'erase_block_bytes':block_bytes,'blocks':blocks})
        size += block_bytes * blocks
    chips.append({'name':cstr(name),'entry_address':hex(base+offset),
                  'manufacturer_id':hex(packed & 0xff),'device_pattern':hex(device),
                  'compiled_geometry_bytes':size,'regions':regions})
assert len(chips) == 11 and chips[0]['compiled_geometry_bytes'] == 2097152

windows = [
    ('default_credentials_gate',0x8000e398,0x8000e424),
    ('public_path_substring_gate',0x8000e424,0x8000e4e0),
    ('authentication_and_failure',0x8000e4e0,0x8000e8f4),
    ('query_removed_before_auth',0x8000ff48,0x8000ff84),
    ('post_upload_detection',0x800103f0,0x800104b8),
    ('streaming_upload_before_dispatch_auth',0x80010588,0x80010798),
    ('firmware_upload_staging',0x80010e3c,0x80010eb4),
    ('streamed_flash_writer',0x800065a0,0x8000680c),
    ('flash_erase_wrapper',0x80015268,0x80015660),
    ('flash_program_wrapper',0x80015660,0x800158bc),
    ('flash_identification_and_geometry',0x80014b58,0x80014df0),
    ('referer_header_parsing',0x80010924,0x80010940),
]
lines = []
for name,start,end in windows:
    lines.append('\n'+name+' '+hex(start)+'..'+hex(end))
    lines.extend(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in instructions(start,end))
(HERE/'management-flash-audit-disassembly.txt').write_text('\n'.join(lines)+'\n')
report = {
    'scope':'Offline binary inspection only; findings are not live exploitation results.',
    'main_sha256':hashlib.sha256(main).hexdigest(),
    'captured_flash_sha256':hashlib.sha256(flash).hexdigest(),
    'captured_flash_bytes':len(flash),
    'physical_flash_bytes':None,
    'observed_jedec_id':None,
    'config_ids':config_ids,
    'authentication':{
        'entry':'0x8000e4e0',
        'default_admin_admin_skips_regular_auth':True,
        'evidence':['0x8000e398','0x8000e3bc','0x8000e3d0','0x8000e3dc','0x8000e404','0x8000e568'],
        'public_path_matching':'substring, not exact resource path',
        'public_path_tokens':public_tokens,
        'query_separated_before_path_auth':True,
        'failure_status':401,
        'current_device_credentials_checked':False,
        'live_bypass_verified':False,
    },
    'streamed_firmware_upload':{
        'command':'SYS_UPG',
        'pre_dispatch_path':['0x80010498','0x80010e3c','0x80010598','0x800106b0'],
        'writer':'0x80006614',
        'erase_call':'0x800066ec -> 0x80015268',
        'program_call':'0x80006724 -> 0x80015660',
        'later_regular_auth_call':'0x80010784 -> 0x8000e4e0',
        'assessment':'Potential pre-auth Flash side effects: a later authentication rejection cannot be assumed to undo streamed writes. Header/state constraints and live reachability remain unverified.',
        'live_test_performed':False,
    },
    'flash_identification':{
        'probe':'0x80014b58',
        'rdid_opcode':'0x9f',
        'selected_entry_pointer':'0x802131b8',
        'geometry_initializer':'0x80014d60',
        'non_exact_id_fallback_present':True,
        'fallback_initial_geometry_bytes':chips[0]['compiled_geometry_bytes'],
        'compiled_supported_entries':chips,
        'runtime_cli_spi_id_supported':False,
        'runtime_cli_note':'Known eCos help only lists rd/wr/er. Bootloader spi id is a different command environment.',
    },
    'recovery':{
        'bootloader':'U-Boot 1.1.3',
        'spi_id_help_offset':'0x1474b',
        'tftp_menu_offset':'0x13214',
        'successful_recovery_record_available':False,
    },
    'csrf':{
        'referer_header_is_parsed':True,
        'complete_server_origin_or_token_validation_verified':False,
        'new_ui_cookie_same_site':'Lax',
        'note':'SameSite on newly set UI cookies does not establish backend CSRF protection for existing cookies, non-browser clients, or same-site requests.',
    },
}
(HERE/'management-flash-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'instruction_anchors':'verified','chip_table_entries':len(chips),
                  'physical_capacity':'unknown','default_credentials_auth_shortcut':'present',
                  'streaming_upload':'pre-dispatch Flash-write path requires further validation',
                  'device_operations':0},indent=2))
