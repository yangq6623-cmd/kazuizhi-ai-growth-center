(() => {
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  let cache=null;

  async function requestJson(path,options={},timeoutMs=12000){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort('kz_connector_timeout'),timeoutMs);
    try{
      const r=await fetch(path,{cache:'no-store',signal:controller.signal,...options});
      const d=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(d.error||`连接路由返回 ${r.status}`);
      return d;
    }catch(error){
      if(controller.signal.aborted||error?.name==='AbortError'||String(error?.message||'').includes('aborted')){
        throw new Error(`连接路由检查超时（${Math.round(timeoutMs/1000)}秒），不影响 SEO/GEO 主界面继续使用。`);
      }
      throw error;
    }finally{clearTimeout(timer)}
  }
  async function getJson(path){return requestJson(path,{},12000)}
  async function post(path,body={}){
    return requestJson(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)},20000);
  }

  function style(){
    if(document.getElementById('r821-connector-style'))return;
    const s=document.createElement('style');s.id='r821-connector-style';s.textContent=`
      .r821-connect{margin:16px 0;border:1px solid #d9e2ef;border-radius:10px;background:#fff;overflow:hidden;color:#172033}
      .r821-connect-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;padding:13px 15px;border-bottom:1px solid #e8edf4;background:#f8fafd}
      .r821-connect-head p{margin:0 0 3px;color:#2f6fdf;font-size:10px;font-weight:800;letter-spacing:.06em}.r821-connect-head h3{margin:0;font-size:15px}.r821-connect-head small{display:block;margin-top:4px;color:#718096;font-size:10px;line-height:1.5}
      .r821-connect-actions{display:flex;gap:6px;flex-wrap:wrap}.r821-connect-actions button{border:1px solid #c8d5e6;border-radius:6px;background:#fff;color:#315b94;padding:6px 9px;font-size:10px;font-weight:700;cursor:pointer}.r821-connect-actions button.primary{background:#2f6fdf;border-color:#2f6fdf;color:#fff}
      .r821-connect-body{padding:12px 15px}.r821-connect-kpis{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:7px}.r821-connect-kpis div{border:1px solid #e2e8f0;border-radius:7px;padding:8px}.r821-connect-kpis span{display:block;color:#7a8799;font-size:9px}.r821-connect-kpis b{display:block;font-size:16px;margin-top:2px}
      .r821-connect-table-wrap{overflow:auto;max-height:430px;margin-top:10px;border:1px solid #e5eaf1;border-radius:7px}.r821-connect-table{width:100%;border-collapse:collapse;font-size:10px;min-width:980px}.r821-connect-table th,.r821-connect-table td{padding:7px 8px;border-bottom:1px solid #edf1f5;text-align:left;vertical-align:top}.r821-connect-table th{position:sticky;top:0;background:#f8fafd;color:#5f6e83;z-index:1}.r821-connect-table td.route{text-align:center}
      .r821-chip{display:inline-block;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;background:#edf3ff;color:#315ea8}.r821-chip.ok{background:#e9f8ee;color:#267348}.r821-chip.warn{background:#fff4de;color:#986000}.r821-chip.off{background:#f1f3f6;color:#778397}.r821-check{font-weight:800;color:#267348}.r821-dash{color:#adb6c3}.r821-connect-note{margin-top:8px;padding:7px 9px;border-radius:6px;background:#f7f9fc;color:#68778d;font-size:9px;line-height:1.55}.r821-connect-msg{margin-top:7px;color:#627188;font-size:10px}
      @media(max-width:1100px){.r821-connect-kpis{grid-template-columns:repeat(4,1fr)}}@media(max-width:650px){.r821-connect-kpis{grid-template-columns:repeat(2,1fr)}.r821-connect-head{display:block}.r821-connect-actions{margin-top:8px}}
    `;document.head.appendChild(s);
  }

  function panelHtml(){return `<section class="r821-connect" data-r821-connect>
    <div class="r821-connect-head"><div><p>R8-21 · UNIFIED CONNECTOR ROUTER</p><h3>SEO / GEO 统一连接路由矩阵</h3><small>把“系统状态与连接”中的已有通道统一映射到 SEO、GEO、内容分发、AI执行和经营归因；连接成功不等于外部结果成功。</small></div><div class="r821-connect-actions"><button type="button" data-r821-refresh>刷新</button><button type="button" class="primary" data-r821-sync>同步并检查服务器通道</button></div></div>
    <div class="r821-connect-body"><div class="r821-connect-kpis" data-r821-kpis></div><div class="r821-connect-table-wrap"><table class="r821-connect-table"><thead><tr><th>连接</th><th>状态</th><th>SEO</th><th>GEO</th><th>分发</th><th>AI执行</th><th>归因</th><th>Evidence规则 / 下一步</th></tr></thead><tbody data-r821-rows><tr><td colspan="8">正在读取统一连接路由…</td></tr></tbody></table></div><div class="r821-connect-note">正式真值规则：模型/API普通输出不进入GEO正式成绩；社交平台只作为分发/品牌信号；公网发布、搜索提交、抓取、收录、排名和GEO A/B分别等待自己的真实 Evidence / Receipt。</div><div class="r821-connect-msg" data-r821-msg></div></div>
  </section>`}

  function ensure(){
    style();
    ['seo-growth-pane','geo-growth-pane'].forEach(id=>{
      const pane=document.getElementById(id);if(!pane||pane.querySelector('[data-r821-connect]'))return;
      const w=document.createElement('div');w.innerHTML=panelHtml();const p=w.firstElementChild;
      if(id==='geo-growth-pane'){
        const anchor=pane.querySelector('#geo-autonomy-panel,#geo-phase2-analysis,#r820-growth-panel');
        if(anchor&&anchor.parentNode)anchor.parentNode.insertBefore(p,anchor);else pane.appendChild(p);
      }else{
        const pipeline=pane.querySelector('.seo-autonomy-pipeline,#seo-autonomy-pipeline');
        if(pipeline&&pipeline.parentNode)pipeline.parentNode.insertBefore(p,pipeline);else pane.appendChild(p);
      }
    });
    bind();
  }

  function flag(v){return v?'<span class="r821-check">✓</span>':'<span class="r821-dash">—</span>'}
  function stateChip(row){
    const state=String(row.route_state||'');
    const cls=state==='ready'?'ok':state.includes('waiting')||state.includes('pending')||state.includes('configured')?'warn':'off';
    const text=state==='ready'?'已接通':state==='software_ready_external_pending'?'软件已接通/外部待验':state==='configured_waiting_test'?'已配置/待验证':state==='configured_waiting_live'?'已配置/待在线':state==='not_configured'?'未配置':state||'待处理';
    return `<span class="r821-chip ${cls}">${esc(text)}</span>`;
  }

  function render(data){
    cache=data||{};ensure();const s=cache.summary||{};
    const k=[['连接总数',s.total||0],['软件可路由',s.software_ready||0],['外部已验证',s.externally_verified||0],['SEO路由',s.seo_routes||0],['GEO路由',s.geo_routes||0],['分发路由',s.distribution_routes||0],['AI执行',s.ai_execution_routes||0]];
    document.querySelectorAll('[data-r821-kpis]').forEach(el=>el.innerHTML=k.map(x=>`<div><span>${esc(x[0])}</span><b>${esc(x[1])}</b></div>`).join(''));
    const rows=cache.connectors||[];
    const html=rows.length?rows.map(r=>`<tr><td><b>${esc(r.name||r.id)}</b><br><small>${esc(r.id||'')} · ${esc(r.kind||'')}</small></td><td>${stateChip(r)}</td><td class="route">${flag(r.use_for_seo)}</td><td class="route">${flag(r.use_for_geo)}</td><td class="route">${flag(r.use_for_distribution)}</td><td class="route">${flag(r.use_for_ai_execution)}</td><td class="route">${flag(r.use_for_business_attribution)}</td><td>${esc(r.formal_evidence_policy||'')}<br><small>${esc(r.next_action||'')}</small></td></tr>`).join(''):'<tr><td colspan="8">尚无连接路由。</td></tr>';
    document.querySelectorAll('[data-r821-rows]').forEach(el=>el.innerHTML=html);
    const relay=rows.find(x=>x.id==='chatgpt_relay');
    const remote=rows.find(x=>x.id==='remote_agent');
    const note=[];
    if(remote&&!remote.external_verified)note.push('公网服务器 Remote Agent 尚未通过当前健康验证');
    if(relay&&!relay.software_route_ready)note.push('ChatGPT 安全 Relay 尚未配置，因此本对话不能直接远程 Command→Receipt；本地SEO/GEO自治不受影响');
    document.querySelectorAll('[data-r821-msg]').forEach(el=>el.textContent=note.join('；')||'统一路由已同步；没有发现新的连接层阻塞。');
  }

  function showError(message){
    ensure();
    document.querySelectorAll('[data-r821-rows]').forEach(el=>el.innerHTML='<tr><td colspan="8">连接矩阵暂未返回；SEO/GEO 主工作区继续运行，可稍后重试。</td></tr>');
    document.querySelectorAll('[data-r821-msg]').forEach(el=>el.textContent=message||'连接矩阵暂不可用。');
  }
  async function refresh(){
    try{render(await getJson('/api/r8-21/seo-geo/connectors'))}
    catch(error){showError(error.message);throw error}
  }
  async function sync(){
    const buttons=[...document.querySelectorAll('[data-r821-sync]')];
    buttons.forEach(btn=>{btn.disabled=true;btn.dataset.oldText=btn.textContent;btn.textContent='检查中…'});
    document.querySelectorAll('[data-r821-msg]').forEach(el=>el.textContent='正在同步连接路由并检查服务器通道；主界面不会等待此检查。');
    try{
      const d=await post('/api/r8-21/seo-geo/connectors/sync',{check_live:true});render(d.result||d.connector_routes||d);
    }catch(error){showError(error.message);throw error}
    finally{buttons.forEach(btn=>{btn.disabled=false;btn.textContent=btn.dataset.oldText||'同步并检查服务器通道';delete btn.dataset.oldText})}
  }
  let bound=false;
  function bind(){
    if(bound)return;bound=true;
    document.addEventListener('click',e=>{
      const refreshBtn=e.target.closest('[data-r821-refresh]');if(refreshBtn){refresh().catch(err=>document.querySelectorAll('[data-r821-msg]').forEach(el=>el.textContent=err.message));return}
      const syncBtn=e.target.closest('[data-r821-sync]');if(syncBtn){sync().catch(err=>document.querySelectorAll('[data-r821-msg]').forEach(el=>el.textContent=err.message));}
    });
  }
  function boot(){ensure();refresh().catch(()=>{});setInterval(()=>{if(document.visibilityState==='visible')refresh().catch(()=>{})},30000)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
  window.addEventListener('operational:search-updated',()=>{ensure();if(cache)render(cache)});
})();
