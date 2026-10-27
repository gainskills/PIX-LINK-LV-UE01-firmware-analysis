"""Offline bootloader branch experiments. All device/network/Flash backends stubbed.

Not a recovery tool; never sends packets or creates firmware images.
"""
import hashlib,json,struct,sys
from pathlib import Path
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE
from unicorn import mips_const as mc
ROOT=Path(__file__).resolve().parent
B=(ROOT.parent/'flash.bin').read_bytes()[:0x30000]
SHA='5830037ccd300009cc51f05e275d450a9d35ce7d6e3a24aecab96ff7e1f7c2c8'
assert hashlib.sha256(B).hexdigest()==SHA
GP=0xbc016a50;STACK=0x802f0000

def reg(n):return getattr(mc,'UC_MIPS_REG_'+n.upper())
def put(u,a,v):u.mem_write(a&0x1fffffff,struct.pack('<I',v&0xffffffff))
def get(u,a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
def string(u,a):return bytes(u.mem_read(a&0x1fffffff,128)).split(b'\0')[0].decode('ascii')
def machine():
 u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
 u.mem_map(0,0x400000);u.mem_map(0x1c000000,0x80000);u.mem_map(0x10000000,4096)
 u.mem_write(0x1c000000,B)
 for n,v in [('sp',STACK),('gp',GP),('s1',0xb0000000),('s3',0xb0000604)]:u.reg_write(reg(n),v)
 put(u,STACK+0x18,GP);put(u,STACK+0x10,GP)
 return u

def select_gpio(high):
 u=machine();put(u,0xb0000624,64 if high else 0);put(u,0xb0000604,0x80)
 selected=[]
 def code(uc,a,size,unused):
  if a in [0xbc002278,0xbc002454]:selected.append('upgrade_branch' if a==0xbc002278 else 'normal_menu');u.emu_stop()
 u.hook_add(UC_HOOK_CODE,code);u.emu_start(0xbc002238,0xbc002b00,timeout=3000000,count=10000)
 assert selected==['normal_menu' if high else 'upgrade_branch']
 return {'gpio_register':'0xb0000624','bit':6,'modeled_input_high':high,'selected':selected[0]}

def upgrade_tail():
 u=machine();calls=[]
 u.reg_write(reg('s4'),0);u.reg_write(reg('s5'),STACK+0x38);u.reg_write(reg('s2'),5)
 put(u,STACK+0x3c,0x802e0000);u.mem_write(0x2e0000,b'80100000\0')
 put(u,0xbc046dcc,718108)
 def returned(v=0):u.reg_write(reg('v0'),v);u.reg_write(reg('pc'),u.reg_read(reg('ra')))
 def code(uc,a,size,unused):
  if a==0xbc00c020:calls.append({'operation':'tftp_command_backend_stub'});returned()
  elif a==0xbc010a20:assert string(u,u.reg_read(reg('a0')))=='80100000';returned(0x80100000)
  elif a==0xbc009488:
   src,dst,length=[u.reg_read(reg(n)) for n in ['a0','a1','a2']]
   assert (src,dst,length)==(0x80100000,0x50000,718108)
   calls.append({'operation':'firmware_write_backend_stub','offset':hex(dst),'length':length});returned()
  elif a==0xbc008db8:
   offset,length=[u.reg_read(reg(n)) for n in ['a0','a1']]
   assert (offset,length)==(0x30000,0x10000)
   calls.append({'operation':'factory_erase_backend_stub','offset':hex(offset),'length':length});returned()
  elif a in [0xbc00dffc,0xbc003f40]:returned()
  elif a==0xbc011394:
   assert string(u,u.reg_read(reg('a1')))=='0x%X'
   target=u.reg_read(reg('a0'))&0x1fffffff
   u.mem_write(target,('0x%X'%u.reg_read(reg('a2'))).encode()+b'\0');returned()
  elif a==0xbc00ad44:
   calls.append({'operation':'bootm_backend_not_executed'});u.emu_stop()
 u.hook_add(UC_HOOK_CODE,code);u.emu_start(0xbc0022ec,0xbc002b00,timeout=3000000,count=10000)
 assert [c['operation'] for c in calls]==['tftp_command_backend_stub','firmware_write_backend_stub','factory_erase_backend_stub','bootm_backend_not_executed']
 return {'entry':'0xbc0022ec','precondition':'Upgrade path after address/default setup; successful backend outputs modeled','calls':calls}

def ram_autostart(dirty):
 u=machine();calls=[]
 for n,v in [('s0',0xbc010000),('s1',0xbc046dcc),('s2',0x802e0000),('s3',0),('s4',0)]:u.reg_write(reg(n),v)
 put(u,0x802e0000,0x80100000);put(u,0xbc046dcc,718108);put(u,0xbc017040,dirty)
 u.mem_write(0x1c045b54,b'OFFLINE-TEST.bin\0')
 def returned(v=0):u.reg_write(reg('v0'),v);u.reg_write(reg('pc'),u.reg_read(reg('ra')))
 def code(uc,a,size,unused):
  if a==0xbc00d674:
   calls.append({'operation':'setenv_stub','key':string(u,u.reg_read(reg('a0'))),'value':string(u,u.reg_read(reg('a1')))});returned()
  elif a==0xbc010300:calls.append({'operation':'environment_save_backend_stub'});returned()
  elif a==0xbc00dffc:returned()
  elif a==0xbc00ad44:calls.append({'operation':'bootm_backend_not_executed'});u.emu_stop()
 u.hook_add(UC_HOOK_CODE,code);u.emu_start(0xbc00c398,0xbc00c450,timeout=3000000,count=10000)
 assert sum(c['operation']=='environment_save_backend_stub' for c in calls)==int(dirty!=0)
 assert calls[-1]['operation']=='bootm_backend_not_executed'
 return {'entry':'0xbc00c398','precondition':'TFTP successful and autostart=yes branch already selected','parameter_change_flag':dirty,'calls':calls}

if __name__=='__main__':
 cases={'gpio_selection':[select_gpio(False),select_gpio(True)],'upgrade_tail':upgrade_tail(),
        'ram_autostart':[ram_autostart(0),ram_autostart(1)]}
 # Same backend is called by saveenv command and conditional TFTP auto-start.
 assert struct.unpack_from('<I',B,GP-0xbc000000+0x2ec)[0]==0xbc010300
 result={'status':'PASS: five original bootloader branch experiments; backends stubbed',
         'boot_prefix_sha256':SHA,'cases':cases,
         'limits':['Not a full bootloader, physical button or hardware test.',
                   'GPIO bit/register selection does not prove which PCB button drives that input.',
                   'TFTP, Flash writes/erase, environment save, printf, conversion and bootm backends are modeled or intercepted.',
                   'Successful upgrade-path outputs are synthetic; failure handling is not validated.',
                   'RAM auto-start experiments begin after the relevant success/yes branch is selected.',
                   'No recovery, UART access, live environment or candidate boot validated.',
                   'No device access, network packets, new firmware images or AP changes.']}
 (ROOT/'boot-path-experiment.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'gpio_low':'upgrade_branch','upgrade_flash_write_and_factory_erase':True,
                   'ram_autostart_can_save_environment':True,'hardware_validated':False},indent=2))
