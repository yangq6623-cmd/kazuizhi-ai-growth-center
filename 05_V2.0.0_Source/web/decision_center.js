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
      .decision-hero h2{margin:7px 0 5px;font-size:25px}.decision-hero p{color:#dce8ff;margin:0}.decision-hero .article-head{align-items:flex-start}.decision-live{background:rgba(255,255,255,.14);border-radius:999px;padding:7px 10px;font-size:11px;white-space:nowrap}
      .decision-stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:18px}.decision-stat{background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.13);border-radius:12px;padding:12px}.decision-stat b{display:block;font-size:22px}.decision-stat small{display:block;margin-top:5px;color:#dce8ff;font-size:10px}
      .decision-grid{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:16px;align-items:start}.decision-stack{display:grid;gap:10px}.decision-item{border:1px solid #e1e8f3;border-radius:12px;padding:12px;background:#fff}.decision-item strong{display:block;color:#17243b;margin-bottom:6px}.decision-item p{margin:0;color:#65748b;font-size:12px;line-height:1.6}.decision-level{display:inline-block;font-size:9px;border-radius:999px;padding:4px 7px;background:#eef4ff;color:#2d61ca;margin-bottom:7px}.decision-level.high{background:#fff0ed;color:#b2483c}.decision-level.medium{background:#fff6e8;color:#94611c}
      .decision-agent-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.decision-agent{border:1px solid #e1e8f3;border-radius:12px;padding:12px;background:#fff}.decision-agent-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.decision-agent-state{font-size:9px;padding:4px 7px;border-radius:999px;background:#eef2f7;color:#5e6d83}.decision-agent-state.工作中{background:#e8f1ff;color:#245fc9}.decision-agent-state.待执行{background:#fff3dd;color:#95611b}.decision-agent-state.今日已完成{background:#e7f8f1;color:#087a50}.decision-agent-state.异常{background:#fff0ef;color:#b43b32}.decision-agent-metrics{display:flex;gap:8px;flex-wrap:wrap;margin:9px 0;color:#63738c;font-size:10px}.decision-agent-judge{font-size:12px;line-height:1.55;color:#33435c}.decision-evidence{margin-top:8px;font-size:10px;color:#74839a}.decision-evidence li{margin:4px 0}.decision-handoff{background:#f6f8ff;border:1px solid #dfe7fb;border-radius:12px;padding:13px}.decision-handoff strong{display:block;margin-bottom:6px}.decision-handoff p{margin:4px 0;color:#576a86;font-size:12px;line-height:1.55}.decision-refresh{border:0;background:#fff;color:#285fc9;border-radius:9px;padding:8px 11px;font-weight:700;cursor:pointer}.decision-refresh:disabled{opacity:.6;cursor:default}
      @media(max-width:1100px){.decision-grid{grid-template-columns:1fr}.decision-stats{grid-template-columns:repeat(3,1fr)}}
      @media(max-width:700px){.decision-stats{grid-template-columns:repeat(2,1fr)}.decision-agent-grid{grid-template-columns:1fr}}
    `;document.head.appendChild(style);
  }

  function ensureDecisionPage(){
    if ($('decision-center')) return;
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
      <div class="page-title"><small>AI 自主决策中心 V1</small><h2>员工汇报，R7 汇总，ChatGPT 做战略判断</h2><p>员工可以在自己的职责范围内自主判断和优化；R7 每 5 分钟汇总一次。资金、安全和未连接平台始终受保护。</p></div>
      <article class="wide decision-hero"><div class="article-head"><div><label>R7 经理报告</label><h2 id="decision-headline">正在整理今天的员工汇报…</h2><p id="decision-generated">等待第一份经理报告</p></div><div><span class="decision-live">● 每 5 分钟自动汇总</span> <button id="decision-refresh" class="decision-refresh">立即刷新分析</button></div></div><div class="decision-stats"><div class="decision-stat"><b id="decision-planned">--</b><small>今日计划</small></div><div class="decision-stat"><b id="decision-completed">--</b><small>已经完成</small></div><div class="decision-stat"><b id="decision-queued">--</b><small>等待执行</small></div><div class="decision-stat"><b id="decision-failed">--</b><small>失败/异常</small></div><div class="decision-stat"><b id="decision-rate">--</b><small>今日完成度</small></div></div></article>
      <div class="decision-grid"><article><div class="article-head"><div><label>经理判断</label><h3>系统准备怎样调整</h3></div><span class="chip">依据真实记录</span></div><div id="decision-manager-list" class="decision-stack friendly-empty">正在分析…</div></article><article><div class="article-head"><div><label>8 个员工日报</label><h3>每个员工的判断与建议</h3></div><span class="chip">向上汇报</span></div><div id="decision-agent-grid" class="decision-agent-grid friendly-empty">正在读取…</div></article></div>
      <article class="wide"><div class="article-head"><div><label>ChatGPT 战略交接</label><h3>经理报告已准备好给总控制大脑复盘</h3></div><span id="decision-handoff-status" class="status-pill waiting">准备中</span></div><div id="decision-handoff" class="decision-handoff">等待报告。</div></article>
    `;
    const workflow=$('workflow');
    if(workflow)workflow.insertAdjacentElement('afterend',section);else main.appendChild(section);
    $('decision-refresh')?.addEventListener('click',async()=>{
      const button=$('decision-refresh');button.disabled=true;const old=button.textContent;button.textContent='正在分析…';
      try{const data=await api('/api/r7/decision-center/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});renderDecisionCenter(data);toast('AI 自主决策报告已更新')}
      catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent=old}
    });
  }

  function levelClass(level){return level==='high'?'high':level==='medium'?'medium':''}
  function renderDecisionCenter(data){
    ensureDecisionPage();
    const summary=data?.manager_summary||{};
    $('decision-headline').textContent=summary.headline||'经理报告暂无结论';
    const stamp=data?.generated_at?(typeof r7FullDateTime==='function'?r7FullDateTime(data.generated_at):formatTime(data.generated_at)):'尚未生成';
    $('decision-generated').textContent=data?.generated_at?`最近汇总：${stamp}`:stamp;
    $('decision-planned').textContent=summary.planned??0;$('decision-completed').textContent=summary.completed??0;$('decision-queued').textContent=summary.queued??0;$('decision-failed').textContent=summary.failed??0;$('decision-rate').textContent=`${summary.completion_rate??0}%`;
    const decisions=data?.manager_decisions||[];
    $('decision-manager-list').className=decisions.length?'decision-stack':'friendly-empty';
    $('decision-manager-list').innerHTML=decisions.length?decisions.map(item=>`<div class="decision-item"><span class="decision-level ${levelClass(item.level)}">${esc(item.level==='high'?'优先':item.level==='medium'?'关注':'正常')}</span><strong>${esc(item.action)}</strong><p>${esc(item.reason)}</p></div>`).join(''):'当前没有新的策略调整。';
    const reports=data?.employee_reports||[];
    $('decision-agent-grid').className=reports.length?'decision-agent-grid':'friendly-empty';
    $('decision-agent-grid').innerHTML=reports.length?reports.map(item=>`<div class="decision-agent"><div class="decision-agent-head"><strong>${esc(item.agent)}</strong><span class="decision-agent-state ${esc(item.status)}">${esc(item.status)}</span></div><div class="decision-agent-metrics"><span>计划 ${item.planned||0}</span><span>完成 ${item.completed||0}</span><span>待执行 ${item.queued||0}</span><span>完成度 ${item.completion_rate||0}%</span></div><div class="decision-agent-judge">${esc(item.judgement||'暂无判断')}</div>${item.evidence?.length?`<ul class="decision-evidence">${item.evidence.slice(0,3).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}</div>`).join(''):'暂无员工汇报。';
    const handoff=data?.chatgpt_handoff||{};
    $('decision-handoff-status').textContent=handoff.status==='ready_for_strategy_review'?'已准备':'准备中';$('decision-handoff-status').className=`status-pill ${handoff.status==='ready_for_strategy_review'?'ready':'waiting'}`;
    const questions=handoff.questions||[];
    $('decision-handoff').innerHTML=`<strong>${esc(handoff.purpose||'等待经理报告')}</strong>${questions.map(q=>`<p>• ${esc(q)}</p>`).join('')}<p><b>安全边界：</b>${esc(data?.guardrails?.financial||'资金事项人工处理')}</p><p><b>发布真实性：</b>${esc(data?.guardrails?.external_publish||'没有平台回执不记为已发布')}</p>`;
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
