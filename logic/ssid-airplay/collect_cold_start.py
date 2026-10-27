"""Bounded read-only AP/X99 snapshot; never logs HTTP response bodies or credentials."""
import argparse
import datetime
import html
import ipaddress
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path


def private_ipv4(value):
    address = ipaddress.IPv4Address(value)
    if not address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
        raise ValueError('Expected the known private LAN IPv4 address')
    return str(address)


def ap_address(value):
    url = urllib.parse.urlsplit(value)
    if url.scheme != 'http' or url.username or url.password or url.path not in ['', '/'] or url.query or url.fragment:
        raise ValueError('Expected an HTTP LAN origin without credentials or path')
    host = private_ipv4(url.hostname)
    port = url.port or 80
    return 'http://' + host + (':' + str(port) if port != 80 else '')


def parse_ap_status(body):
    text = body.decode('utf-8', 'replace')
    def cell(identifier):
        match = re.search(r'<td\b[^>]*\bid=["\']' + identifier + r'["\'][^>]*>(.*?)</td>', text, re.I | re.S)
        value = html.unescape(re.sub(r'<[^>]*>', '', match[1])).strip() if match else ''
        return int(value) if re.fullmatch(r'\d{1,6}', value) else None
    state = re.search(r'\bvar\s+ApCliConnStatus\s*=\s*["\'](Connected|Disconnected)(?:;[^"\']*)?["\']', text)
    uptime = re.search(r'\bvar\s+_uptime\s*=\s*["\'](\d{1,12})["\']', text)
    version = re.search(r'v28K\.RPT\.\d{8}', text)
    return {'upstream_state':state[1] if state else None,'channel':cell('drv_chan0'),
            'wireless_clients':cell('drv_client0'),'uptime_seconds':int(uptime[1]) if uptime else None,
            'firmware_version':version[0] if version else None,
            'known_device_mac_present':'02:00:00:00:00:01' in text.lower()}


def command(args, timeout):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr.decode('utf-8', 'replace')[:240]
    except subprocess.TimeoutExpired:
        return None, b'', 'collector timeout; child terminated and waited'
    except OSError as error:
        return None, b'', str(error)


def get_http(url, status=False):
    marker = b'\n__COLD_START_META__'
    fmt = '\n__COLD_START_META__{"http_code":%{http_code},"peer":"%{remote_ip}","connect_seconds":%{time_connect},"total_seconds":%{time_total}}'
    code, data, error = command(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','2','--max-time','3','--max-filesize','32768','--write-out',fmt,url], 5)
    body, separator, metadata = data.rpartition(marker)
    try:
        row = json.loads(metadata) if separator else {'http_code':None}
    except ValueError:
        row = {'http_code':None}
    row.update(curl_exit=code,request_method='GET',sent_credentials=False)
    if error:
        row['error'] = error
    if status and row['http_code'] == 200:
        row.update(parse_ap_status(body))
    # Neither the body nor arbitrary headers are returned or stored.
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--x99-ip', required=True)
    parser.add_argument('--ap-url', default='http://192.168.1.2:8080')
    parser.add_argument('--label', choices=['baseline','failure','recovered'], required=True)
    parser.add_argument('--out-dir', type=Path, default=Path(__file__).resolve().parent/'cold-start-captures')
    args = parser.parse_args()
    try:
        x99 = private_ipv4(args.x99_ip)
        ap = ap_address(args.ap_url)
    except ValueError as error:
        parser.error(str(error))
    samples = []
    for number in range(2):
        samples.append({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'ap':get_http(ap+'/status.htm',status=True),'x99':get_http('http://'+x99+'/')})
        if number == 0:
            time.sleep(1)
    ping_code, ping, ping_error = command(['/sbin/ping','-n','-c','3','-W','1000','-t','4',x99],6)
    summary = re.search(rb'\d+ packets transmitted[^\r\n]*',ping)
    arp = []
    for ip in [urllib.parse.urlsplit(ap).hostname,x99]:
        code, output, error = command(['/usr/sbin/arp','-n',ip],2)
        # Retain only the specifically requested neighbor, never the whole LAN table.
        text = output.decode('utf-8','replace').strip()
        arp.append({'ip':ip,'exit':code,'entry':text[:250] if '('+ip+')' in text or 'no entry' in text.lower() else None,'error':error or None})
    result = {'label':args.label,'x99_ip':x99,'ap_url':ap,'samples':samples,
              'icmp':{'exit':ping_code,'summary':summary[0].decode() if summary else None,'error':ping_error or None},
              'arp':arp,'limits':['An ICMP failure alone does not prove packet loss; this environment previously had ICMP restrictions.',
                                 'These are upstream-side observations, not a capture of all X99 unicast traffic.',
                                 'The AP may rewrite client MAC addresses; a shared ARP MAC alone does not prove an IP conflict.',
                                 'No PHY registers, AP-side MAT table, mDNS or AirPlay audio stream are captured by this tool.'],
              'safety':'GET, bounded ICMP, and neighbor reads only; no POST, authentication changes, scans, reboot, register writes, or firmware operations.'}
    args.out_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination=args.out_dir/(stamp+'-'+args.label+'.json')
    with destination.open('x') as handle:
        destination.chmod(0o600)
        json.dump(result,handle,indent=2)
        handle.write('\n')
    print(json.dumps(result,indent=2))
    print('Saved:',destination)


if __name__=='__main__':
    main()
