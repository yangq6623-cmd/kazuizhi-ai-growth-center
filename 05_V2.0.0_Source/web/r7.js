const R7_STATE={awaiting_approval:'待审批',queued:'已批准 · 待执行',running:'进行中',completed:'已完成',failed:'失败',cancelled:'已取消'};
const R7_AGENT_TARGETS={market:'insights',seo:'promotion',content:'promotion',social:'promotion',video:'promotion',local:'insights',conversion:'analytics',review:'review'};
let r7Jobs=[];

function r7Action(job,action,label){return `<button class="outline-button r7-action" data-job="${esc(job.id)}" data-action="${action}">${label}</button>`}
function renderR7Jobs(items){
  r7Jobs=items;
  $('r7-jobs').className=items.length?'r7-job-list':'friendly-empty';
  $('r7-jobs').innerHTML=items.length?items.map(job=>{
    let actions='';
    if(job.state==='awaiting_approval')actions=r7Action(job,'approve','批准执行')+r7Action(job,'cancel','取消');
    if(job.state==='queued'&&job.mode==='manual')actions=r7Action(job,'start','开始人工任务')+r7Action(job,'cancel','取消');
    if(job.state==='queued'&&job.mode==='local')actions='<span class="subtle">调度器将按时间执行</span>'+r7Action(job,'cancel','取消');
    if(job.state==='running'&&job.mode==='manual')actions=`<input data-outcome="${esc(job.id)}" maxlength="1000" placeholder="填写实际完成结果">`+r7Action(job,'complete','确认完成');
    if(job.state==='failed')actions=r7Action(job,'retry','重试')+r7Action(job,'cancel','取消');
    return `<article class="r7-job"><div class="r7-job-top"><div><strong>${esc(job.title)}</strong><small>${esc(job.agent)} · ${esc(job.kind)} · ${formatTime(job.created_at)}</small></div><span class="status-pill ${job.state==='completed'?'ready':job.state==='failed'?'blocked':'waiting'}">${R7_STATE[job.state]||esc(job.state)}</span></div><div class="r7-progress"><i style="width:${job.progress}%"></i></div><p>实际完成 ${job.completed_steps}/${job.total_steps} 步 · ${job.progress}%${job.due_at?' · 计划 '+esc(job.due_at):''}</p>${job.error?`<p class="r7-error">${esc(job.error)}</p>`:''}${job.result?`<p>结果：${esc(job.result.outcome||job.result.headline||'已记录')}</p>`:''}<div class="r7-job-actions">${actions}</div></article>`;
  }).join(''):'还没有工作流任务。创建任务后，需要人工批准才会进入执行队列。';
  document.querySelectorAll('.r7-action').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;
    const payload={id:button.dataset.job,action:button.dataset.action,actor:'本机管理员'};
    if(payload.action==='complete')payload.outcome=document.querySelector(`[data-outcome="${payload.id}"]`)?.value||'';
    try{await api('/api/r7/jobs/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});await loadR7();toast('任务状态已更新')}
    catch(error){toast(error.message,'error');button.disabled=false}
  }));
}

function renderR7Agents(items){
  $('r7-agent-grid').innerHTML=items.map(agent=>`<div class="r7-agent r7-agent-action" role="button" tabindex="0" data-agent="${esc(agent.id)}" data-target="${esc(R7_AGENT_TARGETS[agent.id]||'workflow')}"><b>${esc(agent.name)}</b><span>${esc(agent.purpose)}</span><small>职责已登记 · 点击打开对应工作台</small></div>`).join('');
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
  try{
    const [jobs,agents,engine,audit,routes]=await Promise.all([api('/api/r7/jobs'),api('/api/r7/agents'),api('/api/r7/engine'),api('/api/r7/audit'),api('/api/r7/model-routes')]);
    renderR7Jobs(jobs.items);
    $('r7-engine-status').textContent=`待审批 ${engine.jobs.awaiting_approval} · 待执行 ${engine.jobs.queued} · 进行中 ${engine.jobs.running} · 失败 ${engine.jobs.failed}`;
    $('r7-exceptions').textContent=engine.jobs.failed?`${engine.jobs.failed} 项需要人工处理`:'目前没有失败任务';
    $('r7-migration').textContent=engine.migration.result==='complete'?engine.migration.copied.length?`R6 数据备份已完成 · ${engine.migration.copied.length} 个文件`:`未发现旧版数据 · 可直接开始`:'正在检查旧数据';
    $('r7-model-route').textContent=`当前可用模型路线：${routes.routes.map(x=>x.label).join('、')}。${routes.note}`;
    renderR7Agents(agents.items);
    $('r7-audit-integrity').textContent=audit.integrity==='verified'?'审计链已验证':'审计链异常，请停止执行并检查';
    $('r7-audit-list').innerHTML=audit.events.length?audit.events.slice(-20).reverse().map(event=>`<div class="r7-audit-row"><b>${esc(event.kind)}</b><span>${esc(event.actor)} · ${formatTime(event.at)}</span><small>${esc(event.job_id.slice(0,8))}</small></div>`).join(''):'尚无审计记录';
    bindR7OverviewActions();
  }catch(error){toast(error.message,'error')}
}
window.loadR7=loadR7;

$('r7-create').addEventListener('click',async()=>{
  const button=$('r7-create');button.disabled=true;button.textContent='创建中…';
  try{
    await api('/api/r7/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:$('r7-kind').value,title:$('r7-title').value,due_at:$('r7-due').value})});
    $('r7-title').value='';await loadR7();toast('任务已创建，等待人工审批');
  }catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='创建待审批任务'}
});
$('r7-refresh').addEventListener('click',async()=>{const button=$('r7-refresh');button.disabled=true;const original=button.textContent;button.textContent='刷新中…';try{await loadR7();toast('R7 状态已刷新')}finally{button.disabled=false;button.textContent=original}});
setInterval(()=>{if($('workflow').classList.contains('active'))loadR7()},15000);
