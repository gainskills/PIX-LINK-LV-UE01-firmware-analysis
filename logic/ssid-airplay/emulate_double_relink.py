"""Execute combined monitor components and native PHY with explicit HAL stubs.

No network/device actions. The prior monitor model stubbed interface restart;
this model executes that helper separately. The continuous attempt is recorded
as incomplete when Unicorn raises, rather than counted as a successful test.
"""
import hashlib,json,struct,sys
from pathlib import Path
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INTR
from unicorn import mips_const as mc
ROOT=Path(__file__).resolve().parent


def trial(reinitialize,pending,helper_only=False,full_path=False):
    image=(ROOT.parent/'phy-diagnostic/combined/main-secure-ui-phy.NOT-FLASHABLE.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest()=='5b8797c162d21db877a546b66f3927954348497b3c3ad43fdf154e8081e0072d'
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    for address,size in [(0,0x300000),(0x10000000,4096),(0x10110000,4096)]:u.mem_map(address,size)
    u.mem_write(0x400,image)
    reg=lambda name:getattr(mc,'UC_MIPS_REG_'+name.upper())
    def put(address,value):u.mem_write(address&0x1fffffff,struct.pack('<I',value&0xffffffff))
    def get(address):return struct.unpack('<I',u.mem_read(address&0x1fffffff,4))[0]
    u.reg_write(reg('sp'),0x802f0000);u.reg_write(reg('cp0_status'),0x1000ff01)
    put(0x80212ca0,pending);put(0x802551d0,0);put(0x802551e0,reinitialize)
    put(0x801ed2d0,1);u.mem_write(0x25e204,b'eth0\0');u.mem_write(0x25e4e9,b'\0')
    put(0xb0110080,0x83818301);put(0xb0000060,0x80)
    entries=[];writes=[];events=[];iterations=0;tick=0;recent=[];interface_calls=0
    def returned(value=0):
        u.reg_write(reg('v0'),value)
    def code(uc,address,size,unused):
        nonlocal iterations,tick,interface_calls
        recent.append(address)
        if len(recent)>24:recent.pop(0)
        if address==0x8014e3bc and reinitialize and not helper_only and not full_path:
            uc.emu_stop()
        elif address==0x8014e280:
            iterations+=1
            if iterations==2:uc.emu_stop()
        elif address==0x8014e190 and not helper_only and not full_path:
            interface_calls+=1;returned()
        elif address==0x800082cc:
            assert uc.reg_read(reg('a0'))==0x011a0100
            uc.mem_write(uc.reg_read(reg('a1'))&0x1fffffff,b'1\0');returned()
        elif address==0x8015b5a8:returned(1)
        elif address==0x80007728:
            assert uc.reg_read(reg('a0'))==0x04f20100
            put(uc.reg_read(reg('a1')),1);returned()
        elif address==0x80150478:
            ticks=uc.reg_read(reg('a0'));events.append(dict(event='modeled_delay',ticks=ticks,at_tick=tick))
            tick+=ticks;returned()
        elif address==0x80017134:
            entries.append(dict(caller_return=hex(uc.reg_read(reg('ra'))),
                                parent_return=hex(get(uc.reg_read(reg('sp'))+12)) if uc.reg_read(reg('ra'))==0x80003960 else None,
                                at_modeled_tick=tick,link_up_in_model=True))
        elif address==0x8019f32c:
            uc.reg_write(reg('t3'),tick)
        elif address==0x8014fca8:returned()
        elif address in [0x8013139c,0x80003530,0x800035e8,0x80114d08,0x80006c18,
                          0x80004e08,0x80015d1c,0x80016e64,0x80003598,0x80003664,0x80114d14,
                          0x8014dcc0,0x8014dff4,0x8014dc34]:
            events.append(dict(event='stub_dependency',address=hex(address),argument=uc.reg_read(reg('a0'))));returned()
    def read(uc,access,address,size,value,unused):
        if address&0x1fffffff==0x101100c4:
            assert not uc.reg_read(reg('cp0_status'))&1
            put(0xb01100c4,1)
    def write(uc,access,address,size,value,unused):
        if address&0x1fffffff==0x101100c0:
            assert not uc.reg_read(reg('cp0_status'))&1
            writes.append(dict(phy=value&31,register=(value>>8)&31,value=value>>16,at_modeled_tick=tick))
    def intr(uc,number,unused):
        raise RuntimeError(dict(interrupt=number,pc=hex(uc.reg_read(reg('pc'))),recent=[hex(p) for p in recent],word=hex(get(0x8014e30c)),status=hex(uc.reg_read(reg('cp0_status')))))
    # Model external calls with real JR RA / NOP returns, avoiding PC writes
    # from code hooks. The full-path exception still occurs with these stubs.
    stubs=[0x800082cc,0x8015b5a8,0x80007728,0x80150478,0x8014fca8,
           0x8013139c,0x80003530,0x800035e8,0x80114d08,0x80006c18,
           0x80004e08,0x80015d1c,0x80016e64,0x80003598,0x80003664,
           0x80114d14,0x8014dcc0,0x8014dff4,0x8014dc34]
    if not helper_only and not full_path:stubs.append(0x8014e190)
    for target in stubs:u.mem_write(target&0x1fffffff,struct.pack('<II',0x03e00008,0))
    # CP0 Count is a modeled tick source, supplied by the instruction hook.
    put(0x8019f32c,0)
    u.hook_add(UC_HOOK_INTR,intr)
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,read);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.reg_write(reg('ra'),0x802f1000)
    try:
        u.emu_start(0x8014e190 if helper_only else 0x8014e1f8,0x802f1000,timeout=5000000,count=300000)
    except Exception as error:
        raise RuntimeError(dict(case=[reinitialize,pending],pc=hex(u.reg_read(reg('pc'))),
                                recent=[hex(pc) for pc in recent],events=events[-8:])) from error
    expected=1 if helper_only else (0 if reinitialize and not full_path else pending+(reinitialize if full_path else 0))
    assert (u.reg_read(reg('pc'))==0x802f1000 if helper_only else
            u.reg_read(reg('pc'))==0x8014e3bc if reinitialize and not full_path else iterations==2)
    assert len(entries)==expected
    if not helper_only and not full_path:assert interface_calls==reinitialize
    assert len(writes)==10*len(entries)
    if not helper_only and (not reinitialize or full_path):assert get(0x80212ca0)==0 and get(0x802551e0)==0
    assert get(0x8019f36c)==len(entries)
    return dict(interface_reinitialize_requested=bool(reinitialize),phy_request_pending=bool(pending),
                helper_only=helper_only,interface_helper_calls=interface_calls,actual_native_relink_entries=entries,phy0_writes=[w for w in writes if w['phy']==0],
                native_relink_count=get(0x8019f36c),events=events,
                final_pending=get(0x80212ca0),final_interface_request=get(0x802551e0))


