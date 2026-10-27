"""Read-only device identity/config backup before an explicitly authorized test."""
import datetime
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
BASE='http://192.168.1.2:8080'
IMAGE=ROOT/'security/preupload-hardening/web-preupload.uimage.NOT-FOR-FLASHING.bin'
EXPECTED='481ed9575c53ff9ab6d5021638f225eb35cb6ac7b7839d4e0a65ec6a13ae4bb3'


def get(path):
    r=subprocess.run(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','3',
                      '--max-time','6','--max-filesize','65536',BASE+path],capture_output=True,timeout=8)
    assert r.returncode==0,'Read-only HTTP transport failed'
    return r.stdout


def parse_profile(data):
    assert re.match(rb'^#PROFILE\r?\n#VER_2_1\r?\n',data),'Expected complete profile header'
    values={}
    for line in data.splitlines():
        key,sep,value=line.partition(b'=')
        if sep:
            assert key not in values,'Duplicate profile field'
            values[key]=value
    assert b'SYS_USERS' in values and b'SYS_ADMPASS' in values,'Missing account fields'
    return values


def main():
    os.umask(0o077)
    image=IMAGE.read_bytes();assert hashlib.sha256(image).hexdigest()==EXPECTED
    status=get('/status.htm')
    version=re.search(rb'v28K\.RPT\.\d{8}',status,re.I)
    assert version and version[0].lower()==b'v28k.rpt.20220716','Unexpected installed version'
    previous=(ROOT/'deployment/private-device-identity.txt').read_text()
    known=re.search(r"b'([0-9a-f]{2}(?::[0-9a-f]{2}){5})'",previous,re.I)
    assert known,'Missing known device identity reference'
    compact=lambda data:re.sub(rb'[:-]',b'',data.lower())
    assert compact(known[1].encode()) in compact(status),'Device identity mismatch'
    profile=get('/profile.bin');values=parse_profile(profile)
    # Verify unchanged saved fields after backup to catch an incomplete/racing capture.
    confirm=get('/profile.bin');assert parse_profile(confirm)==values,'Configuration changed during preflight'
    directory=ROOT/'deployment/private-captures'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory.mkdir(parents=True,mode=0o700)
    directory.parent.chmod(0o700);directory.chmod(0o700)
    with os.fdopen(os.open(directory/'before-profile.private.bin',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(profile)
    summary=dict(status='PASS: read-only identity and configuration preflight',
                 at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_url=BASE,
                 version=version[0].decode(),known_device_identity_matches=True,
                 candidate_sha256=EXPECTED,candidate_bytes=len(image),
                 configuration_backup_bytes=len(profile),configuration_double_read_matches=True,
                 default_admin_pair=values[b'SYS_USERS']==values[b'SYS_ADMPASS']==b'admin',
                 radio_bandwidth=values.get(b'WLN_HT_BW',b'').decode(),
                 mode=values.get(b'SYS_OPMODE',b'').decode(),
                 uploaded=False,reboot_requested=False,configuration_changed=False)
    (directory/'preflight.json').write_text(json.dumps(summary,indent=2)+'\n')
    (ROOT/'deployment/latest-preflight.json').write_text(json.dumps({'capture':str(directory),'candidate_sha256':EXPECTED},indent=2)+'\n')
    print(json.dumps(summary,indent=2));print('Private capture:',directory)


if __name__=='__main__':main()
