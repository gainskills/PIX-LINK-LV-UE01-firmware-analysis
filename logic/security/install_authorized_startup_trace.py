"""One-shot installation of the explicitly authorized startup trace image."""
import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from preflight_install import ROOT, BASE, parse_profile

EXPECTED = '81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377'


def main():
    os.umask(0o077)
    diagnostic = ROOT/'phy-diagnostic'
    sys.path.insert(0, str(diagnostic))
    from verify_startup_trace import main as verify_artifacts
    image = diagnostic/'startup-trace/startup-trace.uimage.NOT-FOR-FLASHING.bin'
    dst = image.parent
    data = image.read_bytes()
    assert hashlib.sha256(data).hexdigest()==EXPECTED
    verify_artifacts()
    verified=json.loads((dst/'verification-results.json').read_text())
    deployment = ROOT/'deployment'
    install = json.loads((deployment/'upgrade-result.json').read_text())
    known = parse_profile((Path(install['private_evidence_directory'])/'before-profile.private.bin').read_bytes())
    config = ('header = "Authorization: Basic '+base64.b64encode(known[b'SYS_USERS']+b':'+known[b'SYS_ADMPASS']).decode()+'"\n').encode()
    common = ['/usr/bin/curl', '-q', '-sS', '--noproxy', '*', '--connect-timeout', '5', '--config', '-']
    def get(path):
        r = subprocess.run(common+['--max-time', '8', '--max-filesize', '150000', BASE+path], input=config, capture_output=True, timeout=10)
        assert r.returncode==0, 'Preflight GET failed'
        return r.stdout
    status = get('/status.htm')
    reference = (ROOT/'deployment/private-device-identity.txt').read_text()
    mac = re.search(r"b'([0-9a-f]{2}(?::[0-9a-f]{2}){5})'", reference, re.I)
    compact = lambda b: re.sub(rb'[:-]', b'', b.lower())
    assert mac and compact(mac[1].encode()) in compact(status), 'Device identity mismatch'
    assert b'v28k.rpt.20220716' in status.lower(), 'Unexpected version'
    profile = get('/profile.bin');before = parse_profile(profile)
    assert before==parse_profile(get('/profile.bin')), 'Config changed during preflight'
    assert get('/js/app.js')==(ROOT/'web-update/settings.min.js').read_bytes()+b'\n', 'Current UI resource mismatch'
    favicon = get('/favicon.ico')
    assert favicon==b'', 'Expected installed diagnostic firmware before combined upgrade'
    prior=json.loads((deployment/'combined-install-result.json').read_text())
    assert prior['candidate_sha256']=='c2948bec9931d02837ccfe09b5f53aaf55b4e4cd00c1e6060c310f48a68b175a'
    assert prior['configuration_unchanged'] and prior['phy_six_reads_valid']
    directory = deployment/'private-captures'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-startup-trace-install')
    directory.mkdir(mode=0o700)
    (directory/'before-profile.private.bin').write_bytes(profile)
    (directory/'before-status.private.htm').write_bytes(status)
    (directory/'artifact-verification.json').write_text(json.dumps(verified, indent=2)+'\n')
    attempt = dict(status='POST_STARTED', at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   base_url=BASE, candidate_sha256=EXPECTED, candidate_bytes=len(data),
                   known_device_identity_matches=True, user_authorized_startup_trace=True,
                   recovery_unverified=True, automatic_retries=False, separate_reboot_requested=False,
                   private_evidence_directory=str(directory))
    guard = deployment/'startup-trace-install-attempt.json'
    with os.fdopen(os.open(guard, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'w') as f: json.dump(attempt, f, indent=2)
    response = directory/'upload-response.private.bin'
    command = common+['--max-time', '180', '--header', 'Expect:', '--form', 'CMD=SYS_UPG', '--form', 'GO=index.htm',
                      '--form', 'files=@'+str(image)+';type=application/octet-stream', '--output', str(response),
                      '--write-out', '%{http_code} %{size_upload} %{size_download}', BASE+'/setok.htm']
    try:
        result = subprocess.run(command, input=config, capture_output=True, timeout=190)
        metrics = result.stdout.decode(errors='replace').split()
        attempt.update(status='POST_FINISHED_UNVERIFIED', curl_exit=result.returncode,
                       http_status=metrics[0] if metrics else None, uploaded_bytes=metrics[1] if len(metrics)>1 else None,
                       response_bytes=response.stat().st_size if response.exists() else 0)
    except subprocess.TimeoutExpired:
        attempt['status'] = 'POST_TIMED_OUT_UNVERIFIED'
    attempt['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    guard.write_text(json.dumps(attempt, indent=2)+'\n')
    print(json.dumps(attempt, indent=2))


if __name__=='__main__': main()
