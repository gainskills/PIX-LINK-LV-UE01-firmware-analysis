"""Independent offline backup validator. Does not import the capture implementation."""
import hashlib,json,stat,struct,zlib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CAPTURE=ROOT/'private-captures/full-2m-readonly-nc'

def need(ok,message):
    if not ok:raise ValueError(message)
def inspect_copies(first,second):
    need(len(first)==2097152 and len(second)==2097152,'Expected two complete 2 MiB files')
    need(first==second,'Independent backup copies differ')
    offset=0x50000;header=bytearray(first[offset:offset+64])
    magic,hcrc,timestamp,length,load,entry,dcrc=struct.unpack_from('>7I',header)
    need(magic==0x27051956,'Missing uImage magic')
    header[4:8]=bytes(4);need(zlib.crc32(header)==hcrc,'uImage header CRC mismatch')
    end=offset+64+length
    need(length>0 and end<=len(first),'uImage extends outside captured Flash')
    need(zlib.crc32(first[offset+64:end])==dcrc,'uImage payload CRC mismatch')
    return {'bytes':len(first),'copies_identical':True,'sha256':hashlib.sha256(first).hexdigest(),'uimage_offset':hex(offset),'uimage_bytes':64+length,'uimage_sha256':hashlib.sha256(first[offset:end]).hexdigest(),'header_crc_valid':True,'payload_crc_valid':True,'upper_mib_all_ff':first[1048576:]==b'\xff'*1048576,'jedec_id_verified':False,'recovery_tested':False}

def verify():
    manifest=json.loads((CAPTURE/'manifest.json').read_text())
    need(manifest['status']=='PASS','Capture has not completed successfully')
    first=(CAPTURE/'flash-2m-copy0.bin').read_bytes();second=(CAPTURE/'flash-2m-copy1.bin').read_bytes()
    result=inspect_copies(first,second)
    need(result['sha256']==manifest['sha256'],'Capture manifest SHA mismatch')
    expected={f'{address:06x}' for address in range(0,2097152,16384)}
    need(set(manifest['verified_blocks'])==expected,'Missing or unexpected block ranges')
    for address in range(0,2097152,16384):
        key=f'{address:06x}';part=first[address:address+16384]
        need(hashlib.sha256(part).hexdigest()==manifest['verified_blocks'][key]['sha256'],'Block manifest SHA mismatch')
        for copy in (0,1):need((CAPTURE/f'{key}-copy{copy}.bin').read_bytes()==part,'Whole file differs from verified block')
    for name in ['flash-2m-copy0.bin','flash-2m-copy1.bin','manifest.json']:
        need(stat.S_IMODE((CAPTURE/name).stat().st_mode)==0o600,'Private file permissions changed')
    need(stat.S_IMODE(CAPTURE.stat().st_mode)==0o700,'Private directory permissions changed')
    known=(ROOT.parent/'uimage.bin').read_bytes()
    need(result['uimage_sha256']==hashlib.sha256(known).hexdigest(),'Live firmware differs from known source; review required')
    old=(ROOT.parent/'flash.bin').read_bytes()
    result.update(status='PASS: independently checked backup bytes and original firmware CRCs',verified_utc=datetime.now(timezone.utc).isoformat(),verified_blocks=len(expected),all_connections_closed=manifest['all_connections_closed'],old_prefix_bytes_compared=len(old),old_prefix_changed_bytes=sum(a!=b for a,b in zip(old,first)),old_boot_prefix_0_to_0x30000_matches=old[:0x30000]==first[:0x30000],private_backups=str(CAPTURE),limits=['Covers photographed chip nominal 2 MiB address window; live JEDEC ID remains unread.','Sequential block reads are not an atomic Flash snapshot.','Original uImage CRCs/SHA match, but no full-chip manufacturer checksum exists.','No restore, RAM boot or candidate flash has been tested.'])
    (ROOT/'full-backup-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':verify()
