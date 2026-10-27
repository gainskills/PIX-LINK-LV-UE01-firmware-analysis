"""Offline native IPv4 MAT entry-print gate, not a full table/printf emulation."""
import json,struct
from emulate_native_relink import IMAGE,SHA,ROOT,reg,Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE


def trial(enabled,suppress):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0,0x300000);u.mem_write(0x400,IMAGE)
    def word(a,v):u.mem_write(a&0x1fffffff,struct.pack('<I',v&0xffffffff))
    for n,v in [('sp',0x802f0000),('v1',enabled),('s0',0x802b0000),
                ('s4',0x80250000),('fp',0x8017428c),('cp0_status',0x1000ff01)]:
        u.reg_write(reg(n),v)
    word(0x8024af4c,suppress);word(0x802b0000,0xc0a80104)
    u.mem_write(0x2b0004,bytes.fromhex('020000000004'));word(0x802b000c,123)
    outcomes=[];outside=[]
    def code(uc,address,size,unused):
        if address in (0x800517d8,0x8005183c):
            outcomes.append('entry_printf_reached' if address==0x8005183c else 'entry_skipped')
            if address==0x8005183c:
                assert uc.reg_read(reg('a0'))==0x8017428c
                assert uc.reg_read(reg('a1'))==0xc0a80104
            uc.emu_stop()
    def write(uc,access,address,size,value,unused):
        if not 0x2ef000<=address&0x1fffffff<=0x2f0004:outside.append(hex(address))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.emu_start(0x80051800,0x802f1000,timeout=3000000,count=1000)
    expected='entry_printf_reached' if enabled and not suppress else 'entry_skipped'
    assert outcomes==[expected] and not outside
    return {'modeled_logging_gate':enabled,'modeled_suppression_gate':suppress,
            'populated_node_ip':'192.168.1.4','outcome':outcomes[0],'writes_outside_stack':outside}


if __name__=='__main__':
    cases=[trial(0,0),trial(1,1),trial(1,0)]
    result={'status':'PASS: three original IPv4 MAT entry-print gate experiments','source_sha256':SHA,
            'entry':'0x80051800','stop_points':['0x800517d8','0x8005183c'],'cases':cases,
            'limits':['Executes only native gate and entry argument loading with a populated synthetic node.',
                      'Does not execute printf, full table walk, callers or other MAT tables.',
                      'A preceding header print step and its runtime global load are outside this experiment.',
                      'Full-walk/printf emulation was attempted but hit a local Unicorn CPU exception; not a device finding.',
                      'Does not measure actual runtime logging flags or X99 table membership.',
                      'No AP access, network packets, log-level changes or firmware modifications.']}
    (ROOT/'mat-dump-experiment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])
