"""Verify diagnostic resources/config first, then one bounded authorized PHY read."""
import base64
import datetime
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path
from preflight_install import ROOT, BASE, parse_profile


def main():
    os.umask(0o077)
    revision = 'phy-builtin-v2' if sys.argv[1:]==['--builtin-v2'] else 'phy'
    assert sys.argv[1:] in ([], ['--builtin-v2']), 'Unknown verification revision'
    attempt = json.loads((ROOT/('deployment/'+revision+'-install-attempt.json')).read_text())
    assert attempt['status']!='POST_STARTED', 'Upload still in progress'
    directory = Path(attempt['private_evidence_directory'])
    before = parse_profile((directory/'before-profile.private.bin').read_bytes())
    config = ('header = "Authorization: Basic '+base64.b64encode(before[b'SYS_USERS']+b':'+before[b'SYS_ADMPASS']).decode()+'"\n').encode()
    def get(path, auth=True):
        r = subprocess.run(['/usr/bin/curl', '-q', '-sS', '--noproxy', '*', '--connect-timeout', '3', '--max-time', '6',
                            '--max-filesize', '150000', '--config', '-', '--write-out', '\n%{http_code}',
                            BASE+path], input=config if auth else b'', capture_output=True, timeout=8)
        body, _, status = r.stdout.rpartition(b'\n')
        assert r.returncode==0 and status==b'200', 'Management GET failed: '+path
        return body
    status = get('/status.htm');profile = get('/profile.bin')
    favicon = get('/favicon.ico');script = get('/js/jquery.js')
    main_data = (ROOT/'main-decompressed.bin').read_bytes()
    expected_script = main_data[0x1ad83c:0x1c4e66]
    assert script==expected_script and favicon==b'', 'Expected diagnostic resource changes not observed; PHY command NOT sent'
    after = parse_profile(profile)
    changed = [k.decode() for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
    (directory/'after-profile.private.bin').write_bytes(profile)
    (directory/'after-status.private.htm').write_bytes(status)
    uptime = re.search(rb'\bvar\s+_uptime\s*=\s*["\x27](\d+)["\x27]', status)
    report = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), base_url=BASE,
                  candidate_sha256=attempt['candidate_sha256'], original_script_exact_match=True, favicon_empty=True,
                  configuration_unchanged=not changed, changed_configuration_fields=changed,
                  ap_uptime_seconds=int(uptime[1]) if uptime else None,
                  limits=['Resource/diagnostic behavior verification, not a full Flash readback.',
                          'One MDIO read sequence may clear BMSR latched state; both values preserved.',
                          'Startup and brief connectivity do not establish a fix or long-term stability.'])
    sys.path.insert(0, str(ROOT/'recovery'))
    from flash_backup import Session, ReadTimeout
    session = Session();raw = b''
    try:
        with session as s:
            mark = s.send('reg phy')
            try:
                raw = s.wait(mark, lambda b: b'OS>' in b, 5)
                report['phy_response_complete'] = True
            except ReadTimeout as error:
                raw = error.partial
                report['phy_response_complete'] = False
    except Exception as error:
        report['phy_error_type'] = type(error).__name__
    finally:
        report['connections_closed'] = not hasattr(session, 'p') or session.p.poll() is not None
    (directory/'phy-baseline.private.txt').write_bytes(raw)
    summary = re.findall(rb'PHYDIAG relink_calls=(\d+) last_cp0_count=(\d+)', raw)
    rows = re.findall(rb'PHYDIAG p0 reg=(\d+) result=(-?\d+) hex=([0-9a-fA-F]{4,8})', raw)
    report['phy_rows'] = [dict(reg=int(reg), result=int(result), hex=value.decode()) for reg, result, value in rows]
    consistent = all((r['result'] & 0xffffffff)==int(r['hex'],16) for r in report['phy_rows'])
    complete = len(summary)==1 and [r['reg'] for r in report['phy_rows']]==[0,1,1,4,5,6] and consistent and all(0<=r['result']<=65535 for r in report['phy_rows'])
    if len(summary)==1:
        report['relink_calls'] = int(summary[0][0]);report['last_cp0_count'] = int(summary[0][1])
    report['phy_six_reads_valid'] = complete
    if complete:
        report['bmsr_link_first'] = bool(report['phy_rows'][1]['result'] & 4)
        report['bmsr_link_second'] = bool(report['phy_rows'][2]['result'] & 4)
    x99 = subprocess.run(['/usr/bin/curl', '-q', '-sS', '--noproxy', '*', '--connect-timeout', '2', '--max-time', '3',
                          '-o', '/dev/null', '-w', '%{http_code}', 'http://192.168.1.4/'], capture_output=True, timeout=4)
    report['x99_http'] = dict(curl_exit=x99.returncode, status=x99.stdout.decode(errors='replace'))
    report['status'] = 'PASS: diagnostic execution and unchanged configuration verified' if complete and not changed and report.get('phy_response_complete') else 'INCOMPLETE: inspect evidence'
    (directory/'phy-install-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    (ROOT/('deployment/'+revision+'-install-result.json')).write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__=='__main__': main()
