"""Offline feature evidence; never connects to an AP or changes its config."""
from pathlib import Path
import hashlib,json,re,struct,sys
from capstone import Cs,CS_ARCH_MIPS,CS_MODE_MIPS32,CS_MODE_LITTLE_ENDIAN
ROOT=Path(__file__).resolve().parent.parent
b=(ROOT/'main-decompressed.bin').read_bytes();base=0x80000400
keys=['WLN_TxPower','WLN_Channel','WLN_AutoChannelSelect','WLN_HT_BW','WLN_WmmCapable','WLN_APSDCapable','WLN_HT_BSSCoexistence','WLN_BeaconPeriod','WLN_DtimPeriod','WLN_TxBurst','WLN_PktAggregate']
saved={}
for line in (ROOT/'ssid-airplay/longrun/verified-reboot-profile.bin').read_text().splitlines():
 key,sep,value=line.partition('=')
 if sep and key in keys:saved[key]=value
features=[]
for key in keys:
 at=b.index(key.encode()+b'\0');refs=[]
 for m in re.finditer(re.escape(struct.pack('<I',base+at)),b):
  refs.append({'offset':hex(m.start()),'config_id':hex(struct.unpack_from('<I',b,m.start()-4)[0])})
 default=re.search(re.escape(key.encode()+b'=')+rb'([^\n\x00]*)',b)
 features.append({'key':key,'name_offset':hex(at),'config_table_refs':refs,'factory_default':default[1].decode() if default else None,'saved_test_value':saved.get(key)})
d=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
commands=[];disassembly=[]
for key in ['TxPower','AutoChannelSel','HtBw','HtBssCoex','WmmCapable','BeaconPeriod','DtimPeriod']:
 for m in re.finditer(re.escape(key.encode()+b'\0'),b):
  for ref in re.finditer(re.escape(struct.pack('<I',base+m.start())),b):
   f=struct.unpack_from('<I',b,ref.start()+4)[0]
   if not base<f<base+0x160000:continue
   commands.append({'name':key,'table_offset':hex(ref.start()),'function':hex(f)})
   disassembly.append('\n'+key+' '+hex(f))
   for i in d.disasm(b[f-base:f-base+512],f):
    disassembly.append(f'{i.address:08x} {i.mnemonic} {i.op_str}')
report={'scope':'Offline evidence only. Stored profile is historical, not fresh live telemetry. Presence of a setter does not verify RF effect or safe runtime application.','main_sha256':hashlib.sha256(b).hexdigest(),'features':features,'driver_setters':commands}
HERE=Path(__file__).resolve().parent
(HERE/'wireless-feature-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
(HERE/'wireless-feature-disassembly.txt').write_text('\n'.join(disassembly)+'\n')
print(json.dumps(report,indent=2))
