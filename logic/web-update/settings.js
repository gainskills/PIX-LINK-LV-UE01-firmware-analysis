/* New image-free management UI, served from index.htm and lan.htm. */
(function () {
  'use strict';
  function start() {
    if (!document.getElementById('ap-settings')) return;
    var raw = '', config = {}, busy = false;
    var messages = {
      "home": [
        "Home",
        "首页"
      ],
      "title": [
        "Wi-Fi management",
        "Wi-Fi 管理"
      ],
      "mode": [
        "Mode",
        "工作模式"
      ],
      "repeater": [
        "Repeater",
        "中继"
      ],
      "wireless": [
        "Wi-Fi settings",
        "Wi-Fi 设置"
      ],
      "hide": [
        "Hide SSID",
        "隐藏 SSID"
      ],
      "hideNote": [
        "Hides the network name. Wi-Fi and Ethernet remain active.",
        "隐藏网络名称，Wi-Fi 和有线连接继续运行。"
      ],
      "wps": [
        "Enable WPS",
        "启用 WPS"
      ],
      "management": [
        "Management address",
        "管理地址"
      ],
      "current": [
        "Current address",
        "当前管理地址"
      ],
      "bookmark": [
        "Bookmark this address. The upstream IP may change.",
        "可收藏此地址。上游分配的 IP 可能变化。"
      ],
      "dhcp": [
        "Enable DHCP server",
        "启用 DHCP 服务器"
      ],
      "dhcpRepeater": [
        "Off in repeater mode. The upstream router assigns client addresses.",
        "中继模式关闭，由上游路由器为终端分配地址。"
      ],
      "dhcpAP": [
        "Assign IP addresses to connected devices.",
        "为连接本机的终端分配 IP 地址。"
      ],
      "static": [
        "Enable management address",
        "启用管理地址"
      ],
      "address": [
        "Management address",
        "管理地址"
      ],
      "staticNote": [
        "Adds a fixed LAN address on port 80. Upstream management stays enabled. Access the fixed address from the same subnet.",
        "添加使用端口 80 的固定局域网地址。通过上游 IP 管理仍保持启用。访问固定地址时需处于同一网段。"
      ],
      "upstream": [
        "Manage via upstream IP",
        "通过上游 IP 管理"
      ],
      "port": [
        "Upstream management port",
        "上游管理端口"
      ],
      "restartNote": [
        "Save & restart applies all settings and briefly disconnects the network.",
        "“保存并重启”应用所有设置，网络会短暂中断。"
      ],
      "apply": [
        "Save & restart",
        "保存并重启"
      ],
      "backup": [
        "Back up settings",
        "备份当前配置"
      ],
      "loading": [
        "Reading settings…",
        "正在读取设备配置…"
      ],
      "ready": [
        "",
        ""
      ],
      "dhcpDetected": [
        "DHCP server is enabled in repeater mode; saving will turn it off.",
        "检测到中继模式 DHCP 服务器开启；保存时将关闭。"
      ],
      "format": [
        "Unsupported configuration format.",
        "设备配置格式不受支持。"
      ],
      "missing": [
        "Required settings are missing.",
        "设备配置缺少必要设置。"
      ],
      "unsupported": [
        "Unsupported mode.",
        "当前工作模式不受支持。"
      ],
      "entry": [
        "Keep at least one management address enabled.",
        "请至少保留一个管理地址。"
      ],
      "validIP": [
        "Enter a valid management address.",
        "请输入有效的管理地址。"
      ],
      "dhcpRequired": [
        "The DHCP server must stay off in repeater mode.",
        "中继模式必须关闭 DHCP 服务器。"
      ],
      "validPort": [
        "Upstream management port must be 1–65535.",
        "上游管理端口必须为 1–65535。"
      ],
      "collision": [
        "The fixed management address uses port 80; choose another upstream port.",
        "固定管理地址使用端口 80，请为上游管理选择其他端口。"
      ],
      "currentStatic": [
        "Open this page through the upstream address before changing or disabling the current fixed management address.",
        "请先通过上游管理地址打开本页，再修改或关闭当前固定管理地址。"
      ],
      "currentUpstream": [
        "Open the fixed management address before disabling upstream management.",
        "请先通过固定管理地址打开本页，再关闭上游管理。"
      ],
      "duplicate": [
        "Duplicate settings found; saving stopped.",
        "配置中存在重复设置，已停止保存。"
      ],
      "missingChange": [
        "A setting to update is missing.",
        "配置中缺少待更新设置。"
      ],
      "saving": [
        "Saving settings…",
        "正在保存设置…"
      ],
      "freshRead": [
        "Cannot read the latest settings; no changes submitted.",
        "无法读取最新配置，未提交修改。"
      ],
      "concurrent": [
        "Settings changed in another page. Review them and save again.",
        "设备配置已在其他页面变更，请核对后重新保存。"
      ],
      "unverified": [
        "Import could not be verified; restart was not requested. Refresh to check, or restore your backup.",
        "未能确认配置导入，未继续请求重启。请刷新检查，必要时恢复备份。"
      ],
      "restarting": [
        "Settings verified. Restarting; please wait…",
        "配置已回读确认，正在重启。请稍候…"
      ],
      "target": [
        "Settings saved. Waiting for management address: ",
        "配置已保存。正在等待管理地址："
      ],
      "success": [
        "Settings saved and verified. Management connection is working.",
        "设置已保存并回读确认，管理连接正常。"
      ],
      "timeout": [
        "Timed out waiting for the device. Check the management address or restore your backup.",
        "等待设备恢复超时，尚未确认重启结果。请检查管理地址或使用备份恢复。"
      ],
      "readFailure": [
        "Could not read settings. Refresh to retry; no changes made.",
        "读取配置失败。请刷新页面重试；当前未修改设备。"
      ],
      "staticOff": [
        "Not enabled. The address shown is an example.",
        "尚未启用，所示地址仅为示例。"
      ],
      "savedStatic": [
        "Saved address: ",
        "已保存地址："
      ],
      "overview": [
        "Overview",
        "概览"
      ],
      "wirelessStatus": [
        "Wireless status",
        "无线状态"
      ],
      "channel": [
        "Channel",
        "信道"
      ],
      "security": [
        "Security",
        "安全设置"
      ],
      "clients": [
        "Wireless clients",
        "无线客户端"
      ],
      "firmwareVersion": [
        "Firmware version",
        "固件版本"
      ],
      "uptime": [
        "Uptime",
        "运行时间"
      ],
      "deviceMac": [
        "Device MAC",
        "设备 MAC"
      ],
      "unavailable": [
        "Unavailable",
        "暂不可用"
      ],
      "notApplicable": [
        "Not applicable",
        "不适用"
      ],
      "refreshStatus": [
        "Refresh status",
        "刷新状态"
      ],
      "telemetryUnavailable": [
        "Device status unavailable.",
        "设备状态暂不可用。"
      ],
      "extSsid": [
        "Network name (SSID)",
        "网络名称（SSID）"
      ],
      "useDefault": [
        "Use default name",
        "使用默认名称"
      ],
      "defaultNote": [
        "Default name: ",
        "默认名称："
      ],
      "defaultUnavailable": [
        "Enter a network name. The default is available after reading the device MAC.",
        "请输入网络名称。读取设备 MAC 后可使用默认名称。"
      ],
      "ssidInvalid": [
        "SSID must contain 1–32 UTF-8 bytes and no control characters.",
        "SSID 必须为 1–32 个 UTF-8 字节，且不能包含控制字符。"
      ],
      "uplinkSettings": [
        "Upstream Wi-Fi",
        "上游 Wi-Fi"
      ],
      "uplinkStatus": [
        "Upstream Wi-Fi",
        "上游 Wi-Fi"
      ],
      "upstreamSsid": [
        "Network name (SSID)",
        "网络名称（SSID）"
      ],
      "scan": [
        "Scan networks",
        "扫描网络"
      ],
      "scanNote": [
        "Enter the SSID and security settings for a hidden network, or select a scan result. Scanning may briefly interrupt Wi-Fi.",
        "隐藏网络可手动输入 SSID 和安全设置，也可选择扫描结果。扫描可能短暂中断 Wi-Fi。"
      ],
      "scanConfirm": [
        "Scan nearby networks? Wi-Fi may be briefly interrupted.",
        "扫描附近网络？Wi-Fi 可能短暂中断。"
      ],
      "scanning": [
        "Scanning nearby networks…",
        "正在扫描附近网络…"
      ],
      "scanFailed": [
        "Could not read the network scan. No settings changed.",
        "无法读取扫描结果，未修改设置。"
      ],
      "scanReady": [
        "Select a network and enter its key if required.",
        "请选择网络，并按需输入密钥。"
      ],
      "networkSelected": [
        "Network selected. Enter its key if required, then connect.",
        "已选择网络。按需输入密钥后连接。"
      ],
      "keepSecurity": [
        "Keep current",
        "保留当前设置"
      ],
      "openNetwork": [
        "Open network",
        "开放网络"
      ],
      "upstreamPassword": [
        "Security key",
        "安全密钥"
      ],
      "wifiPassword": [
        "Security key",
        "安全密钥"
      ],
      "passwordNote": [
        "For devices joining this AP. Leave blank to keep the saved key; a new security type may require a new key.",
        "供连接本机的终端使用。留空保留原密钥；切换安全类型时可能需要新密钥。"
      ],
      "pskInvalid": [
        "Wi-Fi passwords require 8–63 UTF-8 bytes or 64 hexadecimal digits.",
        "Wi-Fi 密码需为 8–63 个 UTF-8 字节或 64 位十六进制字符。"
      ],
      "securityUnsupported": [
        "Select a supported security type and encryption, or keep the current settings.",
        "请选择支持的安全类型和加密方式，或保留当前设置。"
      ],
      "radioSettings": [
        "Local Wi-Fi",
        "本机 Wi-Fi"
      ],
      "sharedRadio": [
        "Radio settings",
        "无线电设置"
      ],
      "sharedRadioNote": [
        "Shared by local Wi-Fi and the upstream connection in repeater mode.",
        "中继模式下，本机 Wi-Fi 与上游连接共用这些设置。"
      ],
      "power": [
        "Transmit power (%)",
        "发射功率（%）"
      ],
      "powerNote": [
        "Percentage of transmit power. Affects both local and upstream Wi-Fi.",
        "发射功率百分比，影响本机 Wi-Fi 和上游连接。"
      ],
      "bandwidth": [
        "Channel width",
        "信道带宽"
      ],
      "bandwidthNote": [
        "20/40 MHz allows wider channels when available.",
        "20/40 MHz 允许在条件支持时使用更宽信道。"
      ],
      "followUpstream": [
        "Local and upstream Wi-Fi share one radio and channel in repeater mode.",
        "中继模式下，本机与上游 Wi-Fi 共用无线电和信道。"
      ],
      "channelNote": [
        "Auto selects a channel at startup.",
        "自动模式在启动时选择信道。"
      ],
      "auto": [
        "Auto",
        "自动"
      ],
      "powerInvalid": [
        "Transmit power must be 1–100%.",
        "发射功率必须为 1–100%。"
      ],
      "widthInvalid": [
        "Select 20 or 20/40 MHz.",
        "请选择 20 或 20/40 MHz。"
      ],
      "channelInvalid": [
        "Select a valid channel.",
        "请选择有效信道。"
      ],
      "networkChange": [
        "Save Wi-Fi settings and restart? The network will briefly disconnect.",
        "保存 Wi-Fi 设置并重启？网络会短暂中断。"
      ],
      "system": [
        "System",
        "系统"
      ],
      "reload": [
        "Reload settings",
        "重新读取设置"
      ],
      "account": [
        "Admin account",
        "管理员账户"
      ],
      "username": [
        "Username",
        "用户名"
      ],
      "newPassword": [
        "New password",
        "新密码"
      ],
      "confirmPassword": [
        "Confirm password",
        "确认密码"
      ],
      "saveAccount": [
        "Save account",
        "保存账户"
      ],
      "accountInvalid": [
        "Use 1–30 non-space ASCII characters for account fields; passwords must match and username cannot contain a colon.",
        "账户字段需为 1–30 个无空格 ASCII 字符；两次密码须相同，用户名不能含冒号。"
      ],
      "accountConfirm": [
        "Save the new admin account? This session will use the new credentials.",
        "保存新管理员账户？当前会话将使用新的用户名和密码。"
      ],
      "accountSuccess": [
        "Account settings verified.",
        "账户设置已回读确认。"
      ],
      "restoreLabel": [
        "Settings backup",
        "配置备份"
      ],
      "restoreNote": [
        "Restarts after restoring. Keep the current management address and port in the backup.",
        "恢复后重启。备份须保留当前管理地址和端口。"
      ],
      "restore": [
        "Restore & restart",
        "恢复并重启"
      ],
      "restoreConfirm": [
        "Restore this backup and restart? DHCP server stays off in repeater mode; upstream management stays enabled.",
        "恢复此备份并重启？中继模式保持 DHCP 服务器关闭，上游管理保持启用。"
      ],
      "restoreInvalid": [
        "Invalid or incompatible backup, or it changes the current management address. No settings submitted.",
        "备份无效、不兼容或会改变当前管理地址，未提交设置。"
      ],
      "upgradeLabel": [
        "Firmware file",
        "固件文件"
      ],
      "upgradeNote": [
        "Use firmware for this model and hardware version.",
        "请选择匹配型号和硬件版本的固件。"
      ],
      "upgradeConfirm": [
        "I have confirmed firmware compatibility.",
        "我已确认固件兼容。"
      ],
      "upgrade": [
        "Upgrade firmware",
        "升级固件"
      ],
      "upgradeInvalid": [
        "Select a compatible uImage (at most 718108 bytes), confirm the hardware, and check its CRC. Experimental candidates cannot be uploaded.",
        "请选择兼容的 uImage（最多 718108 字节），确认硬件兼容且 CRC 校验通过。禁止上传实验固件。"
      ],
      "upgradeFinalConfirm": [
        "Upload firmware and upgrade? Keep power connected.",
        "上传固件并升级？请保持供电。"
      ],
      "upgrading": [
        "Uploading firmware… Keep power connected.",
        "正在上传固件，请保持供电。"
      ],
      "upgradeUnverified": [
        "Upgrade not yet verified. Keep power connected; check the firmware version when the device returns.",
        "尚未确认升级结果。请保持供电，设备恢复后检查固件版本。"
      ],
      "reboot": [
        "Restart device",
        "重启设备"
      ],
      "rebootConfirm": [
        "Restart now? The network will briefly disconnect.",
        "现在重启？网络会短暂中断。"
      ],
      "clientsNote": [
        "Ethernet devices are not counted.",
        "不统计有线设备。"
      ],
      "signOut": [
        "Sign out",
        "退出登录"
      ],
      "upgradeRejected": [
        "Firmware upload rejected.",
        "固件上传被拒绝。"
      ],
      "upstreamPasswordNote": [
        "For the upstream router. Leave blank to keep the saved key; a new network or security type may require a new key.",
        "用于连接上游路由器。留空保留原密钥；更换网络或切换安全类型时可能需要新密钥。"
      ],
      "securityType": [
        "Security type",
        "安全类型"
      ],
      "encryption": [
        "WPA encryption",
        "WPA 加密"
      ],
      "wepNote": [
        "WEP: 5 or 13 ASCII characters, or 10 or 26 hexadecimal digits.",
        "WEP：5 或 13 个 ASCII 字符，或 10 或 26 位十六进制字符。"
      ],
      "wepInvalid": [
        "Enter a valid WEP key: 5/13 ASCII characters or 10/26 hexadecimal digits.",
        "请输入有效 WEP 密钥：5/13 个 ASCII 字符或 10/26 位十六进制字符。"
      ],
      "keyRequired": [
        "Enter a security key for the selected security type.",
        "请为所选安全类型输入密钥。"
      ],
      "connectUpstream": [
        "Connect & restart",
        "连接并重启"
      ],
      "modeSaveNote": [
        "Mode changed. Use Save & restart to apply all settings together.",
        "模式已更改，请使用“保存并重启”一起应用所有设置。"
      ],
      "connectNote": [
        "Saves upstream settings and restarts. To apply all edits, use Save & restart.",
        "保存上游设置并重启。应用所有修改请使用“保存并重启”。"
      ],
      "connectConfirm": [
        "Save this upstream network and restart in repeater mode? Other unsaved edits will be lost. The management IP may change.",
        "保存此上游网络并以中继模式重启？其他未保存的编辑将丢失，管理 IP 可能变化。"
      ],
      "uplinkSaved": [
        "Upstream settings saved. Check connection status.",
        "上游设置已保存，请检查连接状态。"
      ],
      "connection": [
        "Connection status",
        "连接状态"
      ],
      "connecting": ["Connecting", "连接中"],
      "connected": [
        "Connected",
        "已连接"
      ],
      "disconnected": [
        "Disconnected",
        "未连接"
      ],
      "currentChannel": [
        "Current channel",
        "当前信道"
      ],
      "managementNote": [
        "Management is available in AP and repeater modes, even with the DHCP server off.",
        "AP 和中继模式均可管理设备，不受 DHCP 服务器开关影响。"
      ],
      "upstreamNote": [
        "Upstream IP management stays enabled. A fixed address is optional.",
        "通过上游 IP 管理始终启用，可按需添加固定管理地址。"
      ]
    };
    var language = /^zh\b/i.test((navigator.languages && navigator.languages[0]) || navigator.language || '') ? 'zh' : 'en';
    var lastStatus = 'loading', lastError = false, lastSuffix = '';
    function t(key) { return messages[key] ? messages[key][language === 'zh' ? 1 : 0] : key; }
    function translate() {
      document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
      document.title = t('title');
      document.querySelectorAll('[data-t]').forEach(function (node) { node.textContent = t(node.dataset.t); });
      el('language').value = language;
      if (raw) { if(panel)panel.translate(); staticState(); sync(); }
      status(lastStatus, lastError, lastSuffix);
    }
    el('language').onchange = function () { language = this.value; translate(); };

    var required = ['SYS_WLMODE', 'WLN_HideSSID', 'WLN_WscConfMode', 'LAN_DHCPD_EN',
      'LAN_IP', 'LAN_IP_MODE', 'SYS_RM_EN', 'SYS_RM_PORT', 'WLN_SSID1', 'WLN_ApCliSsid',
      'WLN_RadioOn', 'WLN_ApCliEnable', 'WLN_TxPower', 'WLN_HT_BW', 'WLN_Channel',
      'WLN_AutoChannelSelect', 'WLN_AuthMode', 'WLN_EncrypType', 'WLN_WPAPSK1',
      'WLN_ApCliAuthMode', 'WLN_ApCliEncrypType', 'WLN_ApCliWPAPSK', 'SYS_USERS', 'SYS_ADMPASS'];
    function el(id) { return document.getElementById(id); }
    function status(message, error, suffix) {
      lastStatus = message; lastError = !!error; lastSuffix = suffix || '';
      el('status').textContent = t(message) + lastSuffix;
      el('status').hidden = !el('status').textContent;
      el('status').dataset.error = error ? 'true' : 'false';
    }
    function request(method, url, body, callback, timeout) {
      var xhr = new XMLHttpRequest();
      var finished = false;
      function done(error) {
        if (finished) return;
        finished = true;
        callback(error, xhr.responseText, xhr.status);
      }
      xhr.open(method, url, true);
      xhr.timeout = timeout || 7000;
      if (typeof body === 'string') xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
      xhr.onload = function () { done(xhr.status === 200 ? null : new Error('HTTP ' + xhr.status)); };
      xhr.onerror = xhr.ontimeout = function () { done(new Error('网络连接中断')); };
      xhr.send(body || null);
    }
    function parse(text) {
      if (!/^#PROFILE\r?\n#VER_2_1\r?\n/.test(text)) throw new Error('format');
      var result = Object.create(null);
      text.split(/\r?\n/).forEach(function (line) {
        var n = line.indexOf('=');
        if (n > 0) result[line.slice(0, n)] = line.slice(n + 1);
      });
      required.forEach(function (key) {
        if (!Object.prototype.hasOwnProperty.call(result, key)) throw new Error('missing');
      });
      if (!/^[01]$/.test(result.SYS_WLMODE)) throw new Error('unsupported');
      return result;
    }
    function lock(locked) {
      el('controls').disabled = locked;
      el('network').disabled = locked;
      el('apply').disabled = locked;
      el('backup').disabled = !raw;
      if(panel)panel.lock(locked);
      if (!locked) sync();
    }
    function sync() {
      var repeater = panel ? el('operation-mode').value === '1' : config.SYS_WLMODE === '1';
      el('dhcp').disabled = repeater;
      if (repeater) el('dhcp').checked = false;
      el('dhcp-note').textContent = repeater ? t('dhcpRepeater') : t('dhcpAP');
      el('lan-address').disabled = !el('independent').checked;
      if(panel)panel.sync();
    }
    function staticState() {
      var node = el('static-state');
      node.textContent = t(config.LAN_IP === '0.0.0.0' ? 'staticOff' : 'savedStatic');
      if (config.LAN_IP !== '0.0.0.0') {
        var link = document.createElement('a');
        link.href = link.textContent = 'http://' + config.LAN_IP + '/';
        node.appendChild(link);
      }
    }
    function render() {
      el('hide-ssid').checked = config.WLN_HideSSID.split(';')[0] === '1';
      el('wps').checked = config.WLN_WscConfMode !== '0';
      el('dhcp').checked = config.LAN_DHCPD_EN === '1';
      el('independent').checked = config.LAN_IP !== '0.0.0.0';
      el('lan-address').value = config.LAN_IP === '0.0.0.0' ? '' : config.LAN_IP;
      el('port').value = managementDefaults(config).SYS_RM_PORT;
      el('current-link').textContent = location.origin;
      el('current-link').href = location.origin + '/lan.htm';
      staticState();
      if(panel)panel.render();
      lock(false);
    }
    function read(callback) {
      request('GET', 'profile.bin?ts=' + Date.now(), null, function (error, text) {
        if (error) return callback(error);
        try { callback(null, parse(text), text); } catch (failure) { callback(failure); }
      });
    }
    function validIP(value) {
      var parts = value.split('.');
      return parts.length === 4 && parts.every(function (s) { return /^(0|[1-9]\d{0,2})$/.test(s) && +s <= 255; }) &&
        +parts[0] > 0 && +parts[0] < 224 && +parts[0] !== 127 && +parts[3] > 0 && +parts[3] < 255;
    }
    function managementDefaults(profile) {
      var port=profile.SYS_RM_PORT;
      if(profile.SYS_RM_EN!=='1'&&(!/^\d+$/.test(port)||+port<1||+port>65535||(profile.LAN_IP!=='0.0.0.0'&&+port===80)))port='8080';
      return {SYS_RM_EN:'1',SYS_RM_PORT:port};
    }
    function changes() {
      var independent = el('independent').checked;
      var address = el('lan-address').value.trim();
      var port = Number(el('port').value);
      if (independent && !validIP(address)) throw new Error('validIP');
      if (independent && el('operation-mode').value === '1' && el('dhcp').checked) throw new Error('dhcpRequired');
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('validPort');
      if (independent && port === 80) throw new Error('collision');
      var hidden = config.WLN_HideSSID.split(';');
      hidden[0] = el('hide-ssid').checked ? '1' : '0';
      var result = {
        WLN_HideSSID: hidden.join(';'), WLN_WscConfMode: el('wps').checked ? '7' : '0',
        LAN_DHCPD_EN: el('operation-mode').value === '1' ? '0' : (el('dhcp').checked ? '1' : '0'),
        LAN_IP: independent ? address : '0.0.0.0', LAN_IP_MODE: '1',
        SYS_RM_EN: '1', SYS_RM_PORT: String(port)
      };
      Object.assign(result,panel.changes());
      guard(result);
      return result;
    }
    function guard(desired) {
      var independent=desired.LAN_IP !== '0.0.0.0', address=desired.LAN_IP;
      var upstream=desired.SYS_RM_EN === '1';
      if (config.LAN_IP !== '0.0.0.0' && location.hostname === config.LAN_IP &&
          (!independent || address !== config.LAN_IP)) {
        throw new Error('currentStatic');
      }
      // A port change keeps upstream management available; saveConfig redirects
      // after readback and reboot. Only disabling the active access path is blocked.
      if (String(location.port || 80) === config.SYS_RM_PORT && location.hostname !== config.LAN_IP &&
          !upstream) {
        throw new Error('currentUpstream');
      }
    }
    function replace(text, desired) {
      var found = Object.create(null);
      var updated = text.replace(/^([^=\r\n]+)=([^\r\n]*)/gm, function (line, key) {
        if (!Object.prototype.hasOwnProperty.call(desired, key)) return line;
        if (found[key]) throw new Error('duplicate');
        found[key] = true;
        return key + '=' + desired[key];
      });
      Object.keys(desired).forEach(function (key) {
        if (!found[key]) {
          // Registered native wizard flag is absent from some default exports.
          if(key==='WLN_APCLI_CONFIGED' && desired[key]==='1') updated+=(/\n$/.test(updated)?'':'\n')+key+'=1\n';
          else throw new Error('missingChange');
        }
      });
      return updated;
    }
    el('backup').onclick = function () {
      if (!raw) return;
      var url = URL.createObjectURL(new Blob([raw], { type: 'application/octet-stream' }));
      var link = document.createElement('a');
      link.href = url; link.download = 'ap-settings-backup.bin'; link.click();
      setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
    };
    el('independent').onchange = sync;
    function saveConfig(desired, options) {
      if (busy || !raw) return;
      options = options || {};
      var submitted;
      try { submitted = replace(raw, desired); }
      catch(error) { status(error.message,true);return; }
      busy = true; lock(true); status('saving');
      // Refresh before writing: preserve changes made in another management tab.
      read(function (error, latest, latestRaw) {
        if (error || latestRaw !== raw) {
          busy = false;
          if (!error) { config = latest; raw = latestRaw; render(); }
          else lock(false);
          status(error ? 'freshRead' : 'concurrent', true);
          return;
        }
        var data = new FormData();
        data.append('CMD', 'SYS_CONF'); data.append('CCMD', '3'); data.append('GO', 'lan.htm');
        data.append('files', new Blob([submitted], { type: 'application/octet-stream' }), 'profile.bin');
        request('POST', 'setok.htm', data, function (uploadError) {
          // Do not interpret an HTTP 200 (or a timeout) as successful import.
          if(options.authorize)options.authorize();
          read(function (verifyError, accepted, acceptedRaw) {
            var matches = !verifyError && Object.keys(desired).every(function (key) { return accepted[key] === desired[key]; });
            if (!matches) {
              if(options.undoAuthorize)options.undoAuthorize();
              busy = false; lock(false);
              status('unverified', true);
              return;
            }
            if(options.account){config=accepted;raw=acceptedRaw;busy=false;render();status('accountSuccess');return;}
            status('restarting');
            request('POST', 'man_reboot.htm', 'CMD=SYS_CONF&CCMD=0', function () {});
            var target = location.origin;
            if (location.hostname === config.LAN_IP && desired.LAN_IP !== '0.0.0.0') {
              target = location.protocol + '//' + desired.LAN_IP;
            } else if (desired.SYS_RM_EN === '1' && String(location.port || 80) === config.SYS_RM_PORT) {
              target = location.protocol + '//' + location.hostname + ':' + desired.SYS_RM_PORT;
            }
            if (target !== location.origin) {
              status('target', false, target);
              setTimeout(function () { location.assign(target + '/lan.htm'); }, 60000);
              return;
            }
            var attempts = 0;
            function poll() {
              read(function (failure, saved, savedRaw) {
                if (!failure && Object.keys(desired).every(function (key) { return saved[key] === desired[key]; })) {
                  raw = savedRaw; config = saved; busy = false; render();
                  panel.loadStatus();status(options.uplink?'uplinkSaved':'success');
                } else if (++attempts < 30) setTimeout(poll, 3000);
                else {
                  busy = false; lock(false);
                  status('timeout', true);
                }
              });
            }
            setTimeout(poll, 12000);
          });
        });
      });
    }
    function rebootOnly() {
      if(busy || !raw)return;
      busy=true;lock(true);status('restarting');
      request('POST','man_reboot.htm','CMD=SYS_CONF&CCMD=0',function(){});
      var count=0;
      function poll(){read(function(error,saved,text){
        if(!error){config=saved;raw=text;busy=false;render();panel.loadStatus();status('success');}
        else if(++count<30)setTimeout(poll,3000);
        else{busy=false;lock(false);status('timeout',true);}
      });}
      setTimeout(poll,12000);
    }
    var panel = createPanel({el:el,t:t,status:status,request:request,parse:parse,guard:guard,validIP:validIP,
      managementDefaults:managementDefaults,config:function(){return config;},isBusy:function(){return busy;},sync:sync,save:saveConfig,reboot:rebootOnly,
      lockFile:function(value){busy=value;lock(value);},
      reload:function(){if(busy)return;busy=true;lock(true);read(function(error,parsed,text){busy=false;if(error){lock(false);status('readFailure',true);return;}config=parsed;raw=text;render();panel.loadStatus();status('ready');});}
    });
    el('ap-settings').onsubmit = function(event){
      event.preventDefault();if(busy || !raw)return;
      var desired;
      try{desired=changes();}catch(error){status(error.message,true);return;}
      if((desired.SYS_WLMODE!==config.SYS_WLMODE || 
          desired.WLN_SSID1!==config.WLN_SSID1 || desired.WLN_WPAPSK1 || (desired.WLN_ApCliSsid!==undefined && desired.WLN_ApCliSsid!==config.WLN_ApCliSsid) || desired.WLN_ApCliWPAPSK || ['WLN_AuthMode','WLN_EncrypType','WLN_ApCliAuthMode','WLN_ApCliEncrypType','WLN_Key1Str1','WLN_ApCliKey1Str'].some(function(k){return desired[k]!==undefined&&desired[k]!==config[k];})) && !confirm(t('networkChange')))return;
      saveConfig(desired);
    };
    translate();
    read(function (error, parsed, text) {
      if (error) { status('readFailure', true); return; }
      raw = text; config = parsed; render();panel.loadStatus();try{sessionStorage.removeItem('ap-signin-pending');}catch(_){}
      status(config.SYS_WLMODE === '1' && config.LAN_DHCPD_EN !== '0' ?
        'dhcpDetected' : 'ready');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
}());
