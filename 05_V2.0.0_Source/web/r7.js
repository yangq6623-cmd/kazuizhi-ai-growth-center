const R7_STATE={awaiting_approval:'历史待处理',human_required:'平台人工待处理',queued:'自动待执行',running:'自动执行中',completed:'已完成',failed:'失败',cancelled:'已取消'};
const R7_AGENT_TARGETS={market:'insights',seo:'promotion',content:'promotion',social:'promotion',video:'promotion',local:'insights',conversion:'analytics',review:'review'};
let r7Jobs=[];

function applyAutonomyCopy(){
  const workflow=$('workflow');
  if(!workflow)return;
  const pageCopy=workflow.querySelector('.page-title p');
  if(pageCopy)pageCopy.textContent='非资金运营任务默认自动执行并全程留痕；退款、结算、提现、改价等资金事项只记录为平台人工待处理。';
  const overview=workflow.querySelectorAll('.r7-overview article p');
  if(overview[0])overview[0].textContent='本地调度自动检查到期任务，无需人工批准非资金运营任务。';
  if(overview[1])overview[1].textContent='失败任务自动记录并按策略重试；资金事项单独进入平台人工待处理。';
  const createTitle=workflow.querySelector('.grid.two article .article-head h3');
  if(createTitle)createTitle.textContent='创建自动运营任务';
  const createButton=$('r7-create');if(createButton)createButton.textContent='创建自动任务';
  const kind=$('r7-kind');if(kind&&kind.options[0])kind.options[0].textContent='自动运营任务';
  const help=workflow.querySelector('.r7-create-form + .form-help');
  if(help)help.textContent='非资金任务创建后自动排队执行；退款、结算、改价、提现等资金事项只记录并交平台人工处理。';
  const chip=workflow.querySelector('#r7-agent-grid')?.closest('article')?.querySelector('.chip');
  if(chip)chip.textContent='非资金全自动';
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
function renderR7Jobs(items){
  r7Jobs=items;
  $('r7-jobs').className=items.length?'r7-job-list':'friendly-empty';
  $('r7-jobs').innerHTML=items.length?items.map(job=>{
    let actions='';
    if(job.state==='awaiting_approval')actions='<span class="subtle">这是旧版本遗留记录，新版本启动后会按新自动化策略迁移处理。</span>';
    if(job.state==='human_required')actions='<span class="subtle">请到小程序/平台后台由人工处理资金事项；R7 只记录，不执行。</span>';
    if(job.state==='queued'&&job.mode==='local')actions='<span class="subtle">已进入自动执行队列，无需人工批准</span>';
    if(job.state==='failed'&&job.risk!=='financial')actions=r7Action(job,'retry','立即重试')+r7Action(job,'cancel','取消');
    const riskLabel=job.risk==='financial'?'资金事项 · 平台人工':'非资金 · 全自动';
    return `<article class="r7-job"><div class="r7-job-top"><div><strong>${esc(job.title)}</strong><small>${esc(job.agent||'运营协调员')} · ${esc(job.task_type||job.kind)} · ${riskLabel} · ${formatTime(job.created_at)}</small></div><span class="status-pill ${job.state==='completed'?'ready':job.state==='failed'||job.state==='human_required'?'blocked':'waiting'}">${R7_STATE[job.state]||esc(job.state)}</span></div><div class="r7-progress"><i style="width:${job.progress||0}%"></i></div><p>实际完成 ${job.completed_steps||0}/${job.total_steps||1} 步 · ${job.progress||0}%${job.due_at?' · 计划 '+esc(job.due_at):''}</p>${job.error?`<p class="r7-error">${esc(job.error)}</p>`:''}${job.result?r7ResultHtml(job.result):''}<div class="r7-job-actions">${actions}</div></article>`;
  }).join(''):'还没有自动运营任务。非资金任务创建后会自动排队执行；资金事项只记录并交平台人工处理。';
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
  ensureHumanInterventionPanel();
  const list=$('r7-human-list'), title=$('r7-human-title');
  if(!list||!title)return;
  const rows=(items||[]).slice(0,20);
  title.textContent=`${rows.length} 项需要平台人工介入`;
  list.className=rows.length?'r7-job-list':'friendly-empty';
  list.innerHTML=rows.length?rows.map(item=>`<div class="r7-job"><div class="r7-job-top"><div><strong>${esc(interventionType(item.title))} · ${esc(item.title||'未命名事项')}</strong><small>发现时间：${formatTime(item.created_at)} · 来源：${esc(item.source||'R7 自动识别')}</small></div><span class="status-pill blocked">${esc(item.status||'待平台人工处理')}</span></div><p>${esc(item.reason||'涉及资金事项，R7 仅记录，不执行。')}</p><div class="r7-job-actions"><span class="subtle">处理入口：小程序/平台后台。R7 不提供资金执行按钮。</span></div></div>`).join(''):'当前没有资金类人工事项。';
}

function renderR7Agents(items){
  $('r7-agent-grid').innerHTML=items.map(agent=>`<div class="r7-agent r7-agent-action" role="button" tabindex="0" data-agent="${esc(agent.id)}" data-target="${esc(R7_AGENT_TARGETS[agent.id]||'workflow')}"><b>${esc(agent.name)}</b><span>${esc(agent.purpose)}</span><small>非资金任务默认自动执行 · 点击打开对应工作台</small></div>`).join('');
  document.querySelectorAll('.r7-agent-action').forEach(card=>{
    const activate=()=>{const target=card.dataset.target;openPage(target);toast(`已打开${card.querySelector('b')?.textContent||'AI 员工'}对应工作台`)};
    card.addEventListener('click',activate);
    card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}});
  });
}

