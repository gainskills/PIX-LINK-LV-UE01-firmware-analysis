from pathlib import Path
import struct,zlib,lzma,hashlib,re,json,datetime,sys
ROOT=Path(__file__).resolve().parent
# Capstone is installed through requirements.txt.
from capstone import Cs,CS_ARCH_MIPS,CS_MODE_MIPS32,CS_MODE_LITTLE_ENDIAN
b=(ROOT/'flash.bin').read_bytes()
base=0x50000
h=b[base:base+64]
v=struct.unpack('>7I4B32s',h)
h0=bytearray(h);h0[4:8]=bytes(4)
payload=b[base+64:base+64+v[3]]
metadata={'flash_bytes':len(b),'flash_sha256':hashlib.sha256(b).hexdigest(),'uimage_offset':hex(base),'name':v[-1].rstrip(b'\0').decode(),'timestamp_utc':datetime.datetime.fromtimestamp(v[2],datetime.timezone.utc).isoformat(),'payload_bytes':v[3],'load_address':hex(v[4]),'entry_address':hex(v[5]),'os_id':v[7],'architecture_id':v[8],'image_type':v[9],'compression_id':v[10],'header_crc_expected':hex(v[1]),'header_crc_actual':hex(zlib.crc32(h0)),'payload_crc_expected':hex(v[6]),'payload_crc_actual':hex(zlib.crc32(payload))}
(ROOT/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2),flush=True)
if zlib.crc32(payload)!=v[6]:raise RuntimeError('Payload CRC mismatch; image is not verified')
start=0x52480
main=lzma.decompress(b[start:base+64+v[3]],format=lzma.FORMAT_ALONE)
(ROOT/'main-decompressed.bin').write_bytes(main)
print('Decompressed',len(main),'bytes',flush=True)
strings=list(re.finditer(rb'[\x20-\x7e]{6,}',main))
(ROOT/'main-strings.txt').write_text('\n'.join(f'{m.start():08x} {m[0].decode()}' for m in strings)+'\n')
for m in strings:
 if re.search(rb'(?i)ecos|linux version|copyright|mt7628|28k|RPT|sys_upg|profile.bin|os_spi|version|eCos',m[0]): print(hex(m.start()),m[0][:180])
dis=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
dis.skipdata=True
for name,data,addr in [('bootloader',b[:0x20000],0xbc000000),('uimage-loader',payload[0x60:start-base-64],v[4]+0x60),('main',main[:4096],0x80000400)]:
 with (ROOT/f'{name}-disassembly.txt').open('w') as f:
  for ins in dis.disasm(data,addr):f.write(f'{ins.address:08x}: {ins.bytes.hex():8s} {ins.mnemonic} {ins.op_str}\n')
print('Artifacts saved',flush=True)
# Analysis wrapper only: the device stores a raw MIPS image, not this ELF.
main_addr=struct.unpack_from('<I',payload,8)[0]
ehdr=struct.pack('<16sHHIIIIIHHHHHH',b'\x7fELF'+bytes([1,1,1])+bytes(9),2,8,1,main_addr,52,0,0x50001001,52,32,1,40,0,0)
phdr=struct.pack('<IIIIIIII',1,0x1000,main_addr,main_addr,len(main),len(main),7,0x100)
elf=ehdr+phdr
elf+=bytes(0x1000-len(elf))+main
(ROOT/'main-analysis.elf').write_bytes(elf)
print('Analysis ELF entry',hex(main_addr),flush=True)
