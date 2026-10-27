"""Execute the unchanged native self-extractor against original and candidate RAM payloads.

No device, network, Flash, image rebuild or main-firmware execution. Unicorn RAM,
UART and cache behavior are models, so success is not a hardware boot validation.
"""
import hashlib,json,struct,sys,time
from pathlib import Path
from unicorn import Uc,UcError,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn import mips_const as mc
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'original-baseline'
ENTRY=0x80500000;MAIN=0x80000400


def sha(data):return hashlib.sha256(data).hexdigest()
def reg(name):return getattr(mc,'UC_MIPS_REG_'+name.upper())


def trial(name,image,expected,invalid_properties=False):
    payload=bytearray(image[64:])
    if invalid_properties:payload[0x2440]=0xff
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0,0x800000);u.mem_map(0x10000000,0x1000)
    u.mem_write(0x500000,bytes(payload))
    for n,v in [('sp',0x807f0000),('ra',0x807f1000),('gp',0x8021b190),('cp0_status',0x1000ff01)]:
        u.reg_write(reg(n),v)
    events={'uart_bytes':[],'cache_routine_entries':0,'decoder_failure_branch':False}
    def uart(uc,access,address,size,value,unused):
        if address&0x1fffffff==0x10000c04:events['uart_bytes'].append(value&255)
        else:raise AssertionError('Unexpected MMIO write')
    def cache(uc,address,size,unused):events['cache_routine_entries']+=1
    def failure(uc,address,size,unused):
        events['decoder_failure_branch']=True;uc.emu_stop()
    u.hook_add(UC_HOOK_MEM_WRITE,uart,begin=0xb0000000,end=0xb0000fff)
    u.hook_add(UC_HOOK_MEM_WRITE,uart,begin=0x10000000,end=0x10000fff)
    u.hook_add(UC_HOOK_CODE,cache,begin=0x805000d4,end=0x805000d4)
    u.hook_add(UC_HOOK_CODE,failure,begin=0x805002b8,end=0x805002b8)
    started=time.monotonic();error=None
    try:u.emu_start(ENTRY,MAIN,timeout=20000000,count=250000000)
    except (UcError,AssertionError) as exc:error=type(exc).__name__+': '+str(exc)
    elapsed=round(time.monotonic()-started,3)
    pc=u.reg_read(reg('pc'))
    actual=bytes(u.mem_read(0x400,len(expected)))
    result={'case':name,'invalid_properties_memory_only':invalid_properties,
            'elapsed_seconds':elapsed,'stop_pc':hex(pc),'error':error,
            'reached_main_entry':pc==MAIN,'output_matches_expected_main':actual==expected,
            'output_sha256':sha(actual),**events}
    if invalid_properties:
        result['passed']=error is None and events['decoder_failure_branch'] and pc!=MAIN
    else:
        result['passed']=error is None and pc==MAIN and actual==expected
    print(json.dumps({k:result[k] for k in ('case','elapsed_seconds','stop_pc','error','passed')},indent=2),flush=True)
    return result


def main():
    original=(ROOT.parent/'uimage.bin').read_bytes()
    original_main=(ROOT.parent/'main-decompressed.bin').read_bytes()
    image=(OUT/'phy-diagnostic.uimage.NOT-FOR-FLASHING.bin').read_bytes()
    patched=(OUT/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
    assert sha(original)=='43ef36588e9f3c08b302583a60fc30bcb8fd374953a82a88eb64fcef2714c243'
    assert sha(original_main)=='2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
    assert sha(image)=='64421c4fada9034e9622b0a839745a758534dc75d77ad79dd6da9b71bdbf3706'
    assert sha(patched)=='0ccb104d36fe70b0c5411979eda687519c0395642efb6ff22a168b40ec5251fe'
    assert image[64:64+0x2440]==original[64:64+0x2440]
    cases=[trial('original_control',original,original_main)]
    # Do not diagnose the candidate with an unsupported baseline emulation.
    if cases[0]['passed']:
        cases.append(trial('original_baseline_diagnostic',image,patched))
        if cases[-1]['passed']:cases.append(trial('invalid_lzma_properties',image,patched,True))
    report={'status':'PASS: native loader cases' if len(cases)==3 and all(c['passed'] for c in cases) else 'INCOMPLETE: native loader experiment',
            'candidate_sha256':sha(image),'source_sha256':sha(original),'cases':cases,
            'limits':['Unchanged native loader/decoder execute in emulated RAM, not on MT7628KN.',
                      'Main firmware is not executed; stop at its entry address.',
                      'RAM mapping is a model, not DRAM capacity or aliasing validation.',
                      'UART/cache behavior is emulated; no real cache coherency or peripheral timing validation.',
                      'U-Boot image authentication/CRC/loading and power-on initialization are outside scope.',
                      'Invalid properties change only emulated payload RAM and bypass U-Boot checks.',
                      'No candidate image changes, devices, Flash access, network packets or recovery tests.']}
    (OUT/'native-loader-experiment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],flush=True)
    return 0 if report['status'].startswith('PASS:') else 1


if __name__=='__main__':raise SystemExit(main())
