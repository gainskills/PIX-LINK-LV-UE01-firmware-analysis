"""Offline evidence extraction only; no device access."""
import hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
from capstone import Cs,CS_ARCH_MIPS,CS_MODE_MIPS32,CS_MODE_LITTLE_ENDIAN
flash=(ROOT.parent/'flash.bin').read_bytes()
main=(ROOT.parent/'main-decompressed.bin').read_bytes()
def cstr(b,offset):return b[offset:b.index(b'\0',offset)].decode('ascii')
result={'scope':'Offline recovery survey; not a tested recovery procedure','old_flash_bytes':len(flash),'old_flash_sha256':hashlib.sha256(flash).hexdigest(),'nominal_chip_bytes_from_prior_pcb_review':0x200000,'actual_jedec_id':None,'complete_flash_backup_verified':False,'recovery_tested':False,'compiled_boot_defaults':{},'boot_menu':{},'commands':{}}
for key in ['baudrate','bootdelay','ipaddr','serverip']:
    token=(key+'=').encode();start=flash.find(token,0x16000,0x16200)
    if start>=0:result['compiled_boot_defaults'][key]=cstr(flash,start).split('=',1)[1]
for name,offset in [('ram_tftp',0x131e4),('flash_tftp',0x13214),('default_flash_boot',0x1324c)]:result['boot_menu'][name]={'file_offset':hex(offset),'text':cstr(flash,offset)}
for name,offset in [('bootm',0x16f10),('tftpboot',0x16f40),('saveenv',0x16fa0)]:
    fields=struct.unpack_from('<6I',flash,offset)
    actual=cstr(flash,fields[0]-0xbc000000)
    assert actual==name
    result['commands'][name]={'table_file_offset':hex(offset),'linked_function_address':hex(fields[3]),'function_file_offset':hex(fields[3]-0xbc000000)}
md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
lines=[]
for title,b,base,lo,hi in [('Runtime SPI read bounds',main,0x80000400,0x80112cf4,0x80112d88),('Boot menu printing',flash,0,0x1358,0x1418),('RAM versus Flash menu branches',flash,0,0x25e0,0x2674),('Shared load/dispatch',flash,0,0x2868,0x28a8)]:
    lines.append(title)
    for i in md.disasm(b[lo-base:hi-base],lo):lines.append(f'{i.address:08x} {i.bytes.hex():8} {i.mnemonic} {i.op_str}')
(ROOT/'recovery-path-disassembly.txt').write_text('\n'.join(lines)+'\n')
# Public evidence copies only summaries/hashes, never Flash contents or console payloads.
probe=ROOT/'private-captures/20261020T023744Z-probe-000000/manifest.json'
sample=ROOT/'private-captures/20261020T025253Z-boot-sample-recovered/manifest.json'
p=json.loads(probe.read_text());s=json.loads(sample.read_text())
assert p['status']=='PASS' and s['status']=='PASS'
result['live_read_only_probe']={'addresses':[r['address'] for r in p['records']],'repeated_reads_match':all(r['repeated_reads_match'] for r in p['records']),'scope':'16 bytes at each address, twice; does not establish full capacity or contents'}
result['verified_boot_sample']={k:s[k] for k in ['bytes','copies_match','matches_old_backup','sha256','all_connections_closed']}
result['verified_boot_sample']['repaired_row_count']=len(s['repaired_rows'])
current=ROOT/'private-captures/full-2m-readonly-nc/manifest.json'
full=json.loads((current if current.exists() else ROOT/'private-captures/full-2m-readonly/manifest.json').read_text())
result['full_capture_attempt']={k:full.get(k) for k in ['status','verified_bytes','error','all_connections_closed']}
checked=ROOT/'full-backup-verification.json'
if checked.exists():
    verified=json.loads(checked.read_text())
    result['complete_flash_backup_verified']=full['status']=='PASS' and verified.get('sha256')==full.get('sha256') and verified.get('copies_identical') is True
    result['full_backup_verification']=verified
result['user_has_serial_adapter_and_meter']=False
result['ram_boot_limits']=['Menu and command code are present; serial access is not verified.','TFTP autostart conditionally calls the same environment save backend as saveenv when the parameter-change flag is nonzero.','The startup GPIO Upgrade Mode path contains firmware write and 0x30000/0x10000 erase calls; it is not a RAM-only route.','Compiled default addresses/baudrate are not live environment measurements.','No verified software-only RAM trial-boot or recovery procedure has been established.']
boot_experiment=ROOT/'boot-path-experiment.json'
if boot_experiment.exists():result['boot_path_experiments']=json.loads(boot_experiment.read_text())
console_experiment=ROOT/'boot-console-experiment.json'
if console_experiment.exists():result['boot_console_experiments']=json.loads(console_experiment.read_text())
(ROOT/'recovery-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'evidence_written':str(ROOT/'recovery-evidence.json'),'boot_sample_bytes':s['bytes'],'complete_flash_backup_verified':result['complete_flash_backup_verified'],'recovery_tested':False},indent=2))
