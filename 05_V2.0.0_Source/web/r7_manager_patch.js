/* R7 manager usability patch: clickable KPI filters, dismissible finance alerts,
   full timestamps and clearer employee activity. Loaded after r7.js. */

const R7_HUMAN_DISMISSED_KEY='kazuizhi_r7_human_dismissed_v1';
let r7ManagerLastEngine=null;
let r7ManagerLastInterventions=[];

function r7FullDateTime(value){
  if(!value)return '—';
  const date=new Date(value);
  if(Number.isNaN(date.getTime()))return String(value);
  const pad=n=>String(n).padStart(2,'0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
function r7DismissedHumanIds(){
  try{return new Set(JSON.parse(localStorage.getItem(R7_HUMAN_DISMISSED_KEY)||'[]'))}catch(_){return new Set()}
}
function r7HumanDismissed(id){return r7DismissedHumanIds().has(String(id||''))}
function r7DismissHuman(id){
  const ids=r7DismissedHumanIds();ids.add(String(id||''));
  localStorage.setItem(R7_HUMAN_DISMISSED_KEY,JSON.stringify([...ids].slice(-200)));
}
function r7VisibleHumanJobs(){return r7Jobs.filter(job=>job.state==='human_required'&&!r7HumanDismissed(job.id))}

/* Extend the original task filters with a real queued state and hide acknowledged
   finance reminders from normal daily views while preserving them in 全部记录. */
r7FilteredJobs=function(items){
  let filtered=[...items];
  if(r7AgentFilter)filtered=filtered.filter(job=>r7JobMatchesAgent(job,r7AgentFilter));
  else if(r7TaskFilter==='today')filtered=filtered.filter(r7TodayRelevant);
  else if(r7TaskFilter==='active')filtered=filtered.filter(job=>['running','queued','failed','human_required'].includes(job.state));
  else if(r7TaskFilter==='running')filtered=filtered.filter(job=>job.state==='running');
  else if(r7TaskFilter==='queued')filtered=filtered.filter(job=>job.state==='queued');
  else if(r7TaskFilter==='completed')filtered=filtered.filter(r7CompletedToday);
  else if(r7TaskFilter==='human')filtered=filtered.filter(job=>job.state==='human_required');
  else if(r7TaskFilter==='failed')filtered=filtered.filter(job=>job.state==='failed');
  if(r7TaskFilter!=='all')filtered=filtered.filter(job=>job.state!=='human_required'||!r7HumanDismissed(job.id));
  filtered.sort((a,b)=>new Date(r7JobTime(b)).getTime()-new Date(r7JobTime(a)).getTime());
  return filtered;
};

function ensureQueuedFilter(){
  const filters=$('r7-job-filters');
  if(!filters||filters.querySelector('[data-filter="queued"]'))return;
  const running=filters.querySelector('[data-filter="running"]');
  const button=document.createElement('button');button.className='r7-job-filter';button.dataset.filter='queued';button.textContent='待执行';
  running?.insertAdjacentElement('afterend',button);
}

function bindManagerTopStats(){
  const map=[['r7-today-working','running'],['r7-today-queued','queued'],['r7-today-completed','completed'],['r7-today-human','human']];
  map.forEach(([id,filter])=>{
    const box=$(id)?.closest('.r7-today-stat');
    if(!box||box.dataset.managerBound)return;
    box.dataset.managerBound='1';box.dataset.filter=filter;box.setAttribute('role','button');box.setAttribute('tabindex','0');
    const activate=()=>{r7TaskFilter=filter;r7AgentFilter='';renderR7Jobs(r7Jobs);$('r7-jobs')?.scrollIntoView({behavior:'smooth',block:'start'});};
    box.addEventListener('click',activate);
    box.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}});
  });
}

function ensureManagerStyles(){
  if($('r7-manager-patch-style'))return;
  const style=document.createElement('style');style.id='r7-manager-patch-style';style.textContent=`
    .r7-today-stat[role="button"]{cursor:pointer;transition:.16s}.r7-today-stat[role="button"]:hover{transform:translateY(-2px);background:rgba(255,255,255,.17)}
    .r7-job-dismiss{border:0;background:transparent;color:#9b7042;font-size:20px;line-height:1;cursor:pointer;padding:2px 5px;margin-left:4px}.r7-job-dismiss:hover{color:#b43b32}
    .r7-job-times{display:flex;flex-wrap:wrap;gap:7px;margin-top:6px;color:#65748b;font-size:10px}.r7-job-times span{background:#f4f7fb;border-radius:6px;padding:4px 6px}.r7-job.is-human .r7-job-times span{background:#fff5e7}
    .r7-job-dismissed-note{color:#a36a2c;font-size:10px}.r7-human-head-actions{display:flex;align-items:center;gap:8px}.r7-human-dismiss{border:0;background:#fff2dd;color:#9d6724;border-radius:7px;padding:5px 8px;font-size:10px;cursor:pointer}
  `;document.head.appendChild(style);
}

