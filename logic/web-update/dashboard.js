/* New UI only. The existing status response is parsed as inert text, never executed. */
function createPanel(api) {
  'use strict';
  var el = api.el, t = api.t, telemetry = null, deviceMac = '', selectedNetwork = null, nameEdited=false, useAutoName=false;
  var encoder = new TextEncoder();
  function safeText(s) { return typeof s === 'string' && !/[\x00-\x1f\x7f]/.test(s); }
  function validSSID(s) { return safeText(s) && encoder.encode(s).length > 0 && encoder.encode(s).length <= 32; }
  function psk(s) { var size = encoder.encode(s).length; return safeText(s) && ((size >= 8 && size <= 63) || /^[a-f0-9]{64}$/i.test(s)); }
  function fail(key) { throw new Error(key); }
  function first(value) { return (value || '').split(';')[0]; }
  function primary(value, replacement) { var values = value.split(';'); values[0] = replacement; return values.join(';'); }
  function isWPA(auth) { return ['WPAPSK','WPA2PSK','WPAPSKWPA2PSK'].includes(auth); }
  function securityMode(auth,cipher) { return cipher==='WEP' && ['OPEN','SHARED','WEPAUTO'].includes(auth) ? 'WEP' : auth==='OPEN'&&cipher==='NONE' ? 'OPEN' : isWPA(auth)&&['AES','TKIP','TKIPAES'].includes(cipher) ? auth : 'keep'; }
  function wepType(key) { return /^(?:[a-f0-9]{10}|[a-f0-9]{26})$/i.test(key) ? '0' : /^(?:[\x20-\x7e]{5}|[\x20-\x7e]{13})$/.test(key) ? '1' : null; }
  function sizeNames() { ['ext-ssid','upstream-ssid'].forEach(function(id){var e=el(id);if(e.clientWidth){e.style.height='auto';e.style.height=(e.scrollHeight+2)+'px';}}); }
  function securityFields(prefix,auth,cipher) {
    el(prefix+'-security').value=securityMode(auth,cipher);
    el(prefix+'-encryption').value=['AES','TKIP','TKIPAES'].includes(cipher)?cipher:'AES';
  }
  function securityChanges(result,prefix,newNetwork) {
    var c=api.config(),local=prefix==='wifi',key=el(prefix+'-password').value;
    var oldAuth=local?first(c.WLN_AuthMode):c.WLN_ApCliAuthMode,oldCipher=local?first(c.WLN_EncrypType):c.WLN_ApCliEncrypType;
    var oldMode=securityMode(oldAuth,oldCipher),auth=el(prefix+'-security').value,cipher=el(prefix+'-encryption').value;
    if(auth==='keep'){if(key||newNetwork)fail('securityUnsupported');return;}
    if(isWPA(auth)){
      if(!['AES','TKIP','TKIPAES'].includes(cipher))fail('securityUnsupported');
      if(key&&!psk(key))fail('pskInvalid');
      if(!key&&(newNetwork||!isWPA(oldAuth)))fail('keyRequired');
      if(key)result[local?'WLN_WPAPSK1':'WLN_ApCliWPAPSK']=key;
    }else if(auth==='WEP'){
      cipher='WEP';
      if(key){var type=wepType(key);if(type===null)fail('wepInvalid');
        result[local?'WLN_Key1Str1':'WLN_ApCliKey1Str']=key;
        result[local?'WLN_Key1Type':'WLN_ApCliKey1Type']=local?primary(c.WLN_Key1Type||'1',type):type;
        result[local?'WLN_DefaultKeyID':'WLN_ApCliDefaultKeyID']=local?primary(c.WLN_DefaultKeyID||'1','1'):'1';
      }else if(newNetwork||oldMode!=='WEP')fail('keyRequired');
      auth=oldMode==='WEP'?oldAuth:'OPEN';
    }else if(auth==='OPEN')cipher='NONE';else fail('securityUnsupported');
    result[local?'WLN_AuthMode':'WLN_ApCliAuthMode']=local?primary(c.WLN_AuthMode,auth):auth;
    result[local?'WLN_EncrypType':'WLN_ApCliEncrypType']=local?primary(c.WLN_EncrypType,cipher):cipher;
    if(local&&(auth!==oldAuth||cipher!==oldCipher||key)){
      if(isWPA(auth)&&c.WLN_DefaultKeyID!==undefined)result.WLN_DefaultKeyID=primary(c.WLN_DefaultKeyID,'2');
      if(isWPA(auth)&&key&&c.WLN_WscNewKey!==undefined)result.WLN_WscNewKey=key;
      if(c.WLN_IEEE8021X!==undefined)result.WLN_IEEE8021X=primary(c.WLN_IEEE8021X,'0');
      var wsc={WLN_WscAuthType:cipher==='WEP'?'2':({OPEN:'1',WPAPSK:'2',WPA2PSK:'32',WPAPSKWPA2PSK:'34'})[auth],WLN_WscEncrypType:({NONE:'1',WEP:'2',TKIP:'4',AES:'8',TKIPAES:'12'})[cipher],WLN_WscConfStatus:'2'};
      Object.keys(wsc).forEach(function(k){if(c[k]!==undefined)result[k]=wsc[k];});
    }
  }
  function mode() { return el('operation-mode').value; }
  function decode(value) {
    return value.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos);/gi, function (all, entity) {
      var named = {amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"};
      if (entity[0] !== '#') return named[entity.toLowerCase()] || all;
      var n = entity[1].toLowerCase() === 'x' ? parseInt(entity.slice(2), 16) : Number(entity.slice(1));
      return n > 0 && n <= 0x10ffff && !(n >= 0xd800 && n <= 0xdfff) ? String.fromCodePoint(n) : all;
    });
  }
  function readCell(text, id) {
    var match = new RegExp('<td\\b[^>]*\\bid=["\']' + id + '["\'][^>]*>([^]*?)<\\/td>', 'i').exec(text);
    return match && !/<script\b/i.test(match[1]) ? decode(match[1].replace(/<[^>]*>/g, '')).trim() : '';
  }
  function readLabel(text, label) {
    var match = new RegExp('\\b' + label.replace(/\./g, '\\.') + '\\b[^]*?<\\/td>\\s*<td\\b[^>]*>\\s*([^<]*)<\\/td>', 'i').exec(text);
    return match ? decode(match[1]).trim() : '';
  }
  function numberCell(text, id, max) { var v = readCell(text, id); return /^\d+$/.test(v) && +v <= max ? v : ''; }
  function parseStatus(text) {
    if (text.length > 65536 || !/\bid=["']drv_chan0["']/i.test(text)) fail('telemetryUnavailable');
    var uptime = /\bvar\s+_uptime\s*=\s*["'](\d+)["']/.exec(text);
    var radio = /\bvar\s+v_radio_on\s*=\s*["']([01])["']/.exec(text);
    var association = /\bvar\s+ApCliConnStatus\s*=\s*["']([^"']*)["']/.exec(text);
    var state=association ? association[1].split(';')[0] : '';
    var connection=state==='2'||state==='Connected'?'Connected':state==='1'?'Connecting':state==='0'||state==='Disconnected'?'Disconnected':'';
    var mac = readLabel(text, 'gnet.macaddr').replace(/[:-]/g, '').toUpperCase();
    if (!/^[0-9A-F]{12}$/.test(mac) || /^0{12}$/.test(mac) || parseInt(mac.slice(0,2),16) % 2) mac = '';
    var firmware = readLabel(text, 'pg_upload.firmver');
    return {channel:numberCell(text,'drv_chan0',14),clients:numberCell(text,'drv_client0',4096),
      uptime:uptime ? uptime[1] : '', radio:radio ? radio[1] : '',
      connect:readCell(text,'drv_ssid1'), connection:connection,
      version:/^[A-Za-z0-9._-]{1,64}$/.test(firmware) ? firmware : '', mac:mac};
  }
  function defaultName() {
    if (!deviceMac) return '';
    var source = el('upstream-ssid').value;
    if (!validSSID(source)) return '';
    var prefix = '', count = 0;
    for (var char of source) {
      var bytes = encoder.encode(char).length;
      if (count + bytes > 19) break;
      prefix += char; count += bytes;
    }
    return prefix + '_' + deviceMac;
  }
  function naming() {
    var generated = defaultName();
    if(generated && !nameEdited && (useAutoName || el('ext-ssid').value===generated)){useAutoName=true;el('ext-ssid').value=generated;}
    el('ssid-default').disabled = api.isBusy() || !generated;
    el('ssid-note').textContent = generated ? t('defaultNote') + generated : t('defaultUnavailable');sizeNames();
  }
  function stats() {
    var config = api.config(), data = telemetry || {};
    function set(id, value) { el('stat-' + id).textContent = value || t('unavailable'); }
    set('mode', config.SYS_WLMODE === '1' ? t('repeater') : 'AP');
    set('channel', data.channel); set('clients', data.clients); set('version', data.version);
    set('uptime', data.uptime ? data.uptime + ' s' : ''); set('mac', data.mac ? data.mac.match(/../g).join(':') : '');
    var uplink=config.SYS_WLMODE!=='1'?t('notApplicable'):data.connection?t(data.connection==='Connected'?'connected':data.connection==='Connecting'?'connecting':'disconnected'):t('unavailable');
    set('uplink',uplink);el('uplink-state').textContent=uplink;
    el('telemetry-note').textContent = telemetry ? '' : t('telemetryUnavailable');
    naming();
  }
  function loadStatus() {
    el('refresh-status').disabled = true;
    api.request('GET','status.htm?ts=' + Date.now(),null,function(error,text) {
      telemetry = null; deviceMac = '';
      if (!error) { try { telemetry = parseStatus(text); deviceMac = telemetry.mac; } catch (_) {} }
      stats(); el('refresh-status').disabled = false;
    });
  }
  function sync() {
    var repeater = mode() === '1';
    ['upstream-ssid','upstream-password','upstream-security','upstream-encryption','scan-networks'].forEach(function(id){el(id).disabled = api.isBusy() || !repeater;});
    el('channel').disabled = api.isBusy() || repeater;
    el('channel-row').hidden=repeater;
    var modeChanged=mode()!==api.config().SYS_WLMODE;
    el('connect-upstream').disabled=api.isBusy()||!repeater||modeChanged;
    el('connect-upstream').nextElementSibling.textContent=t(modeChanged?'modeSaveNote':'connectNote');
    el('channel-note').textContent = t(repeater ? 'followUpstream' : 'channelNote');
    ['wifi','upstream'].forEach(function(prefix){
      var value=el(prefix+'-security').value,locked=api.isBusy()||(prefix==='upstream'&&!repeater);
      el(prefix+'-cipher-row').hidden=!isWPA(value);
      el(prefix+'-encryption').disabled=locked||!isWPA(value);
      el(prefix+'-password').disabled=locked||value==='OPEN';
      var note=el(prefix+'-password').parentElement.nextElementSibling;
      note.textContent=t(value==='WEP'?'wepNote':prefix==='wifi'?'passwordNote':'upstreamPasswordNote');
    });
    naming();
  }
  function channels(config) {
    var region = Number(config.WLN_CountryRegion), ranges = [[1,11],[1,13],[10,11],[10,13],[14,14],[1,14],[3,9],[5,13]];
    var range = ranges[region] || [Number(config.WLN_Channel),Number(config.WLN_Channel)];
    if (config.WLN_CountryCode === 'US') range = [Math.max(1,range[0]),Math.min(11,range[1])];
    var selected = config.WLN_AutoChannelSelect !== '0' ? '0' : config.WLN_Channel;
    el('channel').replaceChildren(new Option(t('auto'), '0'));
    for (var i=range[0]; i<=range[1] && i<=14; i++) if(i>0) el('channel').add(new Option(String(i),String(i)));
    if (!Array.from(el('channel').options).some(function(o){return o.value===selected;})) el('channel').add(new Option(selected,selected));
    el('channel').value = selected;
  }
  function render() {
    var config = api.config(); selectedNetwork = null;
    el('operation-mode').value = config.SYS_WLMODE;
    nameEdited=false;useAutoName=!config.WLN_SSID1 || config.WLN_SSID1===config.WLN_ApCliSsid+'_Ext' || config.WLN_SSID1===config.WLN_ApCliSsid+'_EXT';
    el('ext-ssid').value = config.WLN_SSID1;
    el('upstream-ssid').value = config.WLN_ApCliSsid;
    el('wifi-password').value = el('upstream-password').value = '';
    securityFields('wifi',first(config.WLN_AuthMode),first(config.WLN_EncrypType));
    securityFields('upstream',config.WLN_ApCliAuthMode,config.WLN_ApCliEncrypType);
    el('tx-power').value = config.WLN_TxPower; el('bandwidth').value = config.WLN_HT_BW;
    el('account-user').value = config.SYS_USERS || '';
    el('account-password').value = el('account-confirm').value = '';
    channels(config); stats(); sync();
  }
  function changed() {
    var config = api.config(), result = {}, repeater = mode() === '1';
    var name = el('ext-ssid').value, power = Number(el('tx-power').value), width = el('bandwidth').value;
    if (!validSSID(name)) fail('ssidInvalid');
    if (!Number.isInteger(power) || power<1 || power>100) fail('powerInvalid');
    if (!/^[01]$/.test(width)) fail('widthInvalid');
    result.WLN_SSID1 = name; result.WLN_TxPower = String(power); result.WLN_HT_BW = width;
    result.SYS_WLMODE = mode(); result.WLN_ApCliEnable = repeater ? '1' : '0';
    securityChanges(result,'wifi',false);
    if (!repeater) {
      var channel = Number(el('channel').value);
      if (!Number.isInteger(channel) || channel<0 || channel>14) fail('channelInvalid');
      result.WLN_Channel = String(channel); result.WLN_AutoChannelSelect = channel ? '0' : '3';
      if (channel) result.WLN_HT_EXTCHA = channel<7 ? '1' : '0';
    } else {
      Object.assign(result,uplinkChanges());
    }
    return result;
  }
  function uplinkChanges() {
    var config=api.config(), result={SYS_WLMODE:'1',WLN_ApCliEnable:'1',LAN_DHCPD_EN:'0',WLN_APCLI_CONFIGED:'1'};
      if(config.SYS_WLMODE!=='1'){
        result.WLN_HideSSID=primary(config.WLN_HideSSID,el('hide-ssid').checked?'1':'0');
        result.WLN_WscConfMode='0';
      }
      var ssid = el('upstream-ssid').value;
      if (!validSSID(ssid)) fail('ssidInvalid');
      var newUplink = ssid !== config.WLN_ApCliSsid || config.SYS_WLMODE !== '1';
      securityChanges(result,'upstream',newUplink);
      result.WLN_ApCliSsid = ssid;
      if (selectedNetwork && selectedNetwork.ssid === ssid) {
        result.WLN_Channel = String(selectedNetwork.channel); result.WLN_AutoChannelSelect = '0';
        result.WLN_HT_EXTCHA = selectedNetwork.ExtChan === 'ABOVE' ? '1' : '0';
      }
    return result;
  }
  el('connect-upstream').onclick=function(){
    if(api.isBusy()||mode()!=='1'||mode()!==api.config().SYS_WLMODE)return;
    try{
      var desired=Object.assign(uplinkChanges(),api.managementDefaults(api.config()));
      api.guard(Object.assign({},api.config(),desired));
      if(confirm(t('connectConfirm')))api.save(desired,{uplink:true});
    }catch(error){api.status(error.message,true);}
  };
  function crc32(bytes) {
    var crc = 0xffffffff;
    for (var i=0;i<bytes.length;i++) { crc ^= bytes[i]; for(var bit=0;bit<8;bit++) crc = (crc>>>1) ^ (crc&1 ? 0xedb88320 : 0); }
    return (crc ^ 0xffffffff) >>> 0;
  }
  function credentialCookie(user,pass) { document.cookie = 'Authorization=Basic ' + btoa(user+':'+pass) + ';path=/;SameSite=Lax'; }
  el('sign-out').onclick=function(){if(api.isBusy())return;document.cookie='Authorization=;path=/;max-age=0';location.assign('login.htm');};
  el('operation-mode').onchange = function(){el('dhcp').checked=mode()==='0';if(mode()!==api.config().SYS_WLMODE){el('hide-ssid').checked=mode()==='1';el('wps').checked=false;}api.sync();sync();};
  el('upstream-ssid').oninput = function(){selectedNetwork=null;naming();};
  el('ext-ssid').oninput=function(){nameEdited=true;useAutoName=false;sizeNames();};
  ['wifi-security','upstream-security'].forEach(function(id){el(id).onchange=sync;});
  ['ext-ssid','upstream-ssid'].forEach(function(id){el(id).onkeydown=function(e){if(e.key==='Enter')e.preventDefault();};});
  window.addEventListener('resize',sizeNames);
  ['radio-settings','uplink-settings'].forEach(function(id){el(id).addEventListener('toggle',sizeNames);});
  el('ssid-default').onclick = function(){nameEdited=false;useAutoName=true;naming();};
  el('refresh-status').onclick = loadStatus;
  el('reload-settings').onclick = function(){
    if(api.isBusy()) return;
    api.reload();
  };
  el('scan-networks').onclick = function(){
    if(api.isBusy() || !confirm(t('scanConfirm')))return;
    el('scan-networks').disabled=true;api.status('scanning');
    api.request('GET','live_get_site_survey.htm?ts='+Date.now(),null,function(error,text){
      el('scan-networks').disabled=false;el('networks').replaceChildren();
      try{
        if(error)fail('scanFailed');var data=JSON.parse(text);
        if(data.status!=='success'||!Array.isArray(data.list))fail('scanFailed');
        data.list.slice(0,64).forEach(function(network){
          if(typeof network.security!=='string'||!validSSID(network.ssid)||!Number.isInteger(Number(network.channel))||+network.channel<1||+network.channel>14)return;
          var button=document.createElement('button');button.type='button';button.className='secondary';
          button.textContent=network.ssid+' · '+network.channel+' · '+network.security;
          var raw=network.security.toUpperCase(),cipher=String(network.encry||'').toUpperCase().replace(/[+\/ -]/g,''),auth;
          if(raw.includes('WEP')){auth='OPEN';cipher='WEP';}
          else if(raw==='NONE'||raw==='OPEN'){auth='OPEN';cipher='NONE';}
          else if(raw.includes('WPA2')&&(raw.includes('WPA1')||raw.includes('WPAPSKWPA2')||raw.includes('WPA/WPA2')))auth='WPAPSKWPA2PSK';
          else if(raw.includes('WPA2'))auth='WPA2PSK';else if(raw.includes('WPA'))auth='WPAPSK';
          button.disabled=!auth||(isWPA(auth)&&!['AES','TKIP','TKIPAES'].includes(cipher))||/EAP|802\.1X|WPA3/i.test(raw);
          button.onclick=function(){
            selectedNetwork=network;el('upstream-ssid').value=network.ssid;
            el('upstream-password').value='';securityFields('upstream',auth,cipher);sync();
            naming();api.status('networkSelected');
          };el('networks').appendChild(button);
        });api.status('scanReady');
      }catch(_){api.status('scanFailed',true);}
    },45000);
  };
  el('reboot-device').onclick = function(){if(!api.isBusy()&&confirm(t('rebootConfirm')))api.reboot();};
  el('save-account').onclick = function(){
    if(api.isBusy())return;
    var config=api.config(), user=el('account-user').value, pass=el('account-password').value;
    if(!/^[!-~]{1,30}$/.test(user)||user.includes(':')||!/^[!-~]{1,30}$/.test(pass)||pass!==el('account-confirm').value){api.status('accountInvalid',true);return;}
    if(!confirm(t('accountConfirm')))return;
    var desired={SYS_USERS:user,SYS_ADMPASS:pass};
    api.save(desired,{account:true,authorize:function(){credentialCookie(user,pass);},undoAuthorize:function(){credentialCookie(config.SYS_USERS,config.SYS_ADMPASS);}});
  };
  el('restore-settings').onclick = async function(){
    if(api.isBusy())return;var file=el('restore-file').files[0];
    if(!file||file.size>131072){api.status('restoreInvalid',true);return;}
    api.lockFile(true);
    try{
      var text=await file.text(), restored=api.parse(text), seen=Object.create(null);
      text.split(/\r?\n/).forEach(function(line){var at=line.indexOf('=');if(at>0){var key=line.slice(0,at);if(seen[key])fail('restoreInvalid');seen[key]=true;}});
      if(!validSSID(restored.WLN_SSID1)||!['0','1'].includes(restored.SYS_WLMODE))fail('restoreInvalid');
      if(restored.SYS_WLMODE==='1') restored.LAN_DHCPD_EN='0';
      Object.assign(restored,api.managementDefaults(restored));
      if(restored.LAN_IP_MODE!=='1'||!['0','1'].includes(restored.SYS_RM_EN)||(!restored.SYS_RM_EN||restored.SYS_RM_EN==='0')&&restored.LAN_IP==='0.0.0.0')fail('restoreInvalid');
      if(restored.LAN_IP!=='0.0.0.0'&&!api.validIP(restored.LAN_IP))fail('restoreInvalid');
      if(restored.SYS_RM_EN==='1'&&(!/^\d+$/.test(restored.SYS_RM_PORT)||+restored.SYS_RM_PORT<1||+restored.SYS_RM_PORT>65535))fail('restoreInvalid');
      if(!['0','1'].includes(restored.WLN_HT_BW)||restored.WLN_RadioOn!=='1'||!/^\d+$/.test(restored.WLN_TxPower)||+restored.WLN_TxPower<1||+restored.WLN_TxPower>100)fail('restoreInvalid');
      if(restored.LAN_IP!=='0.0.0.0'&&+restored.SYS_RM_PORT===80)fail('restoreInvalid');
      api.guard(restored);
      if(confirm(t('restoreConfirm'))) {
        var current=api.config(),options={};
        if(restored.SYS_USERS!==current.SYS_USERS||restored.SYS_ADMPASS!==current.SYS_ADMPASS){
          if(!/^[!-~]{1,30}$/.test(restored.SYS_USERS)||restored.SYS_USERS.includes(':')||!/^[!-~]{1,30}$/.test(restored.SYS_ADMPASS))fail('restoreInvalid');
          options.authorize=function(){credentialCookie(restored.SYS_USERS,restored.SYS_ADMPASS);};options.undoAuthorize=function(){credentialCookie(current.SYS_USERS,current.SYS_ADMPASS);};
        }
        api.lockFile(false);api.save(restored,options);return;
      }
    }catch(_){api.status('restoreInvalid',true);}
    api.lockFile(false);
  };
  el('upgrade-firmware').onclick = async function(){
    if(api.isBusy())return;var file=el('upgrade-file').files[0];
    if(!file||!el('upgrade-confirm').checked||/NOT[-_ ]?(?:FOR[-_ ]?)?FLASH(?:ING|ABLE)|EXPERIMENTAL/i.test(file.name)){api.status('upgradeInvalid',true);return;}
    api.lockFile(true);
    try{
      if(file.size<64||file.size>718108)fail('upgradeInvalid');
      var bytes=new Uint8Array(await file.arrayBuffer()),view=new DataView(bytes.buffer),header=bytes.slice(0,64);
      header.fill(0,4,8);
      if(view.getUint32(0)!==0x27051956||view.getUint32(12)!==bytes.length-64||crc32(header)!==view.getUint32(4)||crc32(bytes.subarray(64))!==view.getUint32(24))fail('upgradeInvalid');
      if(!confirm(t('upgradeFinalConfirm'))){api.lockFile(false);return;}
      var data=new FormData();data.append('CMD','SYS_UPG');data.append('GO','index.htm');data.append('files',file,file.name);
      api.status('upgrading');
      api.request('POST','setok.htm',data,function(error,text,status){if(status>=400){api.lockFile(false);api.status('upgradeRejected',true);}else api.status('upgradeUnverified');},180000);
      // Keep writes locked. The upload response cannot establish flash/boot success.
      return;
    }catch(_){api.status('upgradeInvalid',true);}
    api.lockFile(false);
  };
  return {render:render, changes:changed, sync:sync, translate:function(){stats();sync();if(el('channel').options[0])el('channel').options[0].textContent=t('auto');}, loadStatus:loadStatus,
    lock:function(locked){el('sign-out').disabled=locked;el('reboot-device').disabled=locked;el('tools').disabled=locked;el('reload-settings').disabled=locked;if(!locked)sync();}};
}
