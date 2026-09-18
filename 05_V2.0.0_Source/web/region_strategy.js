/* Regional Operations Center V1.
   Strategic work allocation is non-financial and evidence-aware. It never
   changes the production service-region switch or claims a reserve area is open. */

(() => {
  if (window.__kazuizhiRegionStrategyLoaded) return;
  window.__kazuizhiRegionStrategyLoaded = true;

  function ensureRegionStyles(){
    if ($('region-strategy-style')) return;
    const style=document.createElement('style');style.id='region-strategy-style';style.textContent=`
      .region-center{margin-top:16px}.region-strategy-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}.region-strategy-head p{margin:5px 0 0;color:#65748b;font-size:12px;line-height:1.55}.region-refresh{border:0;background:#eef4ff;color:#2d61ca;border-radius:9px;padding:8px 11px;font-weight:700;cursor:pointer}.region-refresh:hover{background:#e1ebff}.region-refresh:disabled{opacity:.6;cursor:default}
      .region-flow{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:14px 0}.region-tier{border-radius:999px;padding:7px 10px;font-size:10px;font-weight:700;background:#f3f6fb;color:#52637b;border:1px solid #e1e7f0}.region-tier.s{background:#e8f1ff;color:#225bc1;border-color:#c9dcff}.region-tier.a{background:#ecf7ff;color:#21719e;border-color:#d0ebf8}.region-tier.b{background:#eef8f0;color:#34734d;border-color:#d7eddd}.region-tier.c{background:#fff6e8;color:#8c611f;border-color:#f5dfb7}.region-flow i{font-style:normal;color:#a0afc2}
      .region-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.region-card{border:1px solid #e1e8f3;border-radius:12px;padding:12px;background:#fff;cursor:pointer;transition:.15s}.region-card:hover{border-color:#afc5f0;box-shadow:0 7px 18px rgba(49,104,232,.08);transform:translateY(-1px)}.region-card:focus{outline:2px solid #9ebcff;outline-offset:2px}.region-card-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.region-card h4{margin:0;font-size:14px;color:#17243b}.region-badge{font-size:9px;font-weight:700;border-radius:999px;padding:4px 7px;background:#eef4ff;color:#2d61ca}.region-card p{margin:7px 0;color:#64748b;font-size:10px;line-height:1.5}.region-kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin:9px 0}.region-kpi{background:#f7f9fd;border-radius:8px;padding:7px}.region-kpi b{display:block;color:#20334f;font-size:15px}.region-kpi small{display:block;color:#78869a;font-size:9px;margin-top:2px}.region-readiness{height:6px;border-radius:99px;background:#edf1f6;overflow:hidden;margin:8px 0}.region-readiness i{display:block;height:100%;background:linear-gradient(90deg,#4e7cea,#33b98c)}.region-recommendation{font-size:10px;color:#43556f;line-height:1.5}.region-open-hint{display:block;margin-top:8px;color:#3168e8;font-size:10px;font-weight:700}.region-rules{margin-top:12px;background:#f7f9fd;border:1px solid #e1e8f3;border-radius:10px;padding:10px 12px;color:#5b6d86;font-size:10px;line-height:1.55}
      @media(max-width:1200px){.region-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.region-grid{grid-template-columns:1fr}}
    `;document.head.appendChild(style);
  }

  function ensureRegionPanel(){
    const page=$('decision-center');
    if(!page)return null;
    if($('region-strategy-panel'))return $('region-strategy-panel');
    ensureRegionStyles();
    const panel=document.createElement('article');panel.id='region-strategy-panel';panel.className='wide region-center';
    panel.innerHTML=`
      <div class="region-strategy-head"><div><label>区域作战中心 V1</label><h3>增长必须知道重点在哪里</h3><p id="region-headline">正在整理区域战略…</p></div><button id="region-refresh" class="region-refresh">更新区域判断</button></div>
      <div class="region-flow"><span class="region-tier s">S 涟水 · 核心样板</span><i>→</i><span class="region-tier a">A 淮安 · 主战区</span><i>→</i><span class="region-tier b">B 江苏 · 扩张准备</span><i>→</i><span class="region-tier c">C 浙江/上海 · 战略储备</span></div>
      <div id="region-grid" class="region-grid friendly-empty">正在读取区域策略…</div>
      <div id="region-rules" class="region-rules">区域准备度只用于运营排序，不代表市场份额、订单规模或已经开放下单。</div>`;
    const handoff=$('decision-handoff')?.closest('article');
    if(handoff)handoff.parentNode.insertBefore(panel,handoff);else page.appendChild(panel);
    $('region-refresh')?.addEventListener('click',async()=>{
      const button=$('region-refresh');button.disabled=true;const old=button.textContent;button.textContent='正在更新…';
      try{const data=await api('/api/r7/decision-center/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});renderRegionStrategy(data?.region_strategy||{});if(typeof renderDecisionCenter==='function')renderDecisionCenter(data);toast('区域作战判断已更新')}
      catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent=old}
    });
    return panel;
  }

  function openRegionDetail(region){
    if(region.mode==='core'||region.mode==='main'){
      openPage('insights');toast(`已打开市场洞察，重点查看${region.name}的需求与本地信号`);return;
    }
    if(region.mode==='prepare'||region.mode==='reserve'){
      openPage('promotion');toast(`已打开内容增长，${region.name}当前以关键词、素材和战备储存为主`);return;
    }
    openPage('insights');toast('已打开长期区域机会监测');
  }

  function renderRegionStrategy(strategy){
    ensureRegionPanel();
    $('region-headline').textContent=strategy?.headline||'区域战略尚未生成';
    const rows=(strategy?.regions||[]).filter(item=>item.work_share_pct>0||item.tier!=='D');
    const grid=$('region-grid');grid.className=rows.length?'region-grid':'friendly-empty';
    grid.innerHTML=rows.length?rows.map(item=>{
      const verified=item.verified_region_aggregate;
      const verifiedText=verified===null||verified===undefined?'未接入':verified;
      return `<div class="region-card" role="button" tabindex="0" data-region-id="${esc(item.id)}"><div class="region-card-head"><div><h4>${esc(item.name)}</h4><p>${esc(item.role)}</p></div><span class="region-badge">${esc(item.tier)}级</span></div><div class="region-kpis"><div class="region-kpi"><b>${item.work_share_pct||0}%</b><small>建议工作量</small></div><div class="region-kpi"><b>${item.readiness_score||0}</b><small>运营准备度 · ${esc(item.confidence||'较低')}</small></div><div class="region-kpi"><b>${item.public_signal_count||0}</b><small>公开研究信号</small></div><div class="region-kpi"><b>${esc(verifiedText)}</b><small>已验证区域聚合</small></div></div><div class="region-readiness"><i style="width:${Math.max(0,Math.min(100,Number(item.readiness_score||0)))}%"></i></div><div class="region-recommendation">${esc(item.recommendation||item.objective||'等待更多证据')}</div><span class="region-open-hint">点击查看相关工作台 →</span></div>`;
    }).join(''):'暂无区域策略。';
    const byId=new Map(rows.map(item=>[String(item.id),item]));
    grid.querySelectorAll('.region-card').forEach(card=>{
      const activate=()=>{const region=byId.get(card.dataset.regionId);if(region)openRegionDetail(region)};
      card.addEventListener('click',activate);card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}});
    });
    const rules=strategy?.rules||{};
    $('region-rules').innerHTML=`<b>区域安全边界：</b>${esc(rules.platform_opening||'R7 不自动修改小程序区域开放状态。')}<br><b>储备区规则：</b>${esc(rules.reserve_regions||'储备区只做研究与准备。')}<br><b>评分说明：</b>${esc(rules.truth||'准备度只用于运营排序。')}`;
  }

  async function loadRegionStrategy(){
    ensureRegionPanel();
    try{const data=await api('/api/r7/decision-center');renderRegionStrategy(data?.region_strategy||{});return true}catch(error){toast(error.message,'error');return false}
  }

  window.loadRegionStrategy=loadRegionStrategy;
  const start=()=>{if(ensureRegionPanel())loadRegionStrategy();else setTimeout(start,80)};
  start();
  setInterval(()=>{if($('decision-center')?.classList.contains('active'))loadRegionStrategy()},60000);
})();
