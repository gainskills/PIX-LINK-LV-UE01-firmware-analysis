from pathlib import Path
import subprocess,time,re,json
ROOT=Path(__file__).resolve().parent/'local-captures/ssid-raw-test';ROOT.mkdir(exist_ok=True)
events=[]
def run(path,label,value=None):
 cmd=['curl','-sS','--interface','192.168.10.2','--connect-timeout','3','--max-time','8','-o',str(ROOT/(label+'.htm')),'-w','%{http_code}']
 if value is not None:cmd+=['--data',f'CMD=Wl_Basic&GO=wl_basic.htm&SET0=70648064={value}']
 cmd+=['http://192.168.10.1/'+path]
 r=subprocess.run(cmd,capture_output=True,text=True)
 event={'time':time.time(),'label':label,'http':r.stdout,'exit':r.returncode,'error':r.stderr.strip()}
 p=ROOT/(label+'.htm')
 if r.returncode==0 and p.exists():
  s=p.read_text(errors='replace')
  for key in ['c_bssid_num','c_radio_on','WlMode']:
   m=re.search(r"addCfg\('"+key+r"',([^,]+),'([^']*)'\)",s)
   if m:event[key]=m[2]
  m=re.search(r'var apcli_connect_status="([^"\n]*)"',s)
  if m:event['apcli_connect_status']=m[1]
 events.append(event);(ROOT/'events.json').write_text(json.dumps(events,indent=2)+'\n');print(json.dumps(event),flush=True)
 return event
before=run('wl_basic.htm','before');assert before.get('c_bssid_num')=='1'
try:
 run('wl_basic.htm','apply-raw-zero',0)
 for i in range(1,4):
  time.sleep(5);run('wl_basic.htm',f'during-{i}');run('',f'index-{i}')
finally:
 run('wl_basic.htm','restore-raw-one',1)
 for i in range(1,4):
  time.sleep(5);state=run('wl_basic.htm',f'after-{i}');run('',f'index-after-{i}')
  if state.get('c_bssid_num')=='1':break
 else:raise RuntimeError('Restoration not confirmed')
