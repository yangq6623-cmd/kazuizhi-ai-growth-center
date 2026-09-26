(() => {
  'use strict';

  const R810 = {
    connector: {status: 'unverified', label: '未验证连接', last_command_id: '', last_receipt_at: '', permissions: []},
    factory: null,
    mission: null,
    booted: false,
    decorating: false,
  };

  const PRIMARY = [
    {label:'老板总控', icon:'总', target:'dashboard'},
    {label:'AI决策中心', icon:'策', target:'workflow'},
    {label:'执行中心', icon:'执', target:'operational-hub'},
    {label:'待我处理', icon:'待', target:'r810-attention', badge:true},
    {label:'经营结果', icon:'果', target:'analytics'},
    {label:'自进化中心', icon:'进', target:'r810-evolution'},
  ];
  const SECONDARY = [
    {label:'系统状态与连接', icon:'连', target:'connections'},
    {label:'历史与审计', icon:'历', target:'history'},
    {label:'高级设置', icon:'设', target:'connections', action:'advanced'},
  ];
  const PRIMARY_TARGETS = new Set(PRIMARY.map(x=>x.target));
  const CHILD_TO_PRIMARY = {
    insights:'workflow',review:'workflow',plan:'workflow',memory:'workflow',
    promotion:'operational-hub',automation:'operational-hub',summary:'analytics',
  };

  function q(id){return document.getElementById(id)}
  function escapeHtml(value){return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
  async function safeApi(path, options){
    try { return await api(path, options); } catch (error) { return {__error:true, message:error?.message||String(error)}; }
  }
  function showNotice(message, type='ok'){
    if(typeof toast==='function'){toast(message,type);return}
    const node=q('r810-button-reason'); if(!node)return;
    node.textContent=message; node.classList.add('show'); clearTimeout(node._timer); node._timer=setTimeout(()=>node.classList.remove('show'),2800);
  }
  function openRoute(target, options={}){
    if(typeof openPage==='function') openPage(target);
    else {
      document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id===target));
    }
    setNavActive(CHILD_TO_PRIMARY[target]||target);
    if(options.advanced) setTimeout(()=>document.querySelector('.r810-backup-ai')?.scrollIntoView({behavior:'smooth',block:'center'}),80);
    if(target==='analytics') setTimeout(refreshBusinessVisuals,260);
    if(target==='r810-attention') refreshAttention();
    if(target==='r810-evolution') refreshEvolutionSummary(false);
  }
  function setNavActive(target){
    document.querySelectorAll('.r810-nav-button').forEach(btn=>btn.classList.toggle('active',btn.dataset.target===target && btn.dataset.action!=='advanced'));
  }

  function ensureProxyPage(id, title, subtitle){
    if(!q(id)){
      const section=document.createElement('section'); section.id=id; section.className='page';
      const main=document.querySelector('main'); main?.appendChild(section);
    }
    const nav=document.querySelector('aside nav');
    if(nav&&!nav.querySelector(`.nav[data-page="${id}"]`)){
      const proxy=document.createElement('button'); proxy.className='nav r810-legacy-route'; proxy.dataset.page=id; proxy.dataset.title=title; proxy.dataset.subtitle=subtitle; proxy.hidden=true; proxy.textContent=title; nav.appendChild(proxy);
    }
  }

  function rebuildNavigation(){
    const nav=document.querySelector('aside nav'); if(!nav||nav.querySelector('.r810-primary-nav'))return;
    [...nav.children].forEach(child=>child.classList.add('r810-legacy-route'));
    const title=document.createElement('small'); title.className='r810-nav-title'; title.textContent='自治运营';
    const primary=document.createElement('div'); primary.className='r810-primary-nav';
    primary.innerHTML=PRIMARY.map(item=>`<button class="r810-nav-button${item.target==='dashboard'?' active':''}" data-target="${item.target}"><span class="r810-icon">${item.icon}</span><span>${item.label}</span>${item.badge?'<small id="r810-attention-badge" hidden>0</small>':''}</button>`).join('');
    const secondary=document.createElement('div'); secondary.className='r810-secondary-nav';
    secondary.innerHTML=SECONDARY.map(item=>`<button class="r810-nav-button secondary" data-target="${item.target}"${item.action?` data-action="${item.action}"`:''}><span class="r810-icon">${item.icon}</span><span>${item.label}</span></button>`).join('');
    nav.prepend(title,primary); nav.appendChild(secondary);
    nav.querySelectorAll('.r810-nav-button').forEach(btn=>btn.addEventListener('click',()=>openRoute(btn.dataset.target,{advanced:btn.dataset.action==='advanced'})));
    const brandSmall=document.querySelector('aside .brand small'); if(brandSmall)brandSmall.textContent='AI 自治运营工作台';
    const baseline=document.querySelector('.baseline'); if(baseline)baseline.innerHTML='<b>R8-10 · #398 开发版</b><br><span>单工作台 · 真实执行 · 真实回执</span><code>基于 #397 稳定底座</code>';
  }

  function ensureMissionBar(){
    if(q('r810-mission-bar'))return;
    const main=document.querySelector('main'); const header=main?.querySelector(':scope > header'); if(!main||!header)return;
    const bar=document.createElement('div'); bar.id='r810-mission-bar'; bar.className='r810-mission-bar';
    bar.innerHTML=`<div class="r810-mission-main"><small>当前 Mission</small><b id="r810-mission-title">正在读取真实任务状态…</b><span id="r810-mission-goal">目标与执行链统一显示在这里</span></div><div class="r810-mission-state"><span id="r810-ai-state" class="r810-state-pill">ChatGPT总控：未验证</span><span id="r810-stage-state" class="r810-state-pill running">阶段：读取中</span><span id="r810-human-state" class="r810-state-pill">待我处理：0</span></div><div class="r810-mission-actions"><button data-r810-route="workflow">查看AI决策</button><button data-r810-route="operational-hub">查看流水线</button></div>`;
    header.insertAdjacentElement('afterend',bar);
    bar.querySelectorAll('[data-r810-route]').forEach(btn=>btn.addEventListener('click',()=>openRoute(btn.dataset.r810Route)));
  }

  function stageForMission(factory, missionId){
    const videos=(factory?.videos||[]).filter(x=>!missionId||x.campaign_id===missionId);
    if(!videos.length)return '等待执行计划';
    const states=videos.map(x=>String(x.status||''));
    if(states.some(x=>x==='异常待处理'))return '异常待处理';
    if(states.some(x=>x==='等待人工审核'))return '成片审核';
    if(states.some(x=>['发布执行中','等待最佳时间','等待账号','已授权发布'].includes(x)))return '平台发布';
    if(states.some(x=>['生产中','技术质检','等待生产','等待素材路由','等待ChatGPT质检'].includes(x)))return '内容生产';
    if(states.some(x=>['等待ChatGPT策划','退回重做'].includes(x)))return 'AI策划';
    if(states.some(x=>x==='已发布'))return '结果观察';
    return states[0]||'自动处理中';
  }

  async function readConnectorState(){
    const result=await safeApi('/api/chatgpt-control/status');
    if(result&&!result.__error){
      const verified=Boolean(result.verified||result.status==='verified'||result.status==='connected_verified');
      R810.connector={
        status:verified?'verified':(result.status||'authorized'),
        label:verified?'已验证连接':(result.status_label||'已授权待验证'),
        last_command_id:result.last_command_id||'',
        last_receipt_at:result.last_receipt_at||'',
        permissions:Array.isArray(result.permissions)?result.permissions:[],
      };
    }else{
      R810.connector={status:'unverified',label:'未验证连接',last_command_id:'',last_receipt_at:'',permissions:[]};
    }
    return R810.connector;
  }

  async function refreshMission(){
    // The Mission Ledger is the identity source of truth.  Content Factory is
    // only a production child of that Mission, so an empty/stale campaign must
    // never make the owner-facing decision center say that no Mission exists.
    const [factory,ledger]=await Promise.all([safeApi('/api/content-factory'),safeApi('/api/r8-11/mission-ledger'),readConnectorState()]);
    if(factory&&!factory.__error)R810.factory=factory;
    const campaigns=R810.factory?.campaigns||[];
    const activeId=R810.factory?.active_campaign_id||campaigns[0]?.id||'';
    const factoryMission=campaigns.find(x=>x.id===activeId)||campaigns[0]||null;
    const ledgerMission=ledger&&!ledger.__error&&ledger.active_mission&&ledger.active_mission.mission_id
      ? ledger.active_mission : null;
    const mission=ledgerMission||factoryMission||null; R810.mission=mission;
    const missionId=mission?.mission_id||mission?.id||'';
    const title=q('r810-mission-title'),goal=q('r810-mission-goal'),ai=q('r810-ai-state'),stage=q('r810-stage-state'),human=q('r810-human-state');
    if(title)title.textContent=mission?`${missionId} · ${mission.title||mission.service||'当前增长任务'}`:'尚无运行中的 Mission';
    if(goal)goal.textContent=mission?`老板目标：${mission.goal||'等待明确经营目标'}`:'在老板总控下达目标后，由系统建立统一 Mission';
    if(ai){const ok=R810.connector.status==='verified';ai.textContent=`ChatGPT总控：${R810.connector.label}`;ai.className=`r810-state-pill ${ok?'ok':'attention'}`}
    if(stage){const text=ledgerMission?.stage||stageForMission(R810.factory,mission?.id);stage.textContent=`阶段：${text}`;stage.className=`r810-state-pill ${text.includes('异常')?'error':text.includes('审核')?'attention':'running'}`}
    const count=Number(R810.factory?.action_center?.human_count||0); if(human){human.textContent=`待我处理：${count}`;human.className=`r810-state-pill ${count?'attention':'ok'}`}
    const badge=q('r810-attention-badge');if(badge){badge.textContent=String(count);badge.hidden=!count}
    updateCommandAvailability();
  }

  function ensureBossCommand(){
    const dashboard=q('dashboard'); if(!dashboard||q('r810-command'))return;
    const box=document.createElement('div');box.id='r810-command';box.className='r810-command';
    box.innerHTML=`<div><label for="r810-owner-command">告诉 ChatGPT 你希望什么经营结果发生</label><textarea id="r810-owner-command" maxlength="1200" placeholder="例如：这周重点推广涟水县水电维修，提高真实咨询和订单。"></textarea><small id="r810-command-note" class="r810-command-note">正在验证 ChatGPT 总控连接…</small></div><button id="r810-send-command" disabled title="只有完成 ChatGPT 双向总控验证后才能直接下达经营指令">下达目标</button>`;
    dashboard.prepend(box);
    q('r810-send-command')?.addEventListener('click',sendOwnerCommand);
  }
  function updateCommandAvailability(){
    const button=q('r810-send-command'),note=q('r810-command-note');if(!button||!note)return;
    const verified=R810.connector.status==='verified';button.disabled=!verified;
    button.title=verified?'将目标交给 ChatGPT 总控并形成 Mission':'当前 ChatGPT Control Connector 尚未完成双向验证；文件桥或 API 配置不等于 ChatGPT 已连接';
    note.textContent=verified?`总控已验证${R810.connector.last_command_id?` · 最近指令 ${R810.connector.last_command_id}`:''}`:'未验证真实双向连接：本地任务仍可离线运行，但不会伪装成 ChatGPT 已接管。';
  }
  async function sendOwnerCommand(){
    const input=q('r810-owner-command');const objective=input?.value.trim();if(!objective){showNotice('请先填写经营目标','error');return}
    if(R810.connector.status!=='verified'){showNotice('ChatGPT 总控尚未完成双向验证','error');return}
    const button=q('r810-send-command');button.disabled=true;button.textContent='正在下达…';
    const result=await safeApi('/api/chatgpt-control/commands',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({objective,source:'owner_workbench'})});
    button.textContent='下达目标';button.disabled=false;
    if(result.__error){showNotice(`指令未送达：${result.message}`,'error');return}
    input.value='';showNotice(`指令已接收${result.command_id?`：${result.command_id}`:''}`);await refreshMission();
  }

  function ensureDecisionSubtabs(){
    const page=q('workflow');if(!page||page.querySelector('.r810-subtabs'))return;
    const tabs=document.createElement('div');tabs.className='r810-subtabs';
    const items=[['workflow','今日决策'],['insights','市场机会'],['review','经营复盘'],['plan','下一步计划'],['memory','运营记忆']];
    tabs.innerHTML=items.map(([target,label],i)=>`<button class="r810-subtab${i===0?' active':''}" data-target="${target}">${label}</button>`).join('');
    page.querySelector('.page-title')?.insertAdjacentElement('afterend',tabs);
    tabs.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>openRoute(btn.dataset.target)));
    const title=page.querySelector('.page-title h2');if(title)title.textContent='AI 决策中心';
    const intro=page.querySelector('.page-title p');if(intro)intro.textContent='R7 负责收集真实环境、市场机会和经营结果；ChatGPT 负责最终判断与 Mission 决策。';
  }

  function ensureExecutionTabs(){
    const hub=q('operational-hub');if(!hub)return;
    const intro=hub.querySelector('.operational-hub-intro');if(intro){
      const h2=intro.querySelector('h2');if(h2)h2.textContent='执行中心';
      const p=intro.querySelector('p');if(p)p.textContent='内容、品牌增长、平台、真机和转化都在同一执行视图完成；不再出现第二套工作台。';
    }
    if(hub.querySelector('.r810-execution-tabs'))return;
    const tabs=document.createElement('div');tabs.className='r810-execution-tabs';
    const items=[['dashboard','执行总览'],['content','内容生产'],['search','品牌增长'],['accounts','平台账号'],['device','真机执行'],['conversion','咨询与订单'],['health','执行健康']];
    tabs.innerHTML=items.map(([page,label],i)=>`<button class="${i===0?'active':''}" data-execution-page="${page}">${label}</button>`).join('');
    intro?.appendChild(tabs);
    tabs.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>switchExecutionPage(btn.dataset.executionPage,btn)));
  }
  function switchExecutionPage(page,button){
    openRoute('operational-hub');
    const frame=q('operational-frame');
    const activate=()=>{try{frame?.contentWindow?.changeOperationalPage?.(page)}catch(error){showNotice('执行中心页面切换失败，请刷新后重试','error')}};
    if(frame){if(frame.contentDocument?.readyState==='complete')activate();else frame.addEventListener('load',activate,{once:true})}
    document.querySelectorAll('.r810-execution-tabs button').forEach(x=>x.classList.toggle('active',x===button));
  }

  function buildAttentionPage(){
    const page=q('r810-attention');if(!page)return;
    page.innerHTML=`<div class="r810-page-intro"><div><small>唯一人工入口</small><h2>待我处理</h2><p>只有 AI 和本地自动恢复无法替你完成的事情才出现在这里：最终成片、登录验证、风控、重大风险与真正异常。</p></div><div class="r810-kicker"><button class="r810-action" id="r810-refresh-attention">刷新</button></div></div><div class="r810-kpi-grid"><div class="r810-kpi"><small>当前需要你</small><b id="r810-human-total">0</b><span>其余任务继续自动运行</span></div><div class="r810-kpi"><small>最终成片审核</small><b id="r810-video-review">0</b><span>未审核默认不发布</span></div><div class="r810-kpi"><small>账号/验证</small><b id="r810-login-human">0</b><span>扫码、人脸、验证码</span></div><div class="r810-kpi"><small>自动恢复失败</small><b id="r810-hard-errors">0</b><span>达到重试/降级上限</span></div></div><div class="r810-card"><div class="r810-card-head"><div><small>需要老板处理</small><b>按优先级集中到一个入口</b></div></div><div id="r810-attention-list" class="r810-attention-list"><div class="r810-empty">正在读取真实状态…</div></div></div>`;
    q('r810-refresh-attention')?.addEventListener('click',refreshAttention);
  }
  async function refreshAttention(){
    const factory=await safeApi('/api/content-factory');if(!factory.__error){R810.factory=factory;await refreshMission()}
    const items=R810.factory?.action_center?.human_items||[];
    const videos=R810.factory?.videos||[];
    const review=videos.filter(x=>x.status==='等待人工审核').length;
    const hard=videos.filter(x=>x.status==='异常待处理'&&Number(x.retry_count||0)>=3).length;
    const login=items.filter(x=>String(x.id||'').includes('account')||String(x.title||'').includes('账号')).length;
    if(q('r810-human-total'))q('r810-human-total').textContent=String(items.length);
    if(q('r810-video-review'))q('r810-video-review').textContent=String(review);
    if(q('r810-login-human'))q('r810-login-human').textContent=String(login);
    if(q('r810-hard-errors'))q('r810-hard-errors').textContent=String(hard);
    const list=q('r810-attention-list');if(!list)return;
    if(!items.length){list.innerHTML='<div class="r810-empty">当前没有必须由你处理的事项。系统可以继续自动执行已批准 Mission。</div>';return}
    list.innerHTML=items.map((item,index)=>`<div class="r810-attention-item"><div class="r810-attention-icon">${index+1}</div><div><b>${escapeHtml(item.title||'需要处理')}</b><span>${escapeHtml(item.detail||'请打开对应执行环节查看。')}</span></div><button class="r810-action primary" data-attention-page="${escapeHtml(item.page||'dashboard')}">${escapeHtml(item.action||'去处理')}</button></div>`).join('');
    list.querySelectorAll('[data-attention-page]').forEach(btn=>btn.addEventListener('click',()=>{
      const page=btn.dataset.attentionPage;
      if(['content','accounts','device','search','conversion'].includes(page))switchExecutionPage(page,document.querySelector(`[data-execution-page="${page}"]`));else openRoute(page);
    }));
  }

  function buildEvolutionPage(){
    const page=q('r810-evolution');if(!page)return;
    page.innerHTML=`<div class="r810-page-intro"><div><small>受控软件进化</small><h2>自进化中心</h2><p>系统先发现问题，ChatGPT 判断是否值得改代码；只有确认的软件问题才进入 DEV-MISSION，Codex 不参与日常运营。</p></div><div class="r810-kicker"><button class="r810-action primary" id="r810-run-evolution-check">运行系统体检</button><button class="r810-action" data-r810-evolution-route="history">查看历史与审计</button></div></div><div class="r810-status-grid"><div class="r810-status-card"><small>正式生产版本</small><b>#397 稳定底座</b><span>继续作为回滚基线，不直接修改生产程序。</span></div><div class="r810-status-card"><small>当前开发阶段</small><b>#398 · R8-10</b><span>工作台、连接真值、按钮与产品体验收口。</span></div><div class="r810-status-card"><small>Codex运行策略</small><b>按需开发</b><span>普通运营不调用；确认代码缺陷后才创建 DEV-MISSION。</span></div></div><div class="r810-card"><div class="r810-card-head"><div><small>系统优化候选</small><b>只从真实体检和重复故障产生</b></div><button class="r810-action" id="r810-open-system-status">系统状态与连接</button></div><div id="r810-evolution-list"><div class="r810-empty">点击“运行系统体检”生成本次真实优化候选；不会虚构软件缺陷。</div></div></div><div class="r810-card"><div class="r810-card-head"><div><small>DEV-MISSION</small><b>ChatGPT判断 → Codex修改 → CI → Candidate → Stable/回滚</b></div><button class="r810-action" id="r810-dev-mission-disabled" disabled title="#398 先完成受控入口与诊断；自动创建 DEV-MISSION 的后端写入接口将在自进化阶段接入">创建开发任务</button></div><div class="r810-ai-readout"><b>当前规则：</b>普通网络、ADB、FFmpeg、GPU和发布超时先由本地重试/降级处理；只有重复失败且确认属于代码或产品缺陷，才允许进入 Codex 开发队列。</div></div>`;
    q('r810-run-evolution-check')?.addEventListener('click',()=>refreshEvolutionSummary(true));
    q('r810-open-system-status')?.addEventListener('click',()=>openRoute('connections'));
    page.querySelectorAll('[data-r810-evolution-route]').forEach(btn=>btn.addEventListener('click',()=>openRoute(btn.dataset.r810EvolutionRoute)));
  }
  async function refreshEvolutionSummary(run){
    if(!run)return;
    const button=q('r810-run-evolution-check');if(button){button.disabled=true;button.textContent='体检中…'}
    const data=await safeApi('/api/system/diagnostics',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    if(button){button.disabled=false;button.textContent='重新运行体检'}
    const list=q('r810-evolution-list');if(!list)return;
    if(data.__error){list.innerHTML=`<div class="r810-empty">系统体检未完成：${escapeHtml(data.message)}</div>`;return}
    const candidates=(data.checks||[]).filter(x=>x.status!=='pass');
    if(!candidates.length){list.innerHTML='<div class="r810-empty">本次关键检查全部通过。当前没有证据支持创建新的软件开发任务。</div>';return}
    list.innerHTML=candidates.map(x=>`<div class="r810-attention-item"><div class="r810-attention-icon">!</div><div><b>${escapeHtml(x.name||'待检查')}</b><span>${escapeHtml(x.message||'需要进一步确认原因')}</span></div><button class="r810-action" data-evolution-system>查看系统状态</button></div>`).join('');
    list.querySelectorAll('[data-evolution-system]').forEach(btn=>btn.addEventListener('click',()=>openRoute('connections')));
  }

  function ensureConnectionUX(){
    const page=q('connections');if(!page)return;
    const title=page.querySelector('.page-title h2');if(title)title.textContent='系统状态与连接';
    const intro=page.querySelector('.page-title p');if(intro)intro.textContent='这里负责保证 ChatGPT总控、本地自治、执行资源、平台终端和经营数据之间的真实连接；没有往返验证就不显示“已连接”。';
    if(!q('r810-connector-card')){
      const card=document.createElement('div');card.id='r810-connector-card';card.className='r810-connector-card';
      card.innerHTML=`<div><small>CHATGPT CONTROL CONNECTOR</small><h3>ChatGPT 总控连接</h3><p id="r810-connector-copy">正在检查是否存在真实的双向总控接口…</p><p class="r810-connection-warning">文件夹可写、运营桥在线或备用 API 已配置，都不能单独证明 ChatGPT 已连接。</p></div><div class="r810-connector-meta"><div><small>连接状态</small><b id="r810-connector-status">未验证</b></div><div><small>最近 Command ID</small><b id="r810-connector-command">—</b></div><div><small>最近执行回执</small><b id="r810-connector-receipt">—</b></div><div><small>允许能力</small><b id="r810-connector-permissions">仅读取本地状态</b></div></div>`;
      page.querySelector('.page-title')?.insertAdjacentElement('afterend',card);
    }
    const layout=page.querySelector('.connection-layout');const aiCard=layout?.querySelector(':scope > article:first-child');
    if(aiCard&&!aiCard.closest('.r810-backup-ai')){
      aiCard.querySelector('label')&&(aiCard.querySelector('label').textContent='备用 AI 接口（可选）');
      const h3=aiCard.querySelector('h3');if(h3)h3.textContent='仅用于高级灾备，不是正常运营必需项';
      const msg=q('ai-connection-message');if(msg)msg.textContent='默认关闭。ChatGPT 总控与本地自治是主链；只有明确启用备用 API 时才需要这里的密钥。';
      const details=document.createElement('details');details.className='r810-backup-ai';
      const summary=document.createElement('summary');summary.textContent='高级：备用 AI 接口（正常运营无需配置）';
      const body=document.createElement('div');body.className='r810-backup-body';
      aiCard.parentNode.insertBefore(details,aiCard);details.append(summary,body);body.appendChild(aiCard);
    }
    const commandCard=[...page.querySelectorAll('.ai-command-card')].find(x=>x.querySelector('#ai-command-prompt'));
    if(commandCard){const label=commandCard.querySelector('label');if(label)label.textContent='备用 AI 诊断（高级）';const h3=commandCard.querySelector('h3');if(h3)h3.textContent='仅在明确启用备用接口后使用';const chip=commandCard.querySelector('.chip');if(chip)chip.textContent='非 ChatGPT 订阅总控';}
    decorateBridgeLabels(); updateConnectorCard();
  }
  function decorateBridgeLabels(){
    const bridge=q('bridge-panel');if(!bridge)return;
    const label=bridge.querySelector('label');if(label)label.textContent='备用 / 灾备运营桥';
    const h3=bridge.querySelector('h3');if(h3)h3.textContent='用于异步上报、计划接收与执行回执；不等于 ChatGPT 已验证连接';
  }
  function updateConnectorCard(){
    const status=q('r810-connector-status'),copy=q('r810-connector-copy'),cmd=q('r810-connector-command'),receipt=q('r810-connector-receipt'),perms=q('r810-connector-permissions');if(!status)return;
    const verified=R810.connector.status==='verified';status.textContent=R810.connector.label;status.style.color=verified?'#13865f':'#b56c12';
    if(copy)copy.textContent=verified?'双向读取、指令下发与执行回执已经通过真实往返验证。':'当前没有检测到可证明 ChatGPT 订阅总控已完成双向验证的接口，因此保持“未验证连接”。';
    if(cmd)cmd.textContent=R810.connector.last_command_id||'—';if(receipt)receipt.textContent=R810.connector.last_receipt_at||'—';if(perms)perms.textContent=R810.connector.permissions.length?R810.connector.permissions.join(' / '):'尚未授予控制权限';
  }

  function ensureBusinessVisuals(){
    const page=q('analytics');if(!page||q('r810-viz-grid'))return;
    const title=page.querySelector('.page-title h2');if(title)title.textContent='经营结果';
    const intro=page.querySelector('.page-title p');if(intro)intro.textContent='重点看真实咨询、有效需求、报价、订单和服务方向强弱；所有图表只使用已经接入并验证的数据。';
    const grid=document.createElement('div');grid.id='r810-viz-grid';grid.className='r810-viz-grid';
    grid.innerHTML=`<div class="r810-viz-card wide"><div class="r810-viz-head"><b>经营转化漏斗</b><span>只使用真实经营字段</span></div><div id="r810-business-funnel" class="r810-data-missing">正在读取访问、需求、线索与订单数据…</div><div id="r810-funnel-readout" class="r810-ai-readout"><b>ChatGPT解读：</b>数据完整后，根据最大流失环节给出下一轮执行建议。</div></div><div class="r810-viz-card"><div class="r810-viz-head"><b>服务经营雷达</b><span>服务方向强弱</span></div><div class="r810-data-missing">当前生产接口尚未提供“服务分类 × 咨询/订单/完成率”维度。#398 不用虚构分数填充雷达图；接入真实服务维度后自动启用。</div><div class="r810-ai-readout"><b>验收规则：</b>雷达分值必须可追溯到真实咨询、需求、订单、完成率等经营指标。</div></div><div class="r810-viz-card"><div class="r810-viz-head"><b>区域 × 服务机会</b><span>下一步推哪里、推什么</span></div><div class="r810-data-missing">等待接入区域与服务交叉归因数据。没有真实样本时保持空状态，不展示装饰性热力图。</div><div class="r810-ai-readout"><b>目标：</b>真实数据接入后直接识别“高需求低转化”区域并形成可执行建议。</div></div>`;
    const anchor=page.querySelector('.analytics-head');if(anchor)anchor.insertAdjacentElement('afterend',grid);else page.querySelector('.page-title')?.insertAdjacentElement('afterend',grid);
    refreshBusinessVisuals();
  }
  function readMetric(containerId, index){
    const node=q(containerId)?.querySelectorAll('.analysis-values > div')?.[index]?.querySelector('b');
    if(!node)return '—';const text=node.textContent.trim();return text.includes('未接入')?'—':text;
  }
  function refreshBusinessVisuals(){
    const box=q('r810-business-funnel');if(!box)return;
    const values=[['小程序访问',readMetric('user-growth',0)],['维修需求',readMetric('user-growth',1)],['有效线索',readMetric('user-growth',3)],['新增订单',readMetric('order-conversion',1)],['完成订单',readMetric('order-conversion',2)]];
    const any=values.some(([,v])=>v!=='—');
    if(!any){box.className='r810-data-missing';box.textContent='真实经营数据尚未接入完整漏斗；不会用估算数字代替。';return}
    box.className='r810-funnel';box.innerHTML=values.map(([label,value])=>`<div class="r810-funnel-step"><small>${label}</small><b>${escapeHtml(value)}</b></div>`).join('');
    const missing=values.filter(([,v])=>v==='—').map(([label])=>label);
    const readout=q('r810-funnel-readout');if(readout)readout.innerHTML=`<b>ChatGPT解读：</b>${missing.length?`当前仍缺少 ${escapeHtml(missing.join('、'))} 数据；先补齐归因再做转化判断。`:'漏斗数据已具备基础完整度，可在下一阶段加入环节转化率与服务方向对比。'}`;
  }

  function applyOwnerCopy(){
    document.title='卡嘴子 AI 自治运营工作台 · R8-10';
    const eyebrow=document.querySelector('main>header .eyebrow');if(eyebrow)eyebrow.textContent='卡嘴子 AI · 自治运营';
    const dashHeading=document.querySelector('#dashboard .command-welcome h2');if(dashHeading)dashHeading.textContent='你负责目标和结果，其余工作沿 Mission 自动推进。';
    const badge=document.querySelector('#dashboard .welcome-badge');if(badge)badge.textContent='老板总控 · 单一运营工作台';
    const oldLink=document.querySelector('.operational-entry');if(oldLink)oldLink.style.display='none';
  }

  function auditDisabledButtons(){
    document.querySelectorAll('button:disabled').forEach(btn=>{if(!btn.title)btn.title=btn.dataset.disabledReason||'当前条件未满足；完成前置步骤后按钮会自动可用。'});
    if(!q('r810-button-reason')){const node=document.createElement('div');node.id='r810-button-reason';node.className='r810-button-reason';document.body.appendChild(node)}
  }

  function syncActiveRoute(){
    const active=document.querySelector('.page.active');const target=active?.id||'dashboard';setNavActive(CHILD_TO_PRIMARY[target]||target);
  }

  function decorate(){
    if(R810.decorating)return;R810.decorating=true;
    try{
      document.body.classList.add('r810-workbench');
      ensureProxyPage('r810-attention','待我处理','只显示必须由老板介入的事项');
      ensureProxyPage('r810-evolution','自进化中心','系统问题、优化候选与受控软件升级');
      rebuildNavigation();ensureMissionBar();ensureBossCommand();ensureDecisionSubtabs();ensureExecutionTabs();buildAttentionPage();buildEvolutionPage();ensureConnectionUX();ensureBusinessVisuals();applyOwnerCopy();auditDisabledButtons();syncActiveRoute();
    } finally {R810.decorating=false}
  }

  async function boot(){
    if(R810.booted)return;R810.booted=true;decorate();await refreshMission();await refreshAttention();updateConnectorCard();
    const observer=new MutationObserver(()=>{clearTimeout(observer._timer);observer._timer=setTimeout(()=>{decorateBridgeLabels();auditDisabledButtons();ensureExecutionTabs();ensureConnectionUX();ensureBusinessVisuals();},120)});
    observer.observe(document.body,{childList:true,subtree:true});
    document.addEventListener('click',event=>{
      const legacy=event.target.closest?.('.nav[data-page]');if(legacy)setTimeout(syncActiveRoute,0);
    },true);
    setInterval(()=>refreshMission().catch(()=>{}),30000);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,0));else setTimeout(boot,0);
})();
