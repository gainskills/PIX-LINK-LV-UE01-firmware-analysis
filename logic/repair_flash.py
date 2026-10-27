import pathlib,re,struct,subprocess,threading,time,zlib,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
raw=(ROOT/'flash-read.log').read_bytes()
parts=re.split(rb'OFFSET ([0-9a-f]+)\n',raw)
addresses=[]
for j in range(1,len(parts),2):
 base=int(parts[j],16)
 payload=parts[j+1].split(b'OS>',1)[-1]
 words=re.findall(rb'(?<![0-9a-zA-Z])[0-9a-fA-F]{8,9}(?![0-9a-zA-Z])',payload)
 addresses.extend((base+i*4)&~15 for i,w in enumerate(words) if len(w)>8)
addresses=sorted(set(addresses))
print('Repair ranges:',len(addresses),flush=True)
image=bytearray((ROOT/'flash.bin').read_bytes())
(ROOT/'flash-unrepaired.bin').write_bytes(image)
for attempt in range(3):
 if not addresses: break
 raw=bytearray()
 p=subprocess.Popen(['curl','-sS','--no-buffer','--connect-timeout','5','--max-time','180','telnet://192.168.1.2:23'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def drain():
  while True:
   part=p.stdout.read1(65536)
   if not part: break
   raw.extend(part)
 t=threading.Thread(target=drain);t.start()
 try:
  for cmd in ['admin','admin']:
   time.sleep(1);p.stdin.write(cmd.encode()+b'\n');p.stdin.flush()
  for addr in addresses:
   time.sleep(0.15)
   p.stdin.write(f'spi rd {addr:x} 16\n'.encode());p.stdin.flush()
  time.sleep(1);p.stdin.close()
  deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   if bytes(raw).count(b'OS>')>=len(addresses)+1: break
   time.sleep(0.2)
 finally:
  p.terminate();p.wait(timeout=5);t.join(timeout=5)
 (ROOT/f'flash-repair-{attempt}.log').write_bytes(raw)
 replies=bytes(raw).split(b'OS>')[1:]
 completed=replies[:-1]
 print('Replies:',len(completed),'expected:',len(addresses),flush=True)
 if len(completed)!=len(addresses):
  raise RuntimeError('Reply count mismatch; refusing to patch')
 pending=[]
 for addr,payload in zip(addresses,completed):
  words=re.findall(rb'(?<![0-9a-zA-Z])[0-9a-fA-F]{8,9}(?![0-9a-zA-Z])',payload)
  if len(words)!=4 or any(len(w)!=8 for w in words):
   pending.append(addr);continue
  image[addr:addr+16]=b''.join(struct.pack('<I',int(w,16)) for w in words)
 addresses=pending
 print('Remaining suspect ranges:',len(addresses),flush=True)
 (ROOT/'flash.bin').write_bytes(image)
if addresses: raise RuntimeError('Unresolved corrupted output')
h=image[0x50000:0x50040];v=struct.unpack('>7I4B32s',h)
payload=image[0x50040:0x50040+v[3]]
print('Image size:',len(image),'payload:',len(payload))
print('Payload CRC actual:',hex(zlib.crc32(payload)),'expected:',hex(v[6]),flush=True)
print('SHA256:',hashlib.sha256(image).hexdigest(),flush=True)
(ROOT/'uimage.bin').write_bytes(image[0x50000:0x50040+v[3]])
(ROOT/'uimage-payload.bin').write_bytes(payload)