if __name__=='__main__':
    cases=[trial(reinit,pending) for reinit,pending in [(0,0),(0,1),(1,0),(1,1)]]
    helper=trial(0,0,helper_only=True)
    for case in cases:
        case['composed_phy_calls']=int(case['phy_request_pending'])+case['interface_helper_calls']*helper['native_relink_count']
        case['monitor_scope']='prefix through interface-helper return' if case['interface_reinitialize_requested'] else 'one complete iteration'
    try:
        full=trial(1,1,full_path=True)
        full_status=dict(status='PASS',result=full)
    except RuntimeError as error:
        full_status=dict(status='BLOCKED: emulator exception, not a firmware fault finding',details=str(error),
                         cause=str(error.__cause__))
    report=dict(status='PASS: two monitor iterations, two monitor prefixes and actual interface helper; duplicate path supported by static composition',
                cases=cases,actual_interface_helper=helper,full_path_attempt=full_status,
                limits=['In monitor scenarios the interface helper is an explicit return stub; its real code is executed separately.',
                        'Reinitialize=1 monitor runs stop at helper return; pending branch uses validated reinitialize=0 execution and unchanged static continuation.',
                        'Composed counts are not a successful full-path emulation or real-device observation.',
                        'Native PHY and MDIO writes execute; network dependencies and CP0 Count are modeled.',
                        'Modeled delay units are not wall-clock measurements; POA is held up.',
                        'Does not prove simultaneous flags occurred in the real failed boot.',
                        'No AP access, configuration changes, resets or firmware artifact edits.'])
    (ROOT/'double-relink-experiment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],composed_counts=[c['composed_phy_calls'] for c in cases],
                          actual_helper_entries=helper['actual_native_relink_entries'],
                          actual_helper_phy0_writes=helper['phy0_writes'],full_path_status=full_status['status']),indent=2))
