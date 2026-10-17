(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const ACTIVE=new Set(['等待ChatGPT策划','等待素材路由','等待生产','生产中','技术质检','后期增强中','等待ChatGPT质检','等待人工审核','退回重做','已授权发布','等待账号','等待最佳时间','发布执行中','异常待处理']);

  if(!document.querySelector('link[data-r8-ui-hotfix-341]')){
    const link=document.createElement('link');
    link.rel='stylesheet';link.href='/operational-ui-hotfix-341.css';link.dataset.r8UiHotfix341='1';document.head.appendChild(link);
  }
  if(!document.querySelector('script[data-r8-usability-349]')){
    const script=document.createElement('script');script.src='/operational-usability-349.js';script.async=false;script.dataset.r8Usability349='1';document.head.appendChild(script);
  }

  function activeGrowthId(){
    const f=window.state?.factory||{};
    return String(window.getActiveGrowthId?.()||f.active_campaign_id||f.campaigns?.[0]?.id||'').trim();
  }
  function activeCampaign(){const id=activeGrowthId();return (window.state?.factory?.campaigns||[]).find(x=>x.id===id)||null}
  function activeVideo(){const id=activeGrowthId();return (window.state?.factory?.videos||[]).find(x=>x.campaign_id===id&&ACTIVE.has(x.status))||null}

  function syncOrderGoal(){
    const goal=byId('order-goal');if(!goal)return;
    const f=window.state?.factory||{};
    const candidates=[f?.business_results?.completed_orders,f?.business_metrics?.completed_orders,f?.order_metrics?.completed,f?.completed_orders];
    const actual=candidates.map(Number).find(Number.isFinite);
    goal.textContent=Number.isFinite(actual)?`${actual} / 50`:'经营数据待接入';
    const box=goal.closest('.goal');const tail=box?.querySelector(':scope > span');
    if(tail)tail.textContent=Number.isFinite(actual)?'目标 50 单 · 仅统计真实经营回流':'目标 50 单 · 接入经营数据后自动显示';
  }

  function syncCampaignCopy(){
    const details=byId('campaigns')?.querySelector('.final-new-campaign');
    const summary=details?.querySelector(':scope > summary');
    if(summary)summary.textContent=activeCampaign()?'创建新的增长战役':'创建第一个增长战役';
  }

  function syncPlanningTruth(){
    const hero=byId('final-task-hero');if(!hero)return;
    let note=hero.querySelector('.hotfix-planning-truth');
    if(!note){note=document.createElement('small');note.className='hotfix-planning-truth';hero.appendChild(note)}
    const task=activeVideo();if(!task){note.hidden=true;note.textContent='';return}
    note.hidden=false;note.classList.remove('is-blocked','is-connected');
    const handoff=task.chatgpt_handoff||{};
    if(task.plan_received_at||task.production_plan){note.textContent='ChatGPT生产合同已返回，正在进入本地执行。';note.classList.add('is-connected');return}
    if(handoff.phase==='bridge_unavailable'){
      note.textContent='尚未发送给ChatGPT：双向同步桥未连接。系统会持续检查，恢复后自动发送。';note.classList.add('is-blocked');return;
    }
    if(handoff.phase==='retry_exhausted'||task.status==='异常待处理'){
      note.textContent='ChatGPT请求连续重发仍未返回；已停止无限等待并转入待处理。';note.classList.add('is-blocked');return;
    }
    if(handoff.phase==='waiting_response'){
      note.textContent=`请求已写入ChatGPT同步桥 · 等待结构化返回 · 自动重试 ${Number(handoff.retry_count||0)}/${Number(handoff.max_retries||3)}`;note.classList.add('is-connected');return;
    }
    note.textContent='正在准备发送给ChatGPT总控；当前不能证明ChatGPT已接收。';
  }

  function apply(){syncOrderGoal();syncCampaignCopy();syncPlanningTruth()}
  const later=()=>window.setTimeout(apply,0);
  window.addEventListener('operational:refreshed',later);
  window.addEventListener('operational:page-changed',later);
  window.addEventListener('operational:device-status',later);
  apply();window.setTimeout(apply,300);window.setTimeout(apply,1000);
})();
