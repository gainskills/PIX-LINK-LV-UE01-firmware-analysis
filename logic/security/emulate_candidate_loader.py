"""Run the existing native loader model on the current security candidate."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'phy-diagnostic'))
from emulate_native_loader import trial,sha


def main():
    out=ROOT/'security/preupload-hardening'
    original=(ROOT/'uimage.bin').read_bytes();old_main=(ROOT/'main-decompressed.bin').read_bytes()
    image=(out/'web-preupload.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    new_main=(out/'main-preupload.NOT-FLASHABLE.bin').read_bytes()
    assert sha(original)=='43ef36588e9f3c08b302583a60fc30bcb8fd374953a82a88eb64fcef2714c243'
    assert sha(image)=='481ed9575c53ff9ab6d5021638f225eb35cb6ac7b7839d4e0a65ec6a13ae4bb3'
    assert image[64:64+0x2440]==original[64:64+0x2440]
    cases=[trial('original_control',original,old_main)]
    if cases[-1]['passed']:cases.append(trial('web_security_candidate',image,new_main))
    if len(cases)==2 and cases[-1]['passed']:cases.append(trial('invalid_properties',image,new_main,True))
    passed=len(cases)==3 and all(c['passed'] for c in cases)
    report=dict(status='PASS' if passed else 'INCOMPLETE',candidate_sha256=sha(image),cases=cases,
                limits=['Uses existing native MIPS loader/decoder model, not Python decompression.',
                        'Stops at main entry; no application startup, actual cache, hardware or recovery validation.',
                        'Invalid properties change emulator RAM only; no image change.',
                        'No AP access, packets, configuration changes, reboot or Flash operations.'])
    (out/'native-loader-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()
