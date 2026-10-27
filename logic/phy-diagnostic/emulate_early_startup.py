"""Offline main entry through BSS clear, stopping before constructors.

The board HAL initializer is replaced only in emulator RAM with a return stub.
No hardware, networking, constructors, scheduler or firmware file modifications.
"""
import hashlib,json,struct,sys,time
from pathlib import Path
from unicorn import Uc,UcError,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn import mips_const as mc
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'original-baseline'
BASE=0x80000400;STOP=0x80160218
BSS_START=0x80213198;BSS_END=0x80264518
RANGES=[(0xa4b0,0xa4b4),(0x16d34,0x16d3c),(0x19ecc2,0x19f140),(0x211ff0,0x211ff4)]


def sha(data):return hashlib.sha256(data).hexdigest()
def reg(name):return getattr(mc,'UC_MIPS_REG_'+name.upper())
def read(u,address,size):return bytes(u.mem_read(address&0x1fffffff,size))


def machine(main):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0,0x800000);u.mem_write(0,b'\xa5'*0x800000);u.mem_write(0x400,main)
    for n,v in [('sp',0x807f0000),('ra',0x807f1000),('gp',0x8021b190),('cp0_status',0x1000ff01)]:
        u.reg_write(reg(n),v)
    return u


def startup(name,main):
    u=machine(main)
    # Hardware HAL is explicitly outside scope. Keep entry, cache helper,
    # vector setup and native BSS clear unchanged.
    u.mem_write(0x1606e0,struct.pack('<II',0x03e00008,0))
    expected=bytearray(main)
    expected[0x1606e0-0x400:0x1606e8-0x400]=struct.pack('<II',0x03e00008,0)
    before=[read(u,BASE+a,b-a) for a,b in RANGES]
    end_guard=read(u,BSS_END,32)
    started=time.monotonic();error=None
    try:u.emu_start(BASE,STOP,timeout=10000000,count=5000000)
    except UcError as exc:error=str(exc)
    pc=u.reg_read(reg('pc'))
    protected=all(read(u,BASE+a,b-a)==old for (a,b),old in zip(RANGES,before))
    bss=read(u,BSS_START,BSS_END-BSS_START)
    matched=read(u,BASE,len(main))==bytes(expected)
    result={'case':name,'stop_pc':hex(pc),'error':error,'elapsed_seconds':round(time.monotonic()-started,3),
            'diagnostic_ranges_unchanged':protected,'whole_main_matches_except_modeled_hal':matched,
            'bss_zeroed':bss==bytes(len(bss)),'guard_after_bss_preserved':read(u,BSS_END,32)==end_guard,
            'passed':error is None and pc==STOP and protected and matched and bss==bytes(len(bss)) and read(u,BSS_END,32)==end_guard}
    print(json.dumps(result,indent=2),flush=True)
    return result


def canary_control(main):
    u=machine(main);address=0x80220000
    canary=b'DIAGNOSTIC-IN-BSS-MUST-BE-CLEARED'
    u.mem_write(address&0x1fffffff,canary)
    u.emu_start(0x80000b28,0x807f1000,timeout=10000000,count=5000000)
    cleared=read(u,address,len(canary))==bytes(len(canary))
    assert u.reg_read(reg('pc'))==0x807f1000 and cleared
    return {'case':'synthetic_canary_inside_bss','canary_address':hex(address),
            'canary_was_cleared':cleared,'passed':True,
            'meaning':'Confirms native clearing affects a canary inside BSS, unlike actual diagnostic placement.'}


def main():
    original=(ROOT.parent/'main-decompressed.bin').read_bytes()
    patched=(OUT/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
    assert sha(original)=='2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe'
    assert sha(patched)=='0ccb104d36fe70b0c5411979eda687519c0395642efb6ff22a168b40ec5251fe'
    assert BASE+len(patched)==BSS_START
    cases=[startup('original_control',original)]
    if cases[0]['passed']:
        cases.append(startup('original_baseline_diagnostic',patched))
        if cases[-1]['passed']:cases.append(canary_control(patched))
    report={'status':'PASS: three early-startup placement experiments' if len(cases)==3 and all(c['passed'] for c in cases) else 'INCOMPLETE: early-startup experiment',
            'main_sha256':sha(patched),'bss_range':[hex(BSS_START),hex(BSS_END)],
            'protected_main_offsets':[[hex(a),hex(b)] for a,b in RANGES],'cases':cases,
            'limits':['Native entry/cache/vector/BSS code executes in modeled RAM/CP0/cache.',
                      'Board HAL 0x801606e0 is replaced only in emulator RAM with jr ra; nop.',
                      'Stops at 0x80160218 before constructor table processing.',
                      'No constructors, allocator, scheduler, peripheral or later network initialization validated.',
                      'Not real cache coherency, memory capacity, candidate full boot or recovery validation.',
                      'Canary is synthetic; source/candidate images are unchanged.',
                      'No devices, network packets, configuration changes or Flash writes.']}
    (OUT/'early-startup-experiment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],flush=True)
    return 0 if report['status'].startswith('PASS:') else 1


if __name__=='__main__':raise SystemExit(main())
