import subprocess,time,re,struct,pathlib,sys,threading
ROOT=pathlib.Path(__file__).resolve().parent
size=int(sys.argv[1],0) if len(sys.argv)>1 else 4096
block=min(16384,size)
all_data=bytearray((ROOT/'flash.bin').read_bytes()) if (ROOT/'flash.bin').exists() else bytearray()
start=len(all_data)
with (ROOT/'flash-read.log').open('ab') as log:
 for addr in range(start,size,block):
    count=min(block,size-addr)
    raw=bytearray()
    p=subprocess.Popen(['curl','-sS','--no-buffer','--connect-timeout','5','--max-time','90','telnet://192.168.1.2:23'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    def drain():
        while True:
            part=p.stdout.read1(65536)
            if not part: break
            raw.extend(part)
    t=threading.Thread(target=drain);t.start()
    try:
        for cmd in ['admin','admin',f'spi rd {addr:x} {count}']:
            time.sleep(1)
            p.stdin.write(cmd.encode()+b'\n');p.stdin.flush()
        time.sleep(0.5);p.stdin.close()
        deadline=time.monotonic()+80
        while time.monotonic()<deadline:
            if len(raw)>100 and bytes(raw).rstrip().endswith(b'OS>'): break
            time.sleep(0.1)
    finally:
        p.terminate();p.wait(timeout=5);t.join(timeout=5)
    log.write(f'OFFSET {addr:x}\n'.encode()+raw+b'\n');log.flush()
    payload=bytes(raw).split(b'OS>',1)[-1]
    words=re.findall(rb'(?<![0-9a-zA-Z])[0-9a-fA-F]{8,9}(?![0-9a-zA-Z])',payload)
    data=b''.join(struct.pack('<I',int(w,16) & 0xffffffff) for w in words)
    print(f'Offset 0x{addr:x}: {len(data)} / {count} bytes',flush=True)
    if len(data)!=count or not bytes(raw).rstrip().endswith(b'OS>'):
        raise RuntimeError('Incomplete block; raw log saved')
    all_data.extend(data)
    (ROOT/'flash.bin').write_bytes(all_data)
print('Saved',ROOT/'flash.bin',len(all_data),'bytes',flush=True)
