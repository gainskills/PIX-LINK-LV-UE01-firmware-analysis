"""Bounded forensic recovery of two already captured boot-block copies; reads only."""
import hashlib,json,time
from pathlib import Path
from datetime import datetime,timezone
from flash_backup import ROOT,Session,partial_read,parse_read,private_write

def main():
    source=ROOT/'private-captures/20261020T024526Z-capture-000000'
    dest=ROOT/'private-captures'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-boot-sample-recovered')
    dest.mkdir(mode=0o700)
    copies=[];repairs=[];started=time.monotonic()
    for copy in [0,1]:
        rows=partial_read((source/f'000000-{copy}-0.raw').read_bytes(),16384)
        for index,row in enumerate(rows):
            if row is not None:continue
            address=index*16;values=[]
            for repeat in [0,1]:
                value=None
                for attempt in range(3):
                    if time.monotonic()-started>90:raise TimeoutError('90-second sample recovery budget exceeded')
                    with Session() as session:raw=session.read(address,16)
                    private_write(dest/f'{copy}-{address:06x}-{repeat}-{attempt}.raw',raw)
                    try:value=parse_read(raw,16)
                    except ValueError:continue
                    break
                if value is None:raise ValueError('Unresolved corrupt row')
                values.append(value)
            if values[0]!=values[1]:raise ValueError('Repair reads disagree')
            rows[index]=values[0];repairs.append({'copy':copy,'address':hex(address),'two_clean_reads_match':True})
        data=b''.join(rows);private_write(dest/f'boot-16k-copy{copy}.bin',data);copies.append(data)
    if copies[0]!=copies[1]:raise ValueError('Independent reconstructed copies disagree')
    old=(ROOT.parent/'flash.bin').read_bytes()[:16384]
    report={'status':'PASS','scope':'First 16 KiB only; not full Flash backup','bytes':16384,'copies_match':True,'matches_old_backup':copies[0]==old,'sha256':hashlib.sha256(copies[0]).hexdigest(),'repaired_rows':repairs,'source_capture':str(source),'new_capture':str(dest),'device_operations':'spi rd only; each corrupt 16-byte row re-read twice','all_connections_closed':True}
    private_write(dest/'manifest.json',(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
