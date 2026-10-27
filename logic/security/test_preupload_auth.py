"""Bounded pre-body guard tests, not a full HTTP or Flash emulator."""
import argparse
import base64
import json
from pathlib import Path
from test_native_auth import ROOT, run


def cases(main):
    basic = lambda s: 'Basic ' + base64.b64encode(s.encode()).decode()
    result = []
    for path in ('setok.htm', 'login.htm', 'js/app.js', '/setok.htm'):
        for auth, want in [(None, [401, 'cleanup']), (basic('admin:wrong'), [401, 'cleanup']),
                           (basic('admin:admin'), ['body'])]:
            actual, reached = run(main, path, auth, early=True, method=3)
            result.append(dict(path=path, credential_case='missing' if auth is None else ('valid' if want == ['body'] else 'invalid'),
                               expected=want, actual=actual, passed=actual == want))
    actual, _ = run(main, 'index.htm', early=True, method=1)
    result.append(dict(path='index.htm', credential_case='GET unchanged', expected=['normal_nonpost'],
                       actual=actual, passed=actual == ['normal_nonpost']))
    for entry in (0x800103f0, 0x800103f4):
        for auth,want in [(None,[401,'cleanup']),(basic('admin:admin'),['body'])]:
            actual,_=run(main,'setok.htm',auth,early=True,method=3,early_entry=entry)
            result.append(dict(path='setok.htm',entry=hex(entry),expected=want,actual=actual,passed=actual==want))
    for auth,default,want in [(basic('admin:admin'),True,['body']),
                              (basic('admin:wrong'),True,[401,'cleanup']),
                              (basic('admin:fixture-pass'),False,['body'])]:
        actual,_=run(main,'setok.htm',auth+'; other=1',cookie=True,default=default,early=True,method=3)
        result.append(dict(path='setok.htm',credential_case='cookie',default_account=default,
                           expected=want,actual=actual,passed=actual==want))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--main', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    result = cases(a.main.read_bytes())
    if a.report: a.report.write_text(json.dumps(result, indent=2)+'\n')
    for item in result: print(json.dumps(item))
    raise SystemExit(0 if all(i['passed'] for i in result) else 1)
