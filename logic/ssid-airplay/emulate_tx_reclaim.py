"""Offline original Ethernet interrupt/TX reclaim; synthetic MMIO, no AP access."""
import json
import struct
from emulate_native_relink import IMAGE,SHA,ROOT,reg,Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE

DEV=0x802b0000;RING=0x802d0000;META=0x802e0000;RETURN=0x802f1000


def trial(name,interrupt,ready,interface=False):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0,0x300000);u.mem_write(0x400,IMAGE);u.mem_map(0x10100000,0x2000)
    def word(a,v):u.mem_write(a&0x1fffffff,struct.pack('<I',v&0xffffffff))
    def half(a,v):u.mem_write(a&0x1fffffff,struct.pack('<H',v))
    def get(a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
    def gethalf(a):return struct.unpack('<H',u.mem_read(a&0x1fffffff,2))[0]
    for n,v in [('sp',0x802f0000),('ra',RETURN),('cp0_status',0x1000ff01),('gp',0x8021b190)]:u.reg_write(reg(n),v)
    word(0x8021e42c,DEV);word(0x801eee8c,0);word(0xb0100a20,interrupt)
    word(DEV+0x24,0x30001);word(DEV+0x5c,RING);word(DEV+0x60,META)
    half(DEV+0x64,4);half(DEV+0x66,0);half(DEV+0x6a,0);word(DEV+0x6c,0x800)
    for i in range(4):
        word(RING+16*i+4,0x80000000 if i in ready else 0)
        word(META+8*i,0x80290000 if interface else 0)
        word(META+8*i+4,0x80270000+256*i)
    evidence={'case':name,'interrupt_status':hex(interrupt),'ready_descriptors':ready,
              'interface_present':interface,'freed_buffers':[],'mmio_writes':[]}
    recent=[];resume=[]
    def code(uc,address,size,unused):
        recent.append(hex(address));del recent[:-100]
        if address==0x80121528:
            evidence['freed_buffers'].append(hex(uc.reg_read(reg('a0'))))
            uc.reg_write(reg('v0'),0)
            resume.append((uc.reg_read(reg('ra')),uc.reg_read(reg('sp'))))
            uc.emu_stop()
        elif address in (0x800173f4,0x8014fca8):
            raise AssertionError('Unexpected RX or debug-output branch')
    def write(uc,access,address,size,value,unused):
        if 0x10100000<=address&0x1fffffff<0x10102000:
            evidence['mmio_writes'].append({'address':hex(address&0x1fffffff),'value':hex(value)})
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
    try:
        start=0x800177fc
        for segment in range(6):
            u.emu_start(start,RETURN,timeout=3000000,count=20000)
            if not resume:break
            start,saved_sp=resume.pop()
            # Enforce modeled backend's ABI. MIPS hook stop may leave its first
            # stack-adjust instruction applied; that instruction is outside scope.
            u.reg_write(reg('sp'),saved_sp)
        else:raise AssertionError('Exceeded intercepted-call budget')
    except Exception as error:
        raise RuntimeError(f'{name}: pc={u.reg_read(reg("pc")):#x}, ra={u.reg_read(reg("ra")):#x}, sp={u.reg_read(reg("sp")):#x}, freed={evidence["freed_buffers"]}, recent={recent}') from error
    assert u.reg_read(reg('pc'))==RETURN and u.reg_read(reg('sp'))==0x802f0000
    assert u.reg_read(reg('gp'))==0x8021b190
    n=len(ready) if interrupt&1 else 0
    assert gethalf(DEV+0x66)==n and gethalf(DEV+0x6a)==n%4
    assert len(evidence['freed_buffers'])==(n if interface else 0)
    assert get(0x80290070)==(n if interface else 0)
    assert gethalf(DEV+0xbe)==(n if not interface else 0)
    for i in range(n):assert get(META+8*i)==0 and get(META+8*i+4)==0
    if not interface and n:
        chain=[];node=get(DEV+0xc0)
        while node:
            assert len(chain)<4,'Unbounded returned-buffer list'
            chain.append(node);node=get(node)
        assert chain==[0x80270000+256*i for i in reversed(range(n))]
    assert evidence['mmio_writes']==[
        {'address':'0x10100a20','value':hex(interrupt)},
        {'address':'0x10100a28','value':'0x30001'}]
    evidence.update({'returned':True,'final_free_descriptors':gethalf(DEV+0x66),
                     'final_tail':gethalf(DEV+0x6a),'recycled_to_pool':gethalf(DEV+0xbe)})
    return evidence


if __name__=='__main__':
    cases=[trial('no_tx_interrupt',0,[0]),trial('tx_still_owned_by_dma',1,[]),
           trial('completed_buffer_to_pool',1,[0]),trial('completed_buffer_to_free',1,[0],True),
           trial('full_ring_wrap',1,[0,1,2,3])]
    report={'status':'PASS: five original Ethernet TX reclaim experiments','source_sha256':SHA,
            'entry':'0x800177fc','cases':cases,
            'limits':['Synthetic descriptors, TX-only interrupt status, adapter and MMIO state.',
                      'Buffer free backend is modeled; SP is restored to its call-entry value before resuming.',
                      'MIPS stop at backend entry can apply its first stack adjustment; backend internals are outside scope.',
                      'Does not execute packet submission, RX delivery, DMA timing or interrupt scheduler.',
                      'MMIO writes are observed, not an interrupt-controller hardware simulation.',
                      'Does not prove these ring states occurred during X99 failures or rule out lost interrupts.',
                      'No device access, packets, configuration changes, PHY writes or firmware changes.']}
    (ROOT/'tx-reclaim-experiment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])
