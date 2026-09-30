/* Compact executive layout for Autonomous Decision Center.
   Keeps the same data and actions while reducing blank space and page height.
   R8-19 adds one GEO decision summary without creating a ninth AI employee. */
(() => {
  if (window.__kazuizhiDecisionLayoutPatchLoaded) return;
  window.__kazuizhiDecisionLayoutPatchLoaded = true;

  const style = document.createElement('style');
  style.id = 'decision-layout-patch-style';
  style.textContent = `
    /* Manager judgement and employee reports should read like one company dashboard,
       not two uneven columns with a large blank area. */
    .decision-grid{grid-template-columns:1fr!important;gap:14px!important}
    .decision-grid>article{min-width:0}
    .decision-stack{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px!important}
    .decision-agent-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:10px!important}
    .decision-agent{min-height:0;display:flex;flex-direction:column}
    .decision-agent-judge{min-height:38px}
    .decision-agent-open{margin-top:auto;padding-top:8px}

    /* Keep the executive page compact enough to scan without hiding detail. */
    .decision-team,.region-center{margin-top:14px!important}
    .decision-shared-context{grid-template-columns:repeat(4,minmax(0,1fr))!important}
    .decision-shared-item{min-width:0}
    .decision-hero{padding-bottom:16px}
    .decision-item,.decision-agent{padding:11px!important}

    /* R8-19 GEO Phase 1: ChatGPT remains the strategy owner. */
    .geo-decision-brief{margin-top:14px!important;border:1px solid #d9e3f5!important;border-left:4px solid #3168e8!important;background:#fff!important}
    .geo-decision-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}
    .geo-decision-head label{color:#3168e8}
    .geo-decision-head h3{margin:4px 0 5px;color:#17243b;font-size:17px}
    .geo-decision-head p{margin:0;color:#63738c;font-size:12px;line-height:1.55}
    .geo-decision-open{border:1px solid #bcd0f6;background:#fff;color:#285fc9;border-radius:8px;padding:7px 10px;font-size:10px;font-weight:700;cursor:pointer;white-space:nowrap}
    .geo-decision-open:hover{background:#f5f8ff}
    .geo-decision-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:12px}
    .geo-decision-grid>div{padding:9px 10px;border:1px solid #e4eaf3;border-radius:8px;background:#f8faff;min-width:0}
    .geo-decision-grid span{display:block;color:#74839a;font-size:9px;margin-bottom:4px}
    .geo-decision-grid b{display:block;color:#263b5c;font-size:12px;line-height:1.4;font-variant-numeric:tabular-nums;word-break:break-word}
    .geo-decision-grid .geo-wait b{color:#a86512}.geo-decision-grid .geo-danger b{color:#b43b32}.geo-decision-grid .geo-ok b{color:#087a50}
    .geo-decision-foot{display:flex;gap:10px;flex-wrap:wrap;margin-top:9px;color:#8795aa;font-size:9px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
    .geo-decision-error{margin-top:10px;padding:8px 10px;border-radius:7px;background:#fff6e8;color:#94611c;font-size:11px}

    @media(max-width:1250px){
      .decision-agent-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
      .decision-shared-context{grid-template-columns:repeat(2,minmax(0,1fr))!important}
      .geo-decision-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
    }
    @media(max-width:820px){
      .decision-stack,.decision-agent-grid,.decision-shared-context{grid-template-columns:1fr!important}
      .geo-decision-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
      .geo-decision-head{flex-direction:column}.geo-decision-open{width:100%}
    }
  `;
  document.head.appendChild(style);

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  let refreshTimer = null;

  function geoDecisionCard(){
    return `
      <article id="geo-decision-brief" class="wide geo-decision-brief">
        <div class="geo-decision-head">
          <div><label>今日 GEO 决策 · ChatGPT 总脑</label><h3 id="geo-decision-title">正在读取 GEO Mission…</h3><p id="geo-decision-judge">GEO 任务只由 ChatGPT 决策；本地模型仅作辅助分析。</p></div>
          <button id="geo-decision-open" class="geo-decision-open" type="button">打开 GEO 工作区</button>
        </div>
        <div class="geo-decision-grid">
          <div><span>今日测试上限</span><b id="geo-decision-limit">--</b></div>
          <div><span>固定 50 问</span><b id="geo-decision-progress">-- / 50</b></div>
          <div><span>正在执行</span><b id="geo-decision-running">--</b></div>
          <div id="geo-decision-blocker-box"><span>需要人工处理</span><b id="geo-decision-blockers">--</b></div>
          <div><span>下一决策条件</span><b id="geo-decision-next">--</b></div>
        </div>
        <div class="geo-decision-foot"><span id="geo-decision-id">Decision --</span><span id="geo-command-id">Command --</span><span>SEO：冻结开发 / 保持运行</span></div>
        <div id="geo-decision-error" class="geo-decision-error" hidden></div>
      </article>`;
  }

  function ensureGeoDecisionBrief(){
    if (document.getElementById('geo-decision-brief')) return true;
    const center = document.getElementById('decision-center');
    if (!center) return false;
    const hero = center.querySelector('.decision-hero');
    if (!hero) return false;
    hero.insertAdjacentHTML('afterend', geoDecisionCard());
    document.getElementById('geo-decision-open')?.addEventListener('click', () => {
      try { localStorage.setItem('kz-search-growth-workspace','geo'); } catch (_) {}
      window.location.href = 'operational.html#search';
    });
    refreshGeoDecisionBrief();
    return true;
  }

  async function refreshGeoDecisionBrief(){
    if (!document.getElementById('geo-decision-brief')) return;
    const errorBox=document.getElementById('geo-decision-error');
    try{
      const response=await fetch('/api/r8-19/geo',{cache:'no-store'});
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(data.error||`GEO 服务返回 ${response.status}`);
      const decision=data.decision||{},official=data.official||{},queue=data.queue||{},manual=data.manual||{};
      document.getElementById('geo-decision-title').textContent=decision.mission_title||'涟水县 GEO 第一轮基线验证';
      document.getElementById('geo-decision-judge').textContent=decision.judgement||'继续完成真实 GEO 基线，等待可追溯外部证据。';
      document.getElementById('geo-decision-limit').textContent=`${Number(decision.daily_test_limit||0).toLocaleString('zh-CN')} 题`;
      document.getElementById('geo-decision-progress').textContent=`${Number(official.tested||0).toLocaleString('zh-CN')} / 50`;
      document.getElementById('geo-decision-running').textContent=Number(queue.running||0).toLocaleString('zh-CN');
      const blockers=Number(manual.count||0);
      document.getElementById('geo-decision-blockers').textContent=blockers?`${blockers} 项待授权`:'0 · 无人工阻塞';
      const blockerBox=document.getElementById('geo-decision-blocker-box');
      blockerBox?.classList.toggle('geo-wait',blockers>0);blockerBox?.classList.toggle('geo-ok',blockers===0);
      document.getElementById('geo-decision-next').textContent=decision.next_decision_condition||'固定50问完成后再进入下一阶段';
      document.getElementById('geo-decision-id').textContent=`Decision ${decision.decision_id||'--'}`;
      document.getElementById('geo-command-id').textContent=`Command ${decision.command_id||'--'}`;
      if(errorBox){errorBox.hidden=true;errorBox.textContent=''}
    }catch(error){
      if(errorBox){errorBox.hidden=false;errorBox.textContent=`GEO 决策状态暂不可读：${esc(error.message)}`}
    }
  }

  const observer=new MutationObserver(()=>{
    if(ensureGeoDecisionBrief()){
      if(!refreshTimer)refreshTimer=setInterval(refreshGeoDecisionBrief,30000);
    }
  });
  observer.observe(document.documentElement,{childList:true,subtree:true});
  if(ensureGeoDecisionBrief()&&!refreshTimer)refreshTimer=setInterval(refreshGeoDecisionBrief,30000);
})();