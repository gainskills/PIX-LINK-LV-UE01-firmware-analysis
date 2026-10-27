"""Offline stdio registration/input dispatch. Never opens network or a real UART."""
import json,struct
from pathlib import Path
from emulate_boot_paths import machine,reg,put,get,string,SHA,STACK
from unicorn import UC_HOOK_CODE
ROOT=Path(__file__).resolve().parent
GD=0x803e0000;RET=0x802ff000

def registration():
 u=machine();u.reg_write(reg('k0'),GD);put(u,GD+0x14,0)
 u.reg_write(reg('t9'),0xbc00e464);u.reg_write(reg('ra'),RET)
 records=[]
 def returned(v=0):u.reg_write(reg('v0'),v);u.reg_write(reg('pc'),u.reg_read(reg('ra')))
 def code(uc,a,size,unused):
  if a==0xbc00fec8:
   assert u.reg_read(reg('a0'))==0x34;returned(0x803d0000)
  elif a==0xbc010914:
   p,fill,n=[u.reg_read(reg(x)) for x in ['a0','a1','a2']]
   assert fill==0 and n==0x34;u.mem_write(p&0x1fffffff,bytes(n));returned(p)
  elif a==0xbc00e420:
   p=u.reg_read(reg('a0'));raw=bytes(u.mem_read(p&0x1fffffff,0x34))
   record={'name':raw[8:24].split(b'\0')[0].decode(),'flags':hex(struct.unpack_from('<I',raw)[0]),
           'putc':hex(get(u,p+0x20)),'puts':hex(get(u,p+0x24)),
           'tstc':hex(get(u,p+0x28)),'getc':hex(get(u,p+0x2c))}
   records.append((record,raw));returned()
 u.hook_add(UC_HOOK_CODE,code);u.emu_start(0xbc00e464,RET,timeout=3000000,count=10000)
 assert u.reg_read(reg('pc'))==RET and len(records)==1
 record,raw=records[0]
 assert record=={'name':'serial','flags':'0x80000003','putc':'0xbc01231c','puts':'0xbc0123a8','tstc':'0xbc012370','getc':'0xbc012384'}
 return record,raw

def dispatch(kind,stdio_initialized,raw):
 u=machine();u.reg_write(reg('k0'),GD);put(u,GD+4,2 if stdio_initialized else 0)
 u.mem_write(0x3d1000,raw);put(u,0xbc02e190,0x803d1000)
 entry=0xbc00def4 if kind=='getc' else 0xbc00df34
 target=0xbc012384 if kind=='getc' else 0xbc012370
 u.reg_write(reg('t9'),entry);u.reg_write(reg('ra'),RET)
 invoked=[]
 def code(uc,a,size,unused):
  if a==target:
   invoked.append(hex(a));u.reg_write(reg('v0'),49 if kind=='getc' else 1)
   u.reg_write(reg('pc'),u.reg_read(reg('ra')))
 u.hook_add(UC_HOOK_CODE,code);u.emu_start(entry,RET,timeout=3000000,count=10000)
 assert invoked==[hex(target)] and u.reg_read(reg('pc'))==RET
 return {'function':kind,'stdio_initialized':stdio_initialized,'callback':invoked[0],
         'modeled_return':u.reg_read(reg('v0'))}

if __name__=='__main__':
 record,raw=registration()
 cases=[dispatch(kind,ready,raw) for kind in ['getc','tstc'] for ready in [False,True]]
 result={'status':'PASS: original stdio registration plus four input-dispatch cases',
         'boot_prefix_sha256':SHA,'registration_entry':'0xbc00e464','registered_devices':[record],
         'dispatch_cases':cases,'native_uart_status':'0xb0000c14','native_uart_data':'0xb0000c00',
         'limits':['Device allocation/registration insertion and UART callbacks are intercepted.',
                   'Four dispatch cases seed stdin with the record produced by original registration code.',
                   'No physical UART, pin mapping, electrical levels, network console or recovery tested.',
                   'Known initialization path only; not a proof against all possible dynamic code paths.',
                   'No AP access, UART access, network packets or firmware/configuration changes.']}
 (ROOT/'boot-console-experiment.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'registered_devices':[record['name']],
                   'input_callbacks':'UART in all four modeled dispatch cases','network_console_verified':False},indent=2))
