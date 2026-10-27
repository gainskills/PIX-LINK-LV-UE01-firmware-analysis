/* Offline browser test of the actual combined-image resources. No AP requests. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
const root=path.resolve(__dirname,'..'),out=path.join(root,'phy-diagnostic/combined');
const main=fs.readFileSync(path.join(out,'main-secure-ui-phy.NOT-FLASHABLE.bin'));
const html=fs.readFileSync(path.join(__dirname,'lan.htm')),js=Buffer.concat([fs.readFileSync(path.join(__dirname,'settings.min.js')),Buffer.from('\n')]);
assert(main.subarray(0x1a8d69,0x1a8d69+html.length).equals(html));
assert(main.subarray(0x1ad83c,0x1ad83c+js.length).equals(js));
const fixture=require('./scan_fixture.cjs')();
const status='<script>var _uptime="157";var v_radio_on="1";var ApCliConnStatus="Connected;00:11:22:33:44:55;TEST-UPLINK";</script><table><td id="drv_chan0">9</td><td id="drv_client0">0</td><tr><td><script>_T(pg_upload.firmver);</script></td><td>v28K.RPT.20220716</td></tr><tr><td><script>_T(gnet.macaddr);</script></td><td>02:00:00:00:00:01</td></tr></table>';
(async()=>{
 let browser;const report={browser_path:'Browser plugin unavailable; Playwright Core with local Chrome',mode:'OFFLINE MOCK BACKEND; actual combined-image HTML/JS',checks:[],errors:[],network_requests:[]};
 try{
  browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  for(const locale of ['en-US','zh-CN']){
   const context=await browser.newContext({locale});let scans=0,allow=false,scanFailure=false,posts=0;
   await context.route('**/*',async route=>{
    const r=route.request(),url=new URL(r.url());report.network_requests.push({method:r.method(),path:url.pathname});
    assert.equal(url.origin,'http://ap.test');
    if(r.method()!=='GET'){posts++;await route.abort();return;}
    let body,type='text/html';
    if(url.pathname==='/index.htm')body=html;
    else if(url.pathname==='/js/app.js'){body=js;type='application/javascript';}
    else if(url.pathname==='/profile.bin')body=fixture;
    else if(url.pathname==='/status.htm')body=status;
    else if(url.pathname==='/favicon.ico')body='';
    else if(url.pathname==='/live_get_site_survey.htm'){
     scans++;type='application/json';
     if(scanFailure){await route.fulfill({status:503,body:'Unavailable'});return;}
     body=JSON.stringify({status:'success',list:[{ssid:'SCAN-TEST',channel:6,security:'WPA2PSK',encry:'AES',ExtChan:'NONE'}]});
    }else throw new Error('Unexpected request '+url.pathname);
    await route.fulfill({status:200,contentType:type,body});
   });
   const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
   page.on('dialog',async dialog=>{assert.equal(dialog.type(),'confirm');if(allow)await dialog.accept();else await dialog.dismiss();});
   await page.goto('http://ap.test/index.htm');await page.waitForFunction(()=>!document.querySelector('#apply').disabled);
   await page.locator('#scan-networks').click();assert.equal(scans,0);report.checks.push(locale+': cancel starts no scan');
   allow=true;await page.locator('#scan-networks').click();await page.locator('#networks button').waitFor();
   assert.equal(scans,1);await page.locator('#networks button').click();assert.equal(await page.locator('#upstream-ssid').inputValue(),'SCAN-TEST');
   assert.equal(posts,0);report.checks.push(locale+': accept scans, result selectable, no config POST');
   scanFailure=true;await page.locator('#scan-networks').click();await page.waitForFunction(()=>document.querySelector('#status').dataset.error==='true');
   assert.equal(await page.locator('#scan-networks').isDisabled(),false);report.checks.push(locale+': scan failure reported and retry available');
   await page.locator('#operation-mode').selectOption('0');assert(await page.locator('#scan-networks').isDisabled());report.checks.push(locale+': upstream scan disabled in AP mode');
   await context.close();
  }
  assert.deepEqual(report.errors,[]);report.status='PASS';
 }catch(e){report.status='FAIL';report.error=e.message;process.exitCode=1;}
 finally{if(browser){await browser.close();report.browser_closed=true;}fs.writeFileSync(path.join(out,'scan-browser-results.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));}
})();
