(() => {
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const fmt=value=>Number(value||0).toLocaleString('zh-CN');
  const WORKSPACE_KEY='kz-search-growth-workspace';
  let geoCache={dashboard:null,questions:[],queue:[],receipts:[],localPrecheck:{status:null,results:[]}};
  let currentType='all';
  let currentState='all';
  let browserCurrentTask=null;

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
      <button type="button" class="growth-tab" data-growth-tab="geo" role="tab">GEO 增长<span>R8-19 · 浏览器优先</span></button>`;
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
      <article><span>待授权</span><strong id="geo-auth">0</strong><small>登录/验证码/权限</small></article>
    </div>

    <div class="geo-mode-grid">
      <article><span>本地预检</span><b id="geo-local-state">检查中</b><small id="geo-local-progress">0 / 50 · C级辅助</small></article>
      <article><span>网页真实验证</span><b id="geo-browser-state">可用</b><small>默认通道 · 无需API · A级证据</small></article>
      <article><span>API验证</span><b id="geo-api-state">可选</b><small id="geo-api-note">后期需要时再配置</small></article>
    </div>

    <div class="geo-actionbar">
      <button id="geo-local-one" class="geo-secondary" type="button">本地预检1题</button>
      <button id="geo-local-ten" class="geo-ghost" type="button">本地预检10题</button>
      <button id="geo-browser-one" class="geo-primary" type="button">网页真实验证1题</button>
      <button id="geo-browser-ten" class="geo-secondary" type="button">准备10题</button>
      <button id="geo-run-round" class="geo-ghost" type="button">API执行本轮 GEO 测试（可选）</button>
      <button id="geo-bootstrap" class="geo-ghost" type="button">核验固定 50 问</button>
      <button id="geo-refresh" class="geo-ghost" type="button">刷新</button>
      <span id="geo-executor-state" class="geo-executor-state is-neutral">默认：网页真实验证 · 无需API</span>
    </div>

    <div id="geo-truth-banner" class="geo-truth-banner">本地模型负责预检和分析，固定为C级辅助，不改变正式0/50；真实外部AI网页结果可形成A级 Evidence / Receipt。API只是后期可选加速通道。</div>

    <article class="panel geo-panel geo-browser-workbench">
      <div class="panel-head"><div><p>网页验证工作台</p><h3>真实外部 AI 网页 → Evidence / Receipt</h3></div><span id="geo-browser-task-state" class="geo-badge is-neutral">尚未准备题目</span></div>
      <div class="geo-browser-form-grid">
        <label>外部AI平台<select id="geo-browser-platform"><option value="chatgpt_web">ChatGPT 网页版</option><option value="gemini_web">Gemini 网页版</option><option value="copilot_web">Copilot 网页版</option><option value="qwen_web">通义千问网页版</option><option value="deepseek_web">DeepSeek 网页版</option><option value="doubao_web">豆包网页版</option><option value="custom_web">其他真实外部AI网页</option></select></label>
        <label>当前 Task ID<input id="geo-browser-task-id" readonly placeholder="点击“网页真实验证1题”后生成"></label>
      </div>
      <label>原始问题<textarea id="geo-browser-question" readonly rows="2" placeholder="系统会放入固定50问中的一题"></textarea></label>
      <div class="geo-browser-form-grid">
        <label>真实外部页面 URL<input id="geo-browser-url" type="url" placeholder="https://真实AI网页会话地址"></label>
        <label>引用URL（可选，每行一个）<textarea id="geo-browser-citations" rows="2" placeholder="https://example.com/source"></textarea></label>
      </div>
      <label>外部AI完整原始回答<textarea id="geo-browser-answer" rows="6" placeholder="把真实外部AI网页的完整回答原样粘贴到这里；后续Work模式可自动回填"></textarea></label>
      <div class="geo-browser-actions"><button id="geo-browser-submit" class="geo-primary" type="button">保存真实网页 Evidence / Receipt</button><span>当前先支持人工执行；后续 ChatGPT Work / 浏览器代理沿用同一任务契约自动执行。</span></div>
    </article>

    <div class="geo-grid">
      <article class="panel geo-panel geo-questions-panel">
        <div class="panel-head"><div><p>问题雷达</p><h3>固定 50 问 · 长期基线</h3></div><span id="geo-baseline-version" class="geo-version">--</span></div>
        <div class="geo-filters" id="geo-type-filters"><button class="active" data-geo-type="all">全部</button><button data-geo-type="discovery">自然发现 30</button><button data-geo-type="commercial">商业推荐 10</button><button data-geo-type="brand">品牌认知 10</button></div>
        <div class="geo-filters subtle" id="geo-state-filters"><button class="active" data-geo-state="all">全部状态</button><button data-geo-state="unstarted">未开始</button><button data-geo-state="queued">排队</button><button data-geo-state="running">执行中</button><button data-geo-state="succeeded">已验证</button><button data-geo-state="failed">失败</button><button data-geo-state="authorization_required">待授权</button></div>
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
      <article class="panel geo-panel"><div class="panel-head"><div><p>真实证据</p><h3>GEO Evidence / Receipt</h3></div><span class="geo-badge is-success" id="geo-receipt-count">0</span></div><div id="geo-receipt-list" class="geo-receipt-list"><div class="empty">尚无正式外部 GEO 证据。</div></div></article>
      <article class="panel geo-panel"><div class="panel-head"><div><p>本地辅助</p><h3>本地模型预检 · C级</h3></div><span class="geo-badge is-neutral" id="geo-precheck-count">0</span></div><div id="geo-precheck-list" class="geo-precheck-list"><div class="empty">尚未运行本地预检。</div></div></article>
    </div>

    <article class="panel geo-panel"><div class="panel-head"><div><p>待我处理</p><h3>只保留 AI 无法处理的授权事项</h3></div><span class="geo-badge is-waiting" id="geo-manual-count">0</span></div><div id="geo-manual-list" class="geo-manual-list"><div class="geo-ok">当前没有需要人工处理的 GEO 事项。</div></div><p class="truth">只有真实网页登录、OAuth、验证码、账号权限等才进入这里；API未配置不是阻塞，本地预检也不会冒充正式外部结果。</p></article>`}

  function selectWorkspace(name,persist){
    const geo=name==='geo';
    byId('seo-growth-pane').hidden=geo;byId('geo-growth-pane').hidden=!geo;
    document.querySelectorAll('#search-growth-switch [data-growth-tab]').forEach(button=>{const active=button.dataset.growthTab===(geo?'geo':'seo');button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active))});
    if(persist)localStorage.setItem(WORKSPACE_KEY,geo?'geo':'seo');
    if(geo)loadGeo().catch(error=>window.notify?.(error.message,'error')); else loadSeo().catch(error=>window.notify?.(error.message,'error'));
  }

  const typeLabel={discovery:'自然发现',commercial:'商业推荐',brand:'品牌认知'};
  const stateLabel={unstarted:'未开始',queued:'排队',running:'执行中',succeeded:'已验证',failed:'失败',paused:'已暂停',authorization_required:'待授权'};
  const stateClass={unstarted:'is-neutral',queued:'is-running',running:'is-running',succeeded:'is-success',failed:'is-danger',paused:'is-neutral',authorization_required:'is-waiting'};
  function taskStateForQuestion(questionId){
    const receipt=geoCache.receipts.find(item=>item.question_id===questionId&&item.official_truth);if(receipt)return {state:'succeeded',evidence:receipt.evidence_id||receipt.receipt_id||''};
    const tasks=geoCache.queue.filter(item=>item.question_id===questionId);if(!tasks.length)return {state:'unstarted',evidence:''};
    const rank={running:6,authorization_required:5,queued:4,paused:3,failed:2,succeeded:1};const latest=[...tasks].sort((a,b)=>(rank[b.state]||0)-(rank[a.state]||0))[0];return {state:latest.state||'unstarted',evidence:latest.evidence_id||''};
  }
  function renderGeo(){
    const data=geoCache.dashboard||{},decision=data.decision||{},official=data.official||{},queue=data.queue||{},manual=data.manual||{},qset=data.question_set||{},browser=data.browser_executor||data.executor||{},api=data.api_executor||{},local=data.local_precheck||geoCache.localPrecheck.status||{};
    byId('geo-mission').textContent=decision.mission_title||'涟水县 GEO 第一轮基线验证';byId('geo-judgement').textContent=decision.judgement||'等待 ChatGPT 决策';byId('geo-goal').textContent=decision.today_goal||'--';byId('geo-daily-limit').textContent=`${fmt(decision.daily_test_limit||0)} 题`;byId('geo-blockers').textContent=manual.count?`${fmt(manual.count)} 项待授权`:'0 · 无人工阻塞';byId('geo-next-condition').textContent=decision.next_decision_condition||'--';byId('geo-decision-id').textContent=`Decision ${decision.decision_id||'--'}`;byId('geo-command-id').textContent=`Command ${decision.command_id||'--'}`;
    byId('geo-tested').textContent=`${fmt(official.tested)} / ${fmt(qset.total||50)}`;byId('geo-remaining').textContent=fmt(official.remaining??50);byId('geo-running').textContent=fmt(queue.running);byId('geo-evidence').textContent=fmt(official.evidence_count);byId('geo-failed').textContent=fmt(queue.failed);byId('geo-auth').textContent=fmt(queue.authorization_required);byId('geo-queued').textContent=fmt(queue.queued);byId('geo-running-2').textContent=fmt(queue.running);byId('geo-succeeded').textContent=fmt(queue.succeeded);byId('geo-paused').textContent=fmt(queue.paused);byId('geo-queue-total').textContent=`${fmt(queue.total)} 个任务`;byId('geo-baseline-version').textContent=qset.version||'--';byId('geo-baseline-note').textContent=`基准版本 ${qset.version||'--'} · ${qset.immutable_within_version?'同版本内不可静默修改':'请检查版本规则'} · Hash ${String(qset.question_set_hash||'').slice(0,12)||'--'}…`;
    byId('geo-browser-state').textContent=browser.ready?'可用':'等待';byId('geo-local-state').textContent=local.ready?`${local.model||'本地模型'} 已连接`:'待连接';byId('geo-local-progress').textContent=`${fmt(local.tested||0)} / ${fmt(local.total||50)} · C级辅助`;byId('geo-api-state').textContent=api.ready?'已连接':'可选未配置';byId('geo-api-note').textContent=api.ready?`${api.model||'云端模型'} · 可做B级验证`:'不影响网页GEO验证';
    const ex=byId('geo-executor-state');if(ex){ex.textContent='默认：网页真实验证 · 无需API';ex.className='geo-executor-state is-success'}
    const apiBtn=byId('geo-run-round');if(apiBtn)apiBtn.disabled=!api.ready;
    restoreBrowserTask();renderQuestions();renderTasks();renderReceipts();renderManual();renderPrechecks();
  }
  function renderQuestions(){
    const rows=byId('geo-question-rows');if(!rows)return;const items=geoCache.questions.filter(item=>currentType==='all'||item.question_type===currentType).map(item=>({...item,...taskStateForQuestion(item.question_id)})).filter(item=>currentState==='all'||item.state===currentState);
    rows.innerHTML=items.length?items.map(item=>`<tr><td class="mono">${esc(item.question_id)}</td><td class="geo-question-text">${esc(item.question_text)}</td><td><span class="geo-type">${esc(typeLabel[item.question_type]||item.question_type)}</span></td><td>${esc(item.service||'--')}</td><td>${esc(item.intent||'--')}</td><td><span class="geo-badge ${stateClass[item.state]||'is-neutral'}">${esc(stateLabel[item.state]||item.state)}</span></td><td class="mono">${item.evidence?esc(item.evidence):'<span class="muted">--</span>'}</td></tr>`).join(''):'<tr><td colspan="7" class="empty">当前筛选条件没有问题。</td></tr>';
  }
  function renderTasks(){
    const box=byId('geo-task-list');if(!box)return;const items=[...geoCache.queue].reverse().slice(0,12);box.innerHTML=items.length?items.map(item=>`<div class="geo-task"><div><b>${esc(item.question_text||item.question_id)}</b><span>${esc(item.question_id)} · ${esc(item.provider||'待分配')} · ${esc(item.test_method||'--')} · 重试 ${fmt(item.retry_count)}/${fmt(item.max_retries||2)}</span>${item.failure_reason?`<small class="danger-text">${esc(item.failure_reason)}</small>`:''}${item.authorization_reason?`<small class="waiting-text">${esc(item.authorization_reason)}</small>`:''}</div><span class="geo-badge ${stateClass[item.state]||'is-neutral'}">${esc(stateLabel[item.state]||item.state)}</span></div>`).join(''):'<div class="empty">暂无 GEO 执行任务。</div>';
  }
  function renderReceipts(){
    const box=byId('geo-receipt-list');if(!box)return;byId('geo-receipt-count').textContent=fmt(geoCache.receipts.filter(item=>item.official_truth).length);const items=geoCache.receipts.slice(0,10);box.innerHTML=items.length?items.map(item=>`<details class="geo-receipt"><summary><span><b>${esc(item.question_text||item.question_id)}</b><small>${esc(item.provider||'--')} · ${esc(item.tested_at||'--')}</small></span><span class="geo-badge ${item.official_truth?'is-success':'is-neutral'}">${esc(item.evidence_level||'C')}级${item.official_truth?'证据':'辅助'}</span></summary><div class="geo-receipt-body"><div class="geo-receipt-meta"><span>Receipt <b class="mono">${esc(item.evidence_id||item.receipt_id||'--')}</b></span><span>方式 <b>${esc(item.test_method||'--')}</b></span><span>模型/产品 <b>${esc(item.model||'--')}</b></span><span>品牌提及 <b>${item.brand_mentioned?'是':'否'}</b></span><span>官网引用 <b>${item.brand_cited?'是':'否'}</b></span></div><pre>${esc(item.raw_answer||'')}</pre>${item.session_url?`<div class="geo-citations"><span>${esc(item.session_url)}</span></div>`:''}${(item.citation_urls||[]).length?`<div class="geo-citations">${item.citation_urls.map(url=>`<span>${esc(url)}</span>`).join('')}</div>`:''}</div></details>`).join(''):'<div class="empty">尚无 GEO Receipt。未执行真实外部测试时保持为空，不填假数据。</div>';
  }
  function renderManual(){
    const box=byId('geo-manual-list');if(!box)return;const items=(geoCache.dashboard?.manual?.items||[]);byId('geo-manual-count').textContent=fmt(items.length);box.innerHTML=items.length?items.map(item=>`<div class="geo-manual"><div><b>${esc(item.provider||'外部AI平台')}</b><span>${esc(item.question_id||'')} · ${esc(item.reason||'需要人工授权')}</span></div><span class="geo-badge is-waiting">待授权</span></div>`).join(''):'<div class="geo-ok">当前没有需要人工处理的 GEO 事项。API未配置不会出现在这里。</div>';
  }
  function renderPrechecks(){
    const box=byId('geo-precheck-list');if(!box)return;const items=(geoCache.localPrecheck?.results||[]).slice(0,8);byId('geo-precheck-count').textContent=fmt(geoCache.localPrecheck?.status?.tested||items.length);box.innerHTML=items.length?items.map(item=>`<details class="geo-receipt"><summary><span><b>${esc(item.question_text||item.question_id)}</b><small>${esc(item.model||'本地模型')} · ${esc(item.tested_at||'--')}</small></span><span class="geo-badge is-neutral">C级预检</span></summary><div class="geo-receipt-body"><div class="geo-receipt-meta"><span>可能可见性 <b>${esc(item.likely_visibility||'unknown')}</b></span></div><pre>${esc(item.answer||'')}</pre>${(item.content_gaps||[]).length?`<div class="geo-citations">${item.content_gaps.map(x=>`<span>缺口：${esc(x)}</span>`).join('')}</div>`:''}</div></details>`).join(''):'<div class="empty">尚未运行本地预检。</div>';
  }
  function restoreBrowserTask(){
    if(browserCurrentTask)return;const task=[...geoCache.queue].reverse().find(item=>item.state==='running'&&item.test_method==='browser');if(!task)return;browserCurrentTask=task;fillBrowserTask(task);
  }
  function fillBrowserTask(task){
    byId('geo-browser-task-id').value=task?.task_id||'';byId('geo-browser-question').value=task?.question_text||'';const badge=byId('geo-browser-task-state');if(badge){badge.textContent=task?.task_id?'等待网页回答':'尚未准备题目';badge.className=`geo-badge ${task?.task_id?'is-running':'is-neutral'}`}
  }

  async function loadGeo(){
    const [dashboard,questions,queue,receipts,precheck]=await Promise.all([json('/api/r8-19/geo'),json('/api/r8-19/geo/questions'),json('/api/r8-19/geo/queue'),json('/api/r8-19/geo/receipts?limit=200'),json('/api/r8-19/geo/local-precheck?limit=20')]);geoCache={dashboard,questions:questions.questions||[],queue:queue.tasks||[],receipts:receipts.receipts||[],localPrecheck:precheck||{status:null,results:[]}};renderGeo();return geoCache;
  }
  async function runLocalPrecheck(limit,button){button.disabled=true;const original=button.textContent;try{button.textContent=`本地预检中…`;const reply=await post('/api/r8-19/geo/local-precheck/run',{limit});await loadGeo();window.notify?.(`本地模型已完成 ${fmt(reply.result?.completed||0)} 题预检；结果仅为C级辅助，不计正式GEO。`)}catch(error){window.notify?.(error.message,'error')}finally{button.disabled=false;button.textContent=original}}
  async function prepareBrowserTask(limit,button){button.disabled=true;const original=button.textContent;try{await post('/api/r8-19/geo/bootstrap',{});const platform=byId('geo-browser-platform')?.value||'custom_web';const reply=await post('/api/r8-19/geo/browser/prepare',{limit,platform});const task=reply.result?.claim?.task||{};browserCurrentTask=task;fillBrowserTask(task);await loadGeo();window.notify?.(limit>1?`已准备 ${limit} 题网页验证队列，当前先执行第1题。`:'已准备1题真实网页验证，请到外部AI网页提交原始问题。')}catch(error){window.notify?.(error.message,'error')}finally{button.disabled=false;button.textContent=original}}
  async function submitBrowserReceipt(button){button.disabled=true;const original=button.textContent;try{const taskId=byId('geo-browser-task-id')?.value?.trim();if(!taskId)throw new Error('请先点击“网页真实验证1题”准备任务');const sessionUrl=byId('geo-browser-url')?.value?.trim();const rawAnswer=byId('geo-browser-answer')?.value?.trim();if(!sessionUrl||!rawAnswer)throw new Error('请填写真实外部AI页面URL和完整原始回答');const citationUrls=(byId('geo-browser-citations')?.value||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);button.textContent='正在保存 Evidence…';const reply=await post('/api/r8-19/geo/browser/receipt',{task_id:taskId,platform:byId('geo-browser-platform')?.value||'custom_web',session_url:sessionUrl,raw_answer:rawAnswer,citation_urls:citationUrls});browserCurrentTask=null;byId('geo-browser-task-id').value='';byId('geo-browser-question').value='';byId('geo-browser-url').value='';byId('geo-browser-answer').value='';byId('geo-browser-citations').value='';await loadGeo();window.notify?.(`已生成 ${reply.result?.evidence_level||'A'}级真实网页 Receipt：${reply.result?.evidence_id||''}`)}catch(error){window.notify?.(error.message,'error')}finally{button.disabled=false;button.textContent=original}}
  async function runApiRound(button){button.disabled=true;const original=button.textContent;try{const before=await json('/api/r8-19/geo');const api=before.api_executor||{};if(!api.ready)throw new Error('API验证未配置；当前无需API，可继续使用网页真实验证');const decision=before.decision||{};await post('/api/r8-19/geo/decision',{decision_id:decision.decision_id,command_id:decision.command_id,mission_id:decision.mission_id,mission_title:decision.mission_title,today_goal:decision.today_goal,judgement:decision.judgement,next_decision_condition:decision.next_decision_condition,daily_test_limit:decision.daily_test_limit,test_providers:['openai_web_search']});const planReply=await post('/api/r8-19/geo/plan',{limit:decision.daily_test_limit||10,require_executor_ready:true});const created=Number(planReply.result?.created||0);let completed=0;for(let i=0;i<created;i+=1){button.textContent=`API验证中 ${i+1}/${created}`;const reply=await post('/api/r8-19/geo/run',{mode:'openai_web_search'});completed+=reply.result?.ok?1:0;await loadGeo()}window.notify?.(`API验证完成 ${completed} 题。`)}catch(error){window.notify?.(error.message,'error')}finally{button.disabled=false;button.textContent=original}}

  function bindGeoActions(){
    byId('geo-refresh')?.addEventListener('click',()=>loadGeo().catch(error=>window.notify?.(error.message,'error')));
    byId('geo-bootstrap')?.addEventListener('click',async event=>{event.currentTarget.disabled=true;try{await post('/api/r8-19/geo/bootstrap',{});await loadGeo();window.notify?.('固定50问基准已核验：30自然发现 + 10商业推荐 + 10品牌认知')}catch(error){window.notify?.(error.message,'error')}finally{event.currentTarget.disabled=false}});
    byId('geo-local-one')?.addEventListener('click',event=>runLocalPrecheck(1,event.currentTarget));byId('geo-local-ten')?.addEventListener('click',event=>runLocalPrecheck(10,event.currentTarget));byId('geo-browser-one')?.addEventListener('click',event=>prepareBrowserTask(1,event.currentTarget));byId('geo-browser-ten')?.addEventListener('click',event=>prepareBrowserTask(10,event.currentTarget));byId('geo-browser-submit')?.addEventListener('click',event=>submitBrowserReceipt(event.currentTarget));byId('geo-run-round')?.addEventListener('click',event=>runApiRound(event.currentTarget));
    byId('geo-type-filters')?.addEventListener('click',event=>{const button=event.target.closest('[data-geo-type]');if(!button)return;currentType=button.dataset.geoType;byId('geo-type-filters').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===button));renderQuestions()});byId('geo-state-filters')?.addEventListener('click',event=>{const button=event.target.closest('[data-geo-state]');if(!button)return;currentState=button.dataset.geoState;byId('geo-state-filters').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===button));renderQuestions()});
  }

  installWorkspace();
  byId('search-audit')?.addEventListener('click',async event=>{event.currentTarget.disabled=true;try{const result=await json('/api/search-growth/audit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site:'https://kazuizhi.com/'})});await loadSeo();window.notify?.(result.result==='ready'?'官网技术底座检查通过':`发现 ${result.blockers.length} 个搜索技术堵点`)}catch(error){window.notify?.(error.message,'error')}finally{event.currentTarget.disabled=false}});
  byId('search-pack')?.addEventListener('click',async event=>{const campaignId=byId('search-campaign')?.value;if(!campaignId)return window.notify?.('请先选择增长战役','error');event.currentTarget.disabled=true;try{await json('/api/search-growth/packs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({campaign_id:campaignId})});await loadSeo();window.notify?.('SEO网页、FAQ与GEO短答案已生成并绑定增长ID')}catch(error){window.notify?.(error.message,'error')}finally{event.currentTarget.disabled=false}});
  window.searchGrowthActivate=()=>localStorage.getItem(WORKSPACE_KEY)==='geo'?loadGeo():loadSeo();
})();