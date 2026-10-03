const R7_STATE={awaiting_approval:'历史待处理',human_required:'平台人工待处理',queued:'自动待执行',running:'自动执行中',completed:'已完成',failed:'失败',cancelled:'已取消'};
const R7_AGENT_TARGETS={market:'insights',seo:'promotion',content:'promotion',social:'promotion',video:'promotion',local:'insights',conversion:'analytics',review:'review'};
let r7Jobs=[];
let r7Agents=[];
let r7TaskFilter='today';
let r7AgentFilter='';

function r7DateKey(value){
  if(!value)return '';
  const date=new Date(value);
  if(Number.isNaN(date.getTime()))return String(value).slice(0,10);
  const pad=n=>String(n).padStart(2,'0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}`;
}
function r7TodayKey(){return r7DateKey(new Date())}
function r7IsToday(value){return r7DateKey(value)===r7TodayKey()}
function r7TodayAssigned(job){return r7IsToday(job.created_at)||r7IsToday(job.due_at)}
function r7CompletedToday(job){return job.state==='completed'&&r7IsToday(job.updated_at||job.created_at)}
function r7TodayRelevant(job){return r7TodayAssigned(job)||r7IsToday(job.updated_at)}
function r7JobTime(job){return job.updated_at||job.created_at||job.due_at||''}
function r7ResultSummary(result){
  if(!result)return '';
  return result.outcome||result.summary||result.headline||result.status||result.kind||'';
}
function r7JobMatchesAgent(job,agentName){return String(job.agent||'')===String(agentName||'')}

function ensureR7HumanizedStyle(){
  if(document.getElementById('r7-humanized-style'))return;
  const style=document.createElement('style');
  style.id='r7-humanized-style';
  style.textContent=`
  #workflow .r7-overview{display:none!important}
  .r7-today-command{margin:16px 0 18px;background:linear-gradient(135deg,#173f91,#2f6de9 62%,#5167dc);color:#fff;border:0;box-shadow:0 16px 38px rgba(35,82,170,.2)}
  .r7-today-command label{color:#d9e7ff}.r7-today-command h3{font-size:22px;margin:7px 0 3px}.r7-today-command p{color:#dce7ff;margin:0;font-size:12px}
  .r7-today-head{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}.r7-live-dot{display:inline-flex;align-items:center;gap:7px;background:rgba(255,255,255,.14);padding:8px 11px;border-radius:999px;font-size:11px;white-space:nowrap}.r7-live-dot i{width:8px;height:8px;border-radius:50%;background:#62e2a8;box-shadow:0 0 0 4px rgba(98,226,168,.16)}
  .r7-today-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:18px}.r7-today-stat{background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.12);border-radius:13px;padding:13px}.r7-today-stat b{display:block;font-size:24px;line-height:1.1}.r7-today-stat small{display:block;color:#dbe7ff;margin-top:6px;font-size:11px}.r7-today-stat.attention b{color:#ffd4bf}
  .r7-day-progress{margin-top:16px;display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;font-size:12px}.r7-day-progress-track{height:8px;border-radius:999px;background:rgba(255,255,255,.2);overflow:hidden}.r7-day-progress-track i{display:block;height:100%;background:#69e2ac;border-radius:999px}.r7-day-progress strong{font-size:12px}.r7-today-alert{margin-top:10px;font-size:11px;color:#ffe0d1}.r7-today-alert:empty{display:none}
  #workflow>.grid.two{grid-template-columns:minmax(0,1.18fr) minmax(420px,.82fr);align-items:start}.r7-task-center,.r7-agent-center{min-height:620px}.r7-task-center .article-head,.r7-agent-center .article-head{position:sticky;top:76px;background:#fff;z-index:2;padding-bottom:10px}.r7-head-actions{display:flex;gap:8px;align-items:center}.r7-new-task-button{border:0;background:#3168e8;color:#fff;border-radius:9px;padding:8px 11px;font-size:12px;font-weight:700;cursor:pointer}.r7-create-form[hidden],.r7-create-help[hidden]{display:none!important}.r7-create-form{background:#f7f9fd;border:1px solid #e1e8f4;border-radius:12px;padding:12px;margin-bottom:8px}
  .r7-job-filters{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.r7-job-filter{border:1px solid #dce5f3;background:#fff;color:#60708a;border-radius:999px;padding:7px 10px;font-size:11px;cursor:pointer}.r7-job-filter.active{background:#eaf1ff;color:#245cca;border-color:#bcd0fb;font-weight:700}.r7-agent-filter-note{display:flex;align-items:center;justify-content:space-between;gap:10px;background:#edf5ff;color:#315dba;border-radius:10px;padding:9px 11px;font-size:11px;margin-bottom:10px}.r7-agent-filter-note button{border:0;background:transparent;color:#315dba;font-weight:700;cursor:pointer}
  .r7-job-list{max-height:720px}.r7-job{background:#fff}.r7-job.is-running{border-color:#9fc2ff;box-shadow:0 7px 18px rgba(49,104,232,.08)}.r7-job.is-human{border-color:#f2cf99;background:#fffbf3}.r7-job.is-failed{border-color:#efb4ae;background:#fff8f7}.r7-job.is-completed{background:#fbfdfc}.r7-job-top strong{font-size:14px;line-height:1.45}.r7-job-meta{display:flex;flex-wrap:wrap;gap:7px;margin-top:5px;color:#718096;font-size:11px}.r7-job-compact-result{margin-top:9px;color:#336b57;font-size:12px;line-height:1.55}.r7-job details{margin-top:9px;border-top:1px dashed #e0e6ef;padding-top:8px}.r7-job details summary{cursor:pointer;color:#3168e8;font-size:11px;font-weight:700}.r7-result{margin-top:8px}.r7-empty-filter{padding:32px 16px;text-align:center;color:#7b899d;background:#f8fafc;border-radius:12px}
  .r7-agent-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.r7-agent{position:relative;padding:14px;min-height:164px;background:#fff;cursor:pointer;transition:.16s}.r7-agent:hover{transform:translateY(-1px);box-shadow:0 9px 20px rgba(28,58,110,.09)}.r7-agent-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.r7-agent-name{font-size:15px}.r7-agent-state{font-size:10px;border-radius:999px;padding:5px 8px;background:#eef2f7;color:#637189;white-space:nowrap}.r7-agent-state.working{background:#e8f1ff;color:#265fc9}.r7-agent-state.queued{background:#fff3dd;color:#99621a}.r7-agent-state.done{background:#e7f8f1;color:#087b51}.r7-agent-state.error{background:#fff0ef;color:#b43b32}.r7-agent-purpose{font-size:11px!important;color:#7b899d!important;margin:7px 0 9px!important}.r7-agent-current{font-size:12px;line-height:1.55;color:#31405a;min-height:38px}.r7-agent-current b{display:inline!important;color:#172033}.r7-agent-progress{height:6px;border-radius:999px;background:#edf1f7;overflow:hidden;margin:9px 0 8px}.r7-agent-progress i{display:block;height:100%;background:#3168e8;border-radius:999px}.r7-agent-foot{display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:10px;color:#74839a}.r7-agent-workbench{border:0;background:#f0f5ff;color:#2e61c8;padding:5px 7px;border-radius:7px;font-size:10px;cursor:pointer}.r7-agent-filtered{outline:2px solid #7aa3ff;outline-offset:2px}
  #r7-human-panel{border-color:#f0d39f;background:#fffdf8}#r7-human-panel[hidden]{display:none!important}.r7-audit-list[hidden]{display:none!important}.r7-audit-toggle{border:0;background:#f1f5fb;color:#52657f;border-radius:8px;padding:7px 10px;font-size:11px;cursor:pointer}
  @media(max-width:1150px){#workflow>.grid.two{grid-template-columns:1fr}.r7-task-center,.r7-agent-center{min-height:0}.r7-today-stats{grid-template-columns:repeat(2,1fr)}.r7-task-center .article-head,.r7-agent-center .article-head{position:static}}
  @media(max-width:680px){.r7-today-stats{grid-template-columns:1fr 1fr}.r7-day-progress{grid-template-columns:1fr}.r7-agent-grid{grid-template-columns:1fr}.r7-today-head{flex-direction:column}.r7-today-command{padding:16px}}
  `;
  document.head.appendChild(style);
}

function ensureTodayCommandCenter(){
  const workflow=$('workflow');
  if(!workflow)return null;
  let panel=$('r7-today-command');
  if(panel)return panel;
  const overview=workflow.querySelector('.r7-overview');
  panel=document.createElement('article');
  panel.id='r7-today-command';
  panel.className='r7-today-command';
  panel.innerHTML=`<div class="r7-today-head"><div><label>老板今日工作台</label><h3>今天 AI 员工在做什么</h3><p id="r7-today-subtitle">正在汇总今天的任务、进度和完成情况…</p></div><span class="r7-live-dot"><i></i>每 15 秒自动更新</span></div><div class="r7-today-stats"><div class="r7-today-stat"><b id="r7-today-working">0</b><small>AI 员工正在工作</small></div><div class="r7-today-stat"><b id="r7-today-queued">0</b><small>任务等待执行</small></div><div class="r7-today-stat"><b id="r7-today-completed">0</b><small>今天已经完成</small></div><div class="r7-today-stat attention"><b id="r7-today-human">0</b><small>需要你人工处理</small></div></div><div class="r7-day-progress"><span>今日要求完成度</span><div class="r7-day-progress-track"><i id="r7-day-progress-bar" style="width:0%"></i></div><strong id="r7-day-progress-text">0 / 0</strong></div><div id="r7-today-alert" class="r7-today-alert"></div>`;
  if(overview)overview.parentNode.insertBefore(panel,overview);else workflow.querySelector('.page-title')?.insertAdjacentElement('afterend',panel);
  return panel;
}

function ensureTaskCenterUX(){
  const workflow=$('workflow');
  const grid=workflow?.querySelector('.grid.two');
  if(!grid)return;
  const taskArticle=grid.children[0],agentArticle=grid.children[1];
  if(taskArticle){
    taskArticle.classList.add('r7-task-center');
    const h3=taskArticle.querySelector('.article-head h3');if(h3)h3.textContent='今日任务';
    const head=taskArticle.querySelector('.article-head');
    const refresh=$('r7-refresh');
    if(head&&!$('r7-new-task-toggle')){
      const wrap=document.createElement('div');wrap.className='r7-head-actions';
      const create=document.createElement('button');create.id='r7-new-task-toggle';create.className='r7-new-task-button';create.textContent='+ 新建任务';
      if(refresh){head.replaceChild(wrap,refresh);wrap.append(create,refresh)}else{head.appendChild(wrap);wrap.appendChild(create)}
      create.addEventListener('click',()=>{
        const form=taskArticle.querySelector('.r7-create-form'),help=taskArticle.querySelector('.r7-create-form + .form-help, .r7-create-help');
        const opening=form?.hidden!==false;
        if(form)form.hidden=!opening;if(help)help.hidden=!opening;
        create.textContent=opening?'收起新建任务':'+ 新建任务';
      });
    }
    const form=taskArticle.querySelector('.r7-create-form');
    const help=taskArticle.querySelector('.r7-create-form + .form-help');
    if(form&&!form.dataset.humanized){form.dataset.humanized='1';form.hidden=true}
    if(help&&!help.dataset.humanized){help.dataset.humanized='1';help.classList.add('r7-create-help');help.hidden=true}
    if(!$('r7-job-filters')){
      const filters=document.createElement('div');filters.id='r7-job-filters';filters.className='r7-job-filters';
      filters.innerHTML=`<button class="r7-job-filter" data-filter="today">今天全部</button><button class="r7-job-filter" data-filter="active">正在处理</button><button class="r7-job-filter" data-filter="running">执行中</button><button class="r7-job-filter" data-filter="completed">今天完成</button><button class="r7-job-filter" data-filter="human">人工处理</button><button class="r7-job-filter" data-filter="failed">失败</button><button class="r7-job-filter" data-filter="all">全部记录</button>`;
      const jobs=$('r7-jobs');if(jobs)jobs.parentNode.insertBefore(filters,jobs);
      filters.addEventListener('click',event=>{
        const button=event.target.closest('.r7-job-filter');if(!button)return;
        r7TaskFilter=button.dataset.filter;r7AgentFilter='';renderR7Jobs(r7Jobs);
      });
    }
    if(!$('r7-agent-filter-note')){
      const note=document.createElement('div');note.id='r7-agent-filter-note';note.className='r7-agent-filter-note';note.hidden=true;
      note.innerHTML='<span></span><button type="button">取消筛选</button>';
      note.querySelector('button').addEventListener('click',()=>{r7AgentFilter='';r7TaskFilter='today';renderR7Jobs(r7Jobs);renderR7Agents(r7Agents)});
      $('r7-job-filters')?.insertAdjacentElement('afterend',note);
    }
  }
  if(agentArticle){
    agentArticle.classList.add('r7-agent-center');
    const h3=agentArticle.querySelector('.article-head h3');if(h3)h3.textContent='8 个 AI 员工 · 今日工作状态';
    const chip=agentArticle.querySelector('.chip');if(chip)chip.textContent='实时状态';
  }
}

function applyAutonomyCopy(){
  ensureR7HumanizedStyle();
  const workflow=$('workflow');
  if(!workflow)return;
  const pageCopy=workflow.querySelector('.page-title p');
  if(pageCopy)pageCopy.textContent='打开这里就能看到：谁正在工作、做到哪一步、今天完成多少、还有什么需要你处理。';
  const overview=workflow.querySelectorAll('.r7-overview article p');
  if(overview[0])overview[0].textContent='本地调度自动检查到期任务，无需人工批准非资金运营任务。';
  if(overview[1])overview[1].textContent='失败任务自动记录并按策略重试；资金事项单独进入平台人工待处理。';
  const createButton=$('r7-create');if(createButton)createButton.textContent='创建自动任务';
  const kind=$('r7-kind');if(kind&&kind.options[0])kind.options[0].textContent='自动运营任务';
  const help=workflow.querySelector('.r7-create-form + .form-help');
  if(help)help.textContent='非资金任务创建后自动排队执行；退款、结算、改价、提现等资金事项只记录并交平台人工处理。';
  ensureTodayCommandCenter();
  ensureTaskCenterUX();
}
window.applyAutonomyCopy=applyAutonomyCopy;
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyAutonomyCopy);else applyAutonomyCopy();

