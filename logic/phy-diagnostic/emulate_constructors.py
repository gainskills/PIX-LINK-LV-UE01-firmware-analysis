"""Bounded offline constructor execution with a deliberately limited board model.

Original must pass before judging candidate. Any unsupported hardware/CPU path
is an incomplete model, not evidence of a candidate/device defect.
"""
import hashlib,json,struct,time
from emulate_early_startup import ROOT,OUT,BASE,RANGES,machine,read,reg,sha
from unicorn import UcError,UC_HOOK_CODE,UC_HOOK_MEM_WRITE,UC_HOOK_MEM_READ,UC_HOOK_MEM_FETCH_UNMAPPED,UC_HOOK_MEM_READ_UNMAPPED,UC_HOOK_MEM_WRITE_UNMAPPED

STOP=0x80000718


def trial(name,main,refined=False,stop=STOP,prefix_count=None):
    u=machine(main)
    if refined:
        # Keep real board/virtual-vector software setup. Isolate only serial
        # peripheral initialization, and record controller output writes.
        u.mem_write(0x160dcc,struct.pack('<II',0x03e00008,0))
        u.mem_map(0x10000000,0x1000)
    else:u.mem_write(0x1606e0,struct.pack('<II',0x03e00008,0))
    table=[struct.unpack_from('<I',main,a-BASE)[0] for a in range(0x80212d28,0x80212d80,4)]
    entries=[];writes=[];unmapped=[];mmio=[];unsupported=[]
    before=[read(u,BASE+a,b-a) for a,b in RANGES]
    def constructor(uc,address,size,unused):entries.append(hex(address))
    def protected(uc,access,address,size,value,unused):
        writes.append({'address':hex(address),'size':size})
    def missing(uc,access,address,size,value,unused):
        unmapped.append({'address':hex(address),'size':size,'access':access})
        return False
    def peripheral(uc,access,address,size,value,unused):
        physical=address&0x1fffffff
        item={'address':hex(physical),'size':size,'access':access,'value':hex(value)}
        mmio.append(item)
        # Write-only controller initialization/mask/unmask outputs; interrupt
        # delivery and controller readback are not simulated.
        if access!=17 or physical not in (0x10000200,0x10000278,0x10000280) or size!=4:
            unsupported.append(item);uc.emu_stop()
    for address in table:u.hook_add(UC_HOOK_CODE,constructor,begin=address,end=address)
    for a,b in RANGES:
        physical=(BASE+a)&0x1fffffff
        for alias in (0,0x80000000,0xa0000000):
            u.hook_add(UC_HOOK_MEM_WRITE,protected,begin=alias+physical,end=alias+physical+b-a-1)
    u.hook_add(UC_HOOK_MEM_READ_UNMAPPED,missing)
    u.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED,missing)
    u.hook_add(UC_HOOK_MEM_FETCH_UNMAPPED,missing)
    if refined:
        for alias in (0x10000000,0xb0000000):
            u.hook_add(UC_HOOK_MEM_READ,peripheral,begin=alias,end=alias+0xfff)
            u.hook_add(UC_HOOK_MEM_WRITE,peripheral,begin=alias,end=alias+0xfff)
    started=time.monotonic();error=None
    try:u.emu_start(BASE,stop,timeout=15000000,count=30000000)
    except UcError as exc:error=str(exc)
    pc=u.reg_read(reg('pc'))
    expected=[hex(a) for a in reversed(table)]
    if prefix_count is not None:expected=expected[:prefix_count]
    preserved=all(read(u,BASE+a,b-a)==old for (a,b),old in zip(RANGES,before))
    result={'case':name,'elapsed_seconds':round(time.monotonic()-started,3),
            'stop_pc':hex(pc),'error':error,'constructor_entries':entries,
            'expected_constructor_order':expected,'protected_writes':writes,
            'unmapped_accesses':unmapped,'diagnostic_ranges_unchanged':preserved,
            'model':'serial_init_stub_preserve_virtual_vectors' if refined else 'whole_board_hal_stub',
            'modeled_mmio_accesses':mmio,'unsupported_peripheral_accesses':unsupported,
            'reached_pre_application_boundary':pc==STOP,
            'requested_stop':hex(stop),'reached_requested_boundary':pc==stop,
            'constructors_completed_minimum':len(entries) if pc==STOP else max(0,len(entries)-1),
            'passed':error is None and pc==stop and entries==expected and preserved and not writes and not unsupported}
    print(json.dumps(result,indent=2),flush=True)
    return result


def main():
    original=(ROOT.parent/'main-decompressed.bin').read_bytes()
    candidate=(OUT/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
    assert sha(original)=='2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
    assert sha(candidate)=='0ccb104d36fe70b0c5411979eda687519c0395642efb6ff22a168b40ec5251fe'
    cases=[trial('original_control_refined_hal',original,True)]
    if cases[0]['passed']:cases.append(trial('original_baseline_diagnostic_refined_hal',candidate,True))
    passed=len(cases)==2 and all(c['passed'] for c in cases)
    report={'status':'PASS: original and candidate constructor experiments' if passed else 'INCOMPLETE: constructor environment model',
            'candidate_main_sha256':sha(candidate),'cases':cases,
            'limits':['Starts with nonzero modeled RAM; native board virtual-vector software setup executes.',
                      'Only serial peripheral init 0x80160dcc is replaced in emulator RAM; IRQ controller writes at 0x10000200/278/280 are recorded.',
                      'Interrupt delivery and controller readback semantics are not simulated.',
                      'Other observed peripheral access halts the model; no real peripheral state verified.',
                      'Stops before jump to 0x8014ed18 application entry; scheduler/network runtime not validated.',
                      'Emulated CPU/CP0/cache behavior does not establish real hardware timing or coherency.',
                      'An original-control failure is a model limitation; candidate is then not executed.',
                      'No AP access, image rebuild, configuration changes, Flash writes or recovery test.']}
    (OUT/'constructor-experiment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],flush=True)
    known_boundary=(not passed and cases[0]['error'] is None and cases[0]['stop_pc']=='0x80013fac' and
                    len(cases[0]['constructor_entries'])==9 and
                    cases[0]['unsupported_peripheral_accesses']==[
                        {'address':'0x10000034','size':4,'access':17,'value':'0x1000'}])
    if known_boundary:
        prefix=[trial('original_before_system_control_write',original,True,0x80013fa8,9)]
        if prefix[0]['passed']:
            prefix.append(trial('candidate_before_system_control_write',candidate,True,0x80013fa8,9))
        prefix_passed=len(prefix)==2 and all(c['passed'] for c in prefix)
        partial={'status':'PASS: constructor prefix only' if prefix_passed else 'INCOMPLETE: constructor prefix',
                 'candidate_main_sha256':sha(candidate),'cases':prefix,
                 'limits':report['limits']+[
                     'Stops at 0x80013fa8, before address setup and 0x80013fac system-control write; peripheral operation is not executed.',
                     'Eight constructor calls completed, ninth entered; remaining constructor bodies are unverified.',
                     'Full constructor report remains INCOMPLETE, even if both prefix cases pass.']}
        (OUT/'constructor-prefix-experiment.json').write_text(json.dumps(partial,indent=2)+'\n')
        print(partial['status'],flush=True)
    # The full constructor stage must remain incomplete; do not turn partial
    # prefix success into a successful full-stage exit status.
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
