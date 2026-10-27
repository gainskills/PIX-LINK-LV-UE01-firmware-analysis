"""Read-only post-upgrade checks. No POST, scan, reset, or reboot."""
import base64
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path
from preflight_install import ROOT,BASE,parse_profile
EXPECTED="81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377"


def main():
    os.umask(0o077)
    latest=json.loads((ROOT/'deployment/startup-trace-install-attempt.json').read_text())
    directory=Path(latest['private_evidence_directory'])
    before=parse_profile((directory/'before-profile.private.bin').read_bytes())
    token=base64.b64encode(before[b'SYS_USERS']+b':'+before[b'SYS_ADMPASS']).decode()
    def get(path,auth=False):
        config=('header = "Authorization: Basic '+token+'"\n') if auth else ''
        r=subprocess.run(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','3','--max-time','6',
                          '--max-filesize','150000','--config','-','--write-out','\n%{http_code}',BASE+path],
                         input=config.encode(),capture_output=True,timeout=8)
        body,_,code=r.stdout.rpartition(b'\n')
        if r.returncode:raise RuntimeError('Management GET failed, curl exit '+str(r.returncode))
        return body,int(code)
    sha=lambda b:hashlib.sha256(b).hexdigest()
    checks=[]
    expected_script=(ROOT/'web-update/settings.min.js').read_bytes()+b'\n'
    for path,auth,expected in [('/js/app.js',False,expected_script),
                               ('/index.htm',False,(ROOT/'web-update/login.htm').read_bytes()),
                               ('/index.htm',True,(ROOT/'web-update/lan.htm').read_bytes())]:
        body,code=get(path,auth)
        checks.append(dict(path=path,authenticated=auth,http_status=code,
                           body_sha256=sha(body),expected_body_matches=body==expected))
    anonymous,code=get('/profile.bin')
    anonymous_profile=bool(anonymous.startswith(b'#PROFILE'))
    checks.append(dict(path='/profile.bin',authenticated=False,http_status=code,profile_disclosed=anonymous_profile,
                       expected_body_matches=not anonymous_profile and anonymous==(ROOT/'web-update/login.htm').read_bytes()))
    body,code=get('/profile.bin?ts=post-upgrade',True);after=parse_profile(body)
    with os.fdopen(os.open(directory/'after-profile.private.bin',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(body)
    changed=[key.decode() for key in sorted(set(before)|set(after)) if before.get(key)!=after.get(key)]
    checks.append(dict(path='/profile.bin',authenticated=True,http_status=code,
                       expected_body_matches=not changed,changed_configuration_fields=changed))
    body,code=get('/js/app.js?v=post-upgrade')
    checks.append(dict(path='/js/app.js?v=post-upgrade',authenticated=False,http_status=code,
                       expected_body_matches=code in (401,403) and body!=expected_script))
    body,code=get('/js/app.js?v=post-upgrade',True)
    checks.append(dict(path='/js/app.js?v=post-upgrade',authenticated=True,http_status=code,
                       expected_body_matches=code==200 and body==expected_script))
    import re,sys
    import datetime
    body,code=get('/status.htm',True)
    (directory/'after-status.private.htm').write_bytes(body)
    uptime=re.search(rb'\bvar\s+_uptime\s*=\s*["\x27](\d+)["\x27]',body)
    checks.append(dict(path='/status.htm',authenticated=True,http_status=code,expected_body_matches=code==200 and uptime is not None))
    report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_url=BASE,
                candidate_sha256=EXPECTED,checks=checks,configuration_unchanged=not changed,
                changed_configuration_fields=changed,ap_uptime_seconds=int(uptime[1]) if uptime else None,
                private_evidence_directory=str(directory),
                limits=['Resource/authentication and diagnostic behavior verification, not full Flash readback.',
                        'PHY BMSR reads may clear latched status; both readings retained.',
                        'No real Wi-Fi scan, configuration save, extra reboot or long-term stability test.'])
    passed=all(c['expected_body_matches'] for c in checks)
    report['phy_six_reads_valid']=False
    if passed:
        sys.path[:0]=[str(ROOT/'recovery'),str(ROOT/'ssid-airplay')]
        from flash_backup import Session,ReadTimeout
        from capture_phy_fault import parse_phy
        session=Session();raw=b''
        previous={k:os.environ.get(k) for k in ['AP_DIAG_USER','AP_DIAG_PASSWORD']}
        os.environ['AP_DIAG_USER']=before[b'SYS_USERS'].decode()
        os.environ['AP_DIAG_PASSWORD']=before[b'SYS_ADMPASS'].decode()
        try:
            with session as s:
                mark=s.send('reg phy')
                try:
                    raw=s.wait(mark,lambda b:b'OS>' in b,5);report['phy_response_complete']=True
                except ReadTimeout as error:
                    raw=error.partial;report['phy_response_complete']=False
        except Exception as error:report['phy_error_type']=type(error).__name__
        finally:
            for key,value in previous.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
            report['connections_closed']=not hasattr(session,'p') or session.p.poll() is not None
        (directory/'startup-trace-phy-baseline.private.txt').write_bytes(raw)
        report['phy']=parse_phy(raw)
        report['phy_six_reads_valid']=report['phy']['complete_valid'] and report.get('phy_response_complete',False)
        if 'relink_calls' in report['phy']:report['relink_calls']=report['phy']['relink_calls']
    x99=subprocess.run(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','2','--max-time','3',
                        '-o','/dev/null','-w','%{http_code}','http://192.168.1.4/'],capture_output=True,timeout=4)
    report['x99_http']=dict(curl_exit=x99.returncode,status=x99.stdout.decode(errors='replace'))
    traces={}
    if report.get('phy_six_reads_valid'):
        for slot,caller,parent in re.findall(rb'PHYTRACE slot=(\d+) caller=([0-9a-fA-F]{8}) parent=([0-9a-fA-F]{8})',raw):
            traces[int(slot)]=dict(slot=int(slot),caller_return=caller.decode(),parent_return=parent.decode())
        for slot,seq,poa in re.findall(rb'PHYTRACE slot=(\d+) seq=(\d+) poa=([0-9a-fA-F]{8})',raw):
            traces.setdefault(int(slot),dict(slot=int(slot))).update(sequence=int(seq),poa_before=poa.decode(),link_up_before=bool(int(poa,16)&(1<<25)))
        for slot,state,pending in re.findall(rb'PHYTRACE slot=(\d+) state=(\d+) pending=(\d+)',raw):
            traces.setdefault(int(slot),dict(slot=int(slot))).update(upstream_state=int(state),pending_request=int(pending))
        for slot,clock in re.findall(rb'PHYTRACE slot=(\d+) cp0=(\d+)',raw):
            traces.setdefault(int(slot),dict(slot=int(slot))).update(raw_cp0_count=int(clock))
    report['startup_trace_records']=[traces[k] for k in sorted(traces)]
    report['startup_trace_valid']=bool(traces) and sorted(traces)==list(range(min(report.get('relink_calls',0),8))) and all(len(v)==9 for v in traces.values())
    report['status']='PASS: startup trace/UI/authentication and unchanged config verified' if passed and report['phy_six_reads_valid'] and report['startup_trace_valid'] else 'INCOMPLETE: inspect evidence'
    (directory/'startup-trace-install-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'deployment/startup-trace-install-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))



if __name__=='__main__':main()
