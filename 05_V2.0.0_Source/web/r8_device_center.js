(() => {
  const style = document.createElement('style');
  style.textContent = `
    #r8-device-center{margin:18px 0}.r8-device-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
    .r8-device-grid{display:grid;grid-template-columns:minmax(280px,.9fr) minmax(320px,1.1fr);gap:16px;margin-top:14px}
    .r8-device-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.r8-device-meta div{padding:10px;border:1px solid rgba(120,130,150,.22);border-radius:10px}.r8-device-meta small{display:block;opacity:.68;margin-bottom:3px}.r8-device-meta b{word-break:break-all}
    .r8-screen-wrap{background:#101318;border-radius:14px;padding:10px;min-height:260px;display:flex;align-items:center;justify-content:center;position:relative}.r8-screen-wrap img{max-width:100%;max-height:540px;border-radius:8px;cursor:crosshair;display:none}.r8-screen-empty{color:#b8c0cc;text-align:center;padding:26px}
    .r8-device-controls,.r8-swipe-controls{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.r8-device-controls button,.r8-swipe-controls button{min-height:34px}.r8-text-row{display:flex;gap:8px;margin-top:10px}.r8-text-row input{flex:1;min-width:160px}.r8-audit{margin-top:12px;max-height:180px;overflow:auto}.r8-audit div{padding:6px 0;border-bottom:1px solid rgba(120,130,150,.16);font-size:12px}.r8-device-note{margin-top:10px;font-size:12px;opacity:.75}.r8-mode-human{color:#c57900}.r8-mode-r8{color:#22854b}@media(max-width:900px){.r8-device-grid{grid-template-columns:1fr}.r8-device-meta{grid-template-columns:1fr 1fr}}
  `;
  document.head.appendChild(style);

  const connections = document.querySelector('#connections');
  if (!connections || document.querySelector('#r8-device-center')) return;
  const title = connections.querySelector('.page-title');
  const panel = document.createElement('article');
  panel.id = 'r8-device-center';
  panel.className = 'wide';
  panel.innerHTML = `
    <div class="r8-device-head"><div><label>R8-01 单真机设备中心</label><h3>真实 Android 手机 / ADB</h3><p class="subtle">只接受本机 ADB 的真实探测结果；未连接时不会伪装成在线。</p></div><div class="button-row"><button id="r8-device-refresh" class="primary-small">扫描手机</button><button id="r8-screen-refresh" class="outline-button">刷新屏幕</button></div></div>
    <div id="r8-device-message" class="notice">正在读取本机 ADB 与真机状态…</div>
    <div class="r8-device-grid">
      <div><div class="r8-device-meta">
        <div><small>连接状态</small><b id="r8-device-online">检查中</b></div><div><small>控制模式</small><b id="r8-device-mode">--</b></div>
        <div><small>设备 ID</small><b id="r8-device-id">--</b></div><div><small>型号</small><b id="r8-device-model">--</b></div>
        <div><small>Android</small><b id="r8-device-android">--</b></div><div><small>电量</small><b id="r8-device-battery">--</b></div>
        <div><small>屏幕</small><b id="r8-device-size">--</b></div><div><small>ADB</small><b id="r8-adb-path">--</b></div>
      </div>
      <div class="r8-device-controls"><button id="r8-takeover" class="outline-button">人工接管</button><button id="r8-return" class="outline-button">交还 R8</button><button data-r8-action="back" class="outline-button">返回</button><button data-r8-action="home" class="outline-button">Home</button></div>
      <div class="r8-swipe-controls"><button data-r8-swipe="up" class="outline-button">上滑</button><button data-r8-swipe="down" class="outline-button">下滑</button><button data-r8-swipe="left" class="outline-button">左滑</button><button data-r8-swipe="right" class="outline-button">右滑</button></div>
      <div class="r8-text-row"><input id="r8-device-text" maxlength="200" placeholder="ADB 文本输入（当前先支持英文/数字）"><button id="r8-send-text" class="outline-button">输入</button></div>
      <p class="r8-device-note">屏幕图片可直接点击，系统会把点击位置换算成真机坐标。验证码、人脸、短信验证和资金动作不在自动操作范围。</p>
      <div><label>最近设备动作</label><div id="r8-device-audit" class="r8-audit friendly-empty">尚无设备动作</div></div></div>
      <div><div class="r8-screen-wrap"><img id="r8-device-screen" alt="Android 真机屏幕"><div id="r8-screen-empty" class="r8-screen-empty">连接手机后点击“刷新屏幕”</div></div></div>
    </div>`;
  if (title && title.nextSibling) connections.insertBefore(panel, title.nextSibling); else connections.appendChild(panel);

  const el = id => document.getElementById(id);
  let current = null;

  async function request(path, options) {
    const response = await fetch(path, options || {cache:'no-store'});
    const type = response.headers.get('content-type') || '';
    const data = type.includes('application/json') ? await response.json() : null;
    if (!response.ok) throw new Error((data && data.error) || `请求失败 ${response.status}`);
    return data;
  }

  function setText(id, value) { const node = el(id); if (node) node.textContent = value == null || value === '' ? '--' : String(value); }
  function device() { return current && current.devices && current.devices.find(x => x.device_id === current.primary_device_id) || null; }
  function controlsDisabled(disabled) {
    panel.querySelectorAll('[data-r8-action],[data-r8-swipe],#r8-screen-refresh,#r8-takeover,#r8-return,#r8-send-text').forEach(btn => btn.disabled = disabled);
  }

  async function loadAudit() {
    try {
      const data = await request('/api/r8/device/audit', {cache:'no-store'});
      const items = (data.items || []).slice().reverse().slice(0, 20);
      el('r8-device-audit').className = items.length ? 'r8-audit' : 'r8-audit friendly-empty';
      el('r8-device-audit').innerHTML = items.length ? items.map(x => `<div><b>${String(x.action || '')}</b> · ${String(x.result || '')}<br><small>${String(x.at || '')} · ${String(x.device_id || '')}</small></div>`).join('') : '尚无设备动作';
    } catch (_) {}
  }

  async function scan() {
    el('r8-device-message').textContent = '正在扫描 ADB 和 Android 真机…';
    try {
      current = await request('/api/r8/device/status', {cache:'no-store'});
      const d = device();
      setText('r8-adb-path', current.adb && current.adb.found ? current.adb.path : '未找到 adb.exe');
      setText('r8-device-online', d && d.connected ? '已连接' : '未连接');
      setText('r8-device-id', d && d.device_id);
      setText('r8-device-model', d && d.model);
      setText('r8-device-android', d && d.android_version);
      setText('r8-device-battery', d && d.battery != null ? `${d.battery}%` : null);
      setText('r8-device-size', d && d.screen ? `${d.screen.width} × ${d.screen.height}` : null);
      const mode = d && d.control_mode || '--';
      setText('r8-device-mode', mode === 'human' ? '人工接管' : mode === 'r8' ? 'R8 控制' : mode);
      el('r8-device-mode').className = mode === 'human' ? 'r8-mode-human' : mode === 'r8' ? 'r8-mode-r8' : '';
      el('r8-device-message').textContent = current.message || (d ? '设备已读取' : '未发现设备');
      controlsDisabled(!d || !d.connected);
      if (!d) {
        el('r8-device-screen').style.display = 'none';
        el('r8-screen-empty').style.display = 'block';
      }
      await loadAudit();
    } catch (error) {
      el('r8-device-message').textContent = '设备中心读取失败：' + error.message;
      controlsDisabled(true);
    }
  }

  function refreshScreen() {
    const d = device();
    if (!d) return;
    const img = el('r8-device-screen');
    img.onload = () => { img.style.display = 'block'; el('r8-screen-empty').style.display = 'none'; };
    img.onerror = () => { img.style.display = 'none'; el('r8-screen-empty').style.display = 'block'; el('r8-screen-empty').textContent = '屏幕读取失败，请重新扫描设备'; };
    img.src = `/api/r8/device/screenshot?device_id=${encodeURIComponent(d.device_id)}&t=${Date.now()}`;
  }

  async function postAction(payload) {
    const d = device();
    if (!d) return;
    const body = Object.assign({device_id:d.device_id, actor:'owner'}, payload);
    await request('/api/r8/device/action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    await loadAudit();
    setTimeout(refreshScreen, 250);
  }

  el('r8-device-refresh').addEventListener('click', scan);
  el('r8-screen-refresh').addEventListener('click', refreshScreen);
  panel.querySelectorAll('[data-r8-action]').forEach(btn => btn.addEventListener('click', async () => {
    try { await postAction({action:btn.dataset.r8Action}); } catch (error) { if (typeof toast === 'function') toast(error.message, 'error'); }
  }));
  panel.querySelectorAll('[data-r8-swipe]').forEach(btn => btn.addEventListener('click', async () => {
    const d = device(); if (!d || !d.screen) return;
    const w=d.screen.width,h=d.screen.height,cx=Math.round(w/2),cy=Math.round(h/2),m=0.22;
    const map={up:[cx,Math.round(h*(1-m)),cx,Math.round(h*m)],down:[cx,Math.round(h*m),cx,Math.round(h*(1-m))],left:[Math.round(w*(1-m)),cy,Math.round(w*m),cy],right:[Math.round(w*m),cy,Math.round(w*(1-m)),cy]};
    const v=map[btn.dataset.r8Swipe];
    try { await postAction({action:'swipe',x1:v[0],y1:v[1],x2:v[2],y2:v[3],duration:350}); } catch (error) { if (typeof toast === 'function') toast(error.message, 'error'); }
  }));
  el('r8-send-text').addEventListener('click', async () => {
    const text=el('r8-device-text').value;
    try { await postAction({action:'text',text}); } catch (error) { if (typeof toast === 'function') toast(error.message, 'error'); }
  });
  async function takeover(mode) {
    const d=device(); if(!d) return;
    try {
      await request('/api/r8/device/takeover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,mode})});
      await scan();
      if (typeof toast === 'function') toast(mode==='human'?'设备已切换为人工接管':'设备已交还 R8');
    } catch(error){ if(typeof toast==='function') toast(error.message,'error'); }
  }
  el('r8-takeover').addEventListener('click',()=>takeover('human'));
  el('r8-return').addEventListener('click',()=>takeover('r8'));
  el('r8-device-screen').addEventListener('click', async event => {
    const d=device(), img=el('r8-device-screen'); if(!d || !d.screen) return;
    const rect=img.getBoundingClientRect();
    const x=Math.max(0,Math.min(d.screen.width-1,Math.round((event.clientX-rect.left)/rect.width*d.screen.width)));
    const y=Math.max(0,Math.min(d.screen.height-1,Math.round((event.clientY-rect.top)/rect.height*d.screen.height)));
    try { await postAction({action:'tap',x,y}); } catch(error){ if(typeof toast==='function') toast(error.message,'error'); }
  });

  scan();
  setInterval(() => {
    if (document.visibilityState === 'visible' && connections.classList.contains('active')) scan();
  }, 10000);
})();
