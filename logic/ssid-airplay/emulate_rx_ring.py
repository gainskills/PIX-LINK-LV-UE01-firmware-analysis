"""Offline original Ethernet RX ring branches. Synthetic RAM/MMIO, no AP access."""
import json
import struct
from emulate_native_relink import IMAGE, SHA, ROOT, reg, Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE

CTX=0x802c0000; DEV=0x802b0000; RING=0x802d0000; TABLE=0x802e0000
RETURN=0x802f1000; CALC=0x10100908


def trial(name, count, head, ready, length, interface=False):
    u=Uc(UC_ARCH_MIPS, UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0,0x300000); u.mem_write(0x400,IMAGE)
    u.mem_map(0x10100000,0x2000)
    def word(a,v):u.mem_write(a&0x1fffffff,struct.pack('<I',v&0xffffffff))
    def half(a,v):u.mem_write(a&0x1fffffff,struct.pack('<H',v))
    def get(a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
    for n,v in [('sp',0x802f0000),('ra',RETURN),('a0',CTX),('cp0_status',0x1000ff01)]:u.reg_write(reg(n),v)
    word(0x8021e42c,DEV); word(0x801eee8c,0)
    word(CTX,RING); word(CTX+4,TABLE); half(CTX+8,count); half(CTX+0xc,head); word(CTX+0x10,0x900)
    for i in range(count):
        word(RING+16*i,0x280000)
        word(RING+16*i+4,(0x80000000|(length<<16)) if i in ready else 0x40000000)
        word(TABLE+4*i,0x80270000)
    word(0x80270008,0x80280000)
    # VLAN-tagged synthetic packet, VLAN 1. Interface mapping is explicitly modeled.
    u.mem_write(0x28000c,b'\x81\x00\x00\x01')
    if interface:
        word(DEV+0xb0,0x802a0000); half(DEV+0x5a,1)
        word(0x802a0000,0x80290000); half(0x802a0008,0); half(0x802a000c,1)
    evidence={'case':name,'ring_size':count,'initial_head':head,'ready_descriptors':ready,
              'packet_length':length,'mapped_interface':interface,'allocation_calls':0,'calc_writes':[]}
    def write(uc,access,address,size,value,unused):
        if address&0x1fffffff==CALC:evidence['calc_writes'].append(value)
    def code(uc,address,size,unused):
        if address==0x80017200:
            evidence['allocation_calls']+=1
            uc.reg_write(reg('v0'),0);uc.reg_write(reg('pc'),uc.reg_read(reg('ra')))
        elif address==0x8014fca8:
            raise AssertionError('Unexpected debug output path')
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.emu_start(0x800173f4,RETURN,timeout=3000000,count=20000)
    assert u.reg_read(reg('pc'))==RETURN and u.reg_read(reg('sp'))==0x802f0000
    observed={hex(offset):get(CTX+offset) for offset in (0x14,0x18,0x1c,0x20,0x24)}
    n=len(ready)
    assert observed['0x14']==n and observed['0x18']==n*length
    assert observed['0x1c']==(n if length<60 else 0)
    assert observed['0x20']==(n if length>=60 and not interface else 0)
    assert observed['0x24']==(n if length>=60 and interface else 0)
    assert evidence['allocation_calls']==(n if interface and length>=60 else 0)
    assert evidence['calc_writes']==ready
    final_head=struct.unpack('<H',u.mem_read((CTX+0xc)&0x1fffffff,2))[0]
    assert final_head==(head+n)%count
    for i in ready:
        assert get(RING+16*i+4)==0x40000000
        assert get(TABLE+4*i)==0x80270000  # existing buffer retained on drop/failure
    evidence.update({'final_head':final_head,'counters_by_context_offset':observed,
                     'returned':True,'ready_descriptors_rearmed':True})
    return evidence


if __name__=='__main__':
    cases=[trial('nothing_ready',4,0,[],64),trial('short_frame_drop',4,0,[0],42),
           trial('short_frame_wrap',4,3,[3],42),trial('all_ready_bounded_pass',4,0,[0,1,2,3],42),
           trial('no_interface_drop',4,0,[0],64),trial('replacement_allocation_failure',4,0,[0],64,True)]
    report={'status':'PASS: six original Ethernet RX ring branch experiments','source_sha256':SHA,
            'entry':'0x800173f4','cases':cases,
            'limits':['Synthetic ring, descriptors, packet, interface and MMIO state.',
                      'Replacement buffer allocator is stubbed to fail; allocator internals not executed.',
                      'Successful receive delivery, cache operations and DMA timing are not modeled.',
                      'Does not prove descriptors or counters had these states during X99 failure.',
                      'Does not exercise TX, interrupt scheduling or complete recovery.',
                      'No device access, packets, PHY writes, configuration or firmware changes.']}
    (ROOT/'rx-ring-experiment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])