function bindR7OverviewActions(){
  const cards=[...document.querySelectorAll('.r7-overview article')];
  if(cards.length<3)return;
  if(!cards[0].dataset.overviewBound){cards[0].dataset.overviewBound='1';cards[0].style.cursor='pointer';cards[0].tabIndex=0;cards[0].title='点击查看自动任务记录';const activate=()=>{$('r7-jobs')?.scrollIntoView({behavior:'smooth',block:'start'});toast('已定位到自动任务记录')};cards[0].addEventListener('click',activate);cards[0].addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate()}})}
  if(!cards[1].dataset.overviewBound){cards[1].dataset.overviewBound='1';cards[1].style.cursor='pointer';cards[1].tabIndex=0;cards[1].title='点击查看异常与人工待处理';const activate=()=>{const exception=r7Jobs.filter(x=>x.state==='failed'||x.state==='human_required');if(!exception.length){toast('当前没有异常或人工待处理事项');return}renderR7Jobs(exception);$('r7-jobs')?.scrollIntoView({behavior:'smooth',block:'start'});toast(`已筛出 ${exception.length} 个事项`)};cards[1].addEventListener('click',activate);cards[1].addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate()}})}
  if(!cards[2].dataset.overviewBound){cards[2].dataset.overviewBound='1';cards[2].style.cursor='pointer';cards[2].tabIndex=0;cards[2].title='点击查看迁移与审计记录';const activate=()=>{$('r7-audit-list')?.scrollIntoView({behavior:'smooth',block:'start'});toast($('r7-migration')?.textContent||'已定位到迁移与审计记录')};cards[2].addEventListener('click',activate);cards[2].addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate()}})}
}

async function loadR7(){
  try{
    applyAutonomyCopy();
    const [jobs,agents,engine,audit,routes]=await Promise.all([api('/api/r7/jobs'),api('/api/r7/agents'),api('/api/r7/engine'),api('/api/r7/audit'),api('/api/r7/model-routes')]);
    renderR7Jobs(jobs.items);
    const legacy=engine.jobs.awaiting_approval||0,human=engine.jobs.human_required||0,queued=engine.jobs.queued||0,running=engine.jobs.running||0,failed=engine.jobs.failed||0;
    $('r7-engine-status').textContent=`自动待执行 ${queued} · 自动执行中 ${running} · 平台人工 ${human} · 失败 ${failed}${legacy?` · 旧记录 ${legacy}`:''}`;
    $('r7-exceptions').textContent=(human||failed)?`${human} 项平台人工 · ${failed} 项失败`:'目前没有需要人工介入或失败的事项';
    $('r7-migration').textContent=engine.migration.result==='complete'?engine.migration.copied.length?`R6 数据备份已完成 · ${engine.migration.copied.length} 个文件`:`未发现旧版数据 · 可直接开始`:'正在检查旧数据';
    $('r7-model-route').textContent=`自动化策略：${engine.autonomy_policy||'非资金自动执行'}。当前可用模型路线：${routes.routes.map(x=>x.label).join('、')}。`;
    renderR7Agents(agents.items);
    renderHumanInterventions(engine.human_interventions||[]);
    $('r7-audit-integrity').textContent=audit.integrity==='verified'?'审计链已验证 · 自动执行过程可追溯':'审计链异常，请停止执行并检查';
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
$('r7-refresh').addEventListener('click',async()=>{const button=$('r7-refresh');button.disabled=true;const original=button.textContent;button.textContent='刷新中…';try{if(await loadR7())toast('自动任务、员工和审计状态已刷新')}finally{button.disabled=false;button.textContent=original}});
setInterval(()=>{if($('workflow').classList.contains('active'))loadR7()},15000);
