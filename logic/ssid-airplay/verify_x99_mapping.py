"""Compare a pre-probe MAT entry to Sony's documented-by-device http_get fields.

Uses only a fixed query packet, never http_set. Raw MAC/console/API body stay in RAM.
"""
import datetime,hashlib,ipaddress,json,os,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'recovery'))
from flash_backup import Session
from capture_mat_show import summarize

FEATURES=('system.modelname','network.connectiontype','network.macaddress_wired','inet4.dhcp','inet4.ipaddress')
PAYLOAD={'type':'http_get','packet':[{'id':i+1,'feature':f} for i,f in enumerate(FEATURES)]}


def decode(body):
    data=json.loads(body)
    if data.get('type')!='http_get_result' or not isinstance(data.get('packet'),list):
        raise ValueError('Unexpected Sony response type')
    values={}
    for packet in data['packet']:
        feature=packet.get('feature')
        if feature not in FEATURES or feature in values:raise ValueError('Unexpected or duplicate feature')
        if not isinstance(packet.get('value'),str):raise ValueError('Non-string value')
        values[feature]=packet['value']
    if set(values)!=set(FEATURES):raise ValueError('Incomplete feature response')
    mac=values['network.macaddress_wired'].strip()
    if not re.fullmatch(r'(?:[0-9a-fA-F]{12}|(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2})',mac):
        raise ValueError('Invalid wired MAC')
    raw=bytes.fromhex(mac.replace(':','').replace('-',''))
    if raw==bytes(6) or raw[0]&1:raise ValueError('Invalid unicast wired MAC')
    if values['network.connectiontype'] not in ('wired','wireless'):raise ValueError('Unknown connection type')
    if values['inet4.dhcp'] not in ('on','off'):raise ValueError('Unknown DHCP state')
    address=str(ipaddress.IPv4Address(values['inet4.ipaddress']))
    model=values['system.modelname']
    if not re.fullmatch(r'[A-Za-z0-9 _.-]{1,40}',model):raise ValueError('Invalid model text')
    return {'model':model,'connection_type':values['network.connectiontype'],
            'dhcp_enabled':values['inet4.dhcp']=='on','ip':address,
            'wired_mac_sha256':hashlib.sha256(raw).hexdigest()}


def self_test():
    def fixture(mac):
        values=('SRS-X99','wired',mac,'off','192.168.1.4')
        return {'type':'http_get_result','packet':[{'feature':f,'value':v} for f,v in zip(FEATURES,values)]}
    a=decode(json.dumps(fixture('02:00:00:00:00:04')))
    b=decode(json.dumps(fixture('02-00-00-00-00-04')))
    assert a==b and a['connection_type']=='wired' and not a['dhcp_enabled']
    assert '02:00:00:00:00:04' not in json.dumps(a)
    bad=[fixture('ff:ff:ff:ff:ff:ff'),fixture('00:00:00:00:00:00'),fixture('ERR')]
    duplicate=fixture('02:00:00:00:00:04');duplicate['packet'].append(duplicate['packet'][0]);bad.append(duplicate)
    missing=fixture('02:00:00:00:00:04');missing['packet'].pop();bad.append(missing)
    wrong=fixture('02:00:00:00:00:04');wrong['type']='http_set_result';bad.append(wrong)
    for value in bad:
        try:decode(json.dumps(value))
        except ValueError:pass
        else:raise AssertionError('Invalid response accepted')
    assert PAYLOAD['type']=='http_get' and all(p['feature'] in FEATURES for p in PAYLOAD['packet'])
    print('PASS: equivalent MAC formats, redacted summary and six invalid API response rejections; no network')


def main():
    now=datetime.datetime.now(datetime.timezone.utc)
    report={'utc':now.isoformat(),'status':'INCOMPLETE','ap_connections_closed':False,
            'query_type':'http_get','query_features':list(FEATURES),
            'limits':['MAT captured before querying Sony; the query may itself refresh/relearn MAT afterward.',
                      'A correct current mapping does not establish mapping correctness during previous failures.',
                      'Only MAC fingerprints and whitelisted status are saved, not raw responses or MAC addresses.',
                      'No http_set, configuration changes, resets or firmware writes.']}
    session=Session()
    try:
        with session as s:
            mark=s.send('iwpriv ra0 show matinfo')
            raw=s.wait(mark,lambda b:b'OS>' in b,10)
            report['mat_before_sony_query']={'response_complete':True,**summarize(raw)}
        report['sony_query_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        response=subprocess.run(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','2',
                                 '--max-time','4','--fail','-H','Content-Type: application/json',
                                 '--data-binary','@-','http://192.168.1.4/cgi-bin/request.fcgi'],
                                input=json.dumps(PAYLOAD).encode(),capture_output=True,timeout=5)
        report['curl_exit']=response.returncode
        if response.returncode:raise RuntimeError('Sony read query failed')
        info=decode(response.stdout)
        report['sony']=info
        entries=report['mat_before_sony_query']['x99_entries']
        report['mat_entry_present_before_query']=bool(entries)
        report['all_mat_entries_match_sony_wired_mac']=bool(entries) and all(
            entry['mac_sha256']==info['wired_mac_sha256'] for entry in entries)
        report['sony_identity_and_wired_fixed_ip_confirmed']=(
            info['model']=='SRS-X99' and info['connection_type']=='wired' and
            info['ip']=='192.168.1.4' and not info['dhcp_enabled'])
        report['status']='CAPTURED: pre-probe MAT and Sony wired identity compared'
    except Exception as error:report['error_type']=type(error).__name__
    finally:report['ap_connections_closed']=not hasattr(session,'p') or session.p.poll() is not None
    directory=ROOT/'mat-captures';directory.mkdir(mode=0o700,exist_ok=True);directory.chmod(0o700)
    path=directory/(now.strftime('%Y%m%dT%H%M%SZ')+'-x99-identity.json')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:json.dump(report,out,indent=2);out.write('\n')
    print(json.dumps({key:report.get(key) for key in ('status','error_type','ap_connections_closed',
                     'sony_identity_and_wired_fixed_ip_confirmed','mat_entry_present_before_query',
                     'all_mat_entries_match_sony_wired_mac')},indent=2));print('Saved:',path)


if __name__=='__main__':
    if sys.argv[1:]==['--self-test']:self_test()
    elif not sys.argv[1:]:main()
    else:raise SystemExit('Only --self-test or no arguments supported')
