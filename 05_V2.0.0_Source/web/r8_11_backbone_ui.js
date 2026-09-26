(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const get = id => document.getElementById(id);
  async function json(path){
    const response = await fetch(path,{cache:'no-store'});
    const data = await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  function ensureStyles(){
    if(get('r811-style')) return;
    const style=document.createElement('style');style.id='r811-style';style.textContent=`
      .r811-card{margin:14px 0;padding:16px;border:1px solid #dfe6f2;border-radius:16px;background:#fff}.r811-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.r811-head h3{margin:3px 0}.r811-pill{padding:6px 9px;border-radius:999px;background:#eef5ff;color:#285ba6;font-weight:700;white-space:nowrap}.r811-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.r811-grid>div{padding:10px;border:1px solid #e4eaf2;border-radius:10px}.r811-grid small,.r811-channel-row small{display:block;color:#718096}.r811-grid b{display:block;margin-top:3px;word-break:break-word}.r811-channel-list{display:grid;gap:7px;margin-top:12px}.r811-channel-row{display:grid;grid-template-columns:1.1fr .8fr .8fr 1.8fr;gap:10px;align-items:center;padding:10px;border:1px solid #e5eaf1;border-radius:10px}.r811-channel-row strong{font-size:13px}.r811-ok{color:#13865f}.r811-wait{color:#b56c12}.r811-route b{display:block;font-size:12px}.r811-route small{margin-top:2px}.r811-note{margin-top:10px;padding:10px;border-radius:10px;background:#f7f9fc;color:#5f6f82}.r811-refresh{border:1px solid #d7e0ed;background:#fff;border-radius:9px;padding:7px 10px;cursor:pointer}@media(max-width:900px){.r811-grid{grid-template-columns:repeat(2,1fr)}.r811-channel-row{grid-template-columns:1fr 1fr}}`;
    document.head.appendChild(style);
  }
  function ensureMissionCard(){
    const page=get('dashboard'); if(!page) return null;
    let card=get('r811-mission-backbone');
    if(!card){
      card=document.createElement('section');card.id='r811-mission-backbone';card.className='r811-card';
      const anchor=page.querySelector('#r810-command') || page.querySelector('.command-welcome') || page.firstElementChild;
      anchor?.insertAdjacentElement('afterend',card);
    }
    return card;
  }
  function ensureChannelCard(){
    const page=get('connections'); if(!page) return null;
    let card=get('r811-channel-center');
    if(!card){
      card=document.createElement('section');card.id='r811-channel-center';card.className='r811-card';
      page.querySelector('.page-title')?.insertAdjacentElement('afterend',card);
    }
    return card;
  }
  function renderMission(ledger){
    const card=ensureMissionCard(); if(!card) return;
    const m=ledger.active_mission || {};
    const cmd=m.command || {};
    const video=m.active_video || {};
    const pub=m.latest_platform_receipt || {};
    const execution=m.execution || {}, states=execution.states || {}, localReceipt=execution.latest_local_receipt || {};
    card.innerHTML=`<div class="r811-head"><div><small>R8-18 · MISSION CONTROL LEDGER</small><h3>ChatGPT 指令到真实经营结果的统一账本</h3><p>每一步都绑定同一 Mission；缺少真实证据时保持待验证。</p></div><button class="r811-refresh" data-r811-refresh>刷新</button></div><div class="r811-grid"><div><small>ChatGPT Command</small><b>${esc(cmd.command_id || '等待总控指令')}</b></div><div><small>指令状态 / 通道</small><b>${esc(cmd.status || '未绑定')}<br>${esc(cmd.transport || '')}</b></div><div><small>Mission / Growth</small><b>${esc(m.mission_id || '尚无')}<br>${esc(m.growth_id || '')}</b></div><div><small>当前阶段</small><b>${esc(m.stage || '等待任务')}</b></div><div><small>本地任务</small><b>待执行 ${esc(states.queued ?? 0)} · 运行 ${esc(states.running ?? 0)}<br>已完成 ${esc(states.completed ?? 0)}</b></div><div><small>本地执行回执</small><b>${esc(execution.local_execution_receipts ?? 0)}${localReceipt.receipt_id?`<br>${esc(localReceipt.receipt_id)}`:''}</b></div><div><small>当前视频</small><b>${esc(video.video_id || '尚无')}<br>${esc(video.status || '')}</b></div><div><small>真实发布回执</small><b>${esc(pub.receipt_id || '尚未取得')}</b></div><div><small>已验证发布</small><b>${esc(m.verified_publications ?? 0)}</b></div><div><small>下一步</small><b>${esc(m.next_action || '等待 Mission')}</b></div></div><div class="r811-note">${esc(execution.truth || m.truth || ledger.truth_rule || '只有真实平台回执和经营数据才能升级结果状态。')}</div>`;
    card.querySelector('[data-r811-refresh]')?.addEventListener('click',refresh);
  }
  function renderChannels(registry,routes){
    const card=ensureChannelCard(); if(!card) return;
    const rows=registry.channels || [], summary=registry.summary || {};
    const routeMap=new Map((routes.routes||[]).map(row=>[row.channel_id,row]));
    const routeSummary=routes.summary||{};
    card.innerHTML=`<div class="r811-head"><div><small>R8-11 · 全渠道连接中心</small><h3>所有获客渠道统一管理真实连接与执行路由</h3><p>软件路由已登记不等于外部平台已登录；外部状态必须现场验证。</p></div><span class="r811-pill">无需付费第三方 Token</span></div><div class="r811-grid"><div><small>已登记渠道</small><b>${esc(summary.registered ?? rows.length)}</b></div><div><small>软件路由已接入</small><b>${esc(summary.software_route_ready ?? 0)}</b></div><div><small>可准备/可干跑路由</small><b>${esc(routeSummary.ready_or_preparable ?? 0)}</b></div><div><small>需购买 Token</small><b>${esc(summary.paid_token_required ?? 0)}</b></div></div><div class="r811-channel-list">${rows.map(row=>{const route=routeMap.get(row.id)||{};return `<div class="r811-channel-row"><div><b>${esc(row.name)}</b><small>${esc(row.group)}</small></div><strong class="${row.software_route_ready?'r811-ok':'r811-wait'}">${row.software_route_ready?'软件路由已接':'未接'}</strong><strong class="${row.external_verified?'r811-ok':'r811-wait'}">${row.external_verified?'外部已验证':'待现场验证'}</strong><div class="r811-route"><b>${esc(route.route_state || row.state || '待检查')}</b><small>${esc(route.next_action || row.execution || row.mode || '')}</small></div></div>`}).join('')}</div><div class="r811-note">不购买第三方平台 Token。社媒使用真实安卓 + 真实账号；验证码、短信、人脸和最终发布授权保留人工门。路由可用也不等于发布成功，真实 Post ID / URL / Receipt 才算完成。</div>`;
  }
  async function refresh(){
    try{
      const [ledger,channels,routes]=await Promise.all([json('/api/r8-11/mission-ledger'),json('/api/r8-11/channels'),json('/api/r8-11/channel-routes')]);
      renderMission(ledger); renderChannels(channels,routes);
    }catch(error){
      const card=ensureMissionCard(); if(card) card.innerHTML=`<div class="r811-note">R8-11 主链状态读取失败：${esc(error.message)}</div>`;
    }
  }
  function boot(){ensureStyles();refresh();setInterval(refresh,30000)}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
