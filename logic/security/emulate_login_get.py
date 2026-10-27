"""Native GET routing and actual static callback payload checks; I/O modeled."""
import base64
import hashlib
import json
from pathlib import Path
from emulate_http_rejection import run

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'security/preupload-hardening'


def main():
    image=(OUT/'main-preupload.NOT-FLASHABLE.bin').read_bytes()
    web=ROOT/'web-update'
    expected={name:hashlib.sha256((web/file).read_bytes()).hexdigest()
              for name,file in [('login','login.htm'),('dashboard','lan.htm')]}
    expected['script']=hashlib.sha256((web/'settings.min.js').read_bytes()+b'\n').hexdigest()
    scenarios=[('/login.htm',None,'login'),('/js/app.js',None,'script'),
               ('/index.htm',None,'login'),('/index.htm','wrong','login'),
               ('/index.htm','admin','dashboard'),('/profile.bin',None,'login'),
               ('/profile.bin','admin','protected_profile_handler'),
               ('/',None,'login'),('/','admin','dashboard'),
               ('/login.htm?CMD=SYS_CONF&CCMD=3',None,'auth_rejected'),
               ('/js/app.js?CMD=SYS_CONF&CCMD=3',None,'auth_rejected'),
               ('/private/login.htm',None,'login'),
               ('/js/app.js?',None,'script'),
               ('/js/app.js?v=1',None,'auth_rejected'),
               ('/js/app.js?v=1','admin','script'),
               ('/login.htm?CMD=SYS_CONF&CCMD=3','admin','command_authorized')]
    results=[]
    for target,password,want in scenarios:
        cookie='' if password is None else 'Cookie: Authorization=Basic '+base64.b64encode(('admin:'+password).encode()).decode()+'\r\n'
        request=f'GET {target} HTTP/1.0\r\nHost: fixture\r\n{cookie}\r\n'.encode()
        r=run(image,request,advance_body=True,render_get=True)
        if want=='auth_rejected':
            passed=r['returned'] and r['stack_restored'] and any(e.get('status') in (401,403) for e in r['events'])
            passed=passed and not any(e['operation'] in ('command_dispatch_boundary','protected_profile_handler') for e in r['events'])
        elif want=='command_authorized':
            passed=r['auth_calls']>0 and any(e['operation']=='command_dispatch_boundary' for e in r['events'])
        elif want=='protected_profile_handler':passed=any(e['operation']==want for e in r['events'])
        else:
            # Native response setup issues an empty write before the payload.
            # Keep that event, but it contributes no response-body bytes.
            payloads=[e['sha256'] for e in r['events'] if e['operation']=='raw_response_model' and e['bytes']]
            passed=payloads==[expected[want]] and r['returned'] and r['stack_restored']
            assert not any(e['operation']=='protected_profile_handler' for e in r['events'])
        results.append(dict(target=target,credential='missing' if password is None else ('valid' if password=='admin' else 'wrong'),
                            expected=want,observation=r,passed=passed))
    report=dict(status='PASS' if all(r['passed'] for r in results) else 'FAIL',cases=results,
                limits=['Native request parsing, routing, authentication and static callbacks execute.',
                        'Socket input, buffering, allocator, headers, raw writes and frees are modeled.',
                        'Protected profile generation is not executed; valid request stops at handler.',
                        'Static response hashes match embedded UI sources, not actual browser/network output.',
                        'No AP access, settings changes, scans, reboot or Flash operations.'])
    (OUT/'login-get-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],cases=len(results),failed=[r for r in results if not r['passed']])))
    raise SystemExit(0 if report['status']=='PASS' else 1)


if __name__=='__main__':main()
