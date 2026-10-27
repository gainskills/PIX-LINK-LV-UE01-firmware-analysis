"""Offline original IPv4 MAT lookup and aging predicate; no AP/network access."""
import json,struct
from emulate_native_relink import IMAGE,SHA,ROOT,reg,Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE

CTX=0x802d0000;TABLE=0x802c0000;NODE=0x802b0000;DEFAULT=0x80290000
KEY=0x0401a8c0;RETURN=0x802f1000


def machine():
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0,0x300000);u.mem_write(0x400,IMAGE)
    for n,v in [('sp',0x802f0000),('ra',RETURN),('cp0_status',0x1000ff01)]:u.reg_write(reg(n),v)
    return u


def put(u,a,v):u.mem_write(a&0x1fffffff,struct.pack('<I',v&0xffffffff))
def get(u,a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
def bucket(ip):return ((ip&255)^((ip>>8)&255)^((ip>>16)&255)^(ip>>24))&63


def lookup(name,entries,key=KEY,enabled=True,initialized=True,now=40000):
    u=machine();put(u,CTX+0xc,TABLE if initialized else 0)
    u.mem_write(TABLE&0x1fffffff,bytes([int(enabled)]))
    put(u,TABLE+0x104,DEFAULT);u.mem_write((DEFAULT+4)&0x1fffffff,b'\xff'*6)
    put(u,0x8025df98,0x802a0000);put(u,0x802a0008,now);put(u,0x802a000c,0)
    for i,(ip,last) in enumerate(entries):
        address=NODE+32*i
        put(u,address,ip);u.mem_write((address+4)&0x1fffffff,bytes.fromhex('020000000004'))
        put(u,address+0xc,last);put(u,address+0x10,NODE+32*(i+1) if i+1<len(entries) else 0)
        assert bucket(ip)==bucket(key)
    if entries:put(u,TABLE+4+4*bucket(key),NODE)
    u.reg_write(reg('a0'),CTX);u.reg_write(reg('a1'),key)
    u.emu_start(0x80051950,RETURN,timeout=3000000,count=10000)
    assert u.reg_read(reg('pc'))==RETURN and u.reg_read(reg('sp'))==0x802f0000
    result=u.reg_read(reg('v0'))
    multicast=(key&0xf0)==0xe0
    matched=next((i for i,(ip,last) in enumerate(entries) if ip==key),None)
    expected=(0 if not initialized or not enabled else TABLE+0x108 if multicast else
              NODE+32*matched+4 if matched is not None else DEFAULT+4)
    assert result==expected,(name,hex(result),hex(expected))
    for i,(ip,last) in enumerate(entries):
        expected_time=now if enabled and initialized and not multicast and i==matched else last
        assert get(u,NODE+32*i+0xc)==expected_time
    mac=bytes(u.mem_read(result&0x1fffffff,6)).hex(':') if result else None
    if multicast and initialized and enabled:assert mac=='01:00:5e:00:00:fb'
    return {'case':name,'modeled_now':now,'input_timestamps':[last for ip,last in entries],
            'result_pointer':hex(result),'result_mac_synthetic':mac,
            'matched_timestamp_after':get(u,NODE+32*matched+0xc) if matched is not None else None}


def aging(name,last,now,matching=False):
    u=machine();put(u,NODE,KEY if matching else KEY^0x0101);put(u,NODE+0xc,last)
    for n,v in [('s0',NODE),('s3',KEY),('s1',now),('s7',0x80280000)]:u.reg_write(reg(n),v)
    reached=[]
    def code(uc,address,size,unused):
        if address in (0x80051d24,0x80051de0,0x80051d4c):
            reached.append({0x80051d24:'keep_other_entry',0x80051de0:'expired_other_entry',
                            0x80051d4c:'update_matching_entry'}[address]);uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,code)
    u.emu_start(0x80051d04,RETURN,timeout=3000000,count=1000)
    signed_delta=(last+30000-now)&0xffffffff
    expected='update_matching_entry' if matching else 'expired_other_entry' if signed_delta&0x80000000 else 'keep_other_entry'
    assert reached==[expected]
    return {'case':name,'last':last,'now':now,'same_ip':matching,'outcome':reached[0]}


if __name__=='__main__':
    lookups=[lookup('uninitialized',[],initialized=False),lookup('disabled',[],enabled=False),
             lookup('recent_match',[(KEY,39999)]),lookup('old_match_still_refreshes',[(KEY,1)]),
             lookup('empty_bucket_fallback',[]),lookup('collision_miss_fallback',[(KEY^0x0101,1)]),
             lookup('collision_chain_match',[(KEY^0x0101,1),(KEY,2)]),
             lookup('ipv4_multicast_mapping',[],key=0xfb0000e0)]
    ages=[aging('recent_other',100,101),aging('exact_threshold_kept',100,30100),
          aging('beyond_threshold',100,30101),aging('same_ip_bypasses_age',1,40000,True),
          aging('clock_wrap_before_threshold',0xffffff00,0x742f),
          aging('clock_wrap_after_threshold',0xffffff00,0x7431)]
    report={'status':'PASS: eight original MAT lookups and six original aging-branch experiments',
            'source_sha256':SHA,'lookup_entry':'0x80051950','aging_entry':'0x80051d04',
            'lookups':lookups,'aging_branches':ages,
            'limits':['Lookup executes original clock accessor with a synthetic clock object.',
                      'Aging experiments stop before actual deletion, allocation or MAC update.',
                      'Threshold is 30000 native clock units; wall-clock conversion not established.',
                      'Synthetic nodes/default MAC do not establish live table or default values.',
                      'No malformed-packet, concurrency, whole forwarding path or real failure reproduction.',
                      'No AP access, packets, configuration changes or firmware modification.']}
    (ROOT/'mat-lookup-aging-experiment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])
