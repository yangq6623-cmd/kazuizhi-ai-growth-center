(() => {
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const fmt=value=>Number(value||0).toLocaleString('zh-CN');
  const WORKSPACE_KEY='kz-search-growth-workspace';
  let geoCache={dashboard:null,questions:[],queue:[],receipts:[]};
  let currentType='all';
  let currentState='all';

  async function json(path, options){
    const response=await fetch(path,{cache:'no-store',...(options||{})});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.error||`增长服务返回 ${response.status}`);
    return data;
  }
  async function post(path, body={}){
    return json(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  }
  function campaignOptions(){
    const select=byId('search-campaign');if(!select)return;
    const selected=select.value;
    select.innerHTML='<option value="">选择增长战役</option>'+(window.state?.factory?.campaigns||[]).map(item=>`<option value="${esc(item.id)}">${esc(item.region)} · ${esc(item.service)} · ${esc(item.title)}</option>`).join('');
    select.value=selected;
  }
  function renderSeo(data){
    const audit=data.latest_audit,box=byId('search-status');
    if(box)box.innerHTML=audit?`<div class="check-item"><div><b>官网首页 ${audit.homepage_status}</b><small>robots.txt ${audit.robots_status} · sitemap.xml ${audit.sitemap_status} · 结构化数据 ${audit.has_structured_data?'有':'无'}</small></div><strong class="${audit.result==='ready'?'pass':'wait'}">${audit.result==='ready'?'技术底座通过':'需要处理'}</strong></div>${(audit.blockers||[]).map(item=>`<div class="search-blocker">${esc(item)}</div>`).join('')}`:'<p>尚未运行官网抓取检查。</p>';
    const packs=byId('search-pack-list');
    if(packs)packs.innerHTML=(data.packs||[]).length?data.packs.map(item=>`<div class="card-row"><div><b>${esc(item.page_title)}</b><span>${esc(item.id)} · ${esc(item.deployment_status)} · ${esc(item.indexing_status)}</span></div><em class="status">内容包</em></div>`).join(''):'<div class="empty">还没有本地搜索内容包。先建立增长战役，再生成同源网页、FAQ和AI短答案。</div>';
  }
  async function loadSeo(){
    campaignOptions();
    const data=await json('/api/search-growth');
    if(window.state)window.state.search=data;
    renderSeo(data);
    window.dispatchEvent(new Event('operational:search-updated'));
    return data;
  }

  function installWorkspace(){
    const page=byId('search');
    if(!page||byId('search-growth-switch'))return;
    const original=[...page.childNodes];
    const switcher=document.createElement('div');
    switcher.id='search-growth-switch';
    switcher.className='search-growth-switch';
    switcher.setAttribute('role','tablist');
    switcher.innerHTML=`
      <button type="button" class="growth-tab" data-growth-tab="seo" role="tab">SEO 增长<span>保持现有运行</span></button>
      <button type="button" class="growth-tab" data-growth-tab="geo" role="tab">GEO 增长<span>R8-19 Phase 1</span></button>`;
    const seoPane=document.createElement('div');
    seoPane.id='seo-growth-pane';seoPane.className='growth-pane';
    original.forEach(node=>seoPane.appendChild(node));
    const geoPane=document.createElement('div');
    geoPane.id='geo-growth-pane';geoPane.className='growth-pane geo-growth-pane';geoPane.hidden=true;
    geoPane.innerHTML=geoMarkup();
    page.appendChild(switcher);page.appendChild(seoPane);page.appendChild(geoPane);
    page.querySelectorAll('[data-growth-tab]').forEach(button=>button.addEventListener('click',()=>selectWorkspace(button.dataset.growthTab,true)));
    const saved=localStorage.getItem(WORKSPACE_KEY)==='geo'?'geo':'seo';
    selectWorkspace(saved,false);
    bindGeoActions();
  }

  function geoMarkup(){return `
    <div class="geo-control" aria-live="polite">
      <div class="geo-control-copy"><p class="geo-eyebrow">ChatGPT GEO 总控</p><h2 id="geo-mission">正在读取当前 Mission…</h2><p id="geo-judgement" class="geo-judgement">等待 ChatGPT 决策。</p></div>
      <div class="geo-control-meta">
        <div><span>今日目标</span><b id="geo-goal">--</b></div>
        <div><span>今日测试上限</span><b id="geo-daily-limit">--</b></div>
        <div><span>当前阻塞</span><b id="geo-blockers">--</b></div>
        <div><span>下一决策条件</span><b id="geo-next-condition">--</b></div>
      </div>
      <div class="geo-control-ids"><span id="geo-decision-id">Decision --</span><span id="geo-command-id">Command --</span></div>
    </div>

    <div class="geo-kpis" aria-label="GEO第一阶段核心指标">
      <article><span>已测试</span><strong id="geo-tested">0 / 50</strong><small>仅 A/B 级外部证据</small></article>
      <article><span>待测试</span><strong id="geo-remaining">50</strong><small>固定基准问题</small></article>
      <article><span>正在执行</span><strong id="geo-running">0</strong><small>真实外部验证</small></article>
      <article><span>成功取得证据</span><strong id="geo-evidence">0</strong><small>可追溯 Receipt</small></article>
      <article><span>失败</span><strong id="geo-failed">0</strong><small>有明确失败原因</small></article>
      <article><span>待授权</span><strong id="geo-auth">0</strong><small>只显示人工必要事项</small></article>
    </div>

    <div class="geo-actionbar">
      <button id="geo-run-round" class="geo-primary" type="button">执行本轮 GEO 测试</button>
      <button id="geo-bootstrap" class="geo-secondary" type="button">核验固定 50 问</button>
      <button id="geo-refresh" class="geo-ghost" type="button">刷新</button>
      <span id="geo-executor-state" class="geo-executor-state is-neutral">外部验证执行器：检查中</span>
    </div>

    <div id="geo-truth-banner" class="geo-truth-banner">本地模型只做辅助分析，不计入正式 GEO；正式成绩只来自真实外部 AI 的 A/B 级证据。</div>

    <div class="geo-grid">
      <article class="panel geo-panel geo-questions-panel">
        <div class="panel-head"><div><p>问题雷达</p><h3>固定 50 问 · 长期基线</h3></div><span id="geo-baseline-version" class="geo-version">--</span></div>
        <div class="geo-filters" id="geo-type-filters">
          <button class="active" data-geo-type="all">全部</button><button data-geo-type="discovery">自然发现 30</button><button data-geo-type="commercial">商业推荐 10</button><button data-geo-type="brand">品牌认知 10</button>
        </div>
        <div class="geo-filters subtle" id="geo-state-filters">
          <button class="active" data-geo-state="all">全部状态</button><button data-geo-state="unstarted">未开始</button><button data-geo-state="queued">排队</button><button data-geo-state="running">执行中</button><button data-geo-state="succeeded">已验证</button><button data-geo-state="failed">失败</button><button data-geo-state="authorization_required">待授权</button>
        </div>
        <div class="geo-table-wrap"><table class="geo-table"><thead><tr><th>ID</th><th>问题</th><th>类型</th><th>服务</th><th>意图</th><th>状态</th><th>证据</th></tr></thead><tbody id="geo-question-rows"><tr><td colspan="7">正在读取问题库…</td></tr></tbody></table></div>
        <p id="geo-baseline-note" class="geo-footnote">同一版本内基准题不可静默修改。</p>
      </article>

      <article class="panel geo-panel geo-execution-panel">
        <div class="panel-head"><div><p>执行中心 · GEO真实验证</p><h3>问题 → 外部 AI → Receipt</h3></div><span class="geo-badge is-running" id="geo-queue-total">0 个任务</span></div>
        <div class="geo-mini-kpis"><div><span>排队</span><b id="geo-queued">0</b></div><div><span>执行中</span><b id="geo-running-2">0</b></div><div><span>已完成</span><b id="geo-succeeded">0</b></div><div><span>暂停</span><b id="geo-paused">0</b></div></div>
        <div id="geo-task-list" class="geo-task-list"><div class="empty">暂无 GEO 执行任务。</div></div>
      </article>
    </div>

    <div class="geo-grid lower">
      <article class="panel geo-panel">
        <div class="panel-head"><div><p>真实证据</p><h3>GEO Evidence / Receipt</h3></div><span class="geo-badge is-success" id="geo-receipt-count">0</span></div>
        <div id="geo-receipt-list" class="geo-receipt-list"><div class="empty">尚无正式外部 GEO 证据。</div></div>
      </article>
      <article class="panel geo-panel">
        <div class="panel-head"><div><p>待我处理</p><h3>只保留 AI 无法处理的授权事项</h3></div><span class="geo-badge is-waiting" id="geo-manual-count">0</span></div>
        <div id="geo-manual-list" class="geo-manual-list"><div class="geo-ok">当前没有需要人工处理的 GEO 事项。</div></div>
        <p class="truth">登录、OAuth、验证码、账号权限等才进入这里；任务排队、普通分析和本地模型工作不会打扰老板。</p>
      </article>
    </div>`}

  function selectWorkspace(name,persist){
    const geo=name==='geo';
    byId('seo-growth-pane').hidden=geo;
    byId('geo-growth-pane').hidden=!geo;
    document.querySelectorAll('#search-growth-switch [data-growth-tab]').forEach(button=>{
      const active=button.dataset.growthTab===(geo?'geo':'seo');
      button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active));
    });
    if(persist)localStorage.setItem(WORKSPACE_KEY,geo?'geo':'seo');
    if(geo)loadGeo().catch(error=>window.notify?.(error.message,'error')); else loadSeo().catch(error=>window.notify?.(error.message,'error'));
  }

  const typeLabel={discovery:'自然发现',commercial:'商业推荐',brand:'品牌认知'};
  const stateLabel={unstarted:'未开始',queued:'排队',running:'执行中',succeeded:'已验证',failed:'失败',paused:'已暂停',authorization_required:'待授权'};
  const stateClass={unstarted:'is-neutral',queued:'is-running',running:'is-running',succeeded:'is-success',failed:'is-danger',paused:'is-neutral',authorization_required:'is-waiting'};
  function taskStateForQuestion(questionId){
    const receipt=geoCache.receipts.find(item=>item.question_id===questionId&&item.official_truth);
    if(receipt)return {state:'succeeded',evidence:receipt.evidence_id||receipt.receipt_id||''};
    const tasks=geoCache.queue.filter(item=>item.question_id===questionId);
    if(!tasks.length)return {state:'unstarted',evidence:''};
    const rank={running:6,authorization_required:5,queued:4,paused:3,failed:2,succeeded:1};
    const latest=[...tasks].sort((a,b)=>(rank[b.state]||0)-(rank[a.state]||0))[0];
    return {state:latest.state||'unstarted',evidence:latest.evidence_id||''};
  }
  function renderGeo(){
    const data=geoCache.dashboard||{},decision=data.decision||{},official=data.official||{},queue=data.queue||{},manual=data.manual||{},qset=data.question_set||{},executor=data.executor||{};
    byId('geo-mission').textContent=decision.mission_title||'涟水县 GEO 第一轮基线验证';
    byId('geo-judgement').textContent=decision.judgement||'等待 ChatGPT 决策';
    byId('geo-goal').textContent=decision.today_goal||'--';
    byId('geo-daily-limit').textContent=`${fmt(decision.daily_test_limit||0)} 题`;
    byId('geo-blockers').textContent=manual.count?`${fmt(manual.count)} 项待授权`:'0 · 无人工阻塞';
    byId('geo-next-condition').textContent=decision.next_decision_condition||'--';
    byId('geo-decision-id').textContent=`Decision ${decision.decision_id||'--'}`;
    byId('geo-command-id').textContent=`Command ${decision.command_id||'--'}`;
    byId('geo-tested').textContent=`${fmt(official.tested)} / ${fmt(qset.total||50)}`;
    byId('geo-remaining').textContent=fmt(official.remaining??50);
    byId('geo-running').textContent=fmt(queue.running);
    byId('geo-evidence').textContent=fmt(official.evidence_count);
    byId('geo-failed').textContent=fmt(queue.failed);
    byId('geo-auth').textContent=fmt(queue.authorization_required);
    byId('geo-queued').textContent=fmt(queue.queued);byId('geo-running-2').textContent=fmt(queue.running);byId('geo-succeeded').textContent=fmt(queue.succeeded);byId('geo-paused').textContent=fmt(queue.paused);
    byId('geo-queue-total').textContent=`${fmt(queue.total)} 个任务`;
    byId('geo-baseline-version').textContent=qset.version||'--';
    byId('geo-baseline-note').textContent=`基准版本 ${qset.version||'--'} · ${qset.immutable_within_version?'同版本内不可静默修改':'请检查版本规则'} · Hash ${String(qset.question_set_hash||'').slice(0,12)||'--'}…`;
    const ex=byId('geo-executor-state');
    if(ex){ex.textContent=executor.ready?`外部验证执行器：已验证 · ${executor.model||''}`:`外部验证执行器：${executor.reason||'等待连接'}`;ex.className=`geo-executor-state ${executor.ready?'is-success':'is-waiting'}`}
    renderQuestions();renderTasks();renderReceipts();renderManual();
  }
  function renderQuestions(){
    const rows=byId('geo-question-rows');if(!rows)return;
    const items=geoCache.questions.filter(item=>currentType==='all'||item.question_type===currentType).map(item=>({...item,...taskStateForQuestion(item.question_id)})).filter(item=>currentState==='all'||item.state===currentState);
    rows.innerHTML=items.length?items.map(item=>`<tr><td class="mono">${esc(item.question_id)}</td><td class="geo-question-text">${esc(item.question_text)}</td><td><span class="geo-type">${esc(typeLabel[item.question_type]||item.question_type)}</span></td><td>${esc(item.service||'--')}</td><td>${esc(item.intent||'--')}</td><td><span class="geo-badge ${stateClass[item.state]||'is-neutral'}">${esc(stateLabel[item.state]||item.state)}</span></td><td class="mono">${item.evidence?esc(item.evidence):'<span class="muted">--</span>'}</td></tr>`).join(''):'<tr><td colspan="7" class="empty">当前筛选条件没有问题。</td></tr>';
  }
  function renderTasks(){
    const box=byId('geo-task-list');if(!box)return;
    const items=[...geoCache.queue].reverse().slice(0,12);
    box.innerHTML=items.length?items.map(item=>`<div class="geo-task"><div><b>${esc(item.question_text||item.question_id)}</b><span>${esc(item.question_id)} · ${esc(item.provider||'待分配')} · 重试 ${fmt(item.retry_count)}/${fmt(item.max_retries||2)}</span>${item.failure_reason?`<small class="danger-text">${esc(item.failure_reason)}</small>`:''}${item.authorization_reason?`<small class="waiting-text">${esc(item.authorization_reason)}</small>`:''}</div><span class="geo-badge ${stateClass[item.state]||'is-neutral'}">${esc(stateLabel[item.state]||item.state)}</span></div>`).join(''):'<div class="empty">暂无 GEO 执行任务。</div>';
  }
  function renderReceipts(){
    const box=byId('geo-receipt-list');if(!box)return;
    byId('geo-receipt-count').textContent=fmt(geoCache.receipts.filter(item=>item.official_truth).length);
    const items=geoCache.receipts.slice(0,10);
    box.innerHTML=items.length?items.map(item=>`<details class="geo-receipt"><summary><span><b>${esc(item.question_text||item.question_id)}</b><small>${esc(item.provider||'--')} · ${esc(item.tested_at||'--')}</small></span><span class="geo-badge ${item.official_truth?'is-success':'is-neutral'}">${esc(item.evidence_level||'C')}级${item.official_truth?'证据':'模拟'}</span></summary><div class="geo-receipt-body"><div class="geo-receipt-meta"><span>Receipt <b class="mono">${esc(item.evidence_id||item.receipt_id||'--')}</b></span><span>模型 <b>${esc(item.model||'--')}</b></span><span>品牌提及 <b>${item.brand_mentioned?'是':'否'}</b></span><span>官网引用 <b>${item.brand_cited?'是':'否'}</b></span></div><pre>${esc(item.raw_answer||'')}</pre>${(item.citation_urls||[]).length?`<div class="geo-citations">${item.citation_urls.map(url=>`<span>${esc(url)}</span>`).join('')}</div>`:''}</div></details>`).join(''):'<div class="empty">尚无 GEO Receipt。未执行真实外部测试时保持为空，不填假数据。</div>';
  }
  function renderManual(){
    const box=byId('geo-manual-list');if(!box)return;
    const items=(geoCache.dashboard?.manual?.items||[]);byId('geo-manual-count').textContent=fmt(items.length);
    box.innerHTML=items.length?items.map(item=>`<div class="geo-manual"><div><b>${esc(item.provider||'外部AI平台')}</b><span>${esc(item.question_id||'')} · ${esc(item.reason||'需要人工授权')}</span></div><span class="geo-badge is-waiting">待授权</span></div>`).join(''):'<div class="geo-ok">当前没有需要人工处理的 GEO 事项。</div>';
  }

  async function loadGeo(){
    const [dashboard,questions,queue,receipts]=await Promise.all([json('/api/r8-19/geo'),json('/api/r8-19/geo/questions'),json('/api/r8-19/geo/queue'),json('/api/r8-19/geo/receipts?limit=200')]);
    geoCache={dashboard,questions:questions.questions||[],queue:queue.tasks||[],receipts:receipts.receipts||[]};renderGeo();return geoCache;
  }
  async function runGeoRound(button){
    button.disabled=true;const original=button.textContent;
    try{
      await post('/api/r8-19/geo/bootstrap',{});
      const before=await json('/api/r8-19/geo');
      const decision=before.decision||{},executor=before.executor||{};
      const planReply=await post('/api/r8-19/geo/plan',{limit:decision.daily_test_limit||10,provider:'openai_web_search',test_method:'api',mission_id:decision.mission_id||''});
      const created=Number(planReply.result?.created||0);
      await loadGeo();
      if(!created){window.notify?.('本轮没有新的固定基准问题需要入队');return}
      if(!executor.ready){window.notify?.(`已建立 ${created} 个 GEO 真实验证任务；${executor.reason||'外部验证执行器尚未就绪'}。本地模型不会冒充正式结果。`,'error');return}
      let completed=0;
      for(let i=0;i<created;i+=1){
        button.textContent=`真实验证中 ${i+1} / ${created}`;
        const reply=await post('/api/r8-19/geo/run',{mode:'openai_web_search'});
        const result=reply.result||{};completed+=result.ok?1:0;
        if(result.task?.state==='authorization_required')break;
        await loadGeo();
      }
      await loadGeo();window.notify?.(`本轮已完成 ${completed} 个真实外部 GEO 验证，其余任务保持可追溯状态。`);
    }catch(error){window.notify?.(error.message,'error')}finally{button.disabled=false;button.textContent=original}
  }
  function bindGeoActions(){
    byId('geo-refresh')?.addEventListener('click',()=>loadGeo().catch(error=>window.notify?.(error.message,'error')));
    byId('geo-bootstrap')?.addEventListener('click',async event=>{event.currentTarget.disabled=true;try{await post('/api/r8-19/geo/bootstrap',{});await loadGeo();window.notify?.('固定50问基准已核验：30自然发现 + 10商业推荐 + 10品牌认知')}catch(error){window.notify?.(error.message,'error')}finally{event.currentTarget.disabled=false}});
    byId('geo-run-round')?.addEventListener('click',event=>runGeoRound(event.currentTarget));
    byId('geo-type-filters')?.addEventListener('click',event=>{const button=event.target.closest('[data-geo-type]');if(!button)return;currentType=button.dataset.geoType;byId('geo-type-filters').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===button));renderQuestions()});
    byId('geo-state-filters')?.addEventListener('click',event=>{const button=event.target.closest('[data-geo-state]');if(!button)return;currentState=button.dataset.geoState;byId('geo-state-filters').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===button));renderQuestions()});
  }

  installWorkspace();
  byId('search-audit')?.addEventListener('click',async event=>{event.currentTarget.disabled=true;try{const result=await json('/api/search-growth/audit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site:'https://kazuizhi.com/'})});await loadSeo();window.notify?.(result.result==='ready'?'官网技术底座检查通过':`发现 ${result.blockers.length} 个搜索技术堵点`)}catch(error){window.notify?.(error.message,'error')}finally{event.currentTarget.disabled=false}});
  byId('search-pack')?.addEventListener('click',async event=>{const campaignId=byId('search-campaign')?.value;if(!campaignId)return window.notify?.('请先选择增长战役','error');event.currentTarget.disabled=true;try{await json('/api/search-growth/packs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({campaign_id:campaignId})});await loadSeo();window.notify?.('SEO网页、FAQ与GEO短答案已生成并绑定增长ID')}catch(error){window.notify?.(error.message,'error')}finally{event.currentTarget.disabled=false}});
  window.searchGrowthActivate=()=>localStorage.getItem(WORKSPACE_KEY)==='geo'?loadGeo():loadSeo();
})();