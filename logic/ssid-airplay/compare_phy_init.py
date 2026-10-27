"""Offline extraction of this image's PHY init; no network/device operations."""
import hashlib,json,re,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BASE=0x80000400
B=(ROOT/'main-decompressed.bin').read_bytes()
REG=[0]*32
PC=0x80015a88
EVENTS=[]
def word(pc):return struct.unpack_from('<I',B,pc-BASE)[0]
def immediate(w):return (w&65535)-65536 if w&32768 else w&65535
def simple(w):
 op=w>>26;rs=w>>21&31;rt=w>>16&31;rd=w>>11&31
 if w==0:return
 if op==9:
  REG[rt]=(REG[rs]+immediate(w))&0xffffffff
 elif op==15:REG[rt]=(w&65535)<<16
 elif op==13:
  REG[rt]=(REG[rs]|(w&65535)) if isinstance(REG[rs],int) else {'value':REG[rs],'or':w&65535}
 elif op==0 and w&63==33:
  REG[rd]=(REG[rs]+REG[rt])&0xffffffff
 elif op==43:pass  # stack save only in this routine
 elif op==35:REG[rt]=0 # epilogue restores, not inputs to PHY writes
 else:raise ValueError('unsupported instruction '+hex(w))
 REG[0]=0

def call(target,site):
 phy,reg,value=REG[4:7]
 if target==0x800159e0:
  EVENTS.append({'site':hex(site),'operation':'write','phy':phy,'reg':reg,'value':value})
 elif target==0x8001593c:
  EVENTS.append({'site':hex(site),'operation':'read','phy':phy,'reg':reg})
  REG[2]={'read_phy':phy,'read_reg':reg}
 else:raise ValueError('unexpected call '+hex(target))

for steps in range(2000):
 w=word(PC);op=w>>26
 if op==3:
  callsite=PC;target=((PC+4)&0xf0000000)|((w&0x3ffffff)<<2)
  simple(word(PC+4));call(target,callsite);PC+=8
 elif op==5:
  rs=w>>21&31;rt=w>>16&31;branch=REG[rs]!=REG[rt]
  dest=PC+4+immediate(w)*4;simple(word(PC+4));PC=dest if branch else PC+8
 elif op==2:
  target=((PC+4)&0xf0000000)|((w&0x3ffffff)<<2)
  simple(word(PC+4));call(target,PC);break
 else:simple(w);PC+=4
 if not 0x80015a88<=PC<0x80015c98:raise ValueError('escaped init')
else:raise ValueError('step budget')
assert len([e for e in EVENTS if e['operation']=='read'])==5
assert len([e for e in EVENTS if e['operation']=='write'])==85
assert {e['phy'] for e in EVENTS}==set(range(5))

report={'binary_sha256':hashlib.sha256(B).hexdigest(),'range':['0x80015a88','0x80015c98'],'events':EVENTS,
 'scope':'Static instructions only; no claim that the init has executed or these are live PHY values.'}
if len(sys.argv)>1:
 source=Path(sys.argv[1]).read_text()
 begin=source.index('} else if (ralink_soc == MT762X_SOC_MT7628AN')
 end=source.index('} else {',begin)
 section=source[begin:end]
 loop=section.index('for (i = 0; i < 5; i++)')
 brace=section.index('{',loop);close=section.index('}',brace)
 def writes(text,i=0):
  return [{'phy':i if p=='i' else int(p),'reg':int(r),'value':int(v,16)} for p,r,v in re.findall(r'rt305x_mii_write\(esw,\s*(i|0),\s*(\d+),\s*(0x[0-9a-fA-F]+)\)',text)]
 ref=writes(section[:loop])
 for i in range(5):ref+=writes(section[brace:close],i)
 ref+=writes(section[close:])
 assert len(ref)==70
 report['reference']={'url':'https://raw.githubusercontent.com/openwrt/openwrt/main/target/linux/ramips/files/drivers/net/ethernet/ralink/esw_rt3050.c','sha256':hashlib.sha256(source.encode()).hexdigest(),'writes':ref,'scope':'MT7628AN/MT7688 reference, not board-matched source for MT7628KN LV-UE01.'}
output=Path(__file__).with_name('phy-init-comparison.json')
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'writes':85,'reads':5,'reference_writes':len(report.get('reference',{}).get('writes',[])),'saved':str(output)},indent=2))