function r7Action(job,action,label){return `<button class="outline-button r7-action" data-job="${esc(job.id)}" data-action="${action}">${label}</button>`}
function r7ListValues(value){
  if(!Array.isArray(value))return [];
  return value.slice(0,5).map(item=>typeof item==='string'?item:(item?.keyword||item?.title||item?.name||item?.region||JSON.stringify(item))).filter(Boolean);
}
function r7ResultHtml(result){
  if(!result)return '';
  const lines=[];
  const headline=result.outcome||result.summary||result.headline||result.status||result.kind;
  if(typeof headline==='string'&&headline)lines.push(`<div><b>执行成果：</b>${esc(headline)}</div>`);
  if(result.scope)lines.push(`<div><b>范围：</b>${esc(result.scope)}</div>`);
  if(Number.isFinite(result.public_signal_count))lines.push(`<div><b>公开信号：</b>${esc(result.public_signal_count)} 条</div>`);
  const needs=r7ListValues(result.top_needs||result.key_findings);
  if(needs.length)lines.push(`<div><b>关键发现：</b>${needs.map(esc).join('；')}</div>`);
  const regions=r7ListValues(result.top_regions);
  if(regions.length)lines.push(`<div><b>重点区域：</b>${regions.map(esc).join('；')}</div>`);
  if(Number.isFinite(result.calendar_days))lines.push(`<div><b>计划产出：</b>${esc(result.calendar_days)} 天运营日历</div>`);
  const recs=r7ListValues(result.recommendations||result.next_actions);
  if(recs.length)lines.push(`<div><b>下一步：</b>${recs.map(esc).join('；')}</div>`);
  if(result.kind&&result.draft_id)lines.push(`<div><b>草稿：</b>${esc(result.kind)} · ${esc(result.draft_id)}</div>`);
  const note=result.source_note||result.limitation||result.note;
  if(note)lines.push(`<div><b>说明：</b>${esc(note)}</div>`);
  if(!lines.length)lines.push('<div><b>执行成果：</b>已完成并写入执行记录</div>');
  return `<div class="r7-result">${lines.join('')}</div>`;
}
function r7FilteredJobs(items){
  let filtered=[...items];
  if(r7AgentFilter)filtered=filtered.filter(job=>r7JobMatchesAgent(job,r7AgentFilter));
  else if(r7TaskFilter==='today')filtered=filtered.filter(r7TodayRelevant);
  else if(r7TaskFilter==='active')filtered=filtered.filter(job=>['running','queued','failed','human_required'].includes(job.state));
  else if(r7TaskFilter==='running')filtered=filtered.filter(job=>job.state==='running');
  else if(r7TaskFilter==='completed')filtered=filtered.filter(r7CompletedToday);
  else if(r7TaskFilter==='human')filtered=filtered.filter(job=>job.state==='human_required');
  else if(r7TaskFilter==='failed')filtered=filtered.filter(job=>job.state==='failed');
  filtered.sort((a,b)=>new Date(r7JobTime(b)).getTime()-new Date(r7JobTime(a)).getTime());
  return filtered;
}
function updateFilterUI(){
  document.querySelectorAll('.r7-job-filter').forEach(button=>button.classList.toggle('active',!r7AgentFilter&&button.dataset.filter===r7TaskFilter));
  const note=$('r7-agent-filter-note');
  if(note){note.hidden=!r7AgentFilter;note.querySelector('span').textContent=r7AgentFilter?`正在查看：${r7AgentFilter} 今天的工作记录`:''}
}
function renderR7Jobs(items){
  r7Jobs=items;
  ensureTaskCenterUX();
  updateFilterUI();
  const shown=r7FilteredJobs(items);
  const taskTitle=$('r7-jobs')?.closest('article')?.querySelector('.article-head h3');
  if(taskTitle)taskTitle.textContent=`今日任务 · ${shown.length}`;
  $('r7-jobs').className=shown.length?'r7-job-list':'friendly-empty';
  $('r7-jobs').innerHTML=shown.length?shown.map(job=>{
    let actions='';
    if(job.state==='awaiting_approval')actions='<span class="subtle">这是旧版本遗留记录，新版本启动后会按新自动化策略迁移处理。</span>';
    if(job.state==='human_required')actions='<span class="subtle">请到小程序/平台后台由人工处理资金事项；R7 只记录，不执行。</span>';
    if(job.state==='queued'&&job.mode==='local')actions=`<span class="subtle">${esc(job.authorization_note||'已进入自动执行队列，无需人工批准。')}</span>`;
    if(job.state==='failed'&&job.risk!=='financial')actions=r7Action(job,'retry','立即重试')+r7Action(job,'cancel','取消');
    const riskLabel=job.risk==='financial'?'平台人工':'全自动';
    const summary=r7ResultSummary(job.result);
    const detail=(job.result||job.error||actions)?`<details><summary>查看详情</summary>${job.error?`<p class="r7-error">${esc(job.error)}</p>`:''}${job.result?r7ResultHtml(job.result):''}<div class="r7-job-actions">${actions}</div></details>`:'';
    const cls=job.state==='running'?'is-running':job.state==='completed'?'is-completed':job.state==='human_required'?'is-human':job.state==='failed'?'is-failed':'';
    return `<article class="r7-job ${cls}"><div class="r7-job-top"><div><strong>${esc(job.title)}</strong><div class="r7-job-meta"><span>${esc(job.agent||'运营协调员')}</span><span>${riskLabel}</span><span>更新 ${formatTime(job.updated_at||job.created_at)}</span></div></div><span class="status-pill ${job.state==='completed'?'ready':job.state==='failed'||job.state==='human_required'?'blocked':'waiting'}">${R7_STATE[job.state]||esc(job.state)}</span></div><div class="r7-progress"><i style="width:${job.progress||0}%"></i></div><p>进度 ${job.progress||0}% · ${job.completed_steps||0}/${job.total_steps||1} 步${job.due_at?' · 计划 '+formatTime(job.due_at):''}</p>${summary?`<div class="r7-job-compact-result"><b>结果：</b>${esc(summary)}</div>`:''}${detail}</article>`;
  }).join(''):'<div class="r7-empty-filter">当前筛选下没有任务。系统仍会每 15 秒自动检查并更新状态。</div>';
  document.querySelectorAll('.r7-action').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;
    const payload={id:button.dataset.job,action:button.dataset.action,actor:'本机管理员'};
    try{await api('/api/r7/jobs/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});await loadR7();toast('任务状态已更新')}
    catch(error){toast(error.message,'error');button.disabled=false}
  }));
}

