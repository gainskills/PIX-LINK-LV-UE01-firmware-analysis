"""One-shot stock rollback explicitly authorized in the conversation. No retries."""
import base64
import datetime
import hashlib
import json
import lzma
import os
import re
import struct
import subprocess
import zlib
from pathlib import Path
from preflight_install import ROOT, BASE, parse_profile

EXPECTED = '43ef36588e9f3c08b302583a60fc30bcb8fd374953a82a88eb64fcef2714c243'


def main():
    os.umask(0o077)
    image = ROOT / 'uimage.bin'
    data = image.read_bytes()
    assert len(data) == 718108 and hashlib.sha256(data).hexdigest() == EXPECTED
    header = bytearray(data[:64])
    crc = struct.unpack_from('>I', header, 4)[0]
    header[4:8] = bytes(4)
    assert struct.unpack_from('>I', data)[0] == 0x27051956
    assert zlib.crc32(header) == crc
    assert zlib.crc32(data[64:]) == struct.unpack_from('>I', data, 24)[0]
    assert lzma.decompress(data[64+0x2440:], format=lzma.FORMAT_ALONE) == (ROOT/'main-decompressed.bin').read_bytes()
    for index in (0, 1):
        backup = (ROOT/f'recovery/private-captures/full-2m-readonly-nc/flash-2m-copy{index}.bin').read_bytes()
        assert len(backup) == 2097152 and backup[0x50000:0x50000+len(data)] == data
    deployment = ROOT/'deployment'
    install = json.loads((deployment/'upgrade-result.json').read_text())
    known = parse_profile((Path(install['private_evidence_directory'])/'before-profile.private.bin').read_bytes())
    token = base64.b64encode(known[b'SYS_USERS']+b':'+known[b'SYS_ADMPASS']).decode()
    config = ('header = "Authorization: Basic '+token+'"\n').encode()
    common = ['/usr/bin/curl', '-q', '-sS', '--noproxy', '*', '--connect-timeout', '5', '--config', '-']
    def get(path):
        r = subprocess.run(common+['--max-time', '8', '--max-filesize', '65536', BASE+path], input=config, capture_output=True, timeout=10)
        assert r.returncode == 0, 'Preflight GET failed'
        return r.stdout
    status = get('/status.htm')
    reference = (ROOT/'deployment/private-device-identity.txt').read_text()
    mac = re.search(r"b'([0-9a-f]{2}(?::[0-9a-f]{2}){5})'", reference, re.I)
    compact = lambda b: re.sub(rb'[:-]', b'', b.lower())
    assert mac and compact(mac[1].encode()) in compact(status), 'Device identity mismatch'
    assert b'v28k.rpt.20220716' in status.lower(), 'Unexpected firmware version'
    profile = get('/profile.bin')
    before = parse_profile(profile)
    assert before == parse_profile(get('/profile.bin')), 'Configuration changed during preflight'
    directory = deployment/'private-captures'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-rollback')
    directory.mkdir(mode=0o700)
    (directory/'before-profile.private.bin').write_bytes(profile)
    (directory/'before-status.private.htm').write_bytes(status)
    attempt = dict(status='POST_STARTED', at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   base_url=BASE, original_image_sha256=EXPECTED, image_bytes=len(data),
                   known_device_identity_matches=True, image_matches_both_backups=True,
                   user_authorized_stock_rollback=True, automatic_retries=False,
                   separate_reboot_requested=False, private_evidence_directory=str(directory))
    # One global exclusive guard prevents accidental repeat uploads on rerun.
    guard = deployment/'stock-rollback-attempt.json'
    with os.fdopen(os.open(guard, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'w') as f:
        json.dump(attempt, f, indent=2)
    response = directory/'upload-response.private.bin'
    command = common+['--max-time', '180', '--header', 'Expect:', '--form', 'CMD=SYS_UPG',
                      '--form', 'GO=index.htm', '--form', 'files=@'+str(image)+';type=application/octet-stream',
                      '--output', str(response), '--write-out', '%{http_code} %{size_upload} %{size_download}', BASE+'/setok.htm']
    try:
        result = subprocess.run(command, input=config, capture_output=True, timeout=190)
        metrics = result.stdout.decode(errors='replace').split()
        attempt.update(status='POST_FINISHED_UNVERIFIED', curl_exit=result.returncode,
                       http_status=metrics[0] if metrics else None,
                       uploaded_bytes=metrics[1] if len(metrics)>1 else None,
                       response_bytes=response.stat().st_size if response.exists() else 0)
    except subprocess.TimeoutExpired:
        attempt['status'] = 'POST_TIMED_OUT_UNVERIFIED'
    attempt['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    guard.write_text(json.dumps(attempt, indent=2)+'\n')
    print(json.dumps(attempt, indent=2))


if __name__ == '__main__':
    main()
