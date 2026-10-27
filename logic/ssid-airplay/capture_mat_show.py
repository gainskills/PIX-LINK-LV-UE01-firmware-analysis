"""One bounded, read-only native MAT show request. Raw console bytes stay in RAM."""
import datetime,hashlib,json,os,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'recovery'))
from flash_backup import Session,ReadTimeout


def summarize(raw):
    text=raw.decode('ascii','replace')
    rows=re.findall(r'IP=0x([0-9a-fA-F]{1,8}),Mac=(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',text)
    entries=[]
    for match in re.finditer(r'IP=0x([0-9a-fA-F]{1,8}),Mac=((?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}), lastTime=0x([0-9a-fA-F]{1,8})\b',text):
        if int(match.group(1),16) in (0xc0a80104,0x0401a8c0):
            entries.append({'mac_sha256':hashlib.sha256(bytes.fromhex(match.group(2).replace(':',''))).hexdigest(),
                            'last_time_native':int(match.group(3),16)})
    return {'received_bytes':len(raw),'driver_dispatch_message_seen':'this_char=matinfo' in text,
            'printed_ipv4_entries':len(rows),
            'x99_ip_hex_seen':any(int(value,16) in (0xc0a80104,0x0401a8c0) for value in rows),
            'x99_entries':entries,
            'end_marker_seen':'EndOfDump' in text,
            'default_broadcast_line_seen':'Default BroadCast Address=' in text,
            'unknown_command_seen':'Unknown Command' in text}


def main():
    now=datetime.datetime.now(datetime.timezone.utc)
    result={'utc':now.isoformat(),'command':'iwpriv ra0 show matinfo',
            'authenticated':False,'response_complete':False,
            'limits':['No printed rows does not establish an empty MAT table.',
                      'Native table printing is conditional on global logging gates.',
                      'No debug level change, table clear, configuration change or firmware write.']}
    session=Session();raw=b''
    try:
        with session as s:
            result['authenticated']=True
            mark=s.send('iwpriv ra0 show matinfo')
            try:
                raw=s.wait(mark,lambda b:b'OS>' in b,10)
                result['response_complete']=True
            except ReadTimeout as error:
                raw=error.partial
                result['error_type']='ReadTimeout'
    except Exception as error:result['error_type']=type(error).__name__
    finally:result['all_connections_closed']=not hasattr(session,'p') or session.p.poll() is not None
    result.update(summarize(raw))
    directory=ROOT/'mat-captures';directory.mkdir(mode=0o700,exist_ok=True);directory.chmod(0o700)
    path=directory/(now.strftime('%Y%m%dT%H%M%SZ')+'-mat.json')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps(result,indent=2));print('Saved:',path)


if __name__=='__main__':main()
