"""Resumable bounded read-only 2 MiB capture with independently reconstructed copies."""
import hashlib,json,time,os,contextlib
from datetime import datetime,timezone
from pathlib import Path
from flash_backup import ROOT,Session,parse_read,private_write
from safe_read import collect_rows
DEST=ROOT/'private-captures/full-2m-readonly-nc'
TOTAL=0x200000
BLOCK=16384

def sha(b):return hashlib.sha256(b).hexdigest()
def save(report):
    p=DEST/'manifest.json'
    if not p.exists():private_write(p,b'')
    tmp=DEST/'manifest.next.json'
    fd=os.open(tmp,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2);f.write('\n')
    tmp.replace(p)
def main():
    DEST.mkdir(mode=0o700,exist_ok=True);DEST.chmod(0o700);DEST.parent.chmod(0o700)
    now=datetime.now(timezone.utc).isoformat()
    report=json.loads((DEST/'manifest.json').read_text()) if (DEST/'manifest.json').exists() else {'status':'INCOMPLETE','started_utc':now,'nominal_bytes':TOTAL,'block_bytes':BLOCK,'verified_blocks':{},'scope':'2 MiB address window; not JEDEC identification or tested recovery'}
    if report.get('error'):report.setdefault('prior_incomplete_runs',[]).append({'recorded_utc':now,'error':report['error'],'verified_bytes':report.get('verified_bytes',0)})
    report['status']='IN_PROGRESS';report.pop('error',None);save(report)
    deadline=time.monotonic()+2400
    stack=contextlib.ExitStack();session=None
    def read(address,length,label):
        nonlocal session
        for attempt in range(2):
            if time.monotonic()>deadline:raise TimeoutError('40-minute run budget; verified blocks preserved for resume')
            try:
                if session is None:
                    session=stack.enter_context(Session());report['all_connections_closed']=False;save(report)
                raw=session.read(address,length)
            except (TimeoutError,EOFError,BrokenPipeError) as exc:
                partial=getattr(exc,'partial',b'')
                private_write(DEST/f'{address:06x}-{label}-timeout-{time.time_ns()}.raw',partial)
                stack.close();session=None;report['all_connections_closed']=True
                report.setdefault('transport_failures',[]).append({'address':hex(address),'length':length,'attempt':attempt,'error':str(exc),'received_bytes':len(partial)})
                save(report)
                if attempt==1:raise
                time.sleep(.1);continue
            private_write(DEST/f'{address:06x}-{label}-{time.time_ns()}.raw',raw)
            return raw

    try:
        for address in range(0,TOTAL,BLOCK):
            key=f'{address:06x}';existing=report['verified_blocks'].get(key)
            if existing:
                for copy in (0,1):
                    data=(DEST/f'{key}-copy{copy}.bin').read_bytes()
                    if len(data)!=BLOCK or sha(data)!=existing['sha256']:raise ValueError('Saved verified block hash mismatch')
                continue
            for block_attempt in range(2):
                reconstructed=[];repair_count=0
                for copy in (0,1):
                    rows=collect_rows(read,address,BLOCK,f'copy{copy}-segment')
                    for index,row in enumerate(rows):
                        if row is not None:continue
                        values=[]
                        for repeat in (0,1):
                            value=None
                            for attempt in range(3):
                                raw=read(address+index*16,16,f'copy{copy}-repair{repeat}-{attempt}')
                                try:value=parse_read(raw,16)
                                except ValueError:continue
                                break
                            if value is None:raise ValueError('Corrupt small response persisted')
                            values.append(value)
                        if values[0]!=values[1]:raise ValueError('Small repair reads disagree')
                        rows[index]=values[0];repair_count+=1
                    reconstructed.append(b''.join(rows))
                if reconstructed[0]==reconstructed[1]:break
                stamp=time.time_ns()
                for copy,data in enumerate(reconstructed):private_write(DEST/f'{key}-rejected-pair{block_attempt}-{stamp}-copy{copy}.bin',data)
                report.setdefault('block_disagreements',[]).append({'address':hex(address),'pair_attempt':block_attempt,'rejected_copy_sha256':[sha(data) for data in reconstructed],'repaired_rows_before_discard':repair_count})
                save(report)
            else:raise ValueError(f'Independent copies still differ after two full pairs at {address:#x}')
            for copy,data in enumerate(reconstructed):
                path=DEST/f'{key}-copy{copy}.bin'
                if not path.exists():private_write(path,data)
                if path.read_bytes()!=data:raise ValueError('Existing block file differs; refusing overwrite')
            report['verified_blocks'][key]={'sha256':sha(reconstructed[0]),'repaired_rows':repair_count,'two_copies_match':True}
            report['verified_bytes']=len(report['verified_blocks'])*BLOCK;save(report)
            print(json.dumps({'verified_bytes':report['verified_bytes'],'total_bytes':TOTAL,'percent':round(100*report['verified_bytes']/TOTAL,2),'last_block':hex(address),'repaired_rows':repair_count,'connection_reused':True}),flush=True)
        copies=[]
        for copy in (0,1):
            data=b''.join((DEST/f'{address:06x}-copy{copy}.bin').read_bytes() for address in range(0,TOTAL,BLOCK))
            if len(data)!=TOTAL:raise ValueError('Full image length mismatch')
            output=DEST/f'flash-2m-copy{copy}.bin'
            if not output.exists():private_write(output,data)
            if output.read_bytes()!=data:raise ValueError('Saved complete output differs')
            copies.append(data)
        if copies[0]!=copies[1]:raise ValueError('Full copies differ')
        stack.close();session=None
        report.update(status='PASS',bytes=TOTAL,sha256=sha(copies[0]),finished_utc=datetime.now(timezone.utc).isoformat(),all_connections_closed=True,hardware_recovery_tested=False,jedec_id_read=False)
        save(report);print(json.dumps({k:report[k] for k in ['status','bytes','sha256','all_connections_closed','hardware_recovery_tested','jedec_id_read']},indent=2),flush=True)
    except BaseException as exc:
        stack.close();session=None
        report.update(status='INCOMPLETE',error=f'{type(exc).__name__}: {exc}',all_connections_closed=True);save(report)
        print(json.dumps({'status':'INCOMPLETE','error':report['error'],'verified_bytes':len(report['verified_blocks'])*BLOCK,'resume_manifest':str(DEST/'manifest.json')},indent=2),flush=True)
        raise
if __name__=='__main__':main()
