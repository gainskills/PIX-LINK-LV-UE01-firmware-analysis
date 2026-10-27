"""Read-only config/status snapshot and offline stock-image rollback validation."""
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
from preflight_install import ROOT,BASE,parse_profile


def main():
    os.umask(0o077)
    deployment=ROOT/'deployment'
    installed=json.loads((deployment/'upgrade-result.json').read_text())
    previous=Path(installed['private_evidence_directory'])
    before=parse_profile((previous/'before-profile.private.bin').read_bytes())
    token=base64.b64encode(before[b'SYS_USERS']+b':'+before[b'SYS_ADMPASS']).decode()
    config=('header = "Authorization: Basic '+token+'"\n').encode()
    def get(path):
        r=subprocess.run(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','3','--max-time','6',
                          '--max-filesize','65536','--config','-',BASE+path],input=config,capture_output=True,timeout=8)
        assert r.returncode==0,'Authenticated GET failed'
        return r.stdout
    status=get('/status.htm');profile=get('/profile.bin');now=parse_profile(profile)
    changed=[key.decode() for key in sorted(set(before)|set(now)) if before.get(key)!=now.get(key)]
    uptime=re.search(rb'\bvar\s+_uptime\s*=\s*[\"\x27](\d+)[\"\x27]',status)
    link=re.search(rb'\bvar\s+ApCliConnStatus\s*=\s*[\"\x27](Connected|Disconnected)',status)
    directory=deployment/'private-captures'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-fault')
    directory.mkdir(mode=0o700)
    for name,data in [('fault-profile.private.bin',profile),('fault-status.private.htm',status)]:
        with os.fdopen(os.open(directory/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(data)
    stock=(ROOT/'uimage.bin').read_bytes()
    stock_sha=hashlib.sha256(stock).hexdigest()
    assert stock_sha=='43ef36588e9f3c08b302583a60fc30bcb8fd374953a82a88eb64fcef2714c243'
    assert len(stock)==718108 and struct.unpack_from('>I',stock)[0]==0x27051956
    h=bytearray(stock[:64]);crc=struct.unpack_from('>I',h,4)[0];h[4:8]=bytes(4)
    assert zlib.crc32(h)==crc and zlib.crc32(stock[64:])==struct.unpack_from('>I',stock,24)[0]
    assert lzma.decompress(stock[64+0x2440:],format=lzma.FORMAT_ALONE)==(ROOT/'main-decompressed.bin').read_bytes()
    backup=ROOT/'recovery/private-captures/full-2m-readonly-nc'
    first=(backup/'flash-2m-copy0.bin').read_bytes();second=(backup/'flash-2m-copy1.bin').read_bytes()
    assert first==second and first[0x50000:0x50000+len(stock)]==stock
    report=dict(status='CAPTURED: current fault config and validated original rollback file',
                at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_url=BASE,
                ap_uptime_seconds=int(uptime[1]) if uptime else None,
                upstream_connection=link[1].decode() if link else None,
                configuration_matches_before_upgrade=not changed,changed_configuration_fields=changed,
                bandwidth=now.get(b'WLN_HT_BW',b'').decode(),
                original_image_sha256=stock_sha,original_image_bytes=len(stock),
                original_image_matches_both_flash_backups=True,rollback_uploaded=False,
                limits=['Read-only AP status/config GETs; no save, register writes, reset or reboot.',
                        'Current fault snapshot does not by itself prove firmware causation.',
                        'Rollback would restore original UI/auth behavior and requires a separate flash.'])
    (directory/'fault-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    (deployment/'latest-fault.json').write_text(json.dumps({'capture':str(directory)},indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
