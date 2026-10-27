"""Native extraction/staging comparison; stop BEFORE Flash writer executes."""
import hashlib
import json
from pathlib import Path
from emulate_authenticated_post import wire
from emulate_http_rejection import run

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'security/preupload-hardening'


def main():
    images=[(ROOT/'web-update/main-web-update.NOT-FLASHABLE.bin').read_bytes(),
            (OUT/'main-preupload.NOT-FLASHABLE.bin').read_bytes()]
    fixture=b'OFFLINE-NONIMAGE';expected=hashlib.sha256(fixture).hexdigest();cases=[]
    for transport in ('header','cookie'):
        for split in (False,True,'body'):
            request,_=wire('SYS_UPG',transport)
            observations=[run(image,request,split,advance_body=True,advance_upload=True) for image in images]
            for r in observations:
                calls=[e for e in r['events'] if e['operation']=='flash_writer_not_executed']
                assert len(calls)==1 and calls[0]['bytes']==len(fixture) and calls[0]['sha256']==expected,r
            assert observations[0]['auth_calls']==0 and observations[1]['auth_calls']==1
            cases.append(dict(transport=transport,split_input=split,baseline=observations[0],candidate=observations[1],passed=True))
    report=dict(status='PASS: six native file extraction and staging comparisons',cases=cases,
                limits=['Uses a 16-byte nonimage fixture, not an accepted or installable firmware.',
                        'Executes native file lookup, multipart length extraction and staging copy.',
                        'Stops on entry to writer 0x80006614 before any of its instructions execute.',
                        'Startup upload globals remain modeled zero; real initialized state is unverified.',
                        'Allocator/input/I/O backends are modeled; no firmware validation or Flash execution.',
                        'No AP access, packets, reboot, settings change or Flash operation.'])
    (OUT/'upload-staging-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])


if __name__=='__main__':main()
