const R7_STATE={awaiting_approval:'待审批',queued:'已批准 · 待执行',running:'进行中',completed:'已完成',failed:'失败',cancelled:'已取消'};
const R7_AGENT_STATE={working:'工作中',waiting:'等待中',idle:'空闲',completed:'已完成',error:'异常'};
const R7_AGENT_TARGETS={market:'insights',seo:'promotion',content:'promotion',social:'promotion',video:'promotion',local:'insights',conversion:'analytics',review:'review'};
let r7Jobs=[];
let r7Loading=false;

function ensureR7AgentStyles(){
  if(document.getElementById('r7-agent-live-style'))return;
  const style=document.createElement('style');
  style.id='r7-agent-live-style';
  style.textContent=`
    .r7-agent-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:0 0 12px}
    .r7-agent-summary div{background:#f7f9fc;border:1px solid #e3e9f2;border-radius:10px;padding:9px 10px}
    .r7-agent-summary small{display:block;color:#71809a;font-size:11px;margin-bottom:2px}
    .r7-agent-summary b{font-size:17px;color:#17233d}
    .r7-agent{position:relative;overflow:hidden}
    .r7-agent-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:5px}
    .r7-agent-status{font-size:11px;font-weight:700;border-radius:999px;padding:3px 7px;white-space:nowrap;background:#eef2f7;color:#62708a}
    .r7-agent-status.working{background:#e8f8ef;color:#16834f}.r7-agent-status.waiting{background:#fff6df;color:#9a6b00}
    .r7-agent-status.completed{background:#e9f8f1;color:#157a4b}.r7-agent-status.error{background:#ffeded;color:#b52a2a}
    .r7-agent-live-task{font-size:12px;color:#1f2f4d;margin:7px 0 5px;line-height:1.45}
    .r7-agent-live-task strong{font-weight:700}.r7-agent-live-meta{font-size:11px;color:#71809a;line-height:1.45;margin-top:5px}
    .r7-agent-live-result{font-size:11px;color:#28724f;line-height:1.45;margin-top:5px}.r7-agent-live-error{font-size:11px;color:#b52a2a;line-height:1.45;margin-top:5px}
    .r7-agent-progress{height:5px;background:#edf1f6;border-radius:999px;overflow:hidden;margin:6px 0}.r7-agent-progress i{display:block;height:100%;background:#2f6fed;border-radius:999px}
    .r7-agent-truth{grid-column:1/-1;font-size:11px;color:#71809a;margin-top:1px}
    @media(max-width:900px){.r7-agent-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}
  `;
  document.head.appendChild(style);
}

function r7Action(job,action,label){return `<button class="outline-button r7-action" data-job="${esc(job.id)}" data-action="${action}">${label}</button>`}
function renderR7Jobs(items){
  r7Jobs=items;
  $('r7-jobs').className=items.length?'r7-job-list':'friendly-empty';
  $('r7-jobs').innerHTML=items.length?items.map(job=>{
    let actions='';
    if(job.state==='awaiting_approval')actions=r7Action(job,'approve','批准执行')+r7Action(job,'cancel','取消');
    if(job.state==='queued'&&job.mode==='manual')actions=r7Action(job,'start','开始人工任务')+r7Action(job,'cancel','取消');
    if(job.state==='queued'&&job.mode==='local')actions='<span class="subtle">调度器将按时间自动执行</span>'+r7Action(job,'cancel','取消');
    if(job.state==='running'&&job.mode==='manual')actions=`<input data-outcome="${esc(job.id)}" maxlength="1000" placeholder="填写实际完成结果">`+r7Action(job,'complete','确认完成');
    if(job.state==='failed')actions=r7Action(job,'retry','重试')+r7Action(job,'cancel','取消');
    const step=job.current_step?`<p>当前步骤：${esc(job.current_step)}</p>`:'';
    return `<article class="r7-job"><div class="r7-job-top"><div><strong>${esc(job.title)}</strong><small>${esc(job.agent)} · ${esc(job.kind)} · ${formatTime(job.created_at)}</small></div><span class="status-pill ${job.state==='completed'?'ready':job.state==='failed'?'blocked':'waiting'}">${R7_STATE[job.state]||esc(job.state)}</span></div><div class="r7-progress"><i style="width:${Math.max(0,Math.min(100,Number(job.progress)||0))}%"></i></div><p>实际完成 ${job.completed_steps}/${job.total_steps} 步 · ${job.progress}%${job.due_at?' · 计划 '+esc(job.due_at):''}</p>${step}${job.error?`<p class="r7-error">${esc(job.error)}</p>`:''}${job.result?`<p>结果：${esc(r7ResultText(job.result)||'已记录')}</p>`:''}<div class="r7-job-actions">${actions}</div></article>`;
  }).join(''):'还没有工作流任务。非资金任务创建后会自动进入执行队列。';
  document.querySelectorAll('.r7-action').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;
    const payload={id:button.dataset.job,action:button.dataset.action,actor:'本机管理员'};
    if(payload.action==='complete')payload.outcome=document.querySelector(`[data-outcome="${payload.id}"]`)?.value||'';
    try{await api('/api/r7/jobs/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});await loadR7();toast('任务状态已更新')}
    catch(error){toast(error.message,'error');button.disabled=false}
  }));
}

