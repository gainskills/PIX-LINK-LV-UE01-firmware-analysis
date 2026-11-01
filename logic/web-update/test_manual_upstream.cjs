/* Offline controller regression: no device requests or firmware builds. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
const el=id=>{if(!elements.has(id))elements.set(id,{value:'',style:{},nextElementSibling:{},parentElement:{nextElementSibling:{}},addEventListener(){},replaceChildren(){},appendChild(button){this.button=button;}});return elements.get(id);};
const config=Object.fromEntries(require('./scan_fixture.cjs')().split('\n').filter(s=>s.includes('=')).map(s=>[s.slice(0,s.indexOf('=')),s.slice(s.indexOf('=')+1)]));
let saved,error,scans=0;
const api={el,t:s=>s,config:()=>config,isBusy:()=>false,managementDefaults:()=>({}),guard(){},sync(){},save:r=>saved=r,status:s=>error=s,request(method,url,body,cb){scans++;cb(null,JSON.stringify({status:'success',list:[{ssid:'Scanned',channel:6,security:'WPA2PSK',encry:'AES',ExtChan:'ABOVE'}]}));}};
const context={TextEncoder,window:{addEventListener(){}},document:{createElement:()=>({})},confirm:()=>true};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/dashboard.js','utf8'),context);context.createPanel(api);
el('operation-mode').value='1';
function connect(ssid,auth,cipher,key){saved=null;error=null;el('upstream-ssid').value=ssid;el('upstream-ssid').oninput();el('upstream-security').value=auth;el('upstream-encryption').value=cipher;el('upstream-password').value=key;el('connect-upstream').onclick();}
connect('Hidden network','WPA2PSK','AES','hidden-test-key');
assert(saved,`Manual hidden SSID rejected: ${error}`);
assert.equal(saved.WLN_ApCliSsid,'Hidden network');assert.equal(saved.WLN_ApCliAuthMode,'WPA2PSK');assert.equal(saved.WLN_ApCliEncrypType,'AES');assert.equal(saved.WLN_ApCliWPAPSK,'hidden-test-key');assert.equal(saved.LAN_DHCPD_EN,'0');assert.equal(saved.WLN_APCLI_CONFIGED,'1');assert.equal(saved.WLN_Channel,undefined);assert.equal(scans,0);
connect('Hidden network','WPA2PSK','AES','');assert.equal(error,'keyRequired');assert.equal(saved,null);
connect('Hidden network','WPA2PSK','AES','short');assert.equal(error,'pskInvalid');
connect('Hidden open','OPEN','AES','');assert.equal(saved.WLN_ApCliEncrypType,'NONE');
connect('Hidden WEP','WEP','AES','abcde');assert.equal(saved.WLN_ApCliEncrypType,'WEP');assert.equal(saved.WLN_ApCliKey1Str,'abcde');
connect('Hidden network','keep','AES','');assert.equal(error,'securityUnsupported');
connect('','OPEN','AES','');assert.equal(error,'ssidInvalid');
connect('TEST-UPLINK','WPA2PSK','AES','');assert(saved);assert.equal(saved.WLN_ApCliWPAPSK,undefined);
el('scan-networks').onclick();el('networks').button.onclick();el('upstream-password').value='scan-test-key';el('connect-upstream').onclick();assert.equal(saved.WLN_ApCliSsid,'Scanned');assert.equal(saved.WLN_Channel,'6');assert.equal(saved.WLN_HT_EXTCHA,'1');
config.SYS_WLMODE='0';el('operation-mode').value='1';el('operation-mode').onchange();assert.equal(el('hide-ssid').checked,true);
connect('Hidden network','WPA2PSK','AES','hidden-test-key');assert.equal(saved,null);
console.log('PASS: manual hidden WPA/Open/WEP, key validation, saved key reuse, optional scan channel');
