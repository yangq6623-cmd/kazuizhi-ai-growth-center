(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const ACTIVE=new Set(['等待ChatGPT策划','等待素材路由','等待生产','生产中','技术质检','后期增强中','等待ChatGPT质检','等待人工审核','退回重做','已授权发布','等待账号','等待最佳时间','发布执行中','异常待处理']);
  let bridgeTruth=null;

  if(!document.querySelector('link[data-r8-ui-hotfix-341]')){
    const link=document.createElement('link');
    link.rel='stylesheet';link.href='/operational-ui-hotfix-341.css';link.dataset.r8UiHotfix341='1';document.head.appendChild(link);
  }

  function activeGrowthId(){
    const f=window.state?.factory||{};
    return String(window.getActiveGrowthId?.()||f.active_campaign_id||f.campaigns?.[0]?.id||'').trim();
  }
  function activeCampaign(){
    const id=activeGrowthId();
    return (window.state?.factory?.campaigns||[]).find(x=>x.id===id)||null;
  }
  function activeVideo(){
    const id=activeGrowthId();
    return (window.state?.factory?.videos||[]).find(x=>x.campaign_id===id&&ACTIVE.has(x.status))||null;
  }
  function ageMinutes(value){
    if(!value)return null;
    const time=Date.parse(value);if(!Number.isFinite(time))return null;
    return Math.max(0,Math.floor((Date.now()-time)/60000));
  }

  function syncOrderGoal(){
    const goal=byId('order-goal');if(!goal)return;
    const f=window.state?.factory||{};
    const candidates=[f?.business_results?.completed_orders,f?.business_metrics?.completed_orders,f?.order_metrics?.completed,f?.completed_orders];
    const actual=candidates.map(Number).find(Number.isFinite);
    goal.textContent=Number.isFinite(actual)?`${actual} / 50`:'经营数据待接入';
    const box=goal.closest('.goal');
    const tail=box?.querySelector(':scope > span');
    if(tail)tail.textContent=Number.isFinite(actual)?'目标 50 单 · 仅统计真实经营回流':'目标 50 单 · 接入经营数据后自动显示';
  }

  function syncCampaignCopy(){
    const details=byId('campaigns')?.querySelector('.final-new-campaign');
    const summary=details?.querySelector(':scope > summary');
    if(summary)summary.textContent=activeCampaign()?'创建新的增长战役':'创建第一个增长战役';
  }

  function bridgeConnected(){return bridgeTruth?.status==='connected'}
  function syncPlanningTruth(){
    const hero=byId('final-task-hero');if(!hero)return;
    let note=hero.querySelector('.hotfix-planning-truth');
    if(!note){note=document.createElement('small');note.className='hotfix-planning-truth';hero.appendChild(note)}
    note.classList.remove('is-blocked','is-connected');
    const task=activeVideo();
    if(!task){note.textContent='';note.hidden=true;return}
    note.hidden=false;
    const age=ageMinutes(task.updated_at||task.created_at);
    if(task.status==='等待ChatGPT策划'||task.status==='退回重做'){
      if(bridgeTruth===null){note.textContent=`正在检查 ChatGPT 总控连接${age!==null?` · 已等待 ${age} 分钟`:''}`;return}
      if(bridgeConnected()){
        note.classList.add('is-connected');
        note.textContent=`ChatGPT 总控已连接 · 本地调度约每 60 秒同步一次${age!==null?` · 当前已等待 ${age} 分钟`:''}`;
      }else{
        note.classList.add('is-blocked');
        note.textContent=`ChatGPT 总控未连接 · 当前任务不会继续策划${bridgeTruth?.message?` · ${bridgeTruth.message}`:''}`;
      }
      return;
    }
    const bottleneck=task.bottleneck||'';
    const action=task.auto_action||'';
    note.textContent=[`当前：${task.status}`,bottleneck,action].filter(Boolean).join(' · ');
  }

  async function refreshBridgeTruth(){
    try{
      const response=await fetch('/api/bridge/status',{cache:'no-store'});
      bridgeTruth=response.ok?await response.json():{status:'error',message:`HTTP ${response.status}`};
    }catch(error){
      bridgeTruth={status:'error',message:String(error?.message||error||'连接失败')};
    }
    syncPlanningTruth();
  }

  function apply(){syncOrderGoal();syncCampaignCopy();syncPlanningTruth()}

  window.addEventListener('operational:refreshed',()=>{apply();refreshBridgeTruth()});
  window.addEventListener('operational:page-changed',apply);
  window.addEventListener('operational:device-status',apply);
  apply();
  refreshBridgeTruth();
  window.setInterval(()=>{if(window.state?.currentPage==='content')refreshBridgeTruth()},30000);
})();
