"""One bounded fault capture for the installed diagnostic v2; never flashes/resets.

Importing this module performs no I/O. Run only when fault collection is requested.
PHY queries issue MDIO reads and can clear BMSR latch bits; preserve both reads.
"""
import base64
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
EXPECTED='ae98632494f7df945e99ad534a905b009c388ed326991e50a2a8d2beab40481e'


def installation_paths(deployment):
    combined=(deployment/'combined-install-attempt.json').exists()
    stem='combined' if combined else 'phy-builtin-v2'
    expected='c2948bec9931d02837ccfe09b5f53aaf55b4e4cd00c1e6060c310f48a68b175a' if combined else EXPECTED
    startup=(deployment/'startup-trace-install-attempt.json').exists()
    if startup:
        stem='startup-trace'
        expected='81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377'
    result_path=deployment/(stem+'-install-result.json')
    result=json.loads(result_path.read_text())
    if result.get('candidate_sha256')!=expected or not result.get('phy_six_reads_valid'):
        raise ValueError('No verified diagnostic installation record for latest upload')
    if startup and not result.get('startup_trace_valid'):
        raise ValueError('Startup trace installation not verified')
    return deployment/(stem+'-install-attempt.json'),result_path


def parse_phy(raw):
    summaries=[];rows=[];errors=[]
    for line in raw.splitlines():
        line=line.strip()
        if not line.startswith(b'PHYDIAG'):continue
        summary=re.fullmatch(rb'PHYDIAG relink_calls=(\d+) last_cp0_count=(\d+)',line)
        row=re.fullmatch(rb'PHYDIAG p0 reg=(\d+) result=(-?\d+) hex=([0-9a-fA-F]{4,8})',line)
        if summary:
            values=[int(v) for v in summary.groups()]
            if any(v>0xffffffff for v in values):errors.append('Counter outside uint32')
            summaries.append(values)
        elif row:
            reg,result,value=row.groups();result=int(result);value=value.decode().lower()
            rows.append(dict(reg=int(reg),result=result,hex=value))
            if not (-0x80000000<=result<=65535) or (result & 0xffffffff)!=int(value,16):
                errors.append('Invalid result or mismatched hex')
        else:errors.append('Malformed diagnostic line')
    if len(summaries)!=1:errors.append('Missing or duplicate summary')
    order=[r['reg'] for r in rows]
    complete=not errors and order==[0,1,1,4,5,6] and all(r['result']>=0 for r in rows)
    report=dict(complete_valid=complete,rows=rows,errors=errors)
    if len(summaries)==1:
        report.update(relink_calls=summaries[0][0],last_cp0_count=summaries[0][1])
    if complete:report['bmsr_link']=[bool(rows[i]['result'] & 4) for i in (1,2)]
    return report


def main():
    if sys.argv[1:]:raise SystemExit('No arguments supported; run only for a requested fault capture.')
    sys.path[:0]=[str(ROOT.parent/'recovery'),str(ROOT.parent/'security')]
    from flash_backup import Session,ReadTimeout
    from preflight_install import parse_profile
    from capture_dma_state import REGISTERS,parse,http_probe
    from capture_mat_show import summarize
    os.umask(0o077)
    attempt_path,result_path=installation_paths(ROOT.parent/'deployment')
    installation=json.loads(result_path.read_text())
    expected=installation['candidate_sha256']
    attempt=json.loads(attempt_path.read_text())
    profile=parse_profile((Path(attempt['private_evidence_directory'])/'after-profile.private.bin').read_bytes())
    token=base64.b64encode(profile[b'SYS_USERS']+b':'+profile[b'SYS_ADMPASS']).decode()
    auth=('header = "Authorization: Basic '+token+'"\n').encode()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory=ROOT/'phy-fault-captures'/stamp
    directory.parent.mkdir(mode=0o700,exist_ok=True);directory.parent.chmod(0o700)
    directory.mkdir(mode=0o700)
    report=dict(at_utc=stamp,expected_installed_sha256=expected,snapshots=[],
                limits=['No reset, Flash/configuration writes or PHY configuration writes.',
                        'One PHY query can clear latched status; preserve both BMSR readings.',
                        'Sequential samples are not atomic; missing values are not zeros.',
                        'HTTP probes can update MAT; first MAT snapshot precedes probes.',
                        'Saved installation record is not a new firmware identity readback.',
                        'No automatic retries or persistent monitor.'])
    deadline=time.monotonic()+45
    def save_raw(name,raw):
        with os.fdopen(os.open(directory/(name+'.private.txt'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(raw)
    def query(session,name,command):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Capture deadline')
        mark=session.send(command)
        try:raw=session.wait(mark,lambda b:b'OS>' in b,min(3,remaining))
        except ReadTimeout as error:
            save_raw(name,error.partial)
            if command=='reg phy':report['phy_partial']=parse_phy(error.partial)
            raise
        save_raw(name,raw)
        return raw
    session=Session()
    # Session uses the saved credentials without placing them in command arguments.
    old_env={k:os.environ.get(k) for k in ['AP_DIAG_USER','AP_DIAG_PASSWORD']}
    os.environ['AP_DIAG_USER']=profile[b'SYS_USERS'].decode()
    os.environ['AP_DIAG_PASSWORD']=profile[b'SYS_ADMPASS'].decode()
    try:
        with session as s:
            for number in range(2):
                snapshot=dict(round=number,registers=[])
                report['snapshots'].append(snapshot)
                for address,name in REGISTERS.items():
                    raw=query(s,f'r{number}-{name}',f'reg r {address:08x}')
                    value=parse(raw,address)
                    entry=dict(name=name,address=hex(address),value=hex(value))
                    if name=='poa':entry['port0_link']=bool((value>>25)&1)
                    snapshot['registers'].append(entry)
                snapshot['mat']=summarize(query(s,f'r{number}-mat','iwpriv ra0 show matinfo'))
                if number==0:
                    report['phy']=parse_phy(query(s,'phy','reg phy'))
                    report['x99_http']=http_probe()
                    result=subprocess.run(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','2',
                                           '--max-time','4','--max-filesize','65536','--config','-',
                                           '--write-out','\n%{http_code}','http://192.168.1.2:8080/status.htm'],
                                          input=auth,capture_output=True,timeout=5)
                    body,_,code=result.stdout.rpartition(b'\n')
                    save_raw('status',body)
                    report['ap_http']=dict(curl_exit=result.returncode,status=code.decode(errors='replace'))
                    uptime=re.search(rb'\bvar\s+_uptime\s*=\s*["\x27](\d+)["\x27]',body)
                    report['ap_uptime_seconds']=int(uptime[1]) if result.returncode==0 and code==b'200' and uptime else None
    except Exception as error:report['error_type']=type(error).__name__
    finally:
        for key,value in old_env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        report['all_connections_closed']=not hasattr(session,'p') or session.p.poll() is not None
    report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    report['complete_capture']=not report.get('error_type') and report.get('phy',{}).get('complete_valid',False)
    (directory/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'latest-phy-fault.json').write_text(json.dumps({'capture':str(directory)},indent=2)+'\n')
    print(json.dumps(report,indent=2));print('Saved:',directory)


if __name__=='__main__':main()
