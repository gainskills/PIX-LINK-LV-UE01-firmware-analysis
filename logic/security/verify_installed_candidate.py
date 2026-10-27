"""Read-only post-upgrade checks. No POST, scan, reset, or reboot."""
import base64
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path
from preflight_install import ROOT,BASE,EXPECTED,parse_profile


def main():
    os.umask(0o077)
    latest=json.loads((ROOT/'deployment/latest-preflight.json').read_text())
    directory=Path(latest['capture'])
    before=parse_profile((directory/'before-profile.private.bin').read_bytes())
    token=base64.b64encode(before[b'SYS_USERS']+b':'+before[b'SYS_ADMPASS']).decode()
    def get(path,auth=False):
        config=('header = "Authorization: Basic '+token+'"\n') if auth else ''
        r=subprocess.run(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','3','--max-time','6',
                          '--max-filesize','65536','--config','-','--write-out','\n%{http_code}',BASE+path],
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
    report=dict(status='PASS: new UI and read authentication verified' if all(c['expected_body_matches'] for c in checks) else 'CHECK_FAILED',
                at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_url=BASE,
                uploaded_candidate_sha256=EXPECTED,checks=checks,
                configuration_unchanged=not changed,
                limits=['Read-only HTTP checks; no config save or POST-auth probe after upgrade.',
                        'No X99, radio scan, persistence over another reboot or full Flash readback test.',
                        'Bootloader recovery remains unverified.'])
    (directory/'post-upgrade-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
