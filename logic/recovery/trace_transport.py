"""One read-only 16-byte query; compare curl network trace and stdout around stdin EOF."""
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
import flash_backup as fb
DEST=fb.ROOT/'private-captures'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-transport-trace')
DEST.mkdir(mode=0o700)
trace=DEST/'curl.trace';fb.private_write(trace,b'')
original=fb.subprocess.Popen

def traced(argv,*args,**kwargs):
    curl=['/usr/bin/curl','-q','-sS','--noproxy','*','--no-buffer','--connect-timeout','3','--max-time','30','--trace-ascii',str(trace),'--trace-time','telnet://192.168.1.2:23']
    return original(curl,*args,**kwargs)
fb.subprocess.Popen=traced
report={'scope':'One spi rd 0 16; no write, reboot or configuration changes','status':'INCOMPLETE'}
try:
    with fb.Session() as s:
        mark=s.send(fb.read_command(0,16))
        try:s.wait(mark,lambda b:b.rstrip().endswith(b'OS>'),4)
        except TimeoutError:pass
        before=bytes(s.buf[mark:]);fb.private_write(DEST/'before-eof.raw',before)
        trace_before=trace.read_bytes();fb.private_write(DEST/'before-eof.trace',trace_before)
        s.p.stdin.close()
        try:s.wait(mark,lambda b:b.rstrip().endswith(b'OS>'),5)
        except TimeoutError:pass
        after=bytes(s.buf[mark:]);fb.private_write(DEST/'after-eof.raw',after)
        trace_after=trace.read_bytes()
        def counts(b):return [int(v) for v in re.findall(rb'<= Recv data, (\d+) bytes',b)]
        report.update(status='OBSERVED',stdout_before_eof=len(before),stdout_after_eof=len(after),complete_before_eof=before.rstrip().endswith(b'OS>'),complete_after_eof=after.rstrip().endswith(b'OS>'),network_read_sizes_before_eof=counts(trace_before),network_read_sizes_after_eof=counts(trace_after))
        if report['complete_after_eof']:report['strict_read_bytes']=len(fb.parse_read(after,16))
except Exception as exc:report.update(status='FAILED',error=f'{type(exc).__name__}: {exc}')
report.update(all_connections_closed=True,private_capture=str(DEST))
fb.private_write(DEST/'manifest.json',(json.dumps(report,indent=2)+'\n').encode())
print(json.dumps(report,indent=2))
