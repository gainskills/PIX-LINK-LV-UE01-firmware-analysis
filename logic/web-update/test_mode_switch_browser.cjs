/* Offline AP -> repeater save/readback/reboot checks. Every request is mocked. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
(async()=>{const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});let checks=0;
try{for(const locale of ['en-US','zh-CN'])for(const button of ['#apply']){
const context=await browser.newContext({locale});let profile=require('./scan_fixture.cjs')().replace('SYS_WLMODE=1','SYS_WLMODE=0').replace('LAN_DHCPD_EN=0','LAN_DHCPD_EN=1').replace('WLN_HideSSID=1','WLN_HideSSID=0');let submitted='',reboots=0;
await context.route('**/*',async route=>{const req=route.request(),url=new URL(req.url());assert.equal(url.origin,'http://ap.test');let body='',contentType='text/html';
if(url.pathname==='/index.htm')body=fs.readFileSync(__dirname+'/lan.htm');
else if(url.pathname==='/js/app.js'){body=fs.readFileSync(__dirname+'/settings.min.js');contentType='application/javascript';}
else if(url.pathname==='/profile.bin')body=profile;
else if(url.pathname==='/status.htm')body='<td id="drv_chan0">9</td>';
else if(url.pathname==='/setok.htm'){assert.equal(req.method(),'POST');const raw=req.postDataBuffer().toString();submitted=raw.slice(raw.indexOf('#PROFILE'),raw.lastIndexOf('\r\n--'));assert(submitted.startsWith('#PROFILE'));profile=submitted;}
else if(url.pathname==='/man_reboot.htm'){reboots++;}
else if(url.pathname!=='/favicon.ico')throw Error('Unexpected request '+url.pathname);
await route.fulfill({status:200,contentType,body});});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
await page.goto('http://ap.test/index.htm');await page.waitForFunction(()=>!document.querySelector('#apply').disabled);
await page.locator('#operation-mode').selectOption('1');assert(await page.locator('#hide-ssid').isChecked());assert(!(await page.locator('#dhcp').isChecked()));assert(await page.locator('#connect-upstream').isDisabled());assert((await page.locator('#connect-upstream + small').textContent()).includes(locale==='zh-CN'?'保存并重启':'Save & restart'));
await page.locator('#upstream-ssid').fill('Hidden test');await page.locator('#upstream-security').selectOption('WPA2PSK');await page.locator('#upstream-encryption').selectOption('AES');await page.locator('#upstream-password').fill('not-a-real-key');
await page.locator(button).click();await page.waitForFunction(()=>document.querySelector('#status').textContent.toLowerCase().includes('restart')||document.querySelector('#status').textContent.includes('重启'));
for(let n=0;n<50&&reboots===0;n++)await page.waitForTimeout(20);
assert.equal(reboots,1);for(const line of ['SYS_WLMODE=1','LAN_DHCPD_EN=0','WLN_APCLI_CONFIGED=1','WLN_HideSSID=1;0;0;0','WLN_WscConfMode=0','WLN_ApCliEnable=1','WLN_ApCliSsid=Hidden test','SYS_RM_EN=1','LAN_IP_MODE=1'])assert(submitted.split(/\r?\n/).includes(line),line);assert.deepEqual(errors,[]);checks++;await context.close();
}console.log(`PASS: ${checks} EN/ZH AP-to-repeater connect/full-save cases, flag append, readback and reboot`);
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
