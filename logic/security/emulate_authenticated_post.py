"""Compare native multipart/dispatch before and after authentication patch."""
import base64
import json
from pathlib import Path
from emulate_http_rejection import run

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'security/preupload-hardening'


def wire(command,transport):
    fields={'CMD':command,'CCMD':'3','GO':'lan.htm'} if command=='SYS_CONF' else {'CMD':command,'GO':'man_upgrade.htm'}
    body=b''
    for key,value in fields.items():
        body+=f'--fixture\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    payload=b'#PROFILE\n#VER_2_1\nWLN_SSID1=OFFLINE-FIXTURE\n' if command=='SYS_CONF' else b'OFFLINE-NONIMAGE'
    body+=b'--fixture\r\nContent-Disposition: form-data; name="files"; filename="fixture.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'+payload+b'\r\n--fixture--\r\n'
    encoded=base64.b64encode(b'admin:admin').decode()
    auth=('Authorization: Basic ' if transport=='header' else 'Cookie: Authorization=Basic ')+encoded
    request=(f'POST /setok.htm HTTP/1.0\r\nHost: fixture\r\n{auth}\r\nContent-Type: multipart/form-data; boundary=fixture\r\nContent-Length: {len(body)}\r\n\r\n').encode()+body
    return request,fields


def main():
    original=(ROOT/'web-update/main-web-update.NOT-FLASHABLE.bin').read_bytes()
    candidate=(OUT/'main-preupload.NOT-FLASHABLE.bin').read_bytes()
    results=[]
    for command in ('SYS_CONF','SYS_UPG'):
        for transport in ('header','cookie'):
            for split in (False,True,'body'):
                request,expected=wire(command,transport)
                observations=[run(main,request,split,advance_body=True) for main in (original,candidate)]
                boundary='command_dispatch_boundary' if command=='SYS_CONF' else 'upload_staging_boundary'
                for observation in observations:
                    actual=[e for e in observation['events'] if e['operation']==boundary]
                    assert len(actual)==1,(command,transport,observation)
                    assert actual[0]['fields']==expected,actual
                    assert not any(e['operation']=='body_or_flash_boundary' for e in observation['events'])
                results.append(dict(command=command,transport=transport,split_input=split,expected=expected,
                                    baseline=observations[0],candidate=observations[1],passed=True))
    report=dict(status='PASS: twelve native multipart and dispatch comparisons',cases=results,
                limits=['Synthetic accounts, allocator, input buffering and I/O models.',
                        'Executes native multipart parsing and parameter lookup.',
                        'Stops at command dispatcher or upload staging before business/Flash operations.',
                        'Does not prove configuration import, firmware acceptance, reboot, persistence or hardware operation.',
                        'No AP access, packets, settings changes or Flash operations.'])
    (OUT/'authenticated-post-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])


if __name__=='__main__':main()
