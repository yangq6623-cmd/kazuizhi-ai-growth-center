(() => {
  const PLATFORM_META = [
    {id:'douyin', name:'抖音', glyph:'音', tone:'douyin'},
    {id:'xiaohongshu', name:'小红书', glyph:'红', tone:'xiaohongshu'},
    {id:'kuaishou', name:'快手', glyph:'快', tone:'kuaishou'},
    {id:'wechat_channels', name:'视频号', glyph:'视', tone:'wechat'},
    {id:'weibo', name:'微博', glyph:'微', tone:'weibo'},
    {id:'bilibili', name:'B站', glyph:'B', tone:'bilibili'},
    {id:'other', name:'其他', glyph:'+', tone:'other'},
  ];
  const state = {social:null, device:null, activePlatform:'', expandedLogs:false, activeTab:'task', zoom:'fit'};
  let initialized = false;
  let refreshTimer = null;

  const style = document.createElement('style');
  style.textContent = `
    #social-center.cockpit-active>.social-hero,#social-center.cockpit-active>.social-tabs,#social-center.cockpit-active>#social-center-body{display:none!important}
    #social-center.cockpit-active #r8-device-center{margin-top:0!important}
    #r8-device-center.r8-cockpit-v2{padding:0;border:0;background:transparent;box-shadow:none}
    #r8-device-center.r8-cockpit-v2>.r8-console-head{padding:14px 16px;margin-bottom:10px;border:1px solid rgba(120,130,150,.16);border-radius:15px;background:var(--card,#fff)}
    #r8-device-center.r8-cockpit-v2>.r8-console-head p{max-width:760px;margin-bottom:0}
    #r8-device-center.r8-cockpit-v2>#r8-device-message{margin:8px 0}
    .kz-cockpit-summary{display:grid;grid-template-columns:minmax(220px,1.25fr) repeat(4,minmax(120px,.72fr));gap:8px;padding:10px;border:1px solid rgba(120,130,150,.16);border-radius:14px;background:var(--card,#fff);margin-bottom:9px}
    .kz-summary-cell{padding:8px 10px;border-radius:10px;background:rgba(120,130,150,.055);min-width:0}.kz-summary-cell small{display:block;opacity:.58;margin-bottom:3px}.kz-summary-cell b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kz-summary-cell.primary{background:linear-gradient(135deg,rgba(49,103,232,.10),rgba(112,72,232,.06))}.kz-summary-line{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.kz-dot{width:8px;height:8px;border-radius:50%;background:#9ba3b1;display:inline-block}.kz-dot.ok{background:#22a565}.kz-dot.warn{background:#d79b1e}.kz-dot.stop{background:#d9564b}
    .kz-platform-dock{display:flex;gap:8px;align-items:stretch;overflow-x:auto;padding:8px 2px 11px;margin-bottom:7px;scrollbar-width:thin}.kz-platform-item{min-width:112px;border:1px solid rgba(120,130,150,.17);border-radius:13px;padding:8px;background:var(--card,#fff);cursor:pointer;display:grid;grid-template-columns:34px 1fr;gap:7px;align-items:center;text-align:left}.kz-platform-item.active{border-color:#3167e8;box-shadow:0 0 0 2px rgba(49,103,232,.10);background:#f5f8ff}.kz-platform-item small{display:block;opacity:.58;white-space:nowrap}.kz-platform-item b{display:block;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kz-platform-icon{width:31px;height:31px;border-radius:9px;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:13px;flex:0 0 31px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.18)}
    .kz-platform-icon.douyin{background:linear-gradient(135deg,#111 0 45%,#23d7d0 45% 58%,#fe2c55 58%)}.kz-platform-icon.xiaohongshu{background:#ff2442}.kz-platform-icon.kuaishou{background:#ff6f16}.kz-platform-icon.wechat{background:#20b761}.kz-platform-icon.weibo{background:linear-gradient(135deg,#ffba2b,#ee4d2d)}.kz-platform-icon.bilibili{background:#fb7299}.kz-platform-icon.other{background:#77808f}
    .social-platform-button .kz-platform-icon,.social-chip .kz-platform-icon{width:22px;height:22px;border-radius:6px;font-size:10px;flex-basis:22px}.social-platform-button.kz-iconized,.social-chip.kz-iconized{display:inline-flex;align-items:center;gap:6px}
    #r8-device-center.r8-cockpit-v2 .r8-console-status{margin:7px 0 9px}
    #r8-device-center.r8-cockpit-v2 .r8-console-grid{grid-template-columns:minmax(420px,58fr) minmax(330px,42fr);gap:14px;align-items:start}
    #r8-device-center.r8-cockpit-v2 .r8-phone-stage{min-height:360px;height:min(58vh,610px);max-height:610px;padding:10px;overflow:auto;border-radius:16px}
    #r8-device-center.r8-cockpit-v2 .r8-phone-stage img{max-height:100%;max-width:100%;object-fit:contain;transition:max-height .18s ease,transform .18s ease}
    #r8-device-center.r8-cockpit-v2 .r8-phone-stage[data-zoom="75"] img{max-height:75%;max-width:75%}
    #r8-device-center.r8-cockpit-v2 .r8-phone-stage[data-zoom="100"] img{max-height:100%;max-width:100%}
    #r8-device-center.r8-cockpit-v2 .r8-phone-stage:fullscreen{height:100vh;max-height:none;border-radius:0;padding:18px;background:#05070a}
    #r8-device-center.r8-cockpit-v2 .r8-phone-stage:fullscreen img{max-height:calc(100vh - 36px);max-width:100%}
    .kz-screen-tools{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:9px 0 0}.kz-screen-tools button{min-height:32px;padding:6px 9px}.kz-screen-tools button.active{background:#e8efff;color:#2857b8;border-color:#abc0ff}.kz-screen-hint{font-size:11px;opacity:.62;margin-left:auto}
    #r8-device-center.r8-cockpit-v2 .r8-phone-toolbar{margin-top:7px}.r8-phone-toolbar .kz-secondary-hide{display:none}
    .kz-side-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;padding:5px;border-radius:12px;background:rgba(120,130,150,.07);position:sticky;top:8px;z-index:3}.kz-side-tabs button{border:0;background:transparent;padding:8px 6px;border-radius:9px;cursor:pointer;color:inherit}.kz-side-tabs button.active{background:var(--card,#fff);box-shadow:0 2px 8px rgba(30,45,80,.08);font-weight:700;color:#2c5fd0}
    #r8-device-center.r8-cockpit-v2 .r8-console-side{gap:9px}.r8-console-side>[data-cockpit-tab]{display:none!important}.r8-console-side>[data-cockpit-tab].active{display:block!important}
    .kz-task-card,.kz-ai-reason,.kz-platform-panel,.kz-human-panel{border-radius:11px;padding:10px;background:rgba(120,130,150,.055);margin:8px 0}.kz-task-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kz-task-grid div{padding:8px;border-radius:9px;background:var(--card,#fff)}.kz-task-grid small{display:block;opacity:.58}.kz-ai-reason{border:1px solid rgba(49,103,232,.12);background:rgba(49,103,232,.055)}.kz-ai-reason b{display:block;margin-bottom:4px}.kz-run-chain{display:flex;gap:5px;align-items:center;overflow-x:auto;padding:7px 0}.kz-chain-step{display:flex;align-items:center;gap:4px;white-space:nowrap;font-size:11px;padding:5px 7px;border-radius:999px;background:#eef0f4;color:#687080}.kz-chain-step.ready{background:#e7f7ed;color:#237244}.kz-chain-step.running{background:#e8efff;color:#2857b8}.kz-chain-step.waiting{background:#fff3d9;color:#8b6509}.kz-chain-arrow{opacity:.36}
    .kz-account-list{display:grid;gap:6px;margin-top:8px}.kz-account-row{display:grid;grid-template-columns:30px 1fr auto;gap:7px;align-items:center;padding:7px;border-radius:9px;background:rgba(120,130,150,.055)}.kz-account-row small{display:block;opacity:.58}.kz-state-tag{font-size:11px;padding:4px 7px;border-radius:999px;background:#eef0f4;color:#687080}.kz-state-tag.ready{background:#e7f7ed;color:#237244}.kz-state-tag.waiting{background:#fff3d9;color:#8b6509}.kz-state-tag.danger{background:#f8e5e3;color:#9a392f}
    .kz-health{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px;border-radius:10px;background:rgba(120,130,150,.055);margin-bottom:8px}.kz-health-score{font-size:22px;font-weight:800}.kz-health small{opacity:.62}.kz-todo-list{display:grid;gap:6px;margin:8px 0}.kz-todo{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:8px;border-radius:9px;background:#fff7df}.kz-todo.ok{background:#eaf8ef}.kz-todo b{font-size:12px}.kz-owner-todo{display:inline-flex;align-items:center;gap:6px;padding:7px 10px;border-radius:999px;background:#fff3d9;color:#8b6509;border:1px solid #f1d797;font-size:12px;font-weight:700;cursor:pointer}.kz-owner-todo.zero{background:#e7f7ed;color:#237244;border-color:#b9e5c8}
    .kz-log-more{width:100%;margin-top:7px}.r8-audit.kz-collapsed div:nth-child(n+6){display:none}
    .kz-mini-monitor-note{font-size:11px;opacity:.64;margin-left:6px}
    @media(max-width:1100px){.kz-cockpit-summary{grid-template-columns:1fr 1fr 1fr}.kz-summary-cell.primary{grid-column:1/-1}#r8-device-center.r8-cockpit-v2 .r8-console-grid{grid-template-columns:1fr}.kz-screen-hint{width:100%;margin-left:0}}
    @media(max-width:680px){.kz-cockpit-summary{grid-template-columns:1fr}.kz-task-grid{grid-template-columns:1fr}.kz-side-tabs{grid-template-columns:1fr 1fr}.kz-platform-item{min-width:100px}}
  `;
  document.head.appendChild(style);

  function esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  async function request(path, options){
    const response=await fetch(path, options || {cache:'no-store'});
    let data={}; try{data=await response.json();}catch{}
    if(!response.ok) throw new Error(data.error || `请求失败 ${response.status}`);
    return data;
  }
  function platformBy(value){const text=String(value||'').toLowerCase();return PLATFORM_META.find(p=>p.id===text||p.name===value||text.includes(p.id)||text.includes(p.name.toLowerCase()))||PLATFORM_META[6];}
  function icon(platform, compact=false){const p=typeof platform==='object'?platform:platformBy(platform);return `<span class="kz-platform-icon ${p.tone}" aria-hidden="true">${esc(p.glyph)}</span>`;}
  function riskLabel(value){const v=String(value||'').toLowerCase();if(['low','normal','ok','ready'].includes(v))return ['正常','ok'];if(['medium','attention','warning'].includes(v))return ['注意','warn'];if(['high','danger','blocked'].includes(v))return ['高风险','stop'];return ['待检测','warn'];}
  function modeLabel(value){return value==='human'?'人工控制':value==='paused'?'暂停':'R8 自动';}
  function screenLabel(d){if(!d)return ['未检测','warn'];if(d.screen_state==='awake')return ['亮屏可操作','ok'];if(d.screen_state==='screen_off')return ['熄屏','warn'];if(d.screen_state==='secure_lock')return ['安全锁定','stop'];if(d.screen_state==='keyguard')return ['锁屏界面','warn'];return ['待检测','warn'];}
  function accountState(a){if(!a)return ['未配置','offline'];if(['high','attention'].includes(a.risk_level)||a.login_status==='needs_human')return ['待人工','danger'];if(a.login_status==='logged_out')return ['已退出','danger'];if(a.automation_paused)return ['已暂停','waiting'];if(a.login_status==='authorized')return ['已登录','ready'];return ['待登录','waiting'];}
  function currentDevice(){const ds=state.device?.devices||[];return ds.find(x=>x.device_id===state.device?.primary_device_id)||ds.find(x=>x.connected)||null;}
  function deviceAccounts(){const d=currentDevice();return d?(state.social?.accounts||[]).filter(a=>a.device_id===d.device_id):[];}
  function currentPlatformId(d){if(state.activePlatform)return state.activePlatform;const p=PLATFORM_META.find(x=>x.name===d?.platform||x.id===d?.platform);return p?.id||'';}
  function healthScore(d){let score=100;if(!d?.connected)score-=55;if(!state.device?.adb?.found)score-=25;if(!d?.screen_state||d.screen_state==='unknown')score-=8;if(['secure_lock','keyguard'].includes(d?.screen_state))score-=15;const [risk]=riskLabel(d?.risk_level);if(risk==='高风险')score-=25;else if(risk==='注意')score-=10;if(!deviceAccounts().length)score-=5;return Math.max(0,Math.min(100,score));}

  function decoratePlatformIcons(root=document){
    root.querySelectorAll('.social-platform-button:not(.kz-iconized)').forEach(node=>{
      const p=PLATFORM_META.find(x=>node.textContent.includes(x.name));if(!p)return;node.classList.add('kz-iconized');node.insertAdjacentHTML('afterbegin',icon(p,true));
    });
    root.querySelectorAll('.social-chip:not(.kz-iconized)').forEach(node=>{
      const p=PLATFORM_META.find(x=>node.textContent.includes(x.name));if(!p)return;node.classList.add('kz-iconized');node.insertAdjacentHTML('afterbegin',icon(p,true));
    });
  }

  function ensureOwnerTodo(){
    const hero=document.querySelector('#social-center .social-hero');if(!hero)return;
    let button=document.getElementById('kz-owner-todo');
    if(!button){button=document.createElement('button');button.id='kz-owner-todo';button.className='kz-owner-todo';button.type='button';const target=hero.lastElementChild||hero;target.appendChild(button);button.addEventListener('click',()=>{
      const panel=document.getElementById('r8-device-center');if(panel&&!panel.hidden){switchTab('human');panel.scrollIntoView({behavior:'smooth',block:'start'});}else{document.querySelector('[data-social-go-tab="overview"]')?.click();}
    });}
  }

  function ensureCockpit(){
    if(initialized)return true;
    const socialCenter=document.getElementById('social-center');const panel=document.getElementById('r8-device-center');if(!socialCenter||!panel)return false;
    initialized=true;panel.classList.add('r8-cockpit-v2');
    const head=panel.querySelector('.r8-console-head');
    if(head){const label=head.querySelector('label');const h3=head.querySelector('h3');const p=head.querySelector('p');if(label)label.textContent='社媒中心 · R8-01B.2';if(h3)h3.textContent='AI 社媒终端驾驶舱';if(p)p.textContent='以任务和平台为中心管理真实手机：手机画面可直接点击与拖动；设备参数收进详情，需要人工时才打扰老板。';const close=document.getElementById('r8-device-close');if(close)close.textContent='返回社媒总览';}

    const message=document.getElementById('r8-device-message');
    if(message&&!document.getElementById('kz-cockpit-summary')){
      const summary=document.createElement('div');summary.id='kz-cockpit-summary';summary.className='kz-cockpit-summary';summary.innerHTML=`
        <div class="kz-summary-cell primary"><small>当前终端</small><div class="kz-summary-line"><span id="kz-summary-dot" class="kz-dot"></span><b id="kz-summary-device">等待真机</b></div></div>
        <div class="kz-summary-cell"><small>当前平台 / 账号</small><b id="kz-summary-platform">未绑定</b></div>
        <div class="kz-summary-cell"><small>当前任务</small><b id="kz-summary-task">空闲</b></div>
        <div class="kz-summary-cell"><small>控制权</small><b id="kz-summary-mode">--</b></div>
        <div class="kz-summary-cell"><small>终端健康</small><b id="kz-summary-health">--</b></div>`;
      message.insertAdjacentElement('beforebegin',summary);
      const dock=document.createElement('div');dock.id='kz-platform-dock';dock.className='kz-platform-dock';message.insertAdjacentElement('beforebegin',dock);
    }

    const phoneStage=panel.querySelector('.r8-phone-stage');
    if(phoneStage&&!document.getElementById('kz-screen-tools')){
      phoneStage.dataset.zoom='fit';
      const tools=document.createElement('div');tools.id='kz-screen-tools';tools.className='kz-screen-tools';tools.innerHTML=`<button class="outline-button active" data-kz-zoom="fit">适应窗口</button><button class="outline-button" data-kz-zoom="75">75%</button><button class="outline-button" data-kz-zoom="100">100%</button><button id="kz-phone-fullscreen" class="outline-button">全屏控制</button><span class="kz-screen-hint">左键点击 · 拖动滑屏 · 右键返回 · 双击全屏</span>`;phoneStage.insertAdjacentElement('afterend',tools);
      tools.querySelectorAll('[data-kz-zoom]').forEach(btn=>btn.addEventListener('click',()=>setZoom(btn.dataset.kzZoom)));
      document.getElementById('kz-phone-fullscreen')?.addEventListener('click',toggleFullscreen);
      const screen=document.getElementById('r8-device-screen');
      if(screen){screen.addEventListener('dblclick',event=>{event.preventDefault();toggleFullscreen();});screen.addEventListener('contextmenu',event=>{event.preventDefault();panel.querySelector('[data-r8-action="back"]')?.click();});}
    }

    const side=panel.querySelector('.r8-console-side');
    if(side&&!document.getElementById('kz-side-tabs')){
      const nav=document.createElement('div');nav.id='kz-side-tabs';nav.className='kz-side-tabs';nav.innerHTML='<button data-kz-tab="task" class="active">任务</button><button data-kz-tab="platform">平台</button><button data-kz-tab="human">人工处理</button><button data-kz-tab="log">日志</button>';side.insertBefore(nav,side.firstChild);nav.querySelectorAll('[data-kz-tab]').forEach(btn=>btn.addEventListener('click',()=>switchTab(btn.dataset.kzTab)));
      const mode=side.querySelector('.r8-mode-box'),info=side.querySelector('.r8-info-box'),actions=side.querySelector('.r8-action-box'),audit=side.querySelector('.r8-audit-box');
      if(mode){mode.dataset.cockpitTab='task';mode.classList.add('active');mode.insertAdjacentHTML('afterbegin',`<div id="kz-task-card" class="kz-task-card"><b>当前任务</b><div class="kz-task-grid"><div><small>任务</small><b id="kz-task-current">空闲</b></div><div><small>下一步</small><b id="kz-task-next">等待任务队列</b></div><div><small>今日平台链</small><b id="kz-task-progress">0 / 0</b></div><div><small>运行时间</small><b>由任务调度器记录</b></div></div><div id="kz-run-chain" class="kz-run-chain"></div></div><div class="kz-ai-reason"><b>AI 当前判断</b><span id="kz-ai-reason">当前没有可解释决策记录。进入 R8-02 平台学习后，这里展示“为什么继续看 / 为什么跳过 / 为什么读评论”等判断理由。</span></div>`);}
      if(info){info.dataset.cockpitTab='platform';info.insertAdjacentHTML('afterbegin','<div class="kz-platform-panel"><b>本机平台账号</b><div id="kz-account-list" class="kz-account-list"></div></div>');}
      if(actions){actions.dataset.cockpitTab='human';actions.insertAdjacentHTML('afterbegin','<div id="kz-human-panel" class="kz-human-panel"><div class="kz-health"><div><small>终端健康度</small><div id="kz-health-score" class="kz-health-score">--</div></div><div id="kz-health-note">检查中</div></div><b>需要人工处理</b><div id="kz-todo-list" class="kz-todo-list"></div><div style="margin-top:8px;font-size:12px;opacity:.7">内容待发布确认与高意向线索将在对应业务接口接入后显示；当前不伪造数量。</div></div>');}
      if(audit){audit.dataset.cockpitTab='log';const log=audit.querySelector('.r8-audit');if(log)log.classList.add('kz-collapsed');const more=document.createElement('button');more.id='kz-log-more';more.className='outline-button kz-log-more';more.textContent='查看全部日志';more.addEventListener('click',()=>{state.expandedLogs=!state.expandedLogs;log?.classList.toggle('kz-collapsed',!state.expandedLogs);more.textContent=state.expandedLogs?'收起日志':'查看全部日志';});audit.appendChild(more);}
    }

    document.getElementById('r8-device-close')?.addEventListener('click',()=>{socialCenter.classList.remove('cockpit-active');stopRefresh();},true);
    document.addEventListener('click',event=>{const button=event.target.closest?.('[data-social-device-control]');if(!button)return;socialCenter.classList.add('cockpit-active');setTimeout(()=>{refreshCockpit();startRefresh();},500);},true);
    ensureOwnerTodo();decoratePlatformIcons();switchTab('task');refreshCockpit();return true;
  }

  function setZoom(value){state.zoom=value;const stage=document.querySelector('#r8-device-center .r8-phone-stage');if(stage)stage.dataset.zoom=value;document.querySelectorAll('[data-kz-zoom]').forEach(btn=>btn.classList.toggle('active',btn.dataset.kzZoom===value));}
  async function toggleFullscreen(){const stage=document.querySelector('#r8-device-center .r8-phone-stage');if(!stage)return;try{if(document.fullscreenElement)await document.exitFullscreen();else await stage.requestFullscreen();}catch(error){if(typeof toast==='function')toast('当前浏览器不允许全屏控制：'+error.message,'error');}}
  function switchTab(tab){state.activeTab=tab;document.querySelectorAll('#kz-side-tabs [data-kz-tab]').forEach(btn=>btn.classList.toggle('active',btn.dataset.kzTab===tab));document.querySelectorAll('#r8-device-center .r8-console-side>[data-cockpit-tab]').forEach(box=>box.classList.toggle('active',box.dataset.cockpitTab===tab));}

  function renderDock(d,accounts){
    const dock=document.getElementById('kz-platform-dock');if(!dock)return;const currentId=currentPlatformId(d);
    dock.innerHTML=PLATFORM_META.map(p=>{const a=accounts.find(x=>x.platform===p.id||x.platform_name===p.name);const [label,klass]=accountState(a);const active=(state.activePlatform||currentId)===p.id;return `<button class="kz-platform-item ${active?'active':''}" data-kz-platform="${p.id}">${icon(p)}<span><b>${esc(p.name)}</b><small>${esc(a?.label||a?.alias||label)}</small></span></button>`;}).join('');
    dock.querySelectorAll('[data-kz-platform]').forEach(btn=>btn.addEventListener('click',()=>{state.activePlatform=btn.dataset.kzPlatform;renderCockpit();switchTab('platform');}));
  }

  function renderAccounts(accounts){const box=document.getElementById('kz-account-list');if(!box)return;if(!accounts.length){box.innerHTML='<div class="social-empty" style="padding:12px">这台手机尚未绑定平台账号。可回到设备矩阵添加。</div>';return;}box.innerHTML=accounts.map(a=>{const p=platformBy(a.platform||a.platform_name);const [label,klass]=accountState(a);return `<div class="kz-account-row">${icon(p,true)}<span><b>${esc(p.name)} · ${esc(a.label||a.alias||'未命名账号')}</b><small>${esc(a.alias||'')} · ${a.automation_paused?'自动化已暂停':'自动化状态正常'}</small></span><span class="kz-state-tag ${klass}">${esc(label)}</span></div>`;}).join('');}

  function renderRunChain(d,accounts){const box=document.getElementById('kz-run-chain');if(!box)return;const bound=PLATFORM_META.filter(p=>p.id!=='other').filter(p=>accounts.some(a=>a.platform===p.id||a.platform_name===p.name));const current=currentPlatformId(d);if(!bound.length){box.innerHTML='<span class="social-subtle">尚未绑定平台，运行链待配置。</span>';document.getElementById('kz-task-progress').textContent='0 / 0';return;}box.innerHTML=bound.map((p,index)=>{const a=accounts.find(x=>x.platform===p.id||x.platform_name===p.name);const [status]=accountState(a);const klass=p.id===current?'running':status==='待人工'?'waiting':status==='已登录'?'ready':'';return `${index?'<span class="kz-chain-arrow">→</span>':''}<span class="kz-chain-step ${klass}">${esc(p.name)} · ${p.id===current?'当前':status}</span>`;}).join('');document.getElementById('kz-task-progress').textContent=`${current?1:0} / ${bound.length}`;}

  function buildTodos(d,accounts){const rows=[];if(!d?.connected)rows.push(['手机离线','检查 USB / ADB 连接','danger']);if(d?.screen_state==='secure_lock')rows.push(['手机安全锁定','请人工解锁后再交还 R8','danger']);else if(d?.screen_state==='keyguard')rows.push(['手机停留在锁屏界面','请人工确认解锁','waiting']);accounts.forEach(a=>{const [label,klass]=accountState(a);if(['待人工','已退出'].includes(label))rows.push([`${platformBy(a.platform||a.platform_name).name} · ${a.label||a.alias||'账号'}`,label==='已退出'?'需要重新登录':'需要人工确认',klass]);});const [risk,riskKind]=riskLabel(d?.risk_level);if(risk==='高风险')rows.push(['终端风险状态','已暂停高风险自动操作',riskKind]);return rows;}

  function renderCockpit(){const d=currentDevice();const accounts=deviceAccounts();const [screen,sKind]=screenLabel(d);const [risk,rKind]=riskLabel(d?.risk_level);const score=healthScore(d);const currentP=platformBy(state.activePlatform||d?.platform);const currentAccount=accounts.find(a=>a.platform===currentP.id||a.platform_name===currentP.name);const currentTask=d?.current_task||'空闲';
    const dot=document.getElementById('kz-summary-dot');if(dot)dot.className=`kz-dot ${d?.connected?'ok':'stop'}`;const set=(id,value)=>{const node=document.getElementById(id);if(node)node.textContent=value;};
    set('kz-summary-device',d?.connected?`${d.model||'Android'} · 在线`:'等待真机');set('kz-summary-platform',currentAccount?`${currentP.name} · ${currentAccount.label||currentAccount.alias||'账号'}`:(d?.platform||'未绑定'));set('kz-summary-task',currentTask);set('kz-summary-mode',modeLabel(d?.control_mode));set('kz-summary-health',`${score} / 100`);set('kz-task-current',currentTask);set('kz-task-next',currentTask==='空闲'?'等待任务队列':'由当前任务调度决定');set('kz-health-score',String(score));set('kz-health-note',score>=85?'状态良好':score>=65?'存在待处理项':'需要优先处理异常');
    const riskNode=document.getElementById('r8-device-risk');if(riskNode)riskNode.textContent=risk;const riskPill=document.getElementById('r8-status-risk');if(riskPill){riskPill.textContent=`风险：${risk}`;riskPill.className=`r8-console-pill ${rKind}`;}
    const screenNode=document.getElementById('r8-device-awake');if(screenNode)screenNode.textContent=screen;const todo=buildTodos(d,accounts);const list=document.getElementById('kz-todo-list');if(list)list.innerHTML=todo.length?todo.map(x=>`<div class="kz-todo"><span><b>${esc(x[0])}</b><br><small>${esc(x[1])}</small></span><span class="kz-state-tag ${x[2]}">处理</span></div>`).join(''):'<div class="kz-todo ok"><span><b>当前无需人工处理</b><br><small>AI 可继续在安全边界内运行</small></span><span class="kz-state-tag ready">正常</span></div>';
    const owner=document.getElementById('kz-owner-todo');if(owner){owner.textContent=todo.length?`需要我处理 ${todo.length}`:'当前无需人工处理';owner.classList.toggle('zero',todo.length===0);}
    renderDock(d,accounts);renderAccounts(accounts);renderRunChain(d,accounts);decoratePlatformIcons();
  }

  async function refreshCockpit(){if(!ensureCockpit())return;const results=await Promise.allSettled([request('/api/r8/social'),request('/api/r8/device/status')]);if(results[0].status==='fulfilled')state.social=results[0].value;if(results[1].status==='fulfilled')state.device=results[1].value;renderCockpit();}
  function startRefresh(){stopRefresh();refreshTimer=setInterval(()=>{const panel=document.getElementById('r8-device-center');if(panel&&!panel.hidden)refreshCockpit();},5000);}
  function stopRefresh(){if(refreshTimer){clearInterval(refreshTimer);refreshTimer=null;}}

  const observer=new MutationObserver(()=>{decoratePlatformIcons();if(!initialized)ensureCockpit();});observer.observe(document.documentElement,{childList:true,subtree:true});
  let attempts=0;const boot=setInterval(()=>{attempts++;if(ensureCockpit()||attempts>80){clearInterval(boot);if(initialized)refreshCockpit();}},125);
})();