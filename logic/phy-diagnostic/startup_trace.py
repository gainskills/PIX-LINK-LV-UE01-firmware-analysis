"""Offline startup trace extension; never accesses the AP."""
import struct
import patch
import hashlib
import json
from pathlib import Path

BASE_SHA='5b8797c162d21db877a546b66f3927954348497b3c3ad43fdf154e8081e0072d'

def assemble():
    old,sym=patch.assemble()
    a=patch.Assembler();a.data=bytearray(old);a.symbols=dict(sym)
    a.label('extended_trace');a.i(9,'sp','sp',-40)
    scratch=['t0','t1','t2','t3','t4','t5','t6','t7']
    for i,n in enumerate(scratch):a.i(43,n,'sp',i*4)
    a.cp0('t0');a.emit(0);a.i(9,'t1','z',-2);a.r(36,'t1','t0','t1');a.cp0('t1',write=True);a.hazards()
    a.address('t1','counter');a.i(35,'t2','t1',0);a.i(9,'t2','t2',1);a.i(43,'t2','t1',0)
    a.label('read_count');a.cp0('t3',9);a.emit(0);a.i(43,'t3','t1',4)
    a.address('t4','record_count');a.i(35,'t5','t4',0);a.i(11,'t6','t5',8)
    a.branch(4,'t6','z','trace_restore')
    # record size 28 = index*32 - index*4; count saturates independently of sequence.
    a.r(0,'t6','z','t5',5);a.r(0,'t7','z','t5',2);a.r(35,'t6','t6','t7')
    a.address('t7','records');a.r(33,'t6','t6','t7')
    a.i(43,'t2','t6',0);a.i(43,'ra','t6',4);a.i(43,'z','t6',8)
    a.li('t7',0x80003960);a.branch(5,'ra','t7','no_parent')
    a.i(35,'t7','sp',52);a.i(43,'t7','t6',8)
    a.label('no_parent');a.li('t7',0xb0110080);a.i(35,'t7','t7',0);a.i(43,'t7','t6',12)
    a.li('t7',0x802551d0);a.i(35,'t7','t7',0);a.i(43,'t7','t6',16)
    a.li('t7',0x80212ca0);a.i(35,'t7','t7',0);a.i(43,'t7','t6',20)
    a.i(43,'t3','t6',24)
    # Publish completed immutable record last, while local interrupts remain masked.
    a.i(9,'t5','t5',1);a.i(43,'t5','t4',0)
    a.label('trace_restore');a.cp0('t0',write=True);a.hazards()
    for i,n in enumerate(scratch):a.i(35,n,'sp',i*4)
    a.i(9,'sp','sp',40);a.emit(0x27bdffe8);a.emit(0x3c028017);a.jump(patch.RELINK+8)

    a.label('trace_dump');a.address('s0','records');a.address('s1','record_count');a.i(35,'s1','s1',0)
    a.move('s2','z');a.branch(4,'s1','z','extended_done')
    a.label('dump_loop')
    for fmt,left,right in [('caller_fmt',4,8),('link_fmt',0,12),('state_fmt',16,20),('clock_fmt',24,None)]:
        a.address('a0',fmt);a.move('a1','s2');a.i(35,'a2','s0',left)
        if right is not None:a.i(35,'a3','s0',right)
        a.jump(patch.PRINTF,True)
    a.i(9,'s0','s0',28);a.i(9,'s2','s2',1);a.i(9,'s1','s1',-1);a.branch(5,'s1','z','dump_loop')
    a.label('extended_done');a.data+=old[sym['done']-patch.START:sym['legacy']-patch.START]
    a.label('record_count');a.data+=bytes(4)
    a.label('records');a.data+=bytes(8*28)
    for name,fmt in [
        ('caller_fmt','PHYTRACE slot=%u caller=%08x parent=%08x\n'),
        ('link_fmt','PHYTRACE slot=%u seq=%u poa=%08x\n'),
        ('state_fmt','PHYTRACE slot=%u state=%u pending=%u\n'),
        ('clock_fmt','PHYTRACE slot=%u cp0=%u\n')]:
        a.label(name);a.data+=fmt.encode()+b'\0'
    while len(a.data)%4:a.data+=b'\0'
    a.label('extended_end')
    blob,symbols=a.finish();out=bytearray(blob)
    for previous,next_symbol in [('trace','extended_trace'),('done','trace_dump')]:
        struct.pack_into('<II',out,sym[previous]-patch.START,0x08000000|((symbols[next_symbol]>>2)&0x3ffffff),0)
    return bytes(out),symbols

def make_main(base):
    if hashlib.sha256(base).hexdigest()!=BASE_SHA:raise ValueError('Unknown installed combined baseline')
    old,_=patch.assemble();blob,_=assemble();lo=patch.START-patch.BASE;hi=lo+len(blob)
    if base[lo:lo+len(old)]!=old:raise ValueError('Existing diagnostic payload differs')
    if hi>0x1a8d69 or base[lo+len(old):hi]!=bytes(len(blob)-len(old)):
        raise ValueError('Extended diagnostic storage is occupied or outside retired images')
    result=bytearray(base);result[lo:hi]=blob
    return bytes(result)

def build():
    import builder
    root=Path(__file__).resolve().parent
    base=(root/'combined/main-secure-ui-phy.NOT-FLASHABLE.bin').read_bytes()
    result=make_main(base);blob,symbols=assemble()
    image,size=builder.package((root.parent/'uimage.bin').read_bytes(),result)
    destination=root/'startup-trace';destination.mkdir(exist_ok=True)
    files={'main-startup-trace.NOT-FLASHABLE.bin':result,
           'startup-trace.uimage.NOT-FOR-FLASHING.bin':image,'payload.bin':blob}
    for name,data in files.items():(destination/name).write_bytes(data)
    manifest=dict(status='OFFLINE CANDIDATE; NOT INSTALLED; NOT A STABILITY FIX',
                  base_main_sha256=BASE_SHA,main_sha256=builder.sha(result),uimage_sha256=builder.sha(image),
                  main_bytes=len(result),uimage_bytes=len(image),payload_bytes=len(blob),
                  compressed_bytes=size,headroom_bytes=builder.BUDGET-size,
                  changed_bytes=sum(x!=y for x,y in zip(base,result)),
                  allowed_range_relative_to_current_main=[hex(patch.START-patch.BASE),hex(patch.START-patch.BASE+len(blob))],
                  record_words=['sequence','caller_return','parent_return_if_interface_enable','poa_before','upstream_state','pending_request','raw_cp0_count'],
                  records=8,symbols={k:hex(v) for k,v in symbols.items()},
                  limits=['First eight entries retained; no persistent log after reboot.',
                          'Raw CP0 Count wraps; not elapsed milliseconds or calibrated wall time.',
                          'One additional POA read per recorded entry and short interrupt-masked RAM writes affect timing.',
                          'Does not change native PHY writes, driver, UI, authentication or network configuration.',
                          'Not boot-tested; no new flash authorized or performed.'])
    (destination/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (destination/'SHA256SUMS').write_text(''.join(builder.sha(data)+'  '+name+'\n' for name,data in files.items()))
    print(json.dumps({k:manifest[k] for k in ['status','uimage_sha256','payload_bytes','compressed_bytes','headroom_bytes','changed_bytes']},indent=2))

if __name__=='__main__':build()
