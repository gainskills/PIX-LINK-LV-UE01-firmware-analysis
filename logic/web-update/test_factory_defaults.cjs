/* Offline rendering of the release's embedded factory defaults; no hardware reset. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
const root=path.resolve(__dirname,'..');
const main=fs.readFileSync(path.join(root,'phy-diagnostic/startup-trace/main-startup-trace.NOT-FLASHABLE.bin'));
const defaults=main.subarray(0x19d000,0x19ecc2).toString('latin1');
const pairs=[...defaults.matchAll(/(?:^|[\n\0])([A-Z][A-Za-z0-9_]+)=([^\r\n\0]{0,1024})(?=[\r\n\0])/g)].map(m=>[m[1],m[2]]);
const config=Object.fromEntries(pairs);
assert.equal(config.SYS_WLMODE,'0');assert.equal(config.WLN_WscConfMode,'0');
const profile='#PROFILE\n#VER_2_1\n'+pairs.map(([k,v])=>k+'='+v).join('\n')+'\n';
const html=fs.readFileSync(path.join(__dirname,'lan.htm')),js=fs.readFileSync(path.join(__dirname,'settings.min.js'));
const status='<script>var _uptime="1";var v_radio_on="1";var ApCliConnStatus="Disconnected";</script><table><td id="drv_chan0">1</td><td id="drv_client0">0</td><tr><td><script>_T(gnet.macaddr);</script></td><td>02:00:00:00:00:01</td></tr></table>';
(async()=>{
 let browser;const report={scope:'OFFLINE factory-default UI rendering; not physical reset or native first-boot verification',checks:[],errors:[],posts:0};
 try{
  browser=await chromium.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  for(const locale of ['en-US','zh-CN']){
   const context=await browser.newContext({locale});
   await context.route('**/*',async route=>{
    const req=route.request(),url=new URL(req.url());assert.equal(url.origin,'http://192.168.10.1');
    if(req.method()!=='GET'){report.posts++;await route.abort();return;}
    if(url.pathname==='/index.htm')await route.fulfill({contentType:'text/html',body:html});
    else if(url.pathname==='/js/app.js')await route.fulfill({contentType:'application/javascript',body:js});
    else if(url.pathname==='/profile.bin')await route.fulfill({body:profile});
    else if(url.pathname==='/status.htm')await route.fulfill({contentType:'text/html',body:status});
    else if(url.pathname==='/favicon.ico')await route.fulfill({body:''});
    else{await route.abort();throw new Error('Unexpected offline request '+url.pathname);}
   });
   const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
   await page.goto('http://192.168.10.1/index.htm');await page.waitForFunction(()=>!document.querySelector('#apply').disabled);
   assert.equal(await page.locator('#operation-mode').inputValue(),'0');
   assert(await page.locator('#dhcp').isChecked());assert(!(await page.locator('#dhcp').isDisabled()));
   assert(!(await page.locator('#wps').isChecked()));assert(!(await page.locator('#hide-ssid').isChecked()));
   assert.equal(await page.locator('#wifi-security').inputValue(),'OPEN');
   assert.equal(await page.locator('#lan-address').inputValue(),'192.168.10.1');
   assert.equal(await page.locator('#port').inputValue(),'8080');
   assert.equal(await page.locator('#language').inputValue(),locale==='zh-CN'?'zh':'en');
   report.checks.push(locale+': embedded AP defaults render; DHCP on, WPS off, visible/open Wi-Fi and expected addresses');
   await page.locator('#operation-mode').selectOption('1');
   assert(!(await page.locator('#dhcp').isChecked()));assert(await page.locator('#dhcp').isDisabled());
   assert.equal(report.posts,0);report.checks.push(locale+': selecting repeater disables DHCP in form; no automatic save/reboot');
   await context.close();
  }
  assert.deepEqual(report.errors,[]);report.status='PASS';
 }catch(e){report.status='FAIL';report.error=e.message;process.exitCode=1;}
 finally{if(browser){await browser.close();report.browser_closed=true;}const out=path.join(root,'phy-diagnostic/startup-trace/factory-browser-results.json');fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));}
})();