function ensureHumanInterventionPanel(){
  let panel=$('r7-human-panel');
  if(panel)return panel;
  const audit=$('r7-audit-list')?.closest('article');
  if(!audit)return null;
  panel=document.createElement('article');
  panel.id='r7-human-panel';
  panel.className='wide';
  panel.innerHTML='<div class="article-head"><div><label>平台人工待处理</label><h3 id="r7-human-title">0 项需要平台人工介入</h3></div><span class="chip">只记录 · 不自动执行</span></div><div id="r7-human-list" class="friendly-empty">当前没有资金类人工事项。</div>';
  audit.parentNode.insertBefore(panel,audit);
  return panel;
}
function interventionType(title){
  const text=String(title||'');
  if(text.includes('退款')||text.includes('退费')||text.includes('返款'))return '退款';
  if(text.includes('提现'))return '提现';
  if(text.includes('结算'))return '结算';
  if(text.includes('改价')||text.includes('调价'))return '改价';
  if(text.includes('付款')||text.includes('支付')||text.includes('打款')||text.includes('转账'))return '付款/划转';
  return '资金事项';
}
function renderHumanInterventions(items){
  const panel=ensureHumanInterventionPanel();
  const list=$('r7-human-list'),title=$('r7-human-title');
  if(!list||!title||!panel)return;
  const rows=(items||[]).slice(0,20);
  panel.hidden=rows.length===0;
  title.textContent=`${rows.length} 项需要平台人工介入`;
  list.className=rows.length?'r7-job-list':'friendly-empty';
  list.innerHTML=rows.length?rows.map(item=>`<div class="r7-job is-human"><div class="r7-job-top"><div><strong>${esc(interventionType(item.title))} · ${esc(item.title||'未命名事项')}</strong><small>发现时间：${formatTime(item.created_at)} · 来源：${esc(item.source||'R7 自动识别')}</small></div><span class="status-pill blocked">${esc(item.status||'待平台人工处理')}</span></div><p>${esc(item.reason||'涉及资金事项，R7 仅记录，不执行。')}</p></div>`).join(''):'当前没有资金类人工事项。';
}

