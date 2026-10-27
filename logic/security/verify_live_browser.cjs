// Read-only smoke test on the explicitly authorized upgraded AP.
const {chromium}=require('playwright-core');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
process.umask(0o077);
const root=path.resolve(__dirname,'..');const combined=process.argv.includes('--combined');
const meta=JSON.parse(fs.readFileSync(path.join(root,combined?'deployment/combined-install-attempt.json':'deployment/latest-preflight.json')));
const capture=meta.capture||meta.private_evidence_directory;const raw=fs.readFileSync(path.join(capture,'before-profile.private.bin'),'utf8');
const values=Object.fromEntries(raw.split(/\r?\n/).filter(s=>s.includes('=')).map(s=>{const i=s.indexOf('=');return[s.slice(0,i),s.slice(i+1)];}));
const BASE='http://192.168.1.2:8080';
(async()=>{
 const result={browser_path:'Browser plugin not available; existing Playwright Core and Chrome',base_url:BASE,blocked_mutations:[],page_errors:[],console_errors:[],failed_requests:[]};
 let browser,relay,activeBase=BASE;
 try{
  if(process.argv.includes('--readonly-relay')){
   const previous=path.join(capture,'live-browser-verification.json');
   if(fs.existsSync(previous))fs.copyFileSync(previous,path.join(capture,'live-browser-direct-result.private.json'));
   const {spawnSync}=require('node:child_process');
   relay=require('node:http').createServer((req,res)=>{
    if(!['GET','HEAD'].includes(req.method)||!req.url.startsWith('/')||req.url.startsWith('//')){res.writeHead(405);res.end();return;}
    let config='';
    for(const key of ['cookie','authorization']){
     const value=req.headers[key];
     if(value){if(/[\r\n]/.test(value)){res.writeHead(400);res.end();return;}config+='header = '+JSON.stringify(key+': '+value)+'\n';}
    }
    const response=spawnSync('/usr/bin/curl',['-q','-sS','--noproxy','*','--connect-timeout','3','--max-time','6','--max-filesize','65536','--include','--config','-',BASE+req.url],{input:config,timeout:8000,maxBuffer:200000});
    if(response.status!==0){res.writeHead(502);res.end('Read-only relay could not reach AP');return;}
    const raw=response.stdout;const split=raw.indexOf('\r\n\r\n');
    if(split<0){res.writeHead(502);res.end();return;}
    const header=raw.subarray(0,split).toString('latin1');const body=raw.subarray(split+4);
    const code=Number(header.match(/^HTTP\/\S+\s+(\d+)/)?.[1]||502);
    const type=header.match(/^Content-Type:\s*(.*)$/im)?.[1]?.trim()||'application/octet-stream';
    res.writeHead(code,{'Content-Type':type,'Content-Length':body.length,'Cache-Control':'no-store'});
    res.end(req.method==='HEAD'?undefined:body);
   });
   await new Promise((resolve,reject)=>{relay.once('error',reject);relay.listen(0,'127.0.0.1',resolve);});
   activeBase='http://127.0.0.1:'+relay.address().port;
   result.browser_origin=activeBase;result.readonly_relay=true;result.direct_browser_error=combined?'Direct Chrome access not retried; using read-only relay after earlier direct-access failure.':'net::ERR_ADDRESS_UNREACHABLE; concurrent outside-sandbox curl returned 200';
  }
  browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const context=await browser.newContext({locale:'zh-CN',viewport:{width:1180,height:1000}});
  await context.route('**/*',async route=>{
   const request=route.request();const url=new URL(request.url());
   if(url.origin!==activeBase||!['GET','HEAD'].includes(request.method())){
    result.blocked_mutations.push({method:request.method(),path:url.pathname});await route.abort();
   }else await route.continue();
  });
  const page=await context.newPage();
  page.on('pageerror',e=>result.page_errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')result.console_errors.push(m.text());});
  page.on('requestfailed',r=>result.failed_requests.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText}));
  page.on('dialog',d=>d.dismiss());
  await page.goto(activeBase+'/index.htm',{waitUntil:'networkidle',timeout:20000});
  await page.locator('#ap-login').waitFor();
  result.anonymous_shows_login=true;result.default_locale=await page.locator('html').getAttribute('lang');
  assert.equal(result.default_locale,'zh-CN');
  await page.locator('#login-user').fill(values.SYS_USERS);await page.locator('#login-password').fill(values.SYS_ADMPASS);
  await page.locator('#login-submit').click();
  await page.waitForFunction(()=>document.querySelector('#apply')&&!document.querySelector('#apply').disabled,{},{timeout:25000});
  await page.waitForFunction(()=>document.querySelector('#stat-version')?.textContent.includes('v28K'),{},{timeout:15000});
  result.login_and_profile_loaded=true;result.version=await page.locator('#stat-version').textContent();
  result.uptime_available=!(await page.locator('#stat-uptime').textContent()).match(/Unavailable|不可用|^—$/);
  assert(result.uptime_available);assert.equal(await page.locator('#bandwidth').inputValue(),values.WLN_HT_BW);
  assert.equal(await page.locator('#operation-mode').inputValue(),values.SYS_WLMODE);
  await page.locator('#language').selectOption('en');result.english_switch=await page.locator('html').getAttribute('lang');
  assert.equal(result.english_switch,'en');
  result.desktop_no_overflow=await page.evaluate(()=>document.body.scrollWidth<=innerWidth);assert(result.desktop_no_overflow);
  await page.screenshot({path:path.join(capture,'live-desktop.private.png'),fullPage:false});
  await page.setViewportSize({width:390,height:844});await page.locator('#language').selectOption('zh');
  result.chinese_switch=await page.locator('html').getAttribute('lang');assert.equal(result.chinese_switch,'zh-CN');
  result.mobile_no_overflow=await page.evaluate(()=>document.body.scrollWidth<=innerWidth);assert(result.mobile_no_overflow);
  await page.screenshot({path:path.join(capture,'live-mobile.private.png'),fullPage:false});
  result.title=await page.title();
  assert.equal(result.page_errors.length,0);assert.equal(result.console_errors.length,0);
  assert.equal(result.failed_requests.length,0);assert.equal(result.blocked_mutations.length,0);
  result.status='PASS: live login, profile/status rendering, locale and responsive smoke test';
 }catch(e){result.status='FAIL';result.error=e.message;throw e;}
 finally{if(browser){await browser.close();result.browser_closed=true;}if(relay){relay.closeAllConnections();await new Promise(resolve=>relay.close(resolve));result.relay_closed=true;}fs.writeFileSync(path.join(capture,'live-browser-verification.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));}
})().catch(()=>{process.exitCode=1;});