renderR7Jobs=function(items){
  r7Jobs=items;
  ensureTaskCenterUX();ensureQueuedFilter();ensureManagerStyles();
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
    const dismissed=job.state==='human_required'&&r7HumanDismissed(job.id);
    const detail=(job.result||job.error||actions)?`<details><summary>查看详情</summary>${job.error?`<p class="r7-error">${esc(job.error)}</p>`:''}${job.result?r7ResultHtml(job.result):''}<div class="r7-job-actions">${actions}</div></details>`:'';
    const cls=job.state==='running'?'is-running':job.state==='completed'?'is-completed':job.state==='human_required'?'is-human':job.state==='failed'?'is-failed':'';
    const stateText=dismissed?'已知 · 平台人工':(R7_STATE[job.state]||esc(job.state));
    const close=job.state==='human_required'&&!dismissed?`<button class="r7-job-dismiss" data-dismiss-human="${esc(job.id)}" title="我知道了，收起提醒" aria-label="收起提醒">×</button>`:'';
    const times=[`创建 ${r7FullDateTime(job.created_at)}`];
    if(job.due_at)times.push(`计划 ${r7FullDateTime(job.due_at)}`);
    if(job.state==='completed')times.push(`完成 ${r7FullDateTime(job.completed_at||job.updated_at)}`);
    else if(job.updated_at&&job.updated_at!==job.created_at)times.push(`更新 ${r7FullDateTime(job.updated_at)}`);
    return `<article class="r7-job ${cls}"><div class="r7-job-top"><div><strong>${esc(job.title)}</strong><div class="r7-job-meta"><span>${esc(job.agent||'运营协调员')}</span><span>${riskLabel}</span></div><div class="r7-job-times">${times.map(x=>`<span>${esc(x)}</span>`).join('')}</div></div><div class="r7-human-head-actions"><span class="status-pill ${job.state==='completed'?'ready':job.state==='failed'||job.state==='human_required'?'blocked':'waiting'}">${stateText}</span>${close}</div></div><div class="r7-progress"><i style="width:${job.progress||0}%"></i></div><p>进度 ${job.progress||0}% · ${job.completed_steps||0}/${job.total_steps||1} 步</p>${summary?`<div class="r7-job-compact-result"><b>结果：</b>${esc(summary)}</div>`:''}${dismissed?'<div class="r7-job-dismissed-note">提醒已收起；完整记录仍保留。</div>':''}${detail}</article>`;
  }).join(''):'<div class="r7-empty-filter">当前筛选下没有任务。系统仍会每 15 秒自动检查并更新状态。</div>';
  document.querySelectorAll('.r7-action').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;const payload={id:button.dataset.job,action:button.dataset.action,actor:'本机管理员'};
    try{await api('/api/r7/jobs/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});await loadR7();toast('任务状态已更新')}
    catch(error){toast(error.message,'error');button.disabled=false}
  }));
  document.querySelectorAll('[data-dismiss-human]').forEach(button=>button.addEventListener('click',()=>{
    r7DismissHuman(button.dataset.dismissHuman);renderR7Jobs(r7Jobs);renderTodayCommand(r7ManagerLastEngine||{});renderHumanInterventions(r7ManagerLastInterventions);toast('已收起提醒，资金事项记录仍保留在“全部记录”中');
  }));
};

renderHumanInterventions=function(items){
  r7ManagerLastInterventions=items||[];
  const panel=ensureHumanInterventionPanel();const list=$('r7-human-list'),title=$('r7-human-title');
  if(!list||!title||!panel)return;
  const rows=(items||[]).filter(item=>!r7HumanDismissed(item.id)).slice(0,20);
  panel.hidden=rows.length===0;title.textContent=`${rows.length} 项需要平台人工介入`;
  list.className=rows.length?'r7-job-list':'friendly-empty';
  list.innerHTML=rows.length?rows.map(item=>`<div class="r7-job is-human"><div class="r7-job-top"><div><strong>${esc(interventionType(item.title))} · ${esc(item.title||'未命名事项')}</strong><small>发现时间：${r7FullDateTime(item.created_at)} · 来源：${esc(item.source||'R7 自动识别')}</small></div><div class="r7-human-head-actions"><span class="status-pill blocked">${esc(item.status||'待平台人工处理')}</span><button class="r7-human-dismiss" data-dismiss-human="${esc(item.id)}">× 我知道了</button></div></div><p>${esc(item.reason||'涉及资金事项，R7 仅记录，不执行。')}</p></div>`).join(''):'当前没有资金类人工事项。';
  list.querySelectorAll('[data-dismiss-human]').forEach(button=>button.addEventListener('click',()=>{
    r7DismissHuman(button.dataset.dismissHuman);renderHumanInterventions(r7ManagerLastInterventions);renderR7Jobs(r7Jobs);renderTodayCommand(r7ManagerLastEngine||{});toast('已收起提醒，记录未删除');
  }));
};