function agentTodayJobs(agentName){return r7Jobs.filter(job=>r7JobMatchesAgent(job,agentName)&&r7TodayRelevant(job))}
function renderR7Agents(items){
  r7Agents=items;
  const grid=$('r7-agent-grid');
  grid.innerHTML=items.map(agent=>{
    const all=r7Jobs.filter(job=>r7JobMatchesAgent(job,agent.name));
    const today=all.filter(r7TodayRelevant);
    const running=all.find(job=>job.state==='running');
    const queued=today.find(job=>job.state==='queued');
    const failed=today.find(job=>job.state==='failed');
    const completed=today.filter(r7CompletedToday);
    const current=running||failed||queued||completed[0]||null;
    let state='空闲',stateClass='idle';
    if(running){state='工作中';stateClass='working'}else if(failed){state='异常';stateClass='error'}else if(queued){state='待执行';stateClass='queued'}else if(completed.length){state='今日已完成';stateClass='done'}
    const currentText=running?`正在：${running.title}`:failed?`异常：${failed.title}`:queued?`下一项：${queued.title}`:completed.length?`最近完成：${completed[0].title}`:'当前没有任务';
    const progress=current?Number(current.progress||0):0;
    const todayAssigned=today.filter(job=>r7TodayAssigned(job)&&job.state!=='cancelled').length;
    const last=all.slice().sort((a,b)=>new Date(r7JobTime(b)).getTime()-new Date(r7JobTime(a)).getTime())[0];
    return `<div class="r7-agent r7-agent-action ${r7AgentFilter===agent.name?'r7-agent-filtered':''}" role="button" tabindex="0" data-agent-name="${esc(agent.name)}"><div class="r7-agent-top"><b class="r7-agent-name">${esc(agent.name)}</b><span class="r7-agent-state ${stateClass}">${state}</span></div><span class="r7-agent-purpose">${esc(agent.purpose)}</span><div class="r7-agent-current"><b>${esc(currentText)}</b></div><div class="r7-agent-progress"><i style="width:${progress}%"></i></div><div class="r7-agent-foot"><span>今日要求 ${todayAssigned} · 完成 ${completed.length}${last?` · 更新 ${formatTime(r7JobTime(last))}`:''}</span><button type="button" class="r7-agent-workbench" data-target="${esc(R7_AGENT_TARGETS[agent.id]||'workflow')}">工作台</button></div></div>`;
  }).join('');
  document.querySelectorAll('.r7-agent-action').forEach(card=>{
    const activate=()=>{r7AgentFilter=card.dataset.agentName;r7TaskFilter='today';renderR7Jobs(r7Jobs);renderR7Agents(r7Agents);$('r7-jobs')?.scrollIntoView({behavior:'smooth',block:'start'});toast(`正在查看${r7AgentFilter}今天的工作记录`)};
    card.addEventListener('click',event=>{if(event.target.closest('.r7-agent-workbench'))return;activate()});
    card.addEventListener('keydown',event=>{if((event.key==='Enter'||event.key===' ')&&!event.target.closest('.r7-agent-workbench')){event.preventDefault();activate()}});
  });
  document.querySelectorAll('.r7-agent-workbench').forEach(button=>button.addEventListener('click',event=>{event.stopPropagation();openPage(button.dataset.target);toast('已打开对应工作台')}));
}

