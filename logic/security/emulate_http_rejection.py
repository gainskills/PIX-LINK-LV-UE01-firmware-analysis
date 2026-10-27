"""Native HTTP parsing/rejection exercise, with input buffers and I/O modeled."""
import argparse
import base64
import hashlib
import json
import struct
from pathlib import Path
from test_native_auth import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE, mc


def run(main, wire, split=False, advance_body=False, render_get=False, advance_upload=False, advance_config=False):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0,0x400000); u.mem_write(0x400,main)
    reg=lambda n:getattr(mc,'UC_MIPS_REG_'+n.upper())
    def put(a,v):u.mem_write(a&0x1fffffff,struct.pack('<I',v&0xffffffff))
    def get(a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
    def text(a,s):u.mem_write(a&0x1fffffff,s.encode()+b'\0')
    def returned(v=0):
        u.reg_write(reg('v0'),v&0xffffffff);u.reg_write(reg('pc'),u.reg_read(reg('ra')))
    conn,context,buffer,stack,end=0x80300000,0x80301000,0x80310000,0x803f0000,0x803e0000
    put(conn,5);put(conn+4,0x0101a8c0);put(conn+8,context);put(context+0x10,context+0x100)
    text(0x8025e214,'admin');text(0x8025e224,'admin');put(0x8025e238,100);put(0x801ed300,1)
    u.reg_write(reg('a0'),conn);u.reg_write(reg('sp'),stack);u.reg_write(reg('ra'),end)
    reads=0;used=0;events=[];allocations={};next_alloc=0x80320000;auth_calls=0
    cut=wire.index(b'\r\n\r\n')+24 if split=='body' else 38
    chunks=[wire[:cut],wire[cut:]] if split else [wire]
    def parameters(request):
        at=get(request+0x38);fields={}
        for i in range(256):
            if not at:break
            key=get(at+i*8)
            if not key:break
            name=bytes(u.mem_read(key&0x1fffffff,128)).split(b'\0')[0].decode('ascii')
            if name in ('CMD','CCMD','GO'):
                value=get(at+i*8+4)
                fields[name]=bytes(u.mem_read(value&0x1fffffff,128)).split(b'\0')[0].decode('ascii')
        return fields
    def code(uc,pc,size,data):
        nonlocal reads,used,next_alloc,auth_calls
        if pc==0x8000fb34:
            if reads>=len(chunks):returned(0)
            else:
                part=chunks[reads]
                assert len(part)<=u.reg_read(reg('a2'))
                u.mem_write(u.reg_read(reg('a1'))&0x1fffffff,part)
                reads+=1;returned(len(part))
        elif pc==0x8000eaa4:
            dest,capacity,length,source,count=[u.reg_read(reg(n)) for n in ('a0','a1','a2','a3','t0')]
            part=bytes(u.mem_read(source&0x1fffffff,count));u.mem_write((buffer+used)&0x1fffffff,part+b'\0')
            used+=count;put(dest,buffer);put(capacity,4096);put(length,used);returned(0)
        elif pc==0x80007728:
            key,dest=u.reg_read(reg('a0')),u.reg_read(reg('a1'))
            assert key in (0x01040100,0x010b0200,0x01010200),hex(key)
            if key==0x01040100:put(dest,0)
            else:text(dest,'admin')
            returned()
        elif pc==0x8000e4e0:auth_calls+=1
        elif advance_body and pc in (0x80154370,0x801542c0,0x80154608):
            size=u.reg_read(reg('a1')) if pc==0x80154608 else u.reg_read(reg('a0'))
            if pc==0x80154370:size*=u.reg_read(reg('a1'))
            assert 0<size<0x20000
            ptr=next_alloc;next_alloc+=(size+15)&~15;assert next_alloc<0x803c0000
            u.mem_write(ptr&0x1fffffff,bytes(size))
            if pc==0x80154608:
                old=u.reg_read(reg('a0'));assert old in allocations
                u.mem_write(ptr&0x1fffffff,bytes(u.mem_read(old&0x1fffffff,min(size,allocations[old]))))
            allocations[ptr]=size;returned(ptr)
        elif pc==0x8015d8e0:returned(1000)
        elif pc in (0x801172d0,):returned(context+0x200)
        elif pc in (0x80005028,0x8014fca8):returned()
        elif pc==0x8000f838:events.append({'operation':'error_response','status':u.reg_read(reg('a1'))})
        elif pc in (0x8000ebb8,0x8000f6ac):returned()
        elif pc==0x801544dc:events.append({'operation':'free_model'});returned()
        elif pc==0x8015a494:events.append({'operation':'context_release_model'});returned()
        elif pc==0x800053e4:events.append({'operation':'native_cleanup_entered'})
        elif render_get and pc==0x8000b640:
            events.append({'operation':'protected_profile_handler'});u.emu_stop()
        elif render_get and pc==0x8000f578:
            pointer,length=u.reg_read(reg('a1')),u.reg_read(reg('a2'))
            assert length<100000
            payload=bytes(u.mem_read(pointer&0x1fffffff,length)) if length else b''
            events.append({'operation':'raw_response_model','bytes':length,'sha256':hashlib.sha256(payload).hexdigest()})
            returned(length)
        elif advance_body and pc==0x8000dc10:
            events.append({'operation':'command_dispatch_boundary','fields':parameters(u.reg_read(reg('a0')))})
            if not advance_config:u.emu_stop()
        elif advance_config and pc==0x800089c0:
            pointer,length=u.reg_read(reg('a1')),u.reg_read(reg('a2'))
            assert 0<length<4096
            data=bytes(u.mem_read(pointer&0x1fffffff,length))
            events.append({'operation':'config_importer_not_executed','bytes':length,'sha256':hashlib.sha256(data).hexdigest()})
            u.emu_stop()
        elif advance_config and pc in (0x80007398,0x800082cc,0x80008894,0x80004908):
            raise AssertionError('Unexpected config mutation/event before importer boundary')
        elif advance_body and pc==0x80010e3c:
            events.append({'operation':'upload_staging_boundary','fields':parameters(u.reg_read(reg('sp'))+4)})
            if not advance_upload:u.emu_stop()
        elif advance_upload and pc==0x80006614:
            pointer,length=u.reg_read(reg('a0')),u.reg_read(reg('a1'))
            assert 0<length<=0x1800
            data=bytes(u.mem_read(pointer&0x1fffffff,length))
            events.append({'operation':'flash_writer_not_executed','bytes':length,'sha256':hashlib.sha256(data).hexdigest()})
            u.emu_stop()
        elif advance_body and pc==0x80005b48:pass
        elif pc in (0x80005b48,0x80010e3c,0x80006614,0x80015268,0x80015660):
            events.append({'operation':'body_or_flash_boundary','address':hex(pc)});u.emu_stop()
    u.hook_add(UC_HOOK_CODE,code)
    u.emu_start(0x8000fc4c,end,timeout=3000000,count=300000)
    return dict(returned=u.reg_read(reg('pc'))==end,stack_restored=u.reg_read(reg('sp'))==stack,
                input_reads=reads,events=events,auth_calls=auth_calls)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--main',type=Path,required=True);p.add_argument('--report',type=Path)
    args=p.parse_args();main=args.main.read_bytes();results=[]
    body=b'--fixture\r\nContent-Disposition: form-data; name="CMD"\r\n\r\nSYS_UPG\r\n--fixture\r\nContent-Disposition: form-data; name="files"; filename="fixture.bin"\r\nContent-Type: application/octet-stream\r\n\r\nOFFLINE-NONIMAGE\r\n--fixture--\r\n'
    for target in ('/setok.htm','/login.htm','/js/app.js'):
        for credential in ('missing','wrong','valid'):
            for transport in (('none',) if credential=='missing' else ('header','cookie')):
                for split in (False,True):
                    encoded=base64.b64encode(('admin:'+('admin' if credential=='valid' else 'wrong')).encode()).decode()
                    auth='' if credential=='missing' else ('Authorization: Basic ' if transport=='header' else 'Cookie: Authorization=Basic ')+encoded+'\r\n'
                    wire=(f'POST {target} HTTP/1.0\r\nHost: fixture\r\n{auth}Content-Type: multipart/form-data; boundary=fixture\r\nContent-Length: {len(body)}\r\n\r\n').encode()+body
                    r=run(main,wire,split);r.update(target=target,credential=credential,credential_transport=transport,split_input=split)
                    touched=any(e['operation']=='body_or_flash_boundary' for e in r['events'])
                    if credential=='valid':r['passed']=touched and not any(e.get('status')==401 for e in r['events'])
                    else:r['passed']=r['returned'] and r['stack_restored'] and any(e.get('status')==401 for e in r['events']) and not touched
                    results.append(r)
    if args.report:args.report.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(dict(cases=len(results),passed=sum(r['passed'] for r in results),failures=[r for r in results if not r['passed']])))
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)
