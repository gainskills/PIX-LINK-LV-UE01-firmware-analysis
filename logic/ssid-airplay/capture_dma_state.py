"""Bounded read-only DMA/MAT sampling with HTTP checks; no configuration writes.

--self-test validates response parsing without opening a network connection.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'recovery'))
from flash_backup import Session,ReadTimeout
from capture_mat_show import summarize as summarize_mat

REGISTERS={0xb0110080:'poa',0xb0100804:'tx_ring_count',0xb0100808:'tx_cpu_index',
           0xb010080c:'tx_dma_index',0xb0100904:'rx_ring_count',
           0xb0100908:'rx_cpu_index',0xb010090c:'rx_dma_index',
           0xb0100a04:'pdma_config',0xb0100a20:'interrupt_status',0xb0100a28:'interrupt_mask'}
ROW=re.compile(rb'(?m)^(?:OS>)?Address = 0x([0-9a-fA-F]{8}), Value = 0x([ \t]*[0-9a-fA-F]{1,8})[ \t]*\r?$')


def parse(raw,address):
    rows=ROW.findall(raw)
    if len(rows)!=1 or int(rows[0][0],16)!=address:
        raise ValueError('Missing, malformed, duplicate or mismatched register response')
    return int(rows[0][1].strip(),16)


def self_test():
    valid=b'Address = 0xb0110080, Value = 0x   83818301\r\nOS>'
    assert parse(valid,0xb0110080)==0x83818301
    bad=[valid.replace(b'b0110080',b'b0100808'),valid+valid,
         valid.replace(b'83818301',b'83LOG18301'),valid.replace(b'83818301',b'183818301'),b'OS>']
    for raw in bad:
        try:parse(raw,0xb0110080)
        except ValueError:pass
        else:raise AssertionError('Invalid response accepted')
    assert all(f'reg r {address:08x}'.split()[:2]==['reg','r'] for address in REGISTERS)
    for value in (b'c0a80104',b'401a8c0'):
        summary=summarize_mat(b'IP=0x'+value+b',Mac=02:00:00:00:00:04, lastTime=0x7b\nOS>')
        assert summary['printed_ipv4_entries']==1 and summary['x99_ip_hex_seen']
        assert not any('02:00:00:00:00:04' in str(v) for v in summary.values())
        assert summary['x99_entries'][0]['last_time_native']==123
    summary=summarize_mat(b'Before check, this_char=matinfo\nOS>')
    assert summary['driver_dispatch_message_seen'] and summary['printed_ipv4_entries']==0
    assert not summary['x99_ip_hex_seen']
    first=summarize_mat(b'IP=0x401a8c0,Mac=02:00:00:00:00:04, lastTime=0x7b')['x99_entries'][0]
    later=summarize_mat(b'IP=0x401a8c0,Mac=02:00:00:00:00:04, lastTime=0x7c')['x99_entries'][0]
    other=summarize_mat(b'IP=0x401a8c0,Mac=02:00:00:00:00:05, lastTime=0x7b')['x99_entries'][0]
    assert first['mac_sha256']==later['mac_sha256'] and first['last_time_native']!=later['last_time_native']
    assert first['mac_sha256']!=other['mac_sha256']
    assert summarize_mat(b'IP=0x401a8c0,Mac=02:00:00:00:00:04')['x99_entries']==[]
    assert mapping_matches({'x99_entries':[first]},first['mac_sha256']) is True
    assert mapping_matches({'x99_entries':[other]},first['mac_sha256']) is False
    assert mapping_matches({'x99_entries':[]},first['mac_sha256']) is None
    print('PASS: six register, six MAT summary and three reference matching checks; no network access')


def http_probe():
    started=time.monotonic()
    try:
        result=subprocess.run(['/usr/bin/curl','-q','-sS','--noproxy','*','--connect-timeout','1',
                               '--max-time','2','-o','/dev/null','-w','%{http_code}',
                               'http://192.168.1.4/'],capture_output=True,timeout=3)
        return {'transport':'curl','exit':result.returncode,'http_status':result.stdout.decode('ascii','replace'),
                'elapsed_ms':round((time.monotonic()-started)*1000)}
    except (OSError,subprocess.TimeoutExpired) as error:
        return {'transport':'curl','error_type':type(error).__name__,
                'elapsed_ms':round((time.monotonic()-started)*1000)}


def mapping_matches(summary,expected):
    entries=summary['x99_entries']
    return all(e['mac_sha256']==expected for e in entries) if expected and entries else None


def read_mat(session,deadline,expected=None):
    if time.monotonic()>=deadline:raise TimeoutError('Sampling deadline')
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
    mark=session.send('iwpriv ra0 show matinfo')
    raw=session.wait(mark,lambda b:b'OS>' in b,min(2,max(.01,deadline-time.monotonic())))
    summary=summarize_mat(raw)
    return {'utc':utc,'response_complete':True,**summary,
            'x99_mac_matches_verified_reference':mapping_matches(summary,expected)}


def main():
    started=datetime.datetime.now(datetime.timezone.utc)
    report={'started_utc':started.isoformat(),'ap':'192.168.1.2','x99':'192.168.1.4',
            'register_names':{hex(k):v for k,v in REGISTERS.items()},'rounds':[],
            'authenticated':False,'all_connections_closed':False,
            'limits':['Sequential reads are not an atomic snapshot.',
                      'HTTP GET is not a playback or packet-loss test.',
                      'Unchanged DMA indices can mean idle traffic, not necessarily a stall.',
                      'Missing or malformed responses are not zero-valued registers.',
                      'MAT printing is gated; no printed X99 entry does not establish absence.',
                      'HTTP probes can refresh or relearn MAT; first pre-HTTP table is captured before any X99 probe.',
                      'No register writes, resets, MDIO transactions or configuration changes.']}
    session=Session()
    try:
        expected=None
        reference_path=ROOT/'mat-captures/x99-wired-identity-reference.json'
        if reference_path.exists():
            reference=json.loads(reference_path.read_text())
            source=ROOT/reference['source']
            if source.resolve().parent!=(ROOT/'mat-captures').resolve():raise ValueError('Invalid identity source path')
            if hashlib.sha256(source.read_bytes()).hexdigest()!=reference['source_sha256']:raise ValueError('Identity source changed')
            verified=json.loads(source.read_text())
            if not (verified['sony_identity_and_wired_fixed_ip_confirmed'] and
                    verified['all_mat_entries_match_sony_wired_mac']):raise ValueError('Unverified identity reference')
            if reference['wired_mac_sha256']!=verified['sony']['wired_mac_sha256']:raise ValueError('Identity reference mismatch')
            expected=reference['wired_mac_sha256']
            report['verified_wired_identity_reference']={'source':reference['source'],'verified_utc':reference['verified_utc']}
        with session as s:
            report['authenticated']=True
            deadline=time.monotonic()+30
            for number in range(3):
                round_={'number':number,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'registers':[]}
                report['rounds'].append(round_)
                round_['mat_before_http']=read_mat(s,deadline,expected)
                for address,name in REGISTERS.items():
                    if time.monotonic()>=deadline:raise TimeoutError('Sampling deadline')
                    at=datetime.datetime.now(datetime.timezone.utc).isoformat()
                    mark=s.send(f'reg r {address:08x}')
                    raw=s.wait(mark,lambda b:b'OS>' in b,min(2,max(.01,deadline-time.monotonic())))
                    value=parse(raw,address)
                    round_['registers'].append({'name':name,'address':hex(address),'value':hex(value),'utc':at})
                round_['x99_http_first']=http_probe()
                round_['mat_after_http']=read_mat(s,deadline,expected)
                round_['x99_http_second']=http_probe()
                if number<2:time.sleep(2)
    except Exception as error:
        # Never include raw login/console bytes in public diagnostics.
        report['error_type']=type(error).__name__
        report['status']='INCOMPLETE: no conclusion from absent samples'
    else:report['status']='CAPTURED: three sequential register rounds'
    finally:
        report['all_connections_closed']=not hasattr(session,'p') or session.p.poll() is not None
    report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    directory=ROOT/'dma-captures';directory.mkdir(mode=0o700,exist_ok=True);directory.chmod(0o700)
    path=directory/(started.strftime('%Y%m%dT%H%M%SZ')+'-dma.json')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:json.dump(report,out,indent=2);out.write('\n')
    print(json.dumps({'status':report['status'],'authenticated':report['authenticated'],
                      'rounds':len(report['rounds']),'valid_reads':sum(len(r['registers']) for r in report['rounds']),
                      'error_type':report.get('error_type'),'all_connections_closed':report['all_connections_closed'],
                      'saved':str(path)},indent=2))


if __name__=='__main__':
    if sys.argv[1:]==['--self-test']:self_test()
    elif not sys.argv[1:]:main()
    else:raise SystemExit('Only --self-test or no arguments are supported')
