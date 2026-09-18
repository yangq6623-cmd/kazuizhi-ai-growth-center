(() => {
  const STORAGE_KEY = 'kz_r8_social_slots_v1';
  const PLATFORMS = [
    {id:'douyin', name:'抖音', short:'抖', note:'短视频 / 搜索 / 评论 / 发布'},
    {id:'xiaohongshu', name:'小红书', short:'红', note:'图文 / 短视频 / 搜索 / 笔记'},
    {id:'wechat_channels', name:'视频号', short:'视', note:'视频 / 直播 / 私域承接'},
    {id:'weibo', name:'微博', short:'微', note:'话题 / 图文 / 热点'},
    {id:'bilibili', name:'哔哩哔哩', short:'B', note:'视频 / 搜索 / 长内容'},
    {id:'other', name:'其他平台', short:'+', note:'论坛 / 博客 / 其他合规渠道'},
  ];

  let activePlatform = 'douyin';
  let deviceSnapshot = null;

  const style = document.createElement('style');
  style.textContent = `
    .social-shell{display:grid;grid-template-columns:220px minmax(0,1fr);gap:16px}.social-platform-list{display:flex;flex-direction:column;gap:8px}.social-platform-btn{display:flex;align-items:center;gap:10px;text-align:left;width:100%;padding:11px;border:1px solid rgba(120,130,150,.18);border-radius:12px;background:var(--card,#fff);cursor:pointer}.social-platform-btn.active{border-color:#3167e8;box-shadow:0 0 0 2px rgba(49,103,232,.08)}.social-platform-icon{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:rgba(49,103,232,.09);font-weight:700}.social-platform-btn strong{display:block}.social-platform-btn small{display:block;opacity:.65;margin-top:2px}.social-toolbar{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;margin-bottom:12px}.social-slot-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:12px}.social-slot{border:1px solid rgba(120,130,150,.18);border-radius:14px;padding:14px;background:var(--card,#fff)}.social-slot-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.social-slot-meta{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.social-slot-meta div{padding:8px;border-radius:9px;background:rgba(120,130,150,.06)}.social-slot-meta small{display:block;opacity:.62}.social-slot-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.social-state{font-size:12px;border-radius:999px;padding:4px 8px}.social-state.ready{background:#e7f7ed;color:#237244}.social-state.waiting{background:#fff3d9;color:#9c6c06}.social-state.offline{background:#f6e6e4;color:#a43d31}.social-add-form{margin-top:16px;padding:14px;border:1px dashed rgba(120,130,150,.28);border-radius:14px}.social-add-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.social-add-grid label{display:flex;flex-direction:column;gap:5px}.social-security-note{margin-top:10px;padding:10px;border-radius:10px;background:#fff7df;color:#775c17;font-size:12px}.social-empty{padding:30px;text-align:center;border:1px dashed rgba(120,130,150,.25);border-radius:14px;opacity:.72}@media(max-width:900px){.social-shell{grid-template-columns:1fr}.social-platform-list{display:grid;grid-template-columns:repeat(2,1fr)}.social-add-grid{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  function loadSlots(){
    try { const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); return Array.isArray(data) ? data : []; }
    catch { return []; }
  }
  function saveSlots(items){ localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); }
  function esc(value){ return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function platform(id){ return PLATFORMS.find(x => x.id === id) || PLATFORMS[0]; }
  function connectedDevice(deviceId){ return (deviceSnapshot?.devices || []).find(x => x.device_id === deviceId && x.connected); }

  async function refreshDevices(){
    try { deviceSnapshot = await fetch('/api/r8/device/status',{cache:'no-store'}).then(r=>r.json()); }
    catch { deviceSnapshot = {devices:[]}; }
    const select = document.getElementById('social-device');
    if (select) {
      const devices = deviceSnapshot.devices || [];
      select.innerHTML = '<option value="">请选择手机</option>' + devices.map(d => `<option value="${esc(d.device_id)}">${esc(d.model || 'Android')} · ${esc(d.device_id)}${d.connected?' · 在线':' · 离线'}</option>`).join('');
    }
    renderSlots();
  }

  function renderPlatforms(){
    const host = document.getElementById('social-platform-list'); if(!host) return;
    host.innerHTML = PLATFORMS.map(p => `<button class="social-platform-btn ${p.id===activePlatform?'active':''}" data-social-platform="${p.id}"><span class="social-platform-icon">${p.short}</span><span><strong>${p.name}</strong><small>${p.note}</small></span></button>`).join('');
    host.querySelectorAll('[data-social-platform]').forEach(btn => btn.addEventListener('click',()=>{activePlatform=btn.dataset.socialPlatform;renderPlatforms();renderSlots();}));
  }

  function renderSlots(){
    const host = document.getElementById('social-slot-grid'); if(!host) return;
    const p = platform(activePlatform); const all = loadSlots(); const items = all.filter(x=>x.platform===activePlatform);
    document.getElementById('social-active-name').textContent = p.name;
    document.getElementById('social-active-note').textContent = p.note;
    host.innerHTML = items.length ? items.map(item => {
      const online = !!connectedDevice(item.deviceId);
      const authorized = item.authState === 'authorized';
      const ready = online && authorized && item.enabled !== false;
      const stateClass = ready ? 'ready' : online ? 'waiting' : 'offline';
      const stateText = ready ? '设备在线 · 授权已确认' : !online ? '设备离线' : authorized ? '授权已确认 · 自动化暂停' : '等待登录/授权';
      return `<div class="social-slot" data-slot="${esc(item.id)}"><div class="social-slot-head"><div><small>${esc(p.name)}账号窗口</small><h3>${esc(item.label || item.accountAlias || '未命名账号')}</h3></div><span class="social-state ${stateClass}">${stateText}</span></div><div class="social-slot-meta"><div><small>绑定手机</small><b>${esc(item.deviceId || '未绑定')}</b></div><div><small>账号标识</small><b>${esc(item.accountAlias || '未填写')}</b></div><div><small>登录状态</small><b>${authorized?'已人工确认登录':'待登录'}</b></div><div><small>运行状态</small><b>${item.enabled===false?'已暂停':ready?'可进入执行队列':'等待条件'}</b></div></div><div class="social-slot-actions"><button class="outline-button" data-social-open-device="${esc(item.id)}">设备中心</button><button class="outline-button" data-social-auth="${esc(item.id)}">${authorized?'重新确认授权':'确认已登录/授权'}</button><button class="outline-button" data-social-toggle="${esc(item.id)}">${item.enabled===false?'恢复':'暂停'}</button><button class="text-button" data-social-remove="${esc(item.id)}">删除</button></div></div>`;
    }).join('') : `<div class="social-empty">${esc(p.name)}还没有账号/手机窗口。点击“添加账号窗口”建立第一个绑定关系。</div>`;

    host.querySelectorAll('[data-social-open-device]').forEach(btn=>btn.addEventListener('click',()=>{if(typeof openPage==='function')openPage('connections'); setTimeout(()=>document.getElementById('r8-device-center')?.scrollIntoView({behavior:'smooth',block:'start'}),100);}));
    host.querySelectorAll('[data-social-auth]').forEach(btn=>btn.addEventListener('click',()=>updateSlot(btn.dataset.socialAuth,{authState:'authorized',authorizedAt:new Date().toISOString()})));
    host.querySelectorAll('[data-social-toggle]').forEach(btn=>btn.addEventListener('click',()=>{const item=loadSlots().find(x=>x.id===btn.dataset.socialToggle);if(item)updateSlot(item.id,{enabled:item.enabled===false});}));
    host.querySelectorAll('[data-social-remove]').forEach(btn=>btn.addEventListener('click',()=>{const items=loadSlots().filter(x=>x.id!==btn.dataset.socialRemove);saveSlots(items);renderSlots();}));
  }

  function updateSlot(id, patch){
    const items=loadSlots(); const index=items.findIndex(x=>x.id===id); if(index<0)return; items[index]=Object.assign({},items[index],patch,{updatedAt:new Date().toISOString()}); saveSlots(items); renderSlots();
    if(typeof toast==='function') toast('社媒账号窗口已更新');
  }

  function addSlot(){
    const deviceId=document.getElementById('social-device').value;
    const accountAlias=document.getElementById('social-account').value.trim();
    const label=document.getElementById('social-label').value.trim();
    if(!deviceId){ if(typeof toast==='function')toast('请先选择要绑定的 Android 手机','error'); return; }
    if(!accountAlias){ if(typeof toast==='function')toast('请填写平台账号标识','error'); return; }
    const items=loadSlots();
    if(items.some(x=>x.platform===activePlatform && x.deviceId===deviceId && x.accountAlias===accountAlias)){if(typeof toast==='function')toast('这个平台账号与手机已经存在','error');return;}
    items.push({id:`social_${Date.now()}_${Math.random().toString(16).slice(2,8)}`,platform:activePlatform,deviceId,accountAlias,label:label||accountAlias,authState:'waiting_login',enabled:true,createdAt:new Date().toISOString()});
    saveSlots(items); document.getElementById('social-account').value=''; document.getElementById('social-label').value=''; renderSlots();
    if(typeof toast==='function')toast('已添加社媒账号窗口；下一步在对应手机平台 App 完成登录和授权');
  }

  function mount(){
    if(document.getElementById('social-center')) return;
    const nav=document.querySelector('aside nav'); const main=document.querySelector('main'); if(!nav||!main)return;
    const analysisGroup=[...nav.querySelectorAll('.nav-group')].find(x=>x.textContent.includes('分析与内容'));
    const group=document.createElement('small'); group.className='nav-group'; group.textContent='社媒执行';
    const button=document.createElement('button'); button.className='nav'; button.dataset.page='social-center'; button.dataset.title='社媒中心'; button.dataset.subtitle='按平台管理真实手机、账号登录与授权状态'; button.innerHTML='<span>◎</span>社媒中心';
    if(analysisGroup){nav.insertBefore(group,analysisGroup);nav.insertBefore(button,analysisGroup);}else{nav.appendChild(group);nav.appendChild(button);}
    const section=document.createElement('section'); section.id='social-center'; section.className='page'; section.innerHTML=`<div class="page-title"><small>R8 社媒执行中心</small><h2>社媒中心</h2><p>一个账号窗口绑定一个真实手机和一个平台账号。先在手机端完成真实登录/验证，再把授权状态交给 R8；不伪造账号环境，不绕过验证码、人脸或平台风控。</p></div><div class="social-shell"><article><label>平台列表</label><div id="social-platform-list" class="social-platform-list"></div></article><article><div class="social-toolbar"><div><label>当前平台</label><h3 id="social-active-name">抖音</h3><p id="social-active-note" class="subtle"></p></div><button id="social-add-toggle" class="primary-small">添加账号窗口</button></div><div id="social-slot-grid" class="social-slot-grid"></div><div id="social-add-form" class="social-add-form" hidden><div class="social-add-grid"><label>绑定手机<select id="social-device"><option value="">正在读取手机…</option></select></label><label>平台账号标识<input id="social-account" maxlength="120" placeholder="手机号/用户名/账号备注"></label><label>窗口名称<input id="social-label" maxlength="80" placeholder="例如：涟水抖音主账号"></label></div><div class="social-security-note"><b>登录密码不在这里明文保存。</b> 首次登录、验证码、人脸和异常验证在真实手机平台 App 内由人工完成；登录会话有效后，R8 才进入自动化执行。后续如确需密码托管，只允许使用 Windows 当前用户加密保管。</div><div class="button-row" style="margin-top:10px"><button id="social-add-save" class="primary-button">保存账号窗口</button><button id="social-add-cancel" class="outline-button">取消</button></div></div></article></div>`;
    main.appendChild(section);
    button.addEventListener('click',()=>{if(typeof openPage==='function')openPage('social-center');refreshDevices();});
    document.getElementById('social-add-toggle').addEventListener('click',()=>{const f=document.getElementById('social-add-form');f.hidden=!f.hidden;if(!f.hidden)refreshDevices();});
    document.getElementById('social-add-cancel').addEventListener('click',()=>document.getElementById('social-add-form').hidden=true);
    document.getElementById('social-add-save').addEventListener('click',addSlot);
    renderPlatforms(); renderSlots(); refreshDevices();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true}); else mount();
})();
