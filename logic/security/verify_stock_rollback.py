"""Bounded, read-only verification after the authorized stock rollback."""
import base64
import datetime
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path
from preflight_install import ROOT, BASE, parse_profile


def main():
    os.umask(0o077)
    attempt = json.loads((ROOT/'deployment/stock-rollback-attempt.json').read_text())
    assert attempt['status'] != 'POST_STARTED', 'Upload process has not finished'
    directory = Path(attempt['private_evidence_directory'])
    before = parse_profile((directory/'before-profile.private.bin').read_bytes())
    token = base64.b64encode(before[b'SYS_USERS']+b':'+before[b'SYS_ADMPASS']).decode()
    config = ('header = "Authorization: Basic '+token+'"\n').encode()
    def get(url, auth=True):
        r = subprocess.run(['/usr/bin/curl', '-q', '-sS', '--noproxy', '*', '--connect-timeout', '3',
                            '--max-time', '6', '--max-filesize', '150000', '--config', '-',
                            '--write-out', '\n%{http_code}', url], input=config if auth else b'', capture_output=True, timeout=8)
        body, _, code = r.stdout.rpartition(b'\n')
        return body, dict(curl_exit=r.returncode, http_status=code.decode(errors='replace'))
    status, status_result = get(BASE+'/status.htm')
    profile, profile_result = get(BASE+'/profile.bin')
    script, script_result = get(BASE+'/js/jquery.js')
    main = (ROOT/'main-decompressed.bin').read_bytes()
    offset = 0x19ecc2
    expected = None
    for entry in range(0x1ede4c, 0x1ee3a8, 28):
        addr, handler, size, *_ = struct.unpack_from('<7I', main, entry)
        name_offset = addr-0x80000400
        name = main[name_offset:main.index(b'\0', name_offset)]
        if name == b'/js/jquery.js':
            expected = main[offset:offset+size]
        offset += size
    assert expected is not None
    try:
        after = parse_profile(profile)
        changed = [k.decode() for k in sorted(set(before)|set(after)) if before.get(k) != after.get(k)]
        unchanged = not changed
    except AssertionError:
        changed = None
        unchanged = False
    uptime = re.search(rb'\bvar\s+_uptime\s*=\s*["\x27](\d+)["\x27]', status)
    x99, x99_result = get('http://192.168.1.4/', False)
    for name, body in [('after-status.private.htm', status), ('after-profile.private.bin', profile)]:
        (directory/name).write_bytes(body)
    report = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), base_url=BASE,
                  original_image_sha256=attempt['original_image_sha256'],
                  management_status=status_result, profile_result=profile_result,
                  stock_script_result=script_result,
                  stock_script_exact_match=script==expected,
                  stock_script_sha256=hashlib.sha256(script).hexdigest(),
                  configuration_unchanged=unchanged, changed_configuration_fields=changed,
                  ap_uptime_seconds=int(uptime[1]) if uptime else None, x99_http=x99_result,
                  limits=['Read-only GET verification, no additional reboot or config changes.',
                          'Resource match does not establish full Flash byte-for-byte identity.',
                          'A brief X99 HTTP check does not establish long-term stability.'])
    report['status'] = 'PASS: stock resources and unchanged configuration verified' if (
        status_result['curl_exit']==0 and status_result['http_status']=='200' and
        script_result['curl_exit']==0 and script_result['http_status']=='200' and script==expected and
        profile_result['curl_exit']==0 and unchanged) else 'NOT_VERIFIED'
    (directory/'rollback-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    (ROOT/'deployment/stock-rollback-result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
