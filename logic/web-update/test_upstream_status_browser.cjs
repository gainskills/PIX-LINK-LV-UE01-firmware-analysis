/* Offline browser contract for upstream state and System-form layout. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
const html=fs.readFileSync(__dirname+'/lan.htm'),js=fs.readFileSync(__dirname+'/settings.min.js');
assert(html.length<=10552,'Dashboard exceeds fixed canonical resource');
const profile=require('./scan_fixture.cjs')();
const labels={
  'en-US':{connected:'Connected',disconnected:'Disconnected',unavailable:'Unavailable',connecting:'Connecting'},
  'zh-CN':{connected:'已连接',disconnected:'未连接',unavailable:'暂不可用',connecting:'连接中'}
};
function status(connection){
  return '<script>var _uptime="1";var v_radio_on="1";var ApCliConnStatus="'+connection+'";</script>'+
    '<table><td id="drv_chan0">6</td><td id="drv_client0">0</td></table>';
}
(async()=>{
  let browser;
  try{
    browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
    for(const locale of Object.keys(labels))for(const scenario of [
      {name:'connected',body:status('Connected;00:11:22:33:44:55;TEST-UPLINK')},
      {name:'connected',body:status('2')},
      {name:'disconnected',body:status('0')},
      {name:'connecting',body:status('1')},
      {name:'unavailable',body:status('')},
      {name:'unavailable',body:status('3')},
      {name:'unavailable',body:'<html>not a status page</html>'}
    ]){
      const context=await browser.newContext({locale});
      await context.route('**/*',async route=>{
        const request=route.request(),url=new URL(request.url());
        assert.equal(request.method(),'GET');assert.equal(url.origin,'http://ap.test');
        if(url.pathname==='/index.htm')return route.fulfill({contentType:'text/html',body:html});
        if(url.pathname==='/js/app.js')return route.fulfill({contentType:'application/javascript',body:js});
        if(url.pathname==='/profile.bin')return route.fulfill({body:profile});
        if(url.pathname==='/status.htm')return route.fulfill({contentType:'text/html',body:scenario.body});
        if(url.pathname==='/favicon.ico')return route.fulfill({body:''});
        throw new Error('Unexpected request '+url.pathname);
      });
      const page=await context.newPage();
      await page.goto('http://ap.test/index.htm');
      await page.waitForFunction(()=>!document.querySelector('#apply').disabled);
      assert.equal(await page.locator('#stat-uplink').count(),1);
      await page.waitForFunction(()=>document.querySelector('#stat-uplink').textContent.length>0);
      assert.equal(await page.locator('#stat-uplink').textContent(),labels[locale][scenario.name]);
      assert.equal(await page.locator('[data-t="wpsNote"]').count(),0);
      assert.deepEqual(await page.locator('#tools input[type="file"]').evaluateAll(elements=>elements.map(e=>[getComputedStyle(e).marginTop,getComputedStyle(e).marginBottom])),[['8px','16px'],['8px','16px']]);
      assert.equal(await page.locator('#account-user').evaluate(e=>getComputedStyle(e.parentElement).marginTop),'16px');
      assert.equal(await page.locator('#account-confirm').evaluate(e=>getComputedStyle(e.parentElement).marginBottom),'16px');
      await context.close();
    }
    console.log('PASS: EN/ZH overview upstream states and System-form spacing');
  }finally{if(browser)await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
