/* Autonomous Decision Center V1.
   Eight AI employees report upward; R7 summarizes evidence; ChatGPT remains
   the strategic control layer. This UI never claims external publication. */

(() => {
  if (window.__kazuizhiDecisionCenterLoaded) return;
  window.__kazuizhiDecisionCenterLoaded = true;

  function ensureDecisionStyles(){
    if ($('decision-center-style')) return;
    const style=document.createElement('style');style.id='decision-center-style';style.textContent=`
      .decision-hero{background:linear-gradient(135deg,#102f73,#2863df 60%,#5169dc);color:#fff;border:0;box-shadow:0 16px 36px rgba(31,77,170,.18)}
      .decision-hero h2{margin:7px 0 5px;font-size:25px}.decision-hero p{color:#dce8ff;margin:0}.decision-hero .article-head{align-items:flex-start}.decision-live{background:rgba(255,255,255,.14);border-radius:999px;padding:7px 10px;font-size:11px;white-space:nowrap;cursor:default}.decision-hero-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
      .decision-stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:18px}.decision-stat{background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.13);border-radius:12px;padding:12px}.decision-stat b{display:block;font-size:22px}.decision-stat small{display:block;margin-top:5px;color:#dce8ff;font-size:10px}.decision-stat[role="button"]{cursor:pointer;transition:.16s}.decision-stat[role="button"]:hover{transform:translateY(-2px);background:rgba(255,255,255,.18)}.decision-stat[role="button"]:focus{outline:2px solid rgba(255,255,255,.78);outline-offset:2px}
      .decision-grid{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:16px;align-items:start}.decision-stack{display:grid;gap:10px}.decision-item{border:1px solid #e1e8f3;border-radius:12px;padding:12px;background:#fff}.decision-item strong{display:block;color:#17243b;margin-bottom:6px}.decision-item p{margin:0;color:#65748b;font-size:12px;line-height:1.6}.decision-item[role="button"]{cursor:pointer;transition:.15s}.decision-item[role="button"]:hover{border-color:#b9cdf6;box-shadow:0 7px 18px rgba(49,104,232,.08);transform:translateY(-1px)}.decision-item-hint{display:block;margin-top:8px;color:#3168e8;font-size:10px;font-weight:700}.decision-level{display:inline-block;font-size:9px;border-radius:999px;padding:4px 7px;background:#eef4ff;color:#2d61ca;margin-bottom:7px}.decision-level.high{background:#fff0ed;color:#b2483c}.decision-level.medium{background:#fff6e8;color:#94611c}
      .decision-agent-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.decision-agent{border:1px solid #e1e8f3;border-radius:12px;padding:12px;background:#fff}.decision-agent[role="button"]{cursor:pointer;transition:.15s}.decision-agent[role="button"]:hover{border-color:#b9cdf6;box-shadow:0 7px 18px rgba(49,104,232,.08);transform:translateY(-1px)}.decision-agent-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.decision-agent-state{font-size:9px;padding:4px 7px;border-radius:999px;background:#eef2f7;color:#5e6d83}.decision-agent-state.工作中{background:#e8f1ff;color:#245fc9}.decision-agent-state.待执行{background:#fff3dd;color:#95611b}.decision-agent-state.今日已完成{background:#e7f8f1;color:#087a50}.decision-agent-state.异常{background:#fff0ef;color:#b43b32}.decision-agent-metrics{display:flex;gap:8px;flex-wrap:wrap;margin:9px 0;color:#63738c;font-size:10px}.decision-agent-judge{font-size:12px;line-height:1.55;color:#33435c}.decision-evidence{margin-top:8px;font-size:10px;color:#74839a}.decision-evidence li{margin:4px 0}.decision-agent-open{display:block;margin-top:8px;color:#3168e8;font-size:10px;font-weight:700}
      .decision-action-button{border:0;background:#eef4ff;color:#2b61ca;border-radius:9px;padding:7px 10px;font-size:10px;font-weight:700;cursor:pointer}.decision-action-button:hover{background:#e1ebff}.decision-action-button.white{background:#fff;color:#285fc9}.decision-action-button.white:hover{background:#f3f6ff}.decision-action-button:focus{outline:2px solid #8fb2ff;outline-offset:2px}
      .decision-team{margin-top:16px}.decision-team-copy{color:#63738c;font-size:12px;line-height:1.6;margin:0 0 12px}.decision-flow{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:12px 0 14px}.decision-flow button{border:1px solid #dce5f3;background:#fff;color:#33435c;border-radius:999px;padding:7px 10px;font-size:10px;cursor:pointer}.decision-flow button:hover{border-color:#9fbaf0;color:#285fc9;background:#f7faff}.decision-flow span{color:#9aacbf;font-size:11px}.decision-shared-context{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.decision-shared-item{background:#f7f9fd;border:1px solid #e4eaf3;border-radius:10px;padding:10px;color:#51647f;font-size:11px;line-height:1.5}.decision-shared-item b{color:#273b59;margin-right:5px}
      .decision-handoff{background:#f6f8ff;border:1px solid #dfe7fb;border-radius:12px;padding:13px}.decision-handoff strong{display:block;margin-bottom:6px}.decision-handoff p{margin:4px 0;color:#576a86;font-size:12px;line-height:1.55}.decision-refresh{border:0;background:#fff;color:#285fc9;border-radius:9px;padding:8px 11px;font-weight:700;cursor:pointer}.decision-refresh:hover{background:#f1f5ff}.decision-refresh:disabled{opacity:.6;cursor:default}
      @media(max-width:1100px){.decision-grid{grid-template-columns:1fr}.decision-stats{grid-template-columns:repeat(3,1fr)}}
      @media(max-width:700px){.decision-stats{grid-template-columns:repeat(2,1fr)}.decision-agent-grid,.decision-shared-context{grid-template-columns:1fr}.decision-hero-actions{justify-content:flex-start}}
    `;document.head.appendChild(style);
  }

  function decisionActivate(element,handler,label){
    if(!element||element.dataset.decisionBound==='1')return;
    element.dataset.decisionBound='1';element.setAttribute('role','button');element.setAttribute('tabindex','0');
    if(label){element.setAttribute('aria-label',label);element.title=label}
    element.addEventListener('click',handler);
    element.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();handler()}});
  }

  function decisionOpenWorkflow(filter='today',agentName=''){
    openPage('workflow');
    const apply=()=>{
      if(agentName){
        const card=[...document.querySelectorAll('.r7-agent-action')].find(item=>item.dataset.agentName===agentName);
        if(card){card.click();return}
      }
      const button=document.querySelector(`.r7-job-filter[data-filter="${filter}"]`);
      if(button){button.click();return}
      toast('已打开任务与员工，可查看相关执行记录');
    };
    try{
      const loaded=typeof loadR7==='function'?loadR7():null;
      if(loaded&&typeof loaded.then==='function')loaded.finally(()=>setTimeout(apply,30));else setTimeout(apply,80);
    }catch(_){setTimeout(apply,80)}
  }

  function decisionOpenPage(page,message){openPage(page);if(message)toast(message)}

  function decisionTarget(item){
    const text=`${item?.action||''} ${item?.reason||''}`;
    if(text.includes('失败')||text.includes('异常'))return {type:'workflow',filter:'failed',label:'查看失败任务'};
    if(/SEO|GEO|关键词|内容/.test(text))return {type:'page',page:'promotion',label:'查看内容增长工作台'};
    if(/市场|需求|区域|本地/.test(text))return {type:'page',page:'insights',label:'查看市场与本地洞察'};
    if(/经营数据|用户|订单|转化/.test(text))return {type:'page',page:'analytics',label:'查看经营分析'};
    if(/复盘|明日|计划/.test(text))return {type:'page',page:'review',label:'查看复盘与计划'};
    return {type:'workflow',filter:'today',label:'查看相关任务'};
  }

  function bindDecisionStaticControls(){
    const filterMap={
      'decision-planned':'today','decision-completed':'completed','decision-queued':'queued','decision-failed':'failed','decision-rate':'today',
    };
    Object.entries(filterMap).forEach(([id,filter])=>{
      const box=$(id)?.closest('.decision-stat');
      decisionActivate(box,()=>decisionOpenWorkflow(filter),`打开${box?.querySelector('small')?.textContent||'对应'}任务`);
    });
    decisionActivate($('decision-evidence-open'),()=>decisionOpenWorkflow('completed'),'查看经理判断所依据的已完成任务');
    decisionActivate($('decision-reports-open'),()=>decisionOpenWorkflow('today'),'查看八个员工今天的全部任务');
    decisionActivate($('decision-bridge-open'),()=>decisionOpenPage('connections','已打开连接与体检，可查看 ChatGPT 双向桥状态'),'查看 ChatGPT 战略交接连接状态');
    document.querySelectorAll('[data-team-page]').forEach(button=>decisionActivate(button,()=>{
      const page=button.dataset.teamPage;
      if(page==='workflow')decisionOpenWorkflow('today');else if(page==='handoff')$('decision-handoff')?.scrollIntoView({behavior:'smooth',block:'center'});else decisionOpenPage(page,`已打开${button.textContent.trim()}相关工作台`);
    },`打开${button.textContent.trim()}相关工作台`));
  }

  function ensureDecisionPage(){
    if ($('decision-center')){bindDecisionStaticControls();return}
    ensureDecisionStyles();
    const nav=document.querySelector('aside nav');
    const workflowNav=document.querySelector('.nav[data-page="workflow"]');
    if(nav && !document.querySelector('.nav[data-page="decision-center"]')){
      const button=document.createElement('button');button.className='nav';button.dataset.page='decision-center';button.dataset.title='AI 自主决策中心';button.dataset.subtitle='员工自主分析、R7 经理汇总、ChatGPT 战略复盘';button.innerHTML='<span>◆</span>自主决策';
      workflowNav?.insertAdjacentElement('afterend',button);
      button.addEventListener('click',()=>{openPage('decision-center');loadDecisionCenter()});
    }
    const main=document.querySelector('main');
    if(!main)return;
    const section=document.createElement('section');section.id='decision-center';section.className='page';
    section.innerHTML=`
      <div class="page-title"><small>AI 自主决策中心 V1</small><h2>员工汇报，R7 汇总，ChatGPT 做战略判断</h2><p>员工在各自职责范围内自主判断；R7 汇总全员信息形成经理意见。你主要看结论、异常和方向，不需要逐项管理。</p></div>
      <article class="wide decision-hero"><div class="article-head"><div><label>R7 经理报告</label><h2 id="decision-headline">正在整理今天的员工汇报…</h2><p id="decision-generated">等待第一份经理报告</p></div><div class="decision-hero-actions"><span class="decision-live">● 自动汇总已开启 · 每 5 分钟</span><button id="decision-refresh" class="decision-refresh">立即刷新分析</button></div></div><div class="decision-stats"><div class="decision-stat"><b id="decision-planned">--</b><small>今日计划</small></div><div class="decision-stat"><b id="decision-completed">--</b><small>已经完成</small></div><div class="decision-stat"><b id="decision-queued">--</b><small>等待执行</small></div><div class="decision-stat"><b id="decision-failed">--</b><small>失败/异常</small></div><div class="decision-stat"><b id="decision-rate">--</b><small>今日完成度</small></div></div></article>
      <div class="decision-grid"><article><div class="article-head"><div><label>经理判断</label><h3>系统准备怎样调整</h3></div><button id="decision-evidence-open" class="decision-action-button">查看任务依据</button></div><div id="decision-manager-list" class="decision-stack friendly-empty">正在分析…</div></article><article><div class="article-head"><div><label>8 个员工日报</label><h3>每个员工的判断与建议</h3></div><button id="decision-reports-open" class="decision-action-button">查看全部任务</button></div><div id="decision-agent-grid" class="decision-agent-grid friendly-empty">正在读取…</div></article></div>
      <article class="wide decision-team"><div class="article-head"><div><label>团队协作</label><h3>不是各干各的，而是共享信息后继续下一轮</h3></div><span class="chip">团队共享</span></div><p class="decision-team-copy">一个员工发现的信息会进入经理汇总；相关员工可以从同一批真实执行结果中继续做关键词、内容、区域、转化和复盘。下面展示团队协作链和今天的共享发现。</p><div class="decision-flow"><button data-team-page="insights">市场情报</button><span>→</span><button data-team-page="promotion">SEO/GEO</button><span>→</span><button data-team-page="promotion">内容/社媒/短视频</button><span>→</span><button data-team-page="insights">本地增长</button><span>→</span><button data-team-page="analytics">用户转化</button><span>→</span><button data-team-page="review">数据复盘</button><span>→</span><button data-team-page="workflow">R7 经理</button><span>→</span><button data-team-page="handoff">ChatGPT 战略</button></div><div id="decision-shared-context" class="decision-shared-context friendly-empty">正在整理团队共享发现…</div></article>
      <article class="wide"><div class="article-head"><div><label>ChatGPT 战略交接</label><h3>经理报告已准备好给总控制大脑复盘</h3></div><button id="decision-bridge-open" class="decision-action-button">查看交接连接</button></div><div id="decision-handoff" class="decision-handoff">等待报告。</div></article>
    `;
    const workflow=$('workflow');
    if(workflow)workflow.insertAdjacentElement('afterend',section);else main.appendChild(section);
    $('decision-refresh')?.addEventListener('click',async()=>{
      const button=$('decision-refresh');button.disabled=true;const old=button.textContent;button.textContent='正在重新汇总…';
      try{
        const data=await api('/api/r7/decision-center/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        renderDecisionCenter(data);toast('AI 自主决策报告已更新');
        button.textContent='已更新';setTimeout(()=>{if(button&&!button.disabled)button.textContent=old},1200);
      }catch(error){toast(error.message,'error')}finally{button.disabled=false;if(button.textContent==='正在重新汇总…')button.textContent=old}
    });
    bindDecisionStaticControls();
  }

  function levelClass(level){return level==='high'?'high':level==='medium'?'medium':''}
  function renderSharedContext(reports){
    const items=[];const seen=new Set();
    (reports||[]).forEach(report=>(report.evidence||[]).forEach(value=>{
      const text=String(value||'').trim();if(!text||seen.has(text))return;seen.add(text);items.push({agent:report.agent,text});
    }));
    const box=$('decision-shared-context');if(!box)return;
    box.className=items.length?'decision-shared-context':'friendly-empty';
    box.innerHTML=items.length?items.slice(0,8).map(item=>`<div class="decision-shared-item"><b>${esc(item.agent)}</b>${esc(item.text)}</div>`).join(''):'当前已完成任务还没有产生新的可核验共享发现。';
  }

  function bindDecisionDynamicControls(data){
    document.querySelectorAll('.decision-agent[data-agent-name]').forEach(card=>decisionActivate(card,()=>decisionOpenWorkflow('today',card.dataset.agentName),`查看${card.dataset.agentName}今天的任务`));
    document.querySelectorAll('.decision-item[data-decision-index]').forEach(card=>{
      const item=(data?.manager_decisions||[])[Number(card.dataset.decisionIndex)]||{};const target=decisionTarget(item);
      decisionActivate(card,()=>{if(target.type==='workflow')decisionOpenWorkflow(target.filter);else decisionOpenPage(target.page,target.label)},target.label);
    });
  }

  function renderDecisionCenter(data){
    ensureDecisionPage();
    const summary=data?.manager_summary||{};
    $('decision-headline').textContent=summary.headline||'经理报告暂无结论';
    const stamp=data?.generated_at?(typeof r7FullDateTime==='function'?r7FullDateTime(data.generated_at):formatTime(data.generated_at)):'尚未生成';
    $('decision-generated').textContent=data?.generated_at?`最近汇总：${stamp}`:stamp;
    $('decision-planned').textContent=summary.planned??0;$('decision-completed').textContent=summary.completed??0;$('decision-queued').textContent=summary.queued??0;$('decision-failed').textContent=summary.failed??0;$('decision-rate').textContent=`${summary.completion_rate??0}%`;
    const decisions=data?.manager_decisions||[];
    $('decision-manager-list').className=decisions.length?'decision-stack':'friendly-empty';
    $('decision-manager-list').innerHTML=decisions.length?decisions.map((item,index)=>{const target=decisionTarget(item);return `<div class="decision-item" data-decision-index="${index}"><span class="decision-level ${levelClass(item.level)}">${esc(item.level==='high'?'优先':item.level==='medium'?'关注':'正常')}</span><strong>${esc(item.action)}</strong><p>${esc(item.reason)}</p><span class="decision-item-hint">${esc(target.label)} →</span></div>`}).join(''):'当前没有新的策略调整。';
    const reports=data?.employee_reports||[];
    $('decision-agent-grid').className=reports.length?'decision-agent-grid':'friendly-empty';
    $('decision-agent-grid').innerHTML=reports.length?reports.map(item=>`<div class="decision-agent" data-agent-name="${esc(item.agent)}"><div class="decision-agent-head"><strong>${esc(item.agent)}</strong><span class="decision-agent-state ${esc(item.status)}">${esc(item.status)}</span></div><div class="decision-agent-metrics"><span>计划 ${item.planned||0}</span><span>完成 ${item.completed||0}</span><span>待执行 ${item.queued||0}</span><span>完成度 ${item.completion_rate||0}%</span></div><div class="decision-agent-judge">${esc(item.judgement||'暂无判断')}</div>${item.evidence?.length?`<ul class="decision-evidence">${item.evidence.slice(0,3).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}<span class="decision-agent-open">查看这个员工今天的任务 →</span></div>`).join(''):'暂无员工汇报。';
    renderSharedContext(reports);
    const handoff=data?.chatgpt_handoff||{};
    const questions=handoff.questions||[];
    $('decision-handoff').innerHTML=`<strong>${esc(handoff.purpose||'等待经理报告')}</strong>${questions.map(q=>`<p>• ${esc(q)}</p>`).join('')}<p><b>安全边界：</b>${esc(data?.guardrails?.financial||'资金事项人工处理')}</p><p><b>发布真实性：</b>${esc(data?.guardrails?.external_publish||'没有平台回执不记为已发布')}</p>`;
    bindDecisionStaticControls();bindDecisionDynamicControls(data);
  }

  async function loadDecisionCenter(){
    ensureDecisionPage();
    try{renderDecisionCenter(await api('/api/r7/decision-center'));return true}catch(error){toast(error.message,'error');return false}
  }
  window.loadDecisionCenter=loadDecisionCenter;
  ensureDecisionPage();
  loadDecisionCenter();
  setInterval(()=>{if($('decision-center')?.classList.contains('active'))loadDecisionCenter()},60000);
})();