function renderTodayCommand(engine){
  ensureTodayCommandCenter();
  const activeAuto=r7Jobs.filter(job=>job.risk!=='financial'&&job.state!=='cancelled');
  const assigned=activeAuto.filter(r7TodayAssigned);
  const assignedDone=assigned.filter(job=>job.state==='completed');
  const completedToday=r7Jobs.filter(r7CompletedToday);
  const runningAgents=new Set(r7Jobs.filter(job=>job.state==='running').map(job=>job.agent).filter(Boolean));
  const queued=r7Jobs.filter(job=>job.state==='queued'&&(r7TodayAssigned(job)||!job.due_at)).length;
  const human=Number(engine?.jobs?.human_required||0);
  const failed=Number(engine?.jobs?.failed||0);
  const pct=assigned.length?Math.round(assignedDone.length*100/assigned.length):0;
  $('r7-today-working').textContent=runningAgents.size;
  $('r7-today-queued').textContent=queued;
  $('r7-today-completed').textContent=completedToday.length;
  $('r7-today-human').textContent=human;
  $('r7-day-progress-bar').style.width=`${pct}%`;
  $('r7-day-progress-text').textContent=assigned.length?`${assignedDone.length} / ${assigned.length} · ${pct}%`:'今天暂未分配任务';
  const last=r7Jobs.slice().sort((a,b)=>new Date(r7JobTime(b)).getTime()-new Date(r7JobTime(a)).getTime())[0];
  $('r7-today-subtitle').textContent=`今日分配 ${assigned.length} 项 · 已完成 ${assignedDone.length} 项 · 当前工作中 ${runningAgents.size} 人${last?` · 最近更新 ${formatTime(r7JobTime(last))}`:''}`;
  $('r7-today-alert').textContent=failed?`注意：当前有 ${failed} 项失败任务，需要检查或等待自动重试。`:'';
}

