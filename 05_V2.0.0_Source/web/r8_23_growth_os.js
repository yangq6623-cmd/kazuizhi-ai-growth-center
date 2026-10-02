(() => {
  'use strict';

  // Release-contract markers retained for the R8-23 gate:
  // R8-23 · FINAL 7×24 AUTONOMOUS GROWTH OS · ChatGPT 总脑 · 双增长引擎 · 8个AI员工 · 能力利用情况
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const byId = id => document.getElementById(id);
  let timer = null;
  let observer = null;

  function style(){
    if(byId('kz-r8-23-style')) return;
    const node = document.createElement('style');
    node.id = 'kz-r8-23-style';
    node.textContent = `
      :root{--kz23-blue:#245fd3;--kz23-navy:#18283f;--kz23-text:#1c2c43;--kz23-muted:#718096;--kz23-line:#e3e9f2;--kz23-soft:#f6f8fc;--kz23-green:#147a55;--kz23-amber:#9a651f;--kz23-red:#b33a34}
      .kz23{margin:12px 0 16px;border:1px solid var(--kz23-line);border-radius:14px;background:#fff;box-shadow:0 6px 20px rgba(24,40,63,.055);overflow:hidden;color:var(--kz23-text);font-family:inherit}
      .kz23-top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;padding:15px 17px;border-bottom:1px solid var(--kz23-line);background:#fff}
      .kz23-eyebrow{font-size:10px;letter-spacing:.07em;color:#5d78a1;font-weight:800}.kz23-top h3{margin:4px 0 3px;font-size:18px;line-height:1.35;color:#17283f}.kz23-top p{margin:0;color:var(--kz23-muted);font-size:11px;line-height:1.5}
      .kz23-live{display:flex;align-items:center;gap:7px;white-space:nowrap;border:1px solid #d8e4f7;background:#f3f7ff;color:#285ebd;border-radius:999px;padding:6px 9px;font-size:10px;font-weight:700}.kz23-live i{width:7px;height:7px;border-radius:50%;background:#23a36d;box-shadow:0 0 0 3px rgba(35,163,109,.12)}
      .kz23-body{padding:14px 16px 15px;display:grid;gap:12px}.kz23-hierarchy{display:grid;grid-template-columns:1.2fr 1fr 1fr .8fr;gap:8px}.kz23-hierarchy article,.kz23-metric,.kz23-card{border:1px solid var(--kz23-line);border-radius:10px;background:#fff}.kz23-hierarchy article{padding:9px 10px;min-width:0}.kz23-label{display:block;color:#7a899f;font-size:9px;margin-bottom:4px}.kz23-value{display:block;font-size:11px;color:#24364f;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kz23-value.state{color:var(--kz23-green)}
      .kz23-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.kz23-metric{padding:9px 10px;min-width:0;background:#fbfcfe}.kz23-metric span{display:block;color:#7a899f;font-size:9px}.kz23-metric b{display:block;margin-top:3px;font-size:17px;color:#20344f;line-height:1.2}.kz23-metric small{display:block;margin-top:3px;color:#8592a5;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kz23-metric.good b{color:var(--kz23-green)}.kz23-metric.warn b{color:var(--kz23-amber)}.kz23-metric.bad b{color:var(--kz23-red)}
      .kz23-progress{height:5px;background:#edf1f6;border-radius:999px;overflow:hidden}.kz23-progress i{display:block;height:100%;border-radius:inherit;background:var(--kz23-blue);transition:width .25s ease}
      .kz23-main{display:grid;grid-template-columns:minmax(0,1.38fr) minmax(300px,.62fr);gap:10px;align-items:start}.kz23-card{padding:11px 12px;min-width:0}.kz23-card-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:9px}.kz23-card h4{margin:0;font-size:12px;color:#2b3e59}.kz23-card-head small{color:#8996a8;font-size:9px}
      .kz23-employees{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.kz23-employee{border:1px solid #e5eaf2;border-radius:9px;padding:8px 9px;background:#fcfdff;min-width:0}.kz23-employee-head{display:flex;justify-content:space-between;gap:6px;align-items:flex-start}.kz23-employee b{font-size:10px;color:#263a55}.kz23-state{font-size:8px;padding:2px 5px;border-radius:4px;background:#eef2f7;color:#66768c;white-space:nowrap}.kz23-state.active{background:#e9f7f1;color:#11724e}.kz23-state.assigned{background:#edf3ff;color:#2b62c7}.kz23-state.wait{background:#fff5e3;color:#90601f}.kz23-employee p{margin:6px 0 0;color:#78869a;font-size:9px;line-height:1.45;min-height:26px}.kz23-employee small{display:block;margin-top:5px;color:#9aa5b4;font-size:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .kz23-side{display:grid;gap:8px}.kz23-engine-row{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kz23-engine{border:1px solid #e3e9f3;border-radius:8px;padding:8px 9px;background:#f8faff}.kz23-engine b{display:block;font-size:10px;color:#29415f}.kz23-engine span{display:block;margin-top:4px;font-size:8px;color:#7e8ca0;line-height:1.4}
      .kz23-chain{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.kz23-chain div{background:var(--kz23-soft);border:1px solid #e5eaf2;border-radius:8px;padding:7px;text-align:center}.kz23-chain b{display:block;font-size:13px;color:#243a58}.kz23-chain span{display:block;margin-top:2px;font-size:8px;color:#7c8a9e}.kz23-chain .formal b{color:#2a61c5}
      .kz23-next{border-left:3px solid #5e8ee8;background:#f6f9ff;border-radius:7px;padding:8px 9px;color:#596b84;font-size:9px;line-height:1.5}.kz23-truth{font-size:9px;line-height:1.55;color:#6c7b90;background:#f7f9fc;border-radius:7px;padding:7px 9px}
      .kz23-details{border:1px solid var(--kz23-line);border-radius:9px;background:#fafbfd;overflow:hidden}.kz23-details>summary{cursor:pointer;list-style:none;padding:9px 11px;font-size:10px;font-weight:700;color:#52667f;display:flex;align-items:center;justify-content:space-between;gap:10px}.kz23-details>summary::-webkit-details-marker{display:none}.kz23-details>summary:after{content:'展开';font-size:8px;color:#8a98ab;font-weight:500}.kz23-details[open]>summary:after{content:'收起'}.kz23-details-content{padding:0 10px 10px}.kz23-tech-table{width:100%;border-collapse:collapse;font-size:9px;background:#fff;border:1px solid #e7ebf2}.kz23-tech-table th,.kz23-tech-table td{padding:6px 7px;border-bottom:1px solid #edf1f5;text-align:left;vertical-align:top}.kz23-tech-table th{color:#78869a;background:#fafbfd;font-weight:600}.kz23-ok{color:var(--kz23-green)}.kz23-wait{color:var(--kz23-amber)}
      .kz23-legacy-slot{display:grid;gap:8px}.kz23-legacy-slot .kz22-panel{margin:0;box-shadow:none;border-color:#e3e8f0}.kz23-legacy-slot .kz22-head{background:#f4f7fb;color:#2b3e59;padding:10px 12px}.kz23-legacy-slot .kz22-head small,.kz23-legacy-slot .kz22-head p{color:#78869a;opacity:1}.kz23-legacy-slot .kz22-head h3{font-size:14px}.kz23-legacy-slot .kz22-grid{padding:9px 10px}.kz23-legacy-slot .kz22-body{padding:0 10px 10px}.kz23-legacy-ledger{border:1px solid #e4e9f1;border-radius:9px;padding:10px;background:#fff}
      #mission-command-strip{margin-bottom:10px!important}
      #r820-growth-panel.kz23-seo-polished{border-color:#e2e8f1;box-shadow:none;border-radius:12px}#r820-growth-panel.kz23-seo-polished .r820-head{background:#fff;color:#20324b;border-bottom:1px solid #e5eaf1;padding:12px 14px}#r820-growth-panel.kz23-seo-polished .r820-head p{color:#607da8}#r820-growth-panel.kz23-seo-polished .r820-head small{color:#78869a}#r820-growth-panel.kz23-seo-polished .r820-tabs button{background:#f5f7fb;color:#53667f;border-color:#dde4ee}#r820-growth-panel.kz23-seo-polished .r820-tabs button.active{background:#245fd3;color:#fff;border-color:#245fd3}#r820-growth-panel.kz23-seo-polished .r820-body{padding:12px 14px}#r820-growth-panel.kz23-seo-polished .r820-kpis{grid-template-columns:repeat(4,minmax(0,1fr))}#r820-growth-panel.kz23-seo-polished .r820-chart{height:175px}#r820-growth-panel.kz23-seo-polished .r820-grid{gap:9px;margin-top:9px}#r820-growth-panel.kz23-seo-polished .r820-card{border-radius:9px}
      .kz23-seo-advanced{margin-top:9px;border:1px solid #e1e7f0;border-radius:9px;background:#fafbfd}.kz23-seo-advanced>summary{cursor:pointer;padding:9px 11px;color:#586b83;font-size:10px;font-weight:700}.kz23-seo-advanced-body{padding:0 9px 9px}
      @media(max-width:1250px){.kz23-employees{grid-template-columns:repeat(2,minmax(0,1fr))}.kz23-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.kz23-hierarchy{grid-template-columns:1fr 1fr}.kz23-main{grid-template-columns:1fr}}
      @media(max-width:760px){.kz23-top{display:block}.kz23-live{display:inline-flex;margin-top:9px}.kz23-hierarchy,.kz23-metrics,.kz23-employees{grid-template-columns:1fr 1fr}.kz23-chain{grid-template-columns:1fr}.kz23-engine-row{grid-template-columns:1fr}}
      @media(max-width:520px){.kz23-hierarchy,.kz23-metrics,.kz23-employees{grid-template-columns:1fr}}
    `;
    document.head.appendChild(node);
  }

  function host(){
    let panel = byId('kz-r8-23-growth-os');
    if(panel) return panel;
    panel = document.createElement('section');
    panel.id = 'kz-r8-23-growth-os';
    panel.className = 'kz23';
    const strip = byId('mission-command-strip');
    if(strip && strip.parentElement){ strip.insertAdjacentElement('afterend', panel); return panel; }
    const r22 = byId('kz-r8-22-autonomy');
    if(r22){ r22.insertAdjacentElement('beforebegin', panel); return panel; }
    const main = document.querySelector('main');
    if(main){ main.prepend(panel); return panel; }
    document.body.prepend(panel);
    return panel;
  }

  async function json(path){
    const response = await fetch(path,{cache:'no-store'});
    if(!response.ok) throw new Error(`${path} HTTP ${response.status}`);
    return response.json();
  }

  function capsArray(data){
    if(Array.isArray(data)) return data;
    if(data && typeof data === 'object') return Object.entries(data).map(([id,row])=>({id,...(row||{})}));
    return [];
  }

  function timestamp(value){
    const time = Date.parse(value || '');
    return Number.isFinite(time) ? time : 0;
  }

  function shortTime(value){
    if(!value) return '尚无调用记录';
    const text = String(value).replace('T',' ');
    return text.length >= 16 ? text.slice(5,16) : text;
  }

  function employeeCards(growth){
    const employees = Array.isArray(growth.employees) ? growth.employees : [];
    const packages = Array.isArray(growth.work_packages) ? growth.work_packages : [];
    const caps = capsArray(growth.capabilities);
    const now = Date.now();
    return employees.map(emp => {
      const assigned = packages.find(pkg => String(pkg.employee_owner||'') === String(emp.id||'') || String(pkg.employee_owner||'') === String(emp.name||''));
      const owned = caps.filter(cap => Array.isArray(cap.owners) && cap.owners.includes(emp.id));
      const used = owned.filter(cap => Number((cap.utilization||{}).invoke_count||0) > 0).sort((a,b)=>timestamp((b.utilization||{}).last_invoked_at)-timestamp((a.utilization||{}).last_invoked_at));
      const latest = used[0];
      const at = timestamp((latest?.utilization||{}).last_invoked_at);
      const recent = at > 0 && now - at < 30*60*1000;
      const state = recent ? ['最近有执行','active'] : assigned ? ['已分配','assigned'] : ['待条件触发','wait'];
      const detail = latest ? `${latest.name || latest.id} · ${(latest.utilization||{}).invoke_count||0}次` : assigned ? (assigned.trigger || assigned.objective || 'Controller Plan 已分配工作包') : '按真实需求触发，不为展示强制运行';
      return `<div class="kz23-employee"><div class="kz23-employee-head"><b>${esc(emp.name)}</b><span class="kz23-state ${state[1]}">${state[0]}</span></div><p>${esc(detail)}</p><small>${esc(latest ? shortTime((latest.utilization||{}).last_invoked_at) : emp.responsibility || '')}</small></div>`;
    }).join('');
  }

  function capabilityTable(growth){
    const caps = capsArray(growth.capabilities);
    if(!caps.length) return '<div class="kz23-truth">等待能力状态。</div>';
    return `<table class="kz23-tech-table"><thead><tr><th>能力</th><th>状态</th><th>实际利用</th><th>真值/回执</th></tr></thead><tbody>${caps.map(cap=>{
      const util=cap.utilization||{}; const ready=cap.ready===true; const unknown=cap.ready==null;
      const state=unknown?(cap.state||'策略就绪'):ready?'可用':(cap.state||'等待');
      return `<tr><td><b>${esc(cap.name||cap.id)}</b></td><td class="${ready?'kz23-ok':'kz23-wait'}">${esc(state)}</td><td>${Number(util.invoke_count||0)} 次${util.last_invoked_at?`<br>${esc(shortTime(util.last_invoked_at))}`:''}</td><td>${esc(cap.truth_level||'—')}${util.last_receipt_id?`<br>${esc(util.last_receipt_id)}`:''}</td></tr>`;
    }).join('')}</tbody></table>`;
  }

  function metric(label,value,note,klass=''){
    return `<div class="kz23-metric ${klass}"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(note||'')}</small></div>`;
  }

  function render(growth, autonomy, seo){
    const panel = host();
    const command = autonomy.command || {};
    const mission = autonomy.mission || {};
    const plan = autonomy.plan || {};
    const progress = autonomy.progress || {};
    const pct = Math.max(0,Math.min(100,Number(progress.percent||0)));
    const ss = seo.seo_summary || {};
    const search = seo.search || {};
    const geo = seo.geo_summary || {};
    const publicPages = Number(ss.public_pages ?? seo.public_pages ?? 0);
    const submitted = Number(ss.submitted_urls ?? ss.submitted ?? search.submitted_urls ?? search.submitted ?? 0);
    const tested = Number(geo.tested ?? geo.formal_tested ?? 0);
    const engines = Array.isArray(growth.business_engines) ? growth.business_engines : [];
    const systemState = Number(progress.running||0) > 0 ? '任务执行中' : Number(progress.queued||0) > 0 ? '自治巡检 · 等待计划时点' : command.command_id ? '持续监听中' : '等待老板目标';
    const failures = Number(progress.failed||0);

    panel.innerHTML = `
      <div class="kz23-top"><div><div class="kz23-eyebrow">R8-23.1 · 老板运营总览</div><h3>ChatGPT 总脑 · 自治增长工作台</h3><p>战略、任务、AI员工、SEO/GEO 和真实回执集中在一屏；技术细节与历史账本默认收起。</p></div><span class="kz23-live"><i></i>${esc(systemState)}</span></div>
      <div class="kz23-body">
        <div class="kz23-hierarchy">
          <article><span class="kz23-label">长期 Mission</span><b class="kz23-value" title="${esc(mission.title||'')}">${esc(mission.title||mission.mission_id||'等待')}</b></article>
          <article><span class="kz23-label">当前 Command</span><b class="kz23-value">${esc(command.command_id||growth.command_id||'—')}</b></article>
          <article><span class="kz23-label">本轮 Controller Plan</span><b class="kz23-value">${esc(plan.plan_id||growth.plan_id||'—')}</b></article>
          <article><span class="kz23-label">自治状态</span><b class="kz23-value state">${esc(systemState)}</b></article>
        </div>
        <div class="kz23-metrics">
          ${metric('Mission进度',`${Number(progress.completed||0)} / ${Number(progress.total||0)}`,`${pct}%`,'good')}
          ${metric('正在执行',Number(progress.running||0),'真实任务')}
          ${metric('等待队列',Number(progress.queued||0),'按优先级/时点执行',Number(progress.queued||0)>0?'warn':'')}
          ${metric('失败/异常',failures,'真实记录',failures?'bad':'good')}
          ${metric('SEO公网 / 提交',`${publicPages} / ${submitted}`,'发布与提交分开记录','good')}
          ${metric('GEO正式Evidence',`${tested} / 50`,'仅真实A/B Evidence','')}
        </div>
        <div class="kz23-progress"><i style="width:${pct}%"></i></div>
        <div class="kz23-main">
          <div class="kz23-card"><div class="kz23-card-head"><h4>8个AI员工 · 当前工作归属</h4><small>只显示真实分配/调用，不制造“忙碌”</small></div><div class="kz23-employees">${employeeCards(growth)}</div></div>
          <div class="kz23-side">
            <div class="kz23-card"><div class="kz23-card-head"><h4>双增长引擎</h4><small>统一归因到订单</small></div><div class="kz23-engine-row">${engines.map(x=>`<div class="kz23-engine"><b>${esc(x.name)}</b><span>${esc((x.outcomes||[]).join(' → '))}</span></div>`).join('')}</div></div>
            <div class="kz23-card"><div class="kz23-card-head"><h4>真实增长闭环</h4><small>外部结果不补造</small></div><div class="kz23-chain"><div><b>${publicPages}</b><span>SEO真实公网</span></div><div><b>${submitted}</b><span>搜索已提交</span></div><div class="formal"><b>${tested}/50</b><span>GEO正式证据</span></div></div></div>
            <div class="kz23-next"><b>下一步：</b>${esc(autonomy.next_action || '系统根据真实 Receipt / Evidence 自动决定下一轮。')}</div>
          </div>
        </div>
        <div class="kz23-truth">${esc(growth.truth_rule || '普通API、本地模型和内部任务只作辅助，不冒充公网发布、搜索收录、排名或正式GEO成绩。')} ${esc(growth.operating_rule || '')}</div>
        <details class="kz23-details" id="kz-r8-23-capability-details"><summary>技术详情 · 能力利用情况与真实回执</summary><div class="kz23-details-content">${capabilityTable(growth)}</div></details>
        <details class="kz23-details" id="kz-r8-23-legacy"><summary>技术主线与历史审计 · 默认收起，不再占满老板工作台</summary><div class="kz23-details-content kz23-legacy-slot"><div id="kz-r8-23-r22-slot"></div><div id="kz-r8-23-ledger-slot"></div></div></details>
      </div>`;
    foldLegacy();
    polishSeo();
  }

  function findLedger(){
    const headings = [...document.querySelectorAll('h1,h2,h3,h4')];
    const heading = headings.find(node => String(node.textContent||'').includes('MISSION CONTROL LEDGER'));
    if(!heading) return null;
    let container = heading.closest('article,.panel,.wide');
    if(!container) container = heading.parentElement;
    if(!container || container.id === 'kz-r8-23-growth-os' || container.contains(byId('kz-r8-23-growth-os'))) return null;
    return container;
  }

  function foldLegacy(){
    const details = byId('kz-r8-23-legacy');
    if(!details) return;
    const r22 = byId('kz-r8-22-autonomy');
    const r22slot = byId('kz-r8-23-r22-slot');
    if(r22 && r22slot && r22.parentElement !== r22slot){
      r22slot.appendChild(r22);
      r22.classList.add('kz23-embedded-legacy');
    }
    const ledger = findLedger();
    const ledgerslot = byId('kz-r8-23-ledger-slot');
    if(ledger && ledgerslot && ledger.parentElement !== ledgerslot){
      ledger.classList.add('kz23-legacy-ledger');
      ledgerslot.appendChild(ledger);
    }
  }

  function polishSeo(){
    const panel = byId('r820-growth-panel');
    if(!panel) return;
    panel.classList.add('kz23-seo-polished');
    if(panel.dataset.kz23Folded === '1') return;
    const body = panel.querySelector('.r820-body');
    const grids = body ? [...body.querySelectorAll(':scope > .r820-grid')] : [];
    if(!body || grids.length < 4) return;
    const details = document.createElement('details');
    details.className = 'kz23-seo-advanced';
    details.innerHTML = '<summary>高级分析、内容治理与运行保障（展开查看）</summary><div class="kz23-seo-advanced-body"></div>';
    const target = details.querySelector('.kz23-seo-advanced-body');
    grids.slice(2).forEach(grid => target.appendChild(grid));
    const actions = body.querySelector('.r820-actions');
    body.insertBefore(details, actions || null);
    panel.dataset.kz23Folded = '1';
  }

  async function refresh(){
    try{
      const [growth, autonomy, seo] = await Promise.all([
        json('/api/r8-23/growth-os'),
        json('/api/r8-22/autonomy'),
        json('/api/r8-20/seo-geo?days=30'),
      ]);
      render(growth||{},autonomy||{},seo||{});
    }catch(error){
      const panel = host();
      panel.innerHTML = `<div class="kz23-top"><div><div class="kz23-eyebrow">R8-23.1 · OWNER COCKPIT</div><h3>运营总览暂不可读</h3><p>${esc(error.message||error)}</p></div><span class="kz23-live"><i></i>等待恢复</span></div>`;
      foldLegacy();
    }
  }

  function boot(){
    style();
    refresh();
    if(timer) clearInterval(timer);
    timer = setInterval(refresh,15000);
    if(observer) observer.disconnect();
    observer = new MutationObserver(()=>{ foldLegacy(); polishSeo(); });
    observer.observe(document.body,{childList:true,subtree:true});
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
})();
