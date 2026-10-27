"""Read-only SPI capture. Private raw files; never writes/erases/resets the AP."""
import argparse,hashlib,json,os,re,struct,subprocess,threading,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def prompt_frame(raw):
    end=raw.find(b'OS>')
    if end<0:raise ValueError('No complete OS prompt')
    return raw[:end+3]

def parse_read(raw,count):
    if count<=0 or count%16:raise ValueError('Expected positive 16-byte-aligned length')
    lines=raw.strip().splitlines()
    if not lines or lines[-1].strip()!=b'OS>':raise ValueError('Missing final OS prompt')
    rows=[]
    for line in lines[:-1]:
        line=line.strip()
        if not line:continue
        if re.fullmatch(rb'spi rd [0-9a-f]+ [0-9]+',line):continue
        if not re.fullmatch(rb'[0-9a-fA-F]{8}(?:[ \t]+[0-9a-fA-F]{8}){3}',line):raise ValueError('Corrupt or unexpected output')
        rows.extend(int(v,16) for v in line.split())
    if len(rows)*4!=count:raise ValueError('Incorrect decoded length')
    return struct.pack('<'+'I'*len(rows),*rows)

def partial_read(raw,count):
    if count<=0 or count%16:raise ValueError('Invalid length')
    lines=[line.strip() for line in raw.strip().splitlines() if line.strip()]
    if not lines or lines.pop()!=b'OS>':raise ValueError('Missing prompt')
    lines=[line for line in lines if not re.fullmatch(rb'spi rd [0-9a-f]+ [0-9]+',line)]
    if len(lines)!=count//16:raise ValueError('Row count mismatch')
    result=[]
    for line in lines:
        if len(line.split()) not in (4,5) or any(not re.fullmatch(rb'[0-9a-fA-F]{1,9}',word) for word in line.split()):raise ValueError('Cannot safely map corrupt row to address')
        try:result.append(parse_read(line+b'\nOS>',16))
        except ValueError:result.append(None)
    return result

def read_command(address,count):
    if address<0 or address%16 or count<=0 or count%16 or count>16384 or address+count>0x200000:raise ValueError('Read outside bounded 2 MiB window or block limit')
    return f'spi rd {address:x} {count}'

