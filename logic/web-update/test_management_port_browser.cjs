/* Offline regression: a port edit through the active upstream URL must save,
 * verify, reboot on the old origin, and reconnect to the new origin.
 * Device HTTP is mocked; the actual page and controller execute in Chrome. */
const fs = require('node:fs'), assert = require('node:assert/strict');
const {chromium} = require('playwright-core');
(async () => {
  const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  let checks = 0;
  try {
    for (const locale of ['en-US','zh-CN']) {
      for (const scenario of ['upstream','default-http','static','invalid','collision','rejected-import']) {
        const context = await browser.newContext({locale});
        context.setDefaultTimeout(10000);
        const oldPort = scenario === 'default-http' ? '80' : '8765';
        const staticAccess = scenario === 'static';
        const origin = staticAccess ? 'http://192.168.10.1' : 'http://ap.test' + (oldPort === '80' ? '' : ':' + oldPort);
        let profile = require('./scan_fixture.cjs')().replace('SYS_RM_PORT=8765','SYS_RM_PORT=' + oldPort);
        if (staticAccess || scenario === 'collision') profile = profile.replace('LAN_IP=0.0.0.0','LAN_IP=192.168.10.1');
        let submitted = '', reboots = 0;
        await context.addInitScript(() => {
          const nativeTimeout = window.setTimeout;
          window.setTimeout = function(callback, delay, ...args) {
            if (delay === 60000) { window.runManagementRedirect = callback; return 0; }
            return nativeTimeout(callback, delay, ...args);
          };
        });
        await context.route('**/*', async route => {
          const req = route.request(), url = new URL(req.url());
          assert([origin,'http://ap.test:8080'].includes(url.origin),url.origin);
          let body = '', contentType = 'text/html';
          if (['/index.htm','/lan.htm'].includes(url.pathname)) body = fs.readFileSync(__dirname + '/lan.htm');
          else if (url.pathname === '/js/app.js') {
            body = process.env.TEST_MINIFIED ? fs.readFileSync(__dirname + '/settings.min.js') :
              fs.readFileSync(__dirname + '/dashboard.js','utf8') + '\n' + fs.readFileSync(__dirname + '/settings.js','utf8');
            contentType = 'application/javascript';
          } else if (url.pathname === '/profile.bin') body = profile;
          else if (url.pathname === '/status.htm') body = '<td id="drv_chan0">9</td>';
          else if (url.pathname === '/setok.htm') {
            assert.equal(url.origin,origin); assert.equal(req.method(),'POST');
            const raw = req.postDataBuffer().toString();
            submitted = raw.slice(raw.indexOf('#PROFILE'),raw.lastIndexOf('\r\n--'));
            if (scenario !== 'rejected-import') profile = submitted;
          } else if (url.pathname === '/man_reboot.htm') {
            assert.equal(url.origin,origin); assert.equal(req.method(),'POST'); reboots++;
          } else if (url.pathname !== '/favicon.ico') throw Error('Unexpected request ' + url.pathname);
          await route.fulfill({status:200,contentType,body});
        });
        const page = await context.newPage(), errors = [];
        page.on('pageerror',e => errors.push(e.message)); page.on('dialog',d => d.accept());
        await page.goto(origin + '/index.htm');
        await page.waitForFunction(() => !document.querySelector('#apply').disabled);
        await page.locator('#port').fill(scenario === 'invalid' ? '0' : scenario === 'collision' ? '80' : '8080');
        await page.locator('#apply').click();
        if (scenario === 'invalid') {
          assert.equal(await page.locator('#port').evaluate(node => node.checkValidity()),false);
          assert.equal(submitted,''); assert.equal(reboots,0);
          assert.deepEqual(errors,[]); checks++; await context.close(); continue;
        }
        await page.waitForFunction(() => {
          const node=document.querySelector('#status');
          return node.dataset.error === 'true' || typeof window.runManagementRedirect === 'function' ||
            /Restarting|正在重启/.test(node.textContent);
        });
        if (['invalid','collision'].includes(scenario)) {
          assert.equal(submitted,''); assert.equal(reboots,0);
          assert.equal(await page.locator('#status').getAttribute('data-error'),'true');
        } else {
          assert(submitted.includes('SYS_RM_PORT=8080'),`${locale}/${scenario}: no saved port; ${await page.locator('#status').textContent()}`);
          assert(submitted.includes('UNKNOWN_PRESERVE=unchanged&=;value'));
          if (scenario === 'rejected-import') {
            await page.waitForFunction(() => document.querySelector('#status').dataset.error === 'true');
            assert.equal(reboots,0); assert.equal(await page.evaluate(() => typeof window.runManagementRedirect),'undefined');
          } else {
            await page.waitForFunction(() => document.querySelector('#status').dataset.error === 'false');
            for (let n=0;n<50 && reboots===0;n++) await page.waitForTimeout(20);
            assert.equal(reboots,1);
            if (!staticAccess) {
              assert((await page.locator('#status').textContent()).includes('http://ap.test:8080'));
              await page.evaluate(() => window.runManagementRedirect());
              await page.waitForURL('http://ap.test:8080/lan.htm');
              await page.waitForFunction(() => document.querySelector('#port').value === '8080');
            } else assert.equal(page.url(),origin + '/index.htm');
          }
        }
        assert.deepEqual(errors,[]); checks++; await context.close();
      }
    }
    console.log(`PASS: ${checks} EN/ZH management-port save, redirect, static-access, validation and failed-readback cases`);
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode=1; });
