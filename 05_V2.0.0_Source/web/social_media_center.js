(() => {
  const PLATFORMS = [
    {id:'douyin', name:'抖音', short:'抖'},
    {id:'xiaohongshu', name:'小红书', short:'红'},
    {id:'kuaishou', name:'快手', short:'快'},
    {id:'wechat_channels', name:'视频号', short:'视'},
    {id:'weibo', name:'微博', short:'微'},
    {id:'bilibili', name:'B站', short:'B'},
    {id:'forum', name:'论坛/社区', short:'坛'},
    {id:'blog', name:'博客/内容站', short:'博'},
    {id:'other', name:'其他平台', short:'+'},
  ];
  const TABS = [
    ['overview','总览'],['devices','设备矩阵'],['platforms','平台矩阵'],
    ['tasks','任务队列'],['content','内容中心'],['messages','消息与线索'],['risk','风险与日志'],
  ];
  let activeTab = 'overview';
  let activePlatform = 'douyin';
  let social = {devices:[],terminals:[],accounts:[],platforms:[],rules:{}};
  let deviceRuntime = {devices:[]};
  let audit = {items:[]};

  const style = document.createElement('style');
  style.textContent = `
    #social-center .social-hero{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;padding:18px;border:1px solid rgba(120,130,150,.18);border-radius:16px;background:linear-gradient(135deg,rgba(49,103,232,.07),rgba(112,72,232,.04));margin-bottom:14px}
    #social-center .social-hero h2{margin:4px 0 7px}#social-center .social-hero p{margin:0;max-width:860px}
    .social-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 16px}.social-tab{border:1px solid rgba(120,130,150,.2);background:var(--card,#fff);padding:8px 12px;border-radius:10px;cursor:pointer}.social-tab.active{border-color:#3167e8;background:rgba(49,103,232,.08);font-weight:700}
    .social-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:14px}.social-kpi{padding:13px;border:1px solid rgba(120,130,150,.16);border-radius:13px;background:var(--card,#fff)}.social-kpi small{display:block;opacity:.65}.social-kpi b{font-size:22px;display:block;margin-top:4px}
    .social-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}.social-card{border:1px solid rgba(120,130,150,.18);border-radius:14px;padding:14px;background:var(--card,#fff)}.social-card-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.social-card h3{margin:4px 0 6px}.social-subtle{font-size:12px;opacity:.67}
    .social-platforms{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.social-chip{display:inline-flex;align-items:center;gap:5px;padding:5px 8px;border-radius:999px;background:rgba(120,130,150,.08);font-size:12px}.social-chip.ready{background:#e7f7ed;color:#237244}.social-chip.waiting{background:#fff3d9;color:#8b6509}.social-chip.danger{background:#f8e5e3;color:#9a392f}.social-chip.offline{background:#eef0f4;color:#687080}
    .social-state{font-size:12px;border-radius:999px;padding:4px 8px;white-space:nowrap}.social-state.ready{background:#e7f7ed;color:#237244}.social-state.waiting{background:#fff3d9;color:#8b6509}.social-state.danger{background:#f8e5e3;color:#9a392f}.social-state.offline{background:#eef0f4;color:#687080}
    .social-meta{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.social-meta div{padding:8px;border-radius:9px;background:rgba(120,130,150,.055)}.social-meta small{display:block;opacity:.62}.social-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px}
    .social-attention{display:grid;gap:8px}.social-attention-row{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:10px;border-radius:10px;background:rgba(120,130,150,.055)}
    .social-platform-menu{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}.social-platform-button{border:1px solid rgba(120,130,150,.18);background:var(--card,#fff);padding:9px 11px;border-radius:10px;cursor:pointer}.social-platform-button.active{border-color:#3167e8;background:rgba(49,103,232,.08)}
    .social-empty{padding:24px;border:1px dashed rgba(120,130,150,.26);border-radius:13px;text-align:center;opacity:.72}.social-coming{padding:16px;border-radius:13px;background:rgba(49,103,232,.055);border:1px solid rgba(49,103,232,.12)}
    .social-form-shell{margin-top:14px;padding:14px;border:1px dashed rgba(120,130,150,.28);border-radius:14px}.social-form-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.social-form-grid label{display:flex;flex-direction:column;gap:5px}.social-note{margin-top:10px;padding:10px;border-radius:10px;background:#fff7df;color:#71591c;font-size:12px}
    .social-audit{display:grid;gap:7px}.social-audit-row{display:grid;grid-template-columns:140px 1fr 100px;gap:9px;align-items:center;padding:9px 10px;border-bottom:1px solid rgba(120,130,150,.1)}
    @media(max-width:1000px){.social-kpis{grid-template-columns:repeat(2,1fr)}.social-form-grid{grid-template-columns:1fr 1fr}}@media(max-width:680px){.social-kpis,.social-form-grid,.social-meta{grid-template-columns:1fr}.social-audit-row{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  function esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  async function request(path, options){
    const response=await fetch(path, options || {cache:'no-store'});
    let data={}; try{data=await response.json();}catch{}
    if(!response.ok) throw new Error(data.error || `请求失败 ${response.status}`);
    return data;
  }
  function runtime(deviceId){return (deviceRuntime.devices||[]).find(x=>x.device_id===deviceId)||{};}
  function accountState(account){
    if(account.risk_level==='high'||account.risk_level==='attention'||account.login_status==='needs_human') return ['danger','需要人工'];
    if(account.login_status==='logged_out') return ['danger','已退出'];
    if(account.automation_paused) return ['waiting','已暂停'];
    if(account.login_status==='authorized') return ['ready','已授权'];
    return ['waiting','待登录'];
  }
  function deviceState(device){
    const live=runtime(device.device_id);
    if(live.connected || device.connection==='connected') return ['ready','在线'];
    return ['offline','离线'];
  }
  function platformName(id){return PLATFORMS.find(x=>x.id===id)?.name || id;}
  function terminalAccounts(deviceId){return (social.accounts||[]).filter(x=>x.device_id===deviceId);}

  async function refresh(quiet=false){
    try{
      const results=await Promise.all([
        request('/api/r8/social'), request('/api/r8/device/status'), request('/api/r8/device/audit')
      ]);
      social=results[0]||social; deviceRuntime=results[1]||deviceRuntime; audit=results[2]||audit;
      render();
    }catch(error){if(!quiet&&typeof toast==='function')toast(error.message,'error');}
  }

  function renderKpis(){
    const devices=social.devices||[]; const accounts=social.accounts||[];
    const online=devices.filter(d=>deviceState(d)[0]==='ready').length;
    const authorized=accounts.filter(a=>a.login_status==='authorized').length;
    const attention=accounts.filter(a=>['needs_human','logged_out'].includes(a.login_status)||['attention','high'].includes(a.risk_level)).length + devices.filter(d=>deviceState(d)[0]==='offline').length;
    return `<div class="social-kpis">
      <div class="social-kpi"><small>真实手机</small><b>${devices.length}</b></div>
      <div class="social-kpi"><small>在线终端</small><b>${online}</b></div>
      <div class="social-kpi"><small>平台账号</small><b>${accounts.length}</b></div>
      <div class="social-kpi"><small>已登录授权</small><b>${authorized}</b></div>
      <div class="social-kpi"><small>需要处理</small><b>${attention}</b></div>
    </div>`;
  }

  function renderAttention(){
    const rows=[];
    (social.devices||[]).forEach(d=>{if(deviceState(d)[0]==='offline')rows.push(`<div class="social-attention-row"><span><b>${esc(d.label||d.device_id)}</b><br><small>真实手机离线</small></span><span class="social-state offline">需要检查连接</span></div>`);});
    (social.accounts||[]).forEach(a=>{
      const [klass,label]=accountState(a);
      if(klass==='danger')rows.push(`<div class="social-attention-row"><span><b>${esc(a.platform_name||platformName(a.platform))} · ${esc(a.label||a.alias)}</b><br><small>${esc(a.last_error||'登录/风险状态需要人工确认')}</small></span><span class="social-state danger">${esc(label)}</span></div>`);
    });
    if(!rows.length)return '<div class="social-empty">当前没有设备或账号异常。视频发布和资金操作仍保持人工确认边界。</div>';
    return `<div class="social-attention">${rows.join('')}</div>`;
  }

  function terminalCard(device){
    const live=runtime(device.device_id); const accounts=terminalAccounts(device.device_id); const [klass,state]=deviceState(device);
    const currentTask=live.current_task || '空闲';
    const chips=accounts.length?accounts.map(a=>{const s=accountState(a);return `<span class="social-chip ${s[0]}">${esc(a.platform_name||platformName(a.platform))} · ${esc(s[1])}</span>`;}).join(''):'<span class="social-chip offline">尚未绑定平台账号</span>';
    return `<div class="social-card"><div class="social-card-head"><div><small>AI 社媒运营终端</small><h3>${esc(device.label||live.model||device.device_id)}</h3><div class="social-subtle">${esc(device.device_id)}</div></div><span class="social-state ${klass}">${state}</span></div>
      <div class="social-platforms">${chips}</div>
      <div class="social-meta"><div><small>平台数量</small><b>${accounts.length}</b></div><div><small>当前任务</small><b>${esc(currentTask)}</b></div><div><small>控制模式</small><b>${esc(live.control_mode==='human'?'人工接管':'R8')}</b></div><div><small>屏幕</small><b>${live.screen_awake===false?'熄屏/待唤醒':live.screen_awake===true?'亮屏':'待检测'}</b></div></div>
      <div class="social-actions"><button class="primary-small" data-social-add-device="${esc(device.device_id)}">添加平台账号</button><button class="outline-button" data-social-device-control="${esc(device.device_id)}">打开真机控制</button></div></div>`;
  }

  function overview(){
    return `${renderKpis()}<div class="grid two"><article><div class="article-head"><div><label>需要我处理</label><h3>异常、登录与人工审批</h3></div></div>${renderAttention()}</article><article><div class="article-head"><div><label>运行规则</label><h3>单手机串行 · 多手机并行</h3></div></div><div class="social-coming"><b>一台手机可以绑定多个平台账号。</b><p>同一台手机的抖音、小红书、快手、视频号、微博、B站等前台任务依次执行；第一台真机 Gate 2 通过后再开放第二台设备并行。</p><p>平台浏览不采用固定机械停留时长，后续 R8-02 按内容相关性和任务目标决定快跳、短停、长停或完整观看，并记录判断理由。</p></div></article></div><article class="wide" style="margin-top:14px"><div class="article-head"><div><label>设备矩阵</label><h3>真实社媒运营终端</h3></div><button class="text-button" data-social-go-tab="devices">查看全部</button></div><div class="social-grid">${(social.devices||[]).length?(social.devices||[]).map(terminalCard).join(''):'<div class="social-empty">还没有已登记的真实 Android 手机。请先完成 ADB 真机接入。</div>'}</div></article>`;
  }

  function devicesView(){
    const rows=(social.devices||[]).map(terminalCard).join('');
    return `<div class="social-toolbar"><div><label>设备矩阵</label><h3>一台手机 = 一个 AI 社媒运营终端</h3><p class="social-subtle">每台终端可绑定多个不同平台账号；同一手机前台任务串行。</p></div><button class="primary-small" id="social-global-add">添加平台账号</button></div><div class="social-grid">${rows||'<div class="social-empty">尚无真实手机。先在“连接与体检”完成 ADB 授权。</div>'}</div>`;
  }

  function platformMenu(){
    return `<div class="social-platform-menu">${PLATFORMS.map(p=>`<button class="social-platform-button ${p.id===activePlatform?'active':''}" data-social-platform="${p.id}">${p.short} ${p.name}</button>`).join('')}</div>`;
  }

  function accountCard(account){
    const [klass,label]=accountState(account); const device=(social.devices||[]).find(d=>d.device_id===account.device_id)||{}; const online=deviceState(device)[0]==='ready';
    return `<div class="social-card"><div class="social-card-head"><div><small>${esc(account.platform_name||platformName(account.platform))}</small><h3>${esc(account.label||account.alias)}</h3><div class="social-subtle">${esc(account.alias)}</div></div><span class="social-state ${klass}">${esc(label)}</span></div>
      <div class="social-meta"><div><small>绑定手机</small><b>${esc(device.label||account.device_id)}</b></div><div><small>设备状态</small><b>${online?'在线':'离线'}</b></div><div><small>登录状态</small><b>${esc(label)}</b></div><div><small>风险</small><b>${esc(account.risk_level||'unknown')}</b></div></div>
      <div class="social-actions"><button class="outline-button" data-social-authorize="${esc(account.account_id)}">确认已登录</button><button class="outline-button" data-social-pause="${esc(account.account_id)}" data-paused="${account.automation_paused?'1':'0'}">${account.automation_paused?'恢复自动化':'暂停自动化'}</button><button class="text-button" data-social-remove="${esc(account.account_id)}">删除绑定</button></div></div>`;
  }

  function platformsView(){
    const accounts=(social.accounts||[]).filter(a=>a.platform===activePlatform);
    const summary=(social.platforms||[]).find(p=>p.id===activePlatform)||{};
    return `${platformMenu()}<div class="social-card" style="margin-bottom:12px"><div class="social-card-head"><div><small>当前平台</small><h3>${esc(platformName(activePlatform))}</h3></div><button class="primary-small" id="social-platform-add">添加该平台账号</button></div><div class="social-meta"><div><small>绑定终端</small><b>${summary.windows||0}</b></div><div><small>在线</small><b>${summary.online||0}</b></div><div><small>已授权</small><b>${summary.authorized||0}</b></div><div><small>需处理</small><b>${summary.attention||0}</b></div></div></div><div class="social-grid">${accounts.length?accounts.map(accountCard).join(''):`<div class="social-empty">${esc(platformName(activePlatform))}还没有绑定到任何手机。</div>`}</div>`;
  }

  function tasksView(){
    const running=(deviceRuntime.devices||[]).filter(d=>d.current_task);
    return `<div class="social-card"><div class="social-card-head"><div><small>R8 设备级调度</small><h3>任务队列</h3></div><span class="social-state waiting">R8-01 / R8-02衔接</span></div><p>当前先显示真实设备正在执行的任务；平台级自动轮转队列将在 Gate 2 真机验收后接入 R8-02。</p>${running.length?`<div class="social-attention">${running.map(d=>`<div class="social-attention-row"><span><b>${esc(d.model||d.device_id)}</b><br><small>${esc(d.current_task)}</small></span><span class="social-state ready">执行中</span></div>`).join('')}</div>`:'<div class="social-empty">当前没有真实设备任务正在执行。</div>'}<div class="social-note">正式调度规则：单手机多个平台依次执行；普通熄屏自动唤醒；任务期间保持可执行状态；安全锁、验证码、人脸或异常登录立即转人工。</div></div>`;
  }

  function contentView(){
    return `<div class="grid two"><article><label>内容生产</label><h3>内容中心保持独立生产、社媒中心负责分发</h3><p>选题、SEO/GEO、广告文案和短视频脚本继续使用现有“内容增长”；后续 R8-04～R8-07 将把已批准内容送入具体手机/平台队列。</p><button class="primary-small" data-social-open-page="promotion">打开内容增长</button></article><article><label>发布安全</label><h3>关键内容仍需老板确认</h3><p>视频发布不能因为社媒终端自动化而绕过老板最终确认；真实发布成功后必须保存平台回执和 URL。</p></article></div>`;
  }

  function messagesView(){
    return `<div class="social-card"><div class="social-card-head"><div><small>后续闭环</small><h3>消息与线索中心</h3></div><span class="social-state waiting">尚未接入真实平台消息</span></div><p>这里将统一承接评论、私信、@提及、咨询、师傅报名、团长咨询和用户报修，再分类进入小程序/订单闭环。</p><div class="social-empty">当前没有接入真实平台消息 API，因此不会显示虚假的消息数量或线索数量。</div></div>`;
  }

  function riskView(){
    const accountIssues=(social.accounts||[]).filter(a=>accountState(a)[0]==='danger');
    const events=(audit.items||[]).slice().reverse().slice(0,30);
    return `<div class="grid two"><article><label>账号/设备风险</label><h3>需要人工检查</h3>${accountIssues.length?accountIssues.map(a=>`<div class="social-attention-row"><span><b>${esc(a.platform_name)} · ${esc(a.label||a.alias)}</b><br><small>${esc(a.last_error||accountState(a)[1])}</small></span><span class="social-state danger">${esc(accountState(a)[1])}</span></div>`).join(''):'<div class="social-empty">当前没有已记录的账号高风险状态。</div>'}</article><article><label>安全边界</label><h3>不可自动绕过</h3><p>验证码、短信、人脸、平台风控、异常登录和资金操作都不会被自动绕过。设备掉线或安全验证出现时，该终端停止，其他终端可继续。</p></article></div><article class="wide" style="margin-top:14px"><label>最近设备审计</label><div class="social-audit">${events.length?events.map(e=>`<div class="social-audit-row"><small>${esc(e.at||'')}</small><b>${esc(e.action||'')}</b><span>${esc(e.result||'')}</span></div>`).join(''):'<div class="social-empty">暂无设备审计记录。</div>'}</div></article>`;
  }

  function currentView(){
    if(activeTab==='devices')return devicesView();
    if(activeTab==='platforms')return platformsView();
    if(activeTab==='tasks')return tasksView();
    if(activeTab==='content')return contentView();
    if(activeTab==='messages')return messagesView();
    if(activeTab==='risk')return riskView();
    return overview();
  }

  function addForm(){
    const devices=social.devices||[];
    return `<div id="social-add-form" class="social-form-shell" hidden><div class="social-form-grid"><label>真实手机<select id="social-form-device"><option value="">请选择手机</option>${devices.map(d=>`<option value="${esc(d.device_id)}">${esc(d.label||d.device_id)}</option>`).join('')}</select></label><label>平台<select id="social-form-platform">${PLATFORMS.map(p=>`<option value="${p.id}">${p.name}</option>`).join('')}</select></label><label>账号标识<input id="social-form-alias" maxlength="100" placeholder="用户名/账号备注"></label><label>终端内名称<input id="social-form-label" maxlength="80" placeholder="例如：涟水抖音主账号"></label></div><div class="social-note"><b>不保存平台明文密码。</b> 首次登录、短信验证码、扫码、人脸或异常验证必须在真实手机 App 内人工完成。设备 ID 是终端主身份；手机号只作为设备属性，不作为系统主键。</div><div class="social-actions"><button id="social-form-save" class="primary-button">保存平台账号绑定</button><button id="social-form-cancel" class="outline-button">取消</button></div></div>`;
  }

  function enhanceAccountForm(){
    const grid=document.querySelector('#social-add-form .social-form-grid');
    if(!grid||document.getElementById('social-form-role'))return;
    grid.insertAdjacentHTML('beforeend',`<label>账号角色<select id="social-form-role"><option value="brand">主品牌号</option><option value="service" selected>服务矩阵号</option></select></label>
      <label>自动化等级<select id="social-form-level"><option value="L1">L1 只观察</option><option value="L2" selected>L2 确认后互动</option><option value="L3">L3 已批准低风险自动化</option><option value="L4">L4 专项验收 Connector</option></select></label>
      <label>服务地区<input id="social-form-region" maxlength="80" value="涟水" placeholder="例如：涟水"></label>
      <label>服务类型<input id="social-form-service" maxlength="120" value="本地生活服务" placeholder="例如：家电维修"></label>`);
  }

  function render(){
    const host=document.getElementById('social-center-body'); if(!host)return;
    host.innerHTML=`<div class="social-tabs">${TABS.map(([id,name])=>`<button class="social-tab ${activeTab===id?'active':''}" data-social-tab="${id}">${name}</button>`).join('')}</div>${currentView()}${addForm()}`;
    enhanceAccountForm();
    bindViewEvents();
  }

  function openAdd(deviceId='', platformId=''){
    const form=document.getElementById('social-add-form'); if(!form)return;
    form.hidden=false;
    if(deviceId)document.getElementById('social-form-device').value=deviceId;
    if(platformId)document.getElementById('social-form-platform').value=platformId;
    form.scrollIntoView({behavior:'smooth',block:'center'});
  }

  async function saveBinding(){
    const device_id=document.getElementById('social-form-device').value;
    const platform=document.getElementById('social-form-platform').value;
    const alias=document.getElementById('social-form-alias').value.trim();
    const label=document.getElementById('social-form-label').value.trim()||alias;
    const role=document.getElementById('social-form-role')?.value||'service';
    const automation_level=document.getElementById('social-form-level')?.value||'L2';
    const region=document.getElementById('social-form-region')?.value.trim()||'涟水';
    const service_category=document.getElementById('social-form-service')?.value.trim()||'本地生活服务';
    if(!device_id)return typeof toast==='function'&&toast('请先选择真实手机','error');
    if(!alias)return typeof toast==='function'&&toast('请填写平台账号标识','error');
    try{
      social=await request('/api/r8/social/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id,platform,alias,label,role,automation_level,region,service_category})});
      if(typeof toast==='function')toast('平台账号已绑定；请在真实手机完成登录后再确认授权');
      render();
    }catch(error){if(typeof toast==='function')toast(error.message,'error');}
  }

  async function setStatus(account_id, patch, message){
    try{social=await request('/api/r8/social/account/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({account_id},patch))}); if(typeof toast==='function')toast(message); render();}
    catch(error){if(typeof toast==='function')toast(error.message,'error');}
  }

  async function removeBinding(account_id){
    try{social=await request('/api/r8/social/account/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({account_id})}); if(typeof toast==='function')toast('平台账号绑定已删除'); render();}
    catch(error){if(typeof toast==='function')toast(error.message,'error');}
  }

  function openDeviceControl(){
    if(typeof openPage==='function')openPage('connections');
    setTimeout(()=>document.getElementById('r8-device-center')?.scrollIntoView({behavior:'smooth',block:'start'}),120);
  }

  function bindViewEvents(){
    document.querySelectorAll('[data-social-tab]').forEach(b=>b.addEventListener('click',()=>{activeTab=b.dataset.socialTab;render();}));
    document.querySelectorAll('[data-social-go-tab]').forEach(b=>b.addEventListener('click',()=>{activeTab=b.dataset.socialGoTab;render();}));
    document.querySelectorAll('[data-social-platform]').forEach(b=>b.addEventListener('click',()=>{activePlatform=b.dataset.socialPlatform;render();}));
    document.querySelectorAll('[data-social-add-device]').forEach(b=>b.addEventListener('click',()=>openAdd(b.dataset.socialAddDevice,'')));
    document.querySelectorAll('[data-social-device-control]').forEach(b=>b.addEventListener('click',openDeviceControl));
    document.querySelectorAll('[data-social-open-page]').forEach(b=>b.addEventListener('click',()=>typeof openPage==='function'&&openPage(b.dataset.socialOpenPage)));
    document.querySelectorAll('[data-social-authorize]').forEach(b=>b.addEventListener('click',()=>setStatus(b.dataset.socialAuthorize,{login_status:'authorized',risk_level:'normal'},'已确认该平台账号在真实手机完成登录')));
    document.querySelectorAll('[data-social-pause]').forEach(b=>b.addEventListener('click',()=>{const paused=b.dataset.paused==='1';setStatus(b.dataset.socialPause,{automation_paused:!paused},paused?'账号自动化已恢复':'账号自动化已暂停');}));
    document.querySelectorAll('[data-social-remove]').forEach(b=>b.addEventListener('click',()=>removeBinding(b.dataset.socialRemove)));
    document.getElementById('social-global-add')?.addEventListener('click',()=>openAdd());
    document.getElementById('social-platform-add')?.addEventListener('click',()=>openAdd('',activePlatform));
    document.getElementById('social-form-save')?.addEventListener('click',saveBinding);
    document.getElementById('social-form-cancel')?.addEventListener('click',()=>{const f=document.getElementById('social-add-form');if(f)f.hidden=true;});
  }

  function mount(){
    if(document.getElementById('social-center'))return;
    const nav=document.querySelector('aside nav'); const main=document.querySelector('main'); if(!nav||!main)return;
    const analysisGroup=[...nav.querySelectorAll('.nav-group')].find(x=>x.textContent.includes('分析与内容'));
    const group=document.createElement('small'); group.className='nav-group'; group.textContent='社媒运营';
    const button=document.createElement('button'); button.className='nav'; button.dataset.page='social-center'; button.dataset.title='社媒中心'; button.dataset.subtitle='管理真实手机、多平台账号、任务、线索与风险'; button.innerHTML='<span>◉</span>社媒中心';
    if(analysisGroup){nav.insertBefore(group,analysisGroup);nav.insertBefore(button,analysisGroup);}else{nav.appendChild(group);nav.appendChild(button);}
    const section=document.createElement('section'); section.id='social-center'; section.className='page';
    section.innerHTML=`<div class="social-hero"><div><small>R8 · Social Operations Center</small><h2>社媒中心</h2><p>运行层以真实手机为中心：一台手机可绑定多个平台账号，单手机多平台串行切换；第一台 Gate 2 通过后，多台手机可并行运行。平台密码不在这里保存，验证码/人脸/风险验证必须转人工。</p></div><button id="social-refresh" class="primary-small">刷新状态</button></div><div id="social-center-body"><div class="friendly-empty">正在读取真实设备和平台账号状态…</div></div>`;
    main.appendChild(section);
    button.addEventListener('click',()=>{if(typeof openPage==='function')openPage('social-center');refresh();});
    document.getElementById('social-refresh').addEventListener('click',()=>refresh());
    refresh(true);
  }

  window.loadSocialCenter=()=>refresh(true);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
  setInterval(()=>{if(document.getElementById('social-center')?.classList.contains('active'))refresh(true);},15000);
})();
