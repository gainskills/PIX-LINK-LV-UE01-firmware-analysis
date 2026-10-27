"""Compare native CCMD=3 file extraction; never execute config importer."""
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
    fixture=b'#PROFILE\n#VER_2_1\nWLN_SSID1=OFFLINE-FIXTURE\n'
    expected=hashlib.sha256(fixture).hexdigest();cases=[]
    for transport in ('header','cookie'):
        for split in (False,True,'body'):
            request,_=wire('SYS_CONF',transport)
            observations=[run(image,request,split,advance_body=True,advance_config=True) for image in images]
            for r in observations:
                calls=[e for e in r['events'] if e['operation']=='config_importer_not_executed']
                assert len(calls)==1 and calls[0]['bytes']==len(fixture) and calls[0]['sha256']==expected,r
            assert observations[0]['auth_calls']==2 and observations[1]['auth_calls']==3
            cases.append(dict(transport=transport,split_input=split,baseline=observations[0],candidate=observations[1],passed=True))
    report=dict(status='PASS: six native CCMD=3 extraction comparisons',cases=cases,
                limits=['Synthetic incomplete profile; not a validated device configuration.',
                        'Executes native HTTP, multipart, CMD/CCMD routing and file extraction.',
                        'Stops at 0x800089c0 before importer executes; no config or event setters execute.',
                        'Allocator/input/I/O modeled; no configuration application, persistence or restart tested.',
                        'No AP access, packets, settings change, reboot or Flash operation.'])
    (OUT/'config-import-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])


if __name__=='__main__':main()
