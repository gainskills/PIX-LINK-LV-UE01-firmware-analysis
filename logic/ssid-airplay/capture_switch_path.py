"""Bounded read-only switch configuration/counter snapshots around HTTP probes.

Counter offsets/fields are from the locally retained esw_rt3050 reference driver;
their interpretation is provisional for this MT7628KN hardware. No writes.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent/'recovery'))
from flash_backup import Session

REGS = {
    0xb0110080: 'poa', 0xb0110090: 'port_control0',
    0xb011008c: 'cpu_port_control', 0xb0110014: 'vlan_control',
    0xb0110040: 'pvid01', 0xb0110050: 'vlan_id01',
    0xb0110070: 'vlan_membership03', 0xb0110098: 'port_control2',
    0xb01100e4: 'switch_global2',
    0xb01100e8: 'port0_rx_counter_reference',
    0xb0110150: 'port0_tx_counter_reference',
    0xb0100808: 'tx_cpu_index', 0xb010080c: 'tx_dma_index',
    0xb0100908: 'rx_cpu_index', 0xb010090c: 'rx_dma_index',
}


def main():
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report = dict(at_utc=stamp, snapshots=[], probes=[],
                  limits=['Sequential, non-atomic reads; no writes, reset or configuration changes.',
                          'Counter meanings use a related reference driver, not a confirmed matching vendor SDK.',
                          'Counters may wrap or have undocumented semantics; zero is not proof of hardware failure.'])
    session = Session()
    deadline = time.monotonic()+30
    try:
        with session as s:
            for number in range(2):
                snapshot = {'round': number, 'registers': []}
                report['snapshots'].append(snapshot)
                for address, name in REGS.items():
                    if time.monotonic()>deadline:
                        raise TimeoutError('Sampling deadline')
                    command = f'reg r {address:x}'
                    mark = s.send(command)
                    raw = s.wait(mark, lambda b: b'OS>' in b, 2)
                    matches = re.findall(rb'Address =\s*0x([0-9a-fA-F]+),\s*Value =\s*0x\s*([0-9a-fA-F]{1,8})\s*(?:\r?\n)', raw)
                    matches = [(int(a, 16), int(v, 16)) for a, v in matches if int(a, 16)==address]
                    if len(matches)!=1:
                        snapshot['registers'].append(dict(name=name, address=hex(address), error='Malformed or ambiguous response'))
                        continue
                    value = matches[0][1]
                    item = dict(name=name, address=hex(address), value=hex(value))
                    if name=='poa':
                        item['port0_link'] = bool((value>>25)&1)
                    snapshot['registers'].append(item)
                if number==0:
                    for url in ['http://192.168.1.4/', 'http://192.168.1.2:8080/status.htm', 'http://192.168.1.4/']:
                        r = subprocess.run(['/usr/bin/curl', '-q', '-sS', '--noproxy', '*', '--connect-timeout', '1',
                                            '--max-time', '2', '-o', '/dev/null', '-w', '%{http_code}', url],
                                           capture_output=True, timeout=3)
                        report['probes'].append(dict(url=url, curl_exit=r.returncode, http_status=r.stdout.decode(errors='replace')))
    except Exception as error:
        report['error_type'] = type(error).__name__
    report['all_connections_closed'] = not hasattr(session, 'p') or session.p.poll() is not None
    report['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    directory = ROOT/'dma-captures'
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory/(stamp+'-switch-path.json')
    with os.fdopen(os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'w') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(report, indent=2))
    print('Saved:', path)


if __name__=='__main__':
    main()
