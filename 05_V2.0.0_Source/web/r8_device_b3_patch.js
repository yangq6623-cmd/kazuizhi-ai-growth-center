(() => {
  const PLATFORMS = [
    {id:'douyin', name:'抖音', mark:'♪', cls:'dy'},
    {id:'xiaohongshu', name:'小红书', mark:'红', cls:'xhs'},
    {id:'kuaishou', name:'快手', mark:'∞', cls:'ks'},
    {id:'wechat_channels', name:'视频号', mark:'视', cls:'wx'},
    {id:'weibo', name:'微博', mark:'◎', cls:'wb'},
    {id:'bilibili', name:'B站', mark:'B', cls:'bili'},
  ];
  let activePlatform = '';
  let sessionActive = false;
  let refreshBusy = false;
  let lastScreenState = '';
  let objectUrl = null;

  async function json(path, options) {
    const response = await fetch(path, options || {cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `请求失败 ${response.status}`);
    return data;
  }

  function currentDeviceId() {
    const value = String(document.getElementById('r8-device-id')?.textContent || '').trim();
    return value && value !== '--' ? value : null;
  }

  function primaryDevice(status) {
    return (status?.devices || []).find(x => x.device_id === status.primary_device_id) || null;
  }

  function translateRisk(value) {
    const key = String(value || '').toLowerCase();
    if (!key || key === 'unknown') return '待检测';
    if (['low','normal','ok'].includes(key)) return '正常';
    if (['medium','attention','warning'].includes(key)) return '注意';
    if (['high','danger'].includes(key)) return '高风险';
    return String(value);
  }

  function translateScreen(state) {
    return ({awake:'亮屏/可操作',screen_off:'熄屏',keyguard:'锁屏界面',secure_lock:'安全锁定'})[state] || '待检测';
  }

  async function postAction(action, extra={}) {
    const deviceId = currentDeviceId();
    if (!deviceId) throw new Error('请先扫描并连接手机');
    return json('/api/r8/device/action', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({device_id:deviceId, action, actor:'owner', ...extra})
    });
  }

  async function refreshMirror() {
    if (refreshBusy) return;
    const deviceId = currentDeviceId();
    const img = document.getElementById('r8-device-screen');
    if (!deviceId || !img) return;
    refreshBusy = true;
    try {
      const response = await fetch(`/api/r8/device/screenshot?device_id=${encodeURIComponent(deviceId)}&t=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || `屏幕读取失败 ${response.status}`);
      }
      const blob = await response.blob();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(blob);
      img.onload = () => {
        img.style.display = 'block';
        const empty = document.getElementById('r8-screen-empty');
        if (empty) empty.style.display = 'none';
      };
      img.src = objectUrl;
    } finally {
      refreshBusy = false;
    }
  }

  async function ensureInteractive({wake=true}={}) {
    let status = await json('/api/r8/device/status', {cache:'no-store'});
    let d = primaryDevice(status);
    if (!d || !d.connected) throw new Error('真实手机当前未通过 ADB 在线');
    if (d.screen_state === 'screen_off' && wake) {
      await postAction('wake');
      await new Promise(resolve => setTimeout(resolve, 700));
      status = await json('/api/r8/device/status', {cache:'no-store'});
      d = primaryDevice(status);
    }
    if (d?.screen_state === 'secure_lock') throw new Error('手机处于安全锁定状态，需要人工解锁');
    if (d?.screen_state === 'keyguard') throw new Error('手机仍停留在锁屏界面，请人工确认后继续');
    await refreshMirror();
    return d;
  }

  async function beginSession() {
    if (sessionActive) return;
    sessionActive = true;
    try {
      await ensureInteractive();
      await postAction('keep_awake_on');
      const hint = document.getElementById('r8-b3-session-state');
      if (hint) hint.textContent = '操作会话进行中 · 手机保持亮屏';
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, 'error');
    }
  }

  async function endSession() {
    if (!sessionActive) return;
    sessionActive = false;
    try { await postAction('keep_awake_off'); } catch (_) {}
    const hint = document.getElementById('r8-b3-session-state');
    if (hint) hint.textContent = '操作台关闭后恢复手机正常休眠';
  }

  async function launchPlatform(platform) {
    const item = PLATFORMS.find(x => x.id === platform);
    try {
      await ensureInteractive();
      await postAction('launch_app', {platform});
      activePlatform = platform;
      document.querySelectorAll('[data-b3-platform]').forEach(btn => btn.classList.toggle('active', btn.dataset.b3Platform === platform));
      const p1 = document.getElementById('r8-status-platform');
      const p2 = document.getElementById('r8-device-platform');
      if (p1) p1.textContent = `平台：${item?.name || platform}`;
      if (p2) p2.textContent = item?.name || platform;
      await new Promise(resolve => setTimeout(resolve, 900));
      await refreshMirror();
      if (typeof toast === 'function') toast(`${item?.name || '平台'}已在手机打开`);
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, 'error');
    }
  }

  function installStyles() {
    if (document.getElementById('r8-b3-style')) return;
    const style = document.createElement('style');
    style.id = 'r8-b3-style';
    style.textContent = `
      #r8-device-center.r8-b3-console{margin-top:14px}
      #r8-device-center.r8-b3-console .r8-console-head p{max-width:900px}
      .r8-b3-context{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:10px 12px;margin:9px 0 10px;border:1px solid rgba(120,130,150,.16);background:rgba(49,103,232,.045);border-radius:12px}
      .r8-b3-context b{font-size:13px}.r8-b3-context small{opacity:.68}
      .r8-b3-dock{display:flex;gap:8px;flex-wrap:wrap;padding:8px 0 12px}.r8-b3-platform{display:flex;align-items:center;gap:7px;border:1px solid rgba(120,130,150,.2);background:#fff;border-radius:12px;padding:7px 10px;cursor:pointer;min-height:40px}.r8-b3-platform.active{border-color:#3167e8;box-shadow:0 0 0 2px rgba(49,103,232,.12)}
      .r8-b3-icon{width:27px;height:27px;border-radius:8px;display:grid;place-items:center;font-weight:800;color:#fff;font-size:13px}.r8-b3-icon.dy{background:#111}.r8-b3-icon.xhs{background:#ef2b38}.r8-b3-icon.ks{background:#ff6b18}.r8-b3-icon.wx{background:#20b86a}.r8-b3-icon.wb{background:#f39b21}.r8-b3-icon.bili{background:#37a8db}
      #r8-device-center.r8-b3-console .r8-console-grid{grid-template-columns:minmax(390px,58%) minmax(330px,42%);gap:14px}
      #r8-device-center.r8-b3-console .r8-phone-stage{min-height:420px;max-height:620px}
      #r8-device-center.r8-b3-console .r8-phone-stage img{max-height:580px}
      .r8-b3-screen-tools{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-top:8px}.r8-b3-screen-tools button{min-height:32px;padding:5px 9px}.r8-b3-screen-tools small{margin-left:auto;opacity:.65}
      #r8-device-center.r8-b3-console.b3-scale-75 .r8-phone-stage img{max-height:450px;max-width:75%}
      #r8-device-center.r8-b3-console.b3-scale-100 .r8-phone-stage img{max-height:none;max-width:100%}
      #r8-device-center.r8-b3-console .r8-device-meta details:not([open]){opacity:.85}
      @media(max-width:1050px){#r8-device-center.r8-b3-console .r8-console-grid{grid-template-columns:1fr}.r8-b3-context{align-items:flex-start}}
    `;
    document.head.appendChild(style);
  }

  function enhance() {
    const panel = document.getElementById('r8-device-center');
    if (!panel || panel.dataset.b3Ready === '1') return false;
    panel.dataset.b3Ready = '1';
    panel.classList.add('r8-b3-console');
    installStyles();

    const label = panel.querySelector('.r8-console-head label');
    const heading = panel.querySelector('.r8-console-head h3');
    const desc = panel.querySelector('.r8-console-head p');
    if (label) label.textContent = '社媒中心 · R8-01B.3 虚拟手机控制';
    if (heading) heading.textContent = 'AI 社媒终端驾驶舱';
    if (desc) desc.textContent = '电脑端手机画面就是主控制面板。普通熄屏自动唤醒并重新抓屏；操作会话期间保持亮屏，关闭操作台后恢复正常休眠。';

    const status = panel.querySelector('.r8-console-status');
    if (status && !document.getElementById('r8-b3-context')) {
      const context = document.createElement('div');
      context.id = 'r8-b3-context';
      context.className = 'r8-b3-context';
      context.innerHTML = `<div><b>当前终端：FIO-BD00</b><br><small>当前 Gate 2 测试机未设置 PIN/密码；普通熄屏无需人工碰手机。</small></div><div><b id="r8-b3-session-state">操作台关闭后恢复手机正常休眠</b></div>`;
      status.insertAdjacentElement('afterend', context);

      const dock = document.createElement('div');
      dock.id = 'r8-b3-dock';
      dock.className = 'r8-b3-dock';
      dock.innerHTML = PLATFORMS.map(p => `<button class="r8-b3-platform" data-b3-platform="${p.id}" title="打开${p.name}"><span class="r8-b3-icon ${p.cls}">${p.mark}</span><span>${p.name}</span></button>`).join('');
      context.insertAdjacentElement('afterend', dock);
      dock.querySelectorAll('[data-b3-platform]').forEach(btn => btn.addEventListener('click', () => launchPlatform(btn.dataset.b3Platform)));
    }

    const stage = panel.querySelector('.r8-phone-stage');
    if (stage && !document.getElementById('r8-b3-screen-tools')) {
      const tools = document.createElement('div');
      tools.id = 'r8-b3-screen-tools';
      tools.className = 'r8-b3-screen-tools';
      tools.innerHTML = `<button class="outline-button" data-b3-scale="fit">适应窗口</button><button class="outline-button" data-b3-scale="75">75%</button><button class="outline-button" data-b3-scale="100">100%</button><button class="outline-button" id="r8-b3-fullscreen">全屏控制</button><small>单击=点击 · 拖动=滑动 · 右键=返回 · 双击=全屏</small>`;
      stage.insertAdjacentElement('afterend', tools);
      tools.querySelectorAll('[data-b3-scale]').forEach(btn => btn.addEventListener('click', () => {
        panel.classList.remove('b3-scale-75','b3-scale-100');
        if (btn.dataset.b3Scale === '75') panel.classList.add('b3-scale-75');
        if (btn.dataset.b3Scale === '100') panel.classList.add('b3-scale-100');
      }));
      document.getElementById('r8-b3-fullscreen').addEventListener('click', () => stage.requestFullscreen?.());
      stage.addEventListener('dblclick', () => stage.requestFullscreen?.());
      stage.addEventListener('click', async event => {
        const img = document.getElementById('r8-device-screen');
        if (event.target === img && img.style.display !== 'none') return;
        try { await ensureInteractive(); } catch (error) { if (typeof toast === 'function') toast(error.message,'error'); }
      });
    }

    const img = document.getElementById('r8-device-screen');
    if (img && !img.dataset.b3Context) {
      img.dataset.b3Context = '1';
      img.addEventListener('contextmenu', async event => {
        event.preventDefault();
        try { await postAction('back'); await new Promise(r=>setTimeout(r,280)); await refreshMirror(); }
        catch (error) { if (typeof toast === 'function') toast(error.message,'error'); }
      });
    }

    const close = document.getElementById('r8-device-close');
    close?.addEventListener('click', endSession, true);
    document.addEventListener('click', event => {
      if (event.target.closest?.('[data-social-device-control]')) setTimeout(beginSession, 450);
    }, true);
    return true;
  }

  async function heartbeat() {
    const panel = document.getElementById('r8-device-center');
    if (!panel || panel.hidden || document.visibilityState !== 'visible') return;
    try {
      const status = await json('/api/r8/device/status', {cache:'no-store'});
      const d = primaryDevice(status);
      if (!d || !d.connected) return;
      lastScreenState = d.screen_state || '';
      const risk = translateRisk(d.risk_level);
      const riskNode = document.getElementById('r8-device-risk');
      const riskPill = document.getElementById('r8-status-risk');
      if (riskNode) riskNode.textContent = risk;
      if (riskPill) riskPill.textContent = `风险：${risk}`;
      const screenNode = document.getElementById('r8-device-awake');
      if (screenNode) screenNode.textContent = translateScreen(d.screen_state);
      if (sessionActive && d.screen_state === 'screen_off') {
        await postAction('wake');
        await new Promise(resolve=>setTimeout(resolve,650));
      }
      await refreshMirror();
      if (activePlatform) {
        const item = PLATFORMS.find(x=>x.id===activePlatform);
        const p1=document.getElementById('r8-status-platform'); if(p1)p1.textContent=`平台：${item?.name||activePlatform}`;
      }
    } catch (_) {
      // Existing device center owns visible error messaging and disconnect state.
    }
  }

  if (!enhance()) {
    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      if (enhance() || attempts > 80) clearInterval(timer);
    }, 250);
  }
  setInterval(heartbeat, 3200);
})();
