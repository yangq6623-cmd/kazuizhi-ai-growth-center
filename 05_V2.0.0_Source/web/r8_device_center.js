(() => {
  const style = document.createElement('style');
  style.textContent = `
    #r8-device-center{margin:18px 0}.r8-console-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap}.r8-console-head h3{margin:4px 0 6px}
    .r8-console-status{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.r8-console-pill{padding:6px 9px;border-radius:999px;background:#eef1f6;font-size:12px}.r8-console-pill.ok{background:#e7f7ed;color:#237244}.r8-console-pill.warn{background:#fff3d9;color:#8b6509}.r8-console-pill.stop{background:#f8e5e3;color:#9a392f}.r8-console-pill.info{background:#e8efff;color:#2857b8}
    .r8-console-grid{display:grid;grid-template-columns:minmax(430px,1.25fr) minmax(330px,.75fr);gap:18px;align-items:start}.r8-phone-column{min-width:0}.r8-phone-stage{background:#0d1117;border-radius:18px;min-height:500px;padding:14px;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden}.r8-phone-stage img{max-width:100%;max-height:690px;border-radius:10px;cursor:pointer;display:none;user-select:none;-webkit-user-drag:none;touch-action:none}.r8-screen-empty{color:#b8c0cc;text-align:center;padding:28px}.r8-screen-overlay{position:absolute;inset:14px;display:none;align-items:center;justify-content:center;text-align:center;border-radius:12px;background:rgba(10,14,20,.72);color:#fff;z-index:4;cursor:pointer;padding:24px}.r8-screen-overlay strong{display:block;font-size:18px;margin-bottom:8px}.r8-screen-overlay small{display:block;opacity:.82;line-height:1.65}
    .r8-phone-toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.r8-phone-toolbar button{min-height:36px}.r8-console-side{display:grid;gap:12px}.r8-mode-box,.r8-info-box,.r8-action-box,.r8-audit-box{border:1px solid rgba(120,130,150,.18);border-radius:14px;padding:13px;background:var(--card,#fff)}.r8-mode-buttons{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:9px}.r8-mode-buttons button.active{background:#3167e8;color:#fff;border-color:#3167e8}.r8-device-meta{display:grid;grid-template-columns:1fr 1fr;gap:8px}.r8-device-meta div{padding:9px;border-radius:9px;background:rgba(120,130,150,.055)}.r8-device-meta small{display:block;opacity:.62;margin-bottom:2px}.r8-device-meta b{word-break:break-all}.r8-device-meta details{grid-column:1/-1}.r8-swipe-controls,.r8-text-row{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}.r8-text-row input{flex:1;min-width:170px}.r8-audit{max-height:210px;overflow:auto}.r8-audit div{padding:6px 0;border-bottom:1px solid rgba(120,130,150,.14);font-size:12px}.r8-device-note{font-size:12px;line-height:1.7;opacity:.78;margin:8px 0 0}.r8-keep-row{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:10px;padding:9px;border-radius:10px;background:rgba(49,103,232,.055)}.r8-keep-row button.active{background:#e7f7ed;color:#237244;border-color:#b9e5c8}
    @media(max-width:1050px){.r8-console-grid{grid-template-columns:1fr}.r8-phone-stage{min-height:420px}.r8-device-meta{grid-template-columns:1fr 1fr}}@media(max-width:640px){.r8-device-meta{grid-template-columns:1fr}.r8-mode-buttons{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const socialCenter = document.querySelector('#social-center');
  if (!socialCenter || document.querySelector('#r8-device-center')) return;
  const body = socialCenter.querySelector('#social-center-body');
  const panel = document.createElement('article');
  panel.id = 'r8-device-center';
  panel.className = 'wide';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="r8-console-head"><div><label>社媒中心 · R8-01B 真机操作台</label><h3>电脑端直接操作真实 Android 手机</h3><p class="subtle">手机画面就是主要操作区：单击=真机点击，鼠标拖动=真机滑动。普通熄屏会先安全唤醒；安全锁、验证码、人脸和平台验证仍转人工。</p></div><div class="button-row"><button id="r8-device-refresh" class="primary-small">扫描手机</button><button id="r8-device-close" class="outline-button">关闭操作台</button></div></div>
    <div id="r8-device-message" class="notice">打开终端后读取本机 ADB 与真机状态…</div>
    <div class="r8-console-status"><span id="r8-status-online" class="r8-console-pill">设备：检查中</span><span id="r8-status-screen" class="r8-console-pill">屏幕：--</span><span id="r8-status-mode" class="r8-console-pill">控制：--</span><span id="r8-status-platform" class="r8-console-pill">平台：未绑定</span><span id="r8-status-risk" class="r8-console-pill">风险：--</span></div>
    <div class="r8-console-grid">
      <div class="r8-phone-column">
        <div class="r8-phone-stage">
          <img id="r8-device-screen" alt="Android 真机屏幕">
          <div id="r8-screen-empty" class="r8-screen-empty">连接手机后点击“扫描手机”</div>
          <div id="r8-screen-overlay" class="r8-screen-overlay"><div><strong id="r8-overlay-title">屏幕已熄灭</strong><small id="r8-overlay-note">点击这里自动唤醒并重新读取手机画面</small></div></div>
        </div>
        <div class="r8-phone-toolbar"><button data-r8-action="back" class="outline-button">← 返回</button><button data-r8-action="home" class="outline-button">Home</button><button id="r8-screen-refresh" class="outline-button">刷新画面</button><button data-r8-action="wake" class="outline-button">唤醒</button><button data-r8-action="power" class="outline-button">电源键</button></div>
      </div>
      <div class="r8-console-side">
        <div class="r8-mode-box"><label>控制模式</label><div class="r8-mode-buttons"><button data-r8-mode="r8" class="outline-button">R8 自动</button><button data-r8-mode="human" class="outline-button">人工控制</button><button data-r8-mode="paused" class="outline-button">暂停</button></div><div class="r8-keep-row"><span><b>任务期间保持亮屏</b><br><small>USB连接时保持屏幕常亮；任务结束可恢复正常熄屏。</small></span><button id="r8-keep-awake" class="outline-button">开启</button></div></div>
        <div class="r8-info-box"><label>终端状态</label><div class="r8-device-meta">
          <div><small>连接状态</small><b id="r8-device-online">检查中</b></div><div><small>屏幕状态</small><b id="r8-device-awake">--</b></div>
          <div><small>设备 ID</small><b id="r8-device-id">--</b></div><div><small>型号</small><b id="r8-device-model">--</b></div>
          <div><small>Android</small><b id="r8-device-android">--</b></div><div><small>电量</small><b id="r8-device-battery">--</b></div>
          <div><small>当前平台</small><b id="r8-device-platform">未绑定</b></div><div><small>当前账号</small><b id="r8-device-account">未绑定</b></div>
          <div><small>当前任务</small><b id="r8-device-task">空闲</b></div><div><small>风险状态</small><b id="r8-device-risk">--</b></div>
          <details><summary>设备详情</summary><div style="margin-top:8px"><small>屏幕尺寸</small><b id="r8-device-size">--</b><br><small>ADB 路径</small><b id="r8-adb-path">--</b></div></details>
        </div></div>
        <div class="r8-action-box"><label>辅助操作</label><div class="r8-swipe-controls"><button data-r8-swipe="up" class="outline-button">上滑</button><button data-r8-swipe="down" class="outline-button">下滑</button><button data-r8-swipe="left" class="outline-button">左滑</button><button data-r8-swipe="right" class="outline-button">右滑</button></div><div class="r8-text-row"><input id="r8-device-text" maxlength="200" placeholder="文本输入（当前支持英文/数字）"><button id="r8-send-text" class="outline-button">输入</button></div><p class="r8-device-note">普通熄屏：点击手机画面会先唤醒并复检；安全锁/PIN/指纹/人脸/验证码：停止自动操作并转人工。所有点击、滑动、接管、唤醒和文件动作保留审计记录。</p></div>
        <div class="r8-audit-box"><label>最近设备动作</label><div id="r8-device-audit" class="r8-audit friendly-empty">尚无设备动作</div></div>
      </div>
    </div>`;
  if (body) socialCenter.insertBefore(panel, body.nextSibling); else socialCenter.appendChild(panel);

  const el = id => document.getElementById(id);
  let current = null;
  let pointerStart = null;

  async function request(path, options) {
    const response = await fetch(path, options || {cache:'no-store'});
    const type = response.headers.get('content-type') || '';
    const data = type.includes('application/json') ? await response.json() : null;
    if (!response.ok) throw new Error((data && data.error) || `请求失败 ${response.status}`);
    return data;
  }

  function setText(id, value) { const node = el(id); if (node) node.textContent = value == null || value === '' ? '--' : String(value); }
  function device() { return current && current.devices && current.devices.find(x => x.device_id === current.primary_device_id) || null; }
  function setPill(id, text, kind='') { const node=el(id); if(!node)return; node.textContent=text; node.className=`r8-console-pill ${kind}`.trim(); }
  function controlsDisabled(disabled) { panel.querySelectorAll('[data-r8-action],[data-r8-swipe],[data-r8-mode],#r8-screen-refresh,#r8-send-text,#r8-keep-awake').forEach(btn => btn.disabled = disabled); }

  function screenKind(d) {
    if (!d) return ['设备：未连接','stop'];
    if (d.screen_state === 'awake') return ['屏幕：亮屏/可操作','ok'];
    if (d.screen_state === 'screen_off') return ['屏幕：熄屏','warn'];
    if (d.screen_state === 'secure_lock') return ['屏幕：安全锁定','stop'];
    if (d.screen_state === 'keyguard') return ['屏幕：锁屏界面','warn'];
    return ['屏幕：未知','warn'];
  }

  function updateOverlay(d) {
    const overlay=el('r8-screen-overlay');
    if (!d || !d.connected || d.screen_state === 'awake') { overlay.style.display='none'; return; }
    overlay.style.display='flex';
    if (d.screen_state === 'screen_off') {
      el('r8-overlay-title').textContent='屏幕已熄灭';
      el('r8-overlay-note').textContent='点击这里自动唤醒，系统会重新检查锁定状态后刷新画面';
    } else {
      el('r8-overlay-title').textContent=d.screen_state === 'secure_lock' ? '手机需要人工解锁' : '手机停留在锁屏界面';
      el('r8-overlay-note').textContent='自动操作已停止。请切换“人工控制”，在手机上完成解锁/验证后再交还 R8。';
    }
  }

  async function loadAudit() {
    try {
      const data = await request('/api/r8/device/audit', {cache:'no-store'});
      const items = (data.items || []).slice().reverse().slice(0, 24);
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
      setText('r8-device-awake', d && (d.screen_state_label || (d.screen_awake === true ? '亮屏/可操作' : d.screen_awake === false ? '熄屏' : '未知')));
      setText('r8-device-platform', d && d.platform ? d.platform : '未绑定');
      setText('r8-device-account', d && d.account ? d.account : '未绑定');
      setText('r8-device-task', d && d.current_task ? d.current_task : '空闲');
      setText('r8-device-risk', d && d.risk_level ? d.risk_level : 'unknown');
      setPill('r8-status-online', d && d.connected ? `设备：${d.model || 'Android'} · 在线` : '设备：未连接', d && d.connected ? 'ok' : 'stop');
      const [screenText,screenClass]=screenKind(d); setPill('r8-status-screen',screenText,screenClass);
      const mode=d && d.control_mode || '--';
      const modeLabel=mode==='human'?'人工控制':mode==='paused'?'暂停':mode==='r8'?'R8自动':mode;
      setPill('r8-status-mode',`控制：${modeLabel}`,mode==='r8'?'info':mode==='human'?'warn':'stop');
      setPill('r8-status-platform',`平台：${d && d.platform ? d.platform : '未绑定'}`,'');
      setPill('r8-status-risk',`风险：${d && d.risk_level ? d.risk_level : 'unknown'}`,d && ['high','attention'].includes(d.risk_level)?'stop':'');
      panel.querySelectorAll('[data-r8-mode]').forEach(btn=>btn.classList.toggle('active',btn.dataset.r8Mode===mode));
      const keep=el('r8-keep-awake'); if(keep){keep.textContent=d&&d.keep_awake?'已开启':'开启';keep.classList.toggle('active',!!(d&&d.keep_awake));}
      el('r8-device-message').textContent = current.message || (d ? '设备已读取' : '未发现设备');
      controlsDisabled(!d || !d.connected);
      updateOverlay(d);
      if (!d) { el('r8-device-screen').style.display='none'; el('r8-screen-empty').style.display='block'; }
      await loadAudit();
      return d;
    } catch (error) {
      el('r8-device-message').textContent = '设备中心读取失败：' + error.message;
      controlsDisabled(true);
      return null;
    }
  }

  function refreshScreen() {
    const d = device();
    if (!d) return;
    const img = el('r8-device-screen');
    img.onload = () => { img.style.display='block'; el('r8-screen-empty').style.display='none'; updateOverlay(device()); };
    img.onerror = () => { img.style.display='none'; el('r8-screen-empty').style.display='block'; el('r8-screen-empty').textContent='屏幕读取失败，请重新扫描设备'; };
    img.src = `/api/r8/device/screenshot?device_id=${encodeURIComponent(d.device_id)}&t=${Date.now()}`;
  }

  async function postAction(payload, refresh=true) {
    const d = device(); if (!d) return;
    const body = Object.assign({device_id:d.device_id, actor:'owner'}, payload);
    await request('/api/r8/device/action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    await loadAudit();
    if (refresh) {
      await new Promise(resolve=>setTimeout(resolve,320));
      await scan();
      refreshScreen();
    }
  }

  function mapPoint(event,img,d) {
    const rect=img.getBoundingClientRect();
    return {
      x:Math.max(0,Math.min(d.screen.width-1,Math.round((event.clientX-rect.left)/rect.width*d.screen.width))),
      y:Math.max(0,Math.min(d.screen.height-1,Math.round((event.clientY-rect.top)/rect.height*d.screen.height)))
    };
  }

  async function takeover(mode) {
    const d=device(); if(!d)return;
    try {
      await request('/api/r8/device/takeover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,mode})});
      await scan();
      if(typeof toast==='function')toast(mode==='human'?'设备已切换为人工控制':mode==='paused'?'设备自动操作已暂停':'设备已交还 R8 自动控制');
    } catch(error){if(typeof toast==='function')toast(error.message,'error');}
  }

  el('r8-device-refresh').addEventListener('click', async()=>{const d=await scan();if(d)refreshScreen();});
  el('r8-screen-refresh').addEventListener('click', refreshScreen);
  el('r8-device-close').addEventListener('click', () => { panel.hidden = true; });
  panel.querySelectorAll('[data-r8-mode]').forEach(btn=>btn.addEventListener('click',()=>takeover(btn.dataset.r8Mode)));
  panel.querySelectorAll('[data-r8-action]').forEach(btn => btn.addEventListener('click', async () => {
    try { await postAction({action:btn.dataset.r8Action}); } catch (error) { if(typeof toast==='function')toast(error.message,'error'); }
  }));
  el('r8-keep-awake').addEventListener('click',async()=>{
    const d=device();if(!d)return;
    try{await postAction({action:d.keep_awake?'keep_awake_off':'keep_awake_on'});if(typeof toast==='function')toast(d.keep_awake?'已恢复手机正常熄屏策略':'任务期间保持亮屏已开启');}catch(error){if(typeof toast==='function')toast(error.message,'error');}
  });
  panel.querySelectorAll('[data-r8-swipe]').forEach(btn => btn.addEventListener('click', async () => {
    const d=device(); if(!d||!d.screen)return;
    const w=d.screen.width,h=d.screen.height,cx=Math.round(w/2),cy=Math.round(h/2),m=.22;
    const map={up:[cx,Math.round(h*(1-m)),cx,Math.round(h*m)],down:[cx,Math.round(h*m),cx,Math.round(h*(1-m))],left:[Math.round(w*(1-m)),cy,Math.round(w*m),cy],right:[Math.round(w*m),cy,Math.round(w*(1-m)),cy]};
    const v=map[btn.dataset.r8Swipe];
    try{await postAction({action:'swipe',x1:v[0],y1:v[1],x2:v[2],y2:v[3],duration:350});}catch(error){if(typeof toast==='function')toast(error.message,'error');}
  }));
  el('r8-send-text').addEventListener('click',async()=>{const text=el('r8-device-text').value;try{await postAction({action:'text',text});}catch(error){if(typeof toast==='function')toast(error.message,'error');}});

  el('r8-screen-overlay').addEventListener('click',async()=>{
    const d=device(); if(!d)return;
    if(d.screen_state==='screen_off'){
      try{await postAction({action:'wake'});}catch(error){if(typeof toast==='function')toast(error.message,'error');}
    }else{
      await takeover('human');
      if(typeof toast==='function')toast('请在手机上完成人工解锁/验证；完成后再点击“R8 自动”交还');
    }
  });

  const screen=el('r8-device-screen');
  screen.addEventListener('pointerdown',event=>{
    const d=device();if(!d||!d.screen)return;
    pointerStart={point:mapPoint(event,screen,d),clientX:event.clientX,clientY:event.clientY,at:Date.now()};
    try{screen.setPointerCapture(event.pointerId);}catch(_){}
  });
  screen.addEventListener('pointerup',async event=>{
    const d=device();if(!pointerStart||!d||!d.screen)return;
    const start=pointerStart; pointerStart=null;
    const end=mapPoint(event,screen,d); const dx=event.clientX-start.clientX,dy=event.clientY-start.clientY; const distance=Math.hypot(dx,dy);
    try{
      if(distance<12){await postAction({action:'tap',x:end.x,y:end.y});}
      else{const duration=Math.max(100,Math.min(1500,Date.now()-start.at));await postAction({action:'swipe',x1:start.point.x,y1:start.point.y,x2:end.x,y2:end.y,duration});}
    }catch(error){if(typeof toast==='function')toast(error.message,'error');}
  });
  screen.addEventListener('pointercancel',()=>{pointerStart=null;});

  // Keep phone operations exclusively inside 社媒中心.  The current pilot is
  // intentionally one real device; clicking any terminal opens this console.
  document.addEventListener('click', async event => {
    const button=event.target.closest&&event.target.closest('[data-social-device-control]');
    if(!button)return;
    event.preventDefault();
    event.stopPropagation();
    panel.hidden=false;
    panel.scrollIntoView({behavior:'smooth',block:'start'});
    const d=await scan();
    if(d)refreshScreen();
  }, true);
})();