function ensureAuditCollapse(){
  const list=$('r7-audit-list');
  const article=list?.closest('article');
  if(!list||!article)return;
  list.hidden=true;
  const head=article.querySelector('.article-head');
  if(head&&!$('r7-audit-toggle')){
    const button=document.createElement('button');button.id='r7-audit-toggle';button.className='r7-audit-toggle';button.textContent='查看技术日志';
    const badge=$('r7-audit-integrity');if(badge){const wrap=document.createElement('div');wrap.className='r7-head-actions';head.replaceChild(wrap,badge);wrap.append(badge,button)}else head.appendChild(button);
    button.addEventListener('click',()=>{list.hidden=!list.hidden;button.textContent=list.hidden?'查看技术日志':'收起技术日志'});
  }
}

function bindR7OverviewActions(){ensureAuditCollapse()}

async function loadR7(){
  try{
    applyAutonomyCopy();
    const [jobs,agents,engine,audit,routes]=await Promise.all([api('/api/r7/jobs'),api('/api/r7/agents'),api('/api/r7/engine'),api('/api/r7/audit'),api('/api/r7/model-routes')]);
    r7Jobs=jobs.items||[];
    renderTodayCommand(engine);
    renderR7Jobs(r7Jobs);
    const legacy=engine.jobs.awaiting_approval||0,human=engine.jobs.human_required||0,queued=engine.jobs.queued||0,running=engine.jobs.running||0,failed=engine.jobs.failed||0;
    $('r7-engine-status').textContent=`自动待执行 ${queued} · 自动执行中 ${running} · 平台人工 ${human} · 失败 ${failed}${legacy?` · 旧记录 ${legacy}`:''}`;
    $('r7-exceptions').textContent=(human||failed)?`${human} 项平台人工 · ${failed} 项失败`:'目前没有需要人工介入或失败的事项';
    $('r7-migration').textContent=engine.migration.result==='complete'?engine.migration.copied.length?`R6 数据备份已完成 · ${engine.migration.copied.length} 个文件`:`未发现旧版数据 · 可直接开始`:'正在检查旧数据';
    $('r7-model-route').textContent=`自动化策略：${engine.autonomy_policy||'非资金自动执行'}。当前可用模型路线：${routes.routes.map(x=>x.label).join('、')}。`;
    renderR7Agents(agents.items||[]);
    renderHumanInterventions(engine.human_interventions||[]);
    $('r7-audit-integrity').textContent=audit.integrity==='verified'?'自动运行正常 · 审计链已验证':'审计链异常，请停止执行并检查';
    $('r7-audit-list').innerHTML=audit.events.length?audit.events.slice(-20).reverse().map(event=>`<div class="r7-audit-row"><b>${esc(event.kind)}</b><span>${esc(event.actor)} · ${formatTime(event.at)}</span><small>${esc(event.job_id.slice(0,8))}</small></div>`).join(''):'尚无审计记录';
    bindR7OverviewActions();
    return true;
  }catch(error){toast(error.message,'error');return false}
}
window.loadR7=loadR7;

$('r7-create').addEventListener('click',async()=>{
  const button=$('r7-create');button.disabled=true;button.textContent='创建中…';
  try{
    const created=await api('/api/r7/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:$('r7-kind').value,title:$('r7-title').value,due_at:$('r7-due').value})});
    $('r7-title').value='';await loadR7();
    toast(created.state==='human_required'?'已记录为平台人工待处理':'任务已进入自动执行队列');
  }catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='创建自动任务'}
});
$('r7-refresh').addEventListener('click',async()=>{const button=$('r7-refresh');button.disabled=true;const original=button.textContent;button.textContent='刷新中…';try{if(await loadR7())toast('今日任务、AI 员工和完成进度已刷新')}finally{button.disabled=false;button.textContent=original}});
setInterval(()=>{if($('workflow').classList.contains('active'))loadR7()},15000);