def private_write(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:out.write(data)

class ReadTimeout(TimeoutError):
    def __init__(self,partial):
        self.partial=partial
        super().__init__(f'CLI response incomplete ({len(partial)} bytes)')

class Session:
    def __enter__(self):
        self.buf=bytearray();self.cond=threading.Condition()
        self.p=subprocess.Popen(['/usr/bin/nc','-t','-G','3','-w','30','192.168.1.2','23'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        def drain():
            while True:
                data=self.p.stdout.read1(65536)
                if not data:break
                with self.cond:self.buf.extend(data);self.cond.notify_all()
            with self.cond:self.cond.notify_all()
        self.thread=threading.Thread(target=drain,daemon=True);self.thread.start()
        try:
            self.wait(0,lambda b:b'login' in b.lower() or b'username' in b.lower(),5)
            mark=self.send(os.environ.get('AP_DIAG_USER','admin'));self.wait(mark,lambda b:b'password' in b.lower(),5)
            mark=self.send(os.environ.get('AP_DIAG_PASSWORD','admin'));raw=self.wait(mark,lambda b:b'OS>' in b or b'CMD>' in b,5)
            if b'OS>' not in raw:
                mark=self.send('os');self.wait(mark,lambda b:b'OS>' in b,5)
            return self
        except BaseException:self.__exit__();raise
    def send(self,text):
        with self.cond:mark=len(self.buf)
        self.p.stdin.write(text.encode()+b'\n');self.p.stdin.flush();return mark
    def wait(self,mark,done,timeout):
        deadline=time.monotonic()+timeout
        with self.cond:
            while True:
                raw=bytes(self.buf[mark:])
                if done(raw):return raw
                if time.monotonic()>deadline or self.p.poll() is not None:raise ReadTimeout(raw)
                self.cond.wait(.05)
    def read(self,address,count):
        mark=self.send(read_command(address,count))
        return prompt_frame(self.wait(mark,lambda b:b'OS>' in b,15))
    def __exit__(self,*args):
        if self.p.poll() is None:self.p.terminate()
        try:self.p.wait(timeout=2)
        except subprocess.TimeoutExpired:self.p.kill();self.p.wait(timeout=2)
        self.thread.join(timeout=2);self.p.stdin.close();self.p.stdout.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['probe','capture']);ap.add_argument('--start',type=lambda v:int(v,0),default=0);ap.add_argument('--length',type=lambda v:int(v,0),default=0x10000);args=ap.parse_args()
    if args.mode=='capture':
        read_command(args.start,16)
        if args.length<=0 or args.length%16384 or args.length>0x200000 or args.start+args.length>0x200000:ap.error('Capture range must be aligned and <=2 MiB')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest=ROOT/'private-captures'/f'{stamp}-{args.mode}-{args.start:06x}'
    dest.mkdir(parents=True,mode=0o700);dest.parent.chmod(0o700)
    result={'utc':stamp,'mode':args.mode,'status':'INCOMPLETE','commands':[],'records':[],'private_capture':str(dest),'device_operations':'Authenticated CLI navigation and spi rd only'}
    def save():
        path=dest/'manifest.json'
        if not path.exists():private_write(path,b'')
        path.write_text(json.dumps(result,indent=2)+'\n')
    save()
    try:
        addresses=[(0,16),(0x100000,16),(0x1ffff0,16)] if args.mode=='probe' else [(a,min(16384,args.start+args.length-a)) for a in range(args.start,args.start+args.length,16384)]
        pending=[(address,count,copy) for address,count in addresses for copy in range(2)]
        accepted={}
        for attempt in range(3):
            if not pending:break
            result['commands'].extend(read_command(address,count) for address,count,copy in pending);save()
            replies=[]
            deadline=time.monotonic()+180
            for offset in range(0,len(pending),64):
                if time.monotonic()>deadline:raise TimeoutError('Capture pass exceeded 180-second budget')
                batch=pending[offset:offset+64]
                with Session() as session:
                    for address,count,copy in batch:
                        if time.monotonic()>deadline:raise TimeoutError('Capture pass budget exceeded')
                        replies.append(session.read(address,count))
                print(f'Pass {attempt+1}: replies {len(replies)}/{len(pending)}; session closed',flush=True)
            retry=[]
            for (address,count,copy),raw in zip(pending,replies):
                private_write(dest/f'{address:06x}-{copy}-{attempt}.raw',raw)
                try:data=parse_read(raw,count)
                except ValueError:
                    result['records'].append({'address':hex(address),'copy':copy,'attempt':attempt,'accepted':False});retry.append((address,count,copy));continue
                accepted[(address,copy)]=data
            pending=retry;save()
        if pending:raise ValueError('Corrupt console output persisted after three reads')
        complete=bytearray()
        for address,count in addresses:
            first=accepted[(address,0)];second=accepted[(address,1)]
            if first!=second:raise ValueError(f'Repeated reads differ at {address:#x}; refusing verified block')
            complete+=first
            result['records'].append({'address':hex(address),'length':count,'repeated_reads_match':True,'sha256':hashlib.sha256(first).hexdigest()})
        private_write(dest/'verified-data.bin',complete)
        result.update(status='PASS',bytes=len(complete),sha256=hashlib.sha256(complete).hexdigest(),process_exited=True)
        save();print(json.dumps(result,indent=2))
    except BaseException as exc:
        result.update(status='FAILED',error=f'{type(exc).__name__}: {exc}',process_exited=True);save();print(json.dumps({k:result[k] for k in ['status','error','private_capture','process_exited']},indent=2));raise SystemExit(1)
if __name__=='__main__':main()