function r7ResultText(result){
  if(!result)return '';
  if(typeof result==='string')return result;
  if(result.outcome)return result.outcome;
  if(result.headline)return result.headline;
  if(typeof result.summary==='string')return result.summary;
  if(result.summary&&result.summary.headline)return result.summary.headline;
  return '结果已记录';
}

function r7RelativeTime(value){
  if(!value)return '暂无';
  const time=new Date(value);if(Number.isNaN(time.getTime()))return formatTime(value);
  const seconds=Math.max(0,Math.floor((Date.now()-time.getTime())/1000));
  if(seconds<60)return `${seconds} 秒前`;
  if(seconds<3600)return `${Math.floor(seconds/60)} 分钟前`;
  if(seconds<86400)return `${Math.floor(seconds/3600)} 小时前`;
  return formatTime(value);
}

function renderR7AgentSummary(summary={}){
  const grid=$('r7-agent-grid');if(!grid)return;
  let box=$('r7-agent-summary');
  if(!box){box=document.createElement('div');box.id='r7-agent-summary';box.className='r7-agent-summary';grid.parentNode.insertBefore(box,grid)}
  box.innerHTML=`
    <div><small>AI 员工</small><b>${Number(summary.total)||8}</b></div>
    <div><small>工作中</small><b>${Number(summary.working)||0}</b></div>
    <div><small>等待中</small><b>${Number(summary.waiting)||0}</b></div>
    <div><small>当前空闲</small><b>${Number(summary.idle)||0}</b></div>
    <div><small>今日完成任务</small><b>${Number(summary.completed_today)||0}</b></div>
    ${Number(summary.error)?`<div><small>异常</small><b>${Number(summary.error)}</b></div>`:''}
    <p class="r7-agent-truth">进度只来自真实任务执行节点；工作中超过 ${Math.round((Number(summary.stale_after_seconds)||300)/60)} 分钟无心跳会标记异常。</p>`;
}

function renderR7Agents(items,summary){
  ensureR7AgentStyles();
  renderR7AgentSummary(summary);
  $('r7-agent-grid').innerHTML=items.map(agent=>{
    const status=agent.status||'idle';
    const progress=Math.max(0,Math.min(100,Number(agent.progress)||0));
    const currentTask=agent.current_task||'';
    const currentStep=agent.current_step||'';
    const result=r7ResultText(agent.result||agent.last_result);
    const heartbeat=agent.heartbeat_at?`最近心跳 ${r7RelativeTime(agent.heartbeat_at)}`:'';
    const started=agent.started_at?`开始 ${formatTime(agent.started_at)}`:'';
    const completedToday=Number(agent.completed_today)||0;
    const taskLine=currentTask?`<div class="r7-agent-live-task"><strong>当前任务：</strong>${esc(currentTask)}</div>`:`<div class="r7-agent-live-task">当前没有正在执行的任务${agent.last_task?` · 最近：${esc(agent.last_task)}`:''}</div>`;
    const progressBar=status==='working'||status==='waiting'||status==='completed'||status==='error'?`<div class="r7-agent-progress"><i style="width:${progress}%"></i></div>`:'';
    const stepLine=currentStep?`<div class="r7-agent-live-meta">当前步骤：${esc(currentStep)}</div>`:'';
    const meta=[started,heartbeat,completedToday?`今日完成 ${completedToday} 项`:''].filter(Boolean).join(' · ');
    return `<div class="r7-agent r7-agent-action" role="button" tabindex="0" data-agent="${esc(agent.id)}" data-target="${esc(R7_AGENT_TARGETS[agent.id]||'workflow')}"><div class="r7-agent-head"><b>${esc(agent.name)}</b><span class="r7-agent-status ${esc(status)}">${R7_AGENT_STATE[status]||esc(status)}</span></div><span>${esc(agent.purpose)}</span>${taskLine}${progressBar}${stepLine}${meta?`<div class="r7-agent-live-meta">${esc(meta)}${progress?` · 进度 ${progress}%`:''}</div>`:''}${agent.error?`<div class="r7-agent-live-error">异常：${esc(agent.error)}</div>`:result&&status==='completed'?`<div class="r7-agent-live-result">结果：${esc(result)}</div>`:''}<small>点击打开对应工作台</small></div>`;
  }).join('');
  document.querySelectorAll('.r7-agent-action').forEach(card=>{
    const activate=()=>{const target=card.dataset.target;openPage(target);toast(`已打开${card.querySelector('b')?.textContent||'AI 员工'}对应工作台`)};
    card.addEventListener('click',activate);
    card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}});
  });
}

