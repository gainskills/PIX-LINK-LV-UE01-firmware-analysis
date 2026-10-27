"""One-shot upload for the user's explicitly authorized experimental test.

No retries, configuration import, reset or separate reboot command. Do not run
without the user's approval of this exact candidate and unverified recovery risk.
"""
import base64
import datetime
import hashlib
import json
import os
import subprocess
from preflight_install import ROOT,BASE,IMAGE,EXPECTED,parse_profile


def main():
    os.umask(0o077)
    latest=json.loads((ROOT/'deployment/latest-preflight.json').read_text())
    directory=__import__('pathlib').Path(latest['capture'])
    assert latest['candidate_sha256']==EXPECTED
    assert hashlib.sha256(IMAGE.read_bytes()).hexdigest()==EXPECTED
    before=parse_profile((directory/'before-profile.private.bin').read_bytes())
    credentials=before[b'SYS_USERS']+b':'+before[b'SYS_ADMPASS']
    config='header = "Authorization: Basic '+base64.b64encode(credentials).decode()+'"\n'
    common=['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','5','--config','-']
    check=subprocess.run(common+['--max-time','8',BASE+'/profile.bin'],input=config.encode(),capture_output=True,timeout=10)
    assert check.returncode==0 and parse_profile(check.stdout)==before,'Pre-upload config mismatch or read failure'
    evidence=directory/'upgrade-attempt.json'
    attempt=dict(status='POST_STARTED',at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 base_url=BASE,candidate_sha256=EXPECTED,bytes=IMAGE.stat().st_size,
                 user_authorized_experimental_flash=True,recovery_unverified=True,
                 automatic_retries=False,separate_reboot_requested=False)
    # Exclusive file creation prevents a second run from silently uploading again.
    with os.fdopen(os.open(evidence,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(attempt,f,indent=2)
    response=directory/'upgrade-response.private.bin'
    with os.fdopen(os.open(response,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb'):pass
    command=common+['--max-time','180','--header','Expect:',
                    '--form','CMD=SYS_UPG','--form','GO=index.htm',
                    '--form','files=@'+str(IMAGE)+';type=application/octet-stream',
                    '--output',str(response),'--write-out','%{http_code} %{size_upload} %{size_download}',
                    BASE+'/setok.htm']
    try:
        result=subprocess.run(command,input=config.encode(),capture_output=True,timeout=190)
        metrics=result.stdout.decode('ascii',errors='replace').strip().split()
        attempt.update(status='POST_FINISHED_UNVERIFIED',curl_exit=result.returncode,
                       http_status=metrics[0] if metrics else None,
                       uploaded_bytes=metrics[1] if len(metrics)>1 else None,
                       response_bytes=response.stat().st_size,
                       transport_error=result.stderr.decode(errors='replace')[:500])
    except subprocess.TimeoutExpired:
        attempt.update(status='POST_TIMED_OUT_UNVERIFIED')
    attempt['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    evidence.write_text(json.dumps(attempt,indent=2)+'\n')
    print(json.dumps(attempt,indent=2))
    print('An upload response does not prove successful Flash or boot; no automatic retry.')


if __name__=='__main__':main()