renderTodayCommand=function(engine){
  r7ManagerLastEngine=engine||{};
  ensureTodayCommandCenter();ensureQueuedFilter();ensureManagerStyles();bindManagerTopStats();
  const activeAuto=r7Jobs.filter(job=>job.risk!=='financial'&&job.state!=='cancelled');
  const assigned=activeAuto.filter(r7TodayAssigned);
  const assignedDone=assigned.filter(job=>job.state==='completed');
  const completedToday=r7Jobs.filter(r7CompletedToday);
  const runningAgents=new Set(r7Jobs.filter(job=>job.state==='running').map(job=>job.agent).filter(Boolean));
  const queued=r7Jobs.filter(job=>job.state==='queued'&&(r7TodayAssigned(job)||!job.due_at)).length;
  const human=r7VisibleHumanJobs().length;
  const failed=Number(engine?.jobs?.failed||0);
  const pct=assigned.length?Math.round(assignedDone.length*100/assigned.length):0;
  $('r7-today-working').textContent=runningAgents.size;$('r7-today-queued').textContent=queued;$('r7-today-completed').textContent=completedToday.length;$('r7-today-human').textContent=human;
  $('r7-day-progress-bar').style.width=`${pct}%`;$('r7-day-progress-text').textContent=assigned.length?`${assignedDone.length} / ${assigned.length} · ${pct}%`:'今天暂未分配任务';
  const last=r7Jobs.slice().sort((a,b)=>new Date(r7JobTime(b)).getTime()-new Date(r7JobTime(a)).getTime())[0];
  $('r7-today-subtitle').textContent=`今日计划 ${assigned.length} 项 · 已完成 ${assignedDone.length} 项 · 工作中 ${runningAgents.size} 人 · 待执行 ${queued} 项${last?` · 最近更新 ${r7FullDateTime(r7JobTime(last))}`:''}`;
  $('r7-today-alert').textContent=failed?`注意：当前有 ${failed} 项失败任务，需要检查或等待自动重试。`:'';
};

renderR7Agents=function(items){
  r7Agents=items;const grid=$('r7-agent-grid');
  grid.innerHTML=items.map(agent=>{
    const all=r7Jobs.filter(job=>r7JobMatchesAgent(job,agent.name));const today=all.filter(r7TodayRelevant);
    const running=all.find(job=>job.state==='running'),queued=today.find(job=>job.state==='queued'),failed=today.find(job=>job.state==='failed'),completed=today.filter(r7CompletedToday);
    const current=running||failed||queued||completed[0]||null;let state='空闲',stateClass='idle';
    if(running){state='工作中';stateClass='working'}else if(failed){state='异常';stateClass='error'}else if(queued){state='待执行';stateClass='queued'}else if(completed.length){state='今日已完成';stateClass='done'}
    const currentText=running?`正在：${running.title}`:failed?`异常：${failed.title}`:queued?`下一项：${queued.title}`:completed.length?`最近完成：${completed[0].title}`:'当前没有任务';
    const progress=current?Number(current.progress||0):0,todayAssigned=today.filter(job=>r7TodayAssigned(job)&&job.state!=='cancelled').length;
    const last=all.slice().sort((a,b)=>new Date(r7JobTime(b)).getTime()-new Date(r7JobTime(a)).getTime())[0];
    return `<div class="r7-agent r7-agent-action ${r7AgentFilter===agent.name?'r7-agent-filtered':''}" role="button" tabindex="0" data-agent-name="${esc(agent.name)}"><div class="r7-agent-top"><b class="r7-agent-name">${esc(agent.name)}</b><span class="r7-agent-state ${stateClass}">${state}</span></div><span class="r7-agent-purpose">${esc(agent.purpose)}</span><div class="r7-agent-current"><b>${esc(currentText)}</b></div><div class="r7-agent-progress"><i style="width:${progress}%"></i></div><div class="r7-agent-foot"><span>今日计划 ${todayAssigned} · 完成 ${completed.length}${last?` · 最近 ${r7FullDateTime(r7JobTime(last))}`:''}</span><button type="button" class="r7-agent-workbench" data-target="${esc(R7_AGENT_TARGETS[agent.id]||'workflow')}">工作台</button></div></div>`;
  }).join('');
  document.querySelectorAll('.r7-agent-action').forEach(card=>{
    const activate=()=>{r7AgentFilter=card.dataset.agentName;r7TaskFilter='today';renderR7Jobs(r7Jobs);renderR7Agents(r7Agents);$('r7-jobs')?.scrollIntoView({behavior:'smooth',block:'start'});toast(`正在查看${r7AgentFilter}今天的工作记录`)};
    card.addEventListener('click',event=>{if(event.target.closest('.r7-agent-workbench'))return;activate()});card.addEventListener('keydown',event=>{if((event.key==='Enter'||event.key===' ')&&!event.target.closest('.r7-agent-workbench')){event.preventDefault();activate()}});
  });
  document.querySelectorAll('.r7-agent-workbench').forEach(button=>button.addEventListener('click',event=>{event.stopPropagation();openPage(button.dataset.target);toast('已打开对应工作台')}));
};

ensureManagerStyles();