function bindR7OverviewActions(){
  const cards=[...document.querySelectorAll('.r7-overview article')];
  if(cards.length<3)return;
  if(!cards[0].dataset.overviewBound){cards[0].dataset.overviewBound='1';cards[0].style.cursor='pointer';cards[0].tabIndex=0;cards[0].title='点击查看工作流任务';const activate=()=>{$('r7-jobs')?.scrollIntoView({behavior:'smooth',block:'start'});toast('已定位到任务工作流')};cards[0].addEventListener('click',activate);cards[0].addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate()}})}
  if(!cards[1].dataset.overviewBound){cards[1].dataset.overviewBound='1';cards[1].style.cursor='pointer';cards[1].tabIndex=0;cards[1].title='点击查看失败任务';const activate=()=>{const failed=r7Jobs.filter(x=>x.state==='failed');if(!failed.length){toast('当前没有失败任务');return}renderR7Jobs(failed);$('r7-jobs')?.scrollIntoView({behavior:'smooth',block:'start'});toast(`已筛出 ${failed.length} 个失败任务`)};cards[1].addEventListener('click',activate);cards[1].addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate()}})}
  if(!cards[2].dataset.overviewBound){cards[2].dataset.overviewBound='1';cards[2].style.cursor='pointer';cards[2].tabIndex=0;cards[2].title='点击查看迁移与审计记录';const activate=()=>{$('r7-audit-list')?.scrollIntoView({behavior:'smooth',block:'start'});toast($('r7-migration')?.textContent||'已定位到迁移与审计记录')};cards[2].addEventListener('click',activate);cards[2].addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate()}})}
}

async function loadR7(){
  if(r7Loading)return false;
  r7Loading=true;
  try{
    const [jobs,agents,engine,audit,routes]=await Promise.all([api('/api/r7/jobs'),api('/api/r7/agents'),api('/api/r7/engine'),api('/api/r7/audit'),api('/api/r7/model-routes')]);
    renderR7Jobs(jobs.items);
    $('r7-engine-status').textContent=`待审批 ${engine.jobs.awaiting_approval} · 待执行 ${engine.jobs.queued} · 进行中 ${engine.jobs.running} · 已完成 ${engine.jobs.completed} · 失败 ${engine.jobs.failed}`;
    $('r7-exceptions').textContent=engine.jobs.failed?`${engine.jobs.failed} 项需要处理`:'目前没有失败任务';
    $('r7-migration').textContent=engine.migration.result==='complete'?engine.migration.copied.length?`R6 数据备份已完成 · ${engine.migration.copied.length} 个文件`:`未发现旧版数据 · 可直接开始`:'正在检查旧数据';
    $('r7-model-route').textContent=`当前可用模型路线：${routes.routes.map(x=>x.label).join('、')}。${routes.note}`;
    renderR7Agents(agents.items,agents.summary||{});
    $('r7-audit-integrity').textContent=audit.integrity==='verified'?'审计链已验证':'审计链异常，请停止执行并检查';
    $('r7-audit-list').innerHTML=audit.events.length?audit.events.slice(-20).reverse().map(event=>`<div class="r7-audit-row"><b>${esc(event.kind)}</b><span>${esc(event.actor)} · ${formatTime(event.at)}</span><small>${esc(event.job_id.slice(0,8))}</small></div>`).join(''):'尚无审计记录';
    bindR7OverviewActions();
    return true;
  }catch(error){toast(error.message,'error');return false}finally{r7Loading=false}
}
window.loadR7=loadR7;

$('r7-create').addEventListener('click',async()=>{
  const button=$('r7-create');button.disabled=true;button.textContent='创建中…';
  try{
    const job=await api('/api/r7/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:$('r7-kind').value,title:$('r7-title').value,due_at:$('r7-due').value})});
    $('r7-title').value='';await loadR7();toast(job.state==='awaiting_approval'?'资金类任务已记录，等待人工审批':'非资金任务已自动进入执行队列');
  }catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='创建自动运营任务'}
});
$('r7-refresh').addEventListener('click',async()=>{const button=$('r7-refresh');button.disabled=true;const original=button.textContent;button.textContent='刷新中…';try{if(await loadR7())toast('任务、AI 员工和审计状态已刷新')}finally{button.disabled=false;button.textContent=original}});
setInterval(()=>{if($('workflow').classList.contains('active'))loadR7()},5000);
