(() => {
  'use strict';

  // Release-contract markers retained for the R8-23 gate:
  // R8-23 · FINAL 7×24 AUTONOMOUS GROWTH OS · ChatGPT 总脑 · 双增长引擎 · 8个AI员工 · 能力利用情况
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const byId = id => document.getElementById(id);
  let timer = null;
  let observer = null;
  let latestSeo = {};
  let seoRequest = null;

  function style(){
    if(byId('kz-r8-23-style')) return;
    const node = document.createElement('style');
    node.id = 'kz-r8-23-style';
    node.textContent = `
      :root{--kz23-blue:#245fd3;--kz23-navy:#18283f;--kz23-text:#1c2c43;--kz23-muted:#718096;--kz23-line:#e3e9f2;--kz23-soft:#f6f8fc;--kz23-green:#147a55;--kz23-amber:#9a651f;--kz23-red:#b33a34}
      .kz23{margin:10px 0 14px;border:1px solid var(--kz23-line);border-radius:12px;background:#fff;box-shadow:0 5px 16px rgba(24,40,63,.045);overflow:hidden;color:var(--kz23-text);font-family:inherit}
      .kz23-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:12px 14px;border-bottom:1px solid var(--kz23-line);background:#fff}
      .kz23-eyebrow{font-size:9px;letter-spacing:.07em;color:#5d78a1;font-weight:800}.kz23-top h3{margin:3px 0 2px;font-size:17px;line-height:1.3;color:#17283f}.kz23-top p{margin:0;color:var(--kz23-muted);font-size:10px;line-height:1.45}
      .kz23-live{display:flex;align-items:center;gap:6px;white-space:nowrap;border:1px solid #d8e4f7;background:#f3f7ff;color:#285ebd;border-radius:999px;padding:5px 8px;font-size:9px;font-weight:700}.kz23-live i{width:6px;height:6px;border-radius:50%;background:#23a36d;box-shadow:0 0 0 3px rgba(35,163,109,.12)}
      .kz23-body{padding:11px 13px 13px;display:grid;gap:9px}.kz23-hierarchy{display:grid;grid-template-columns:1.2fr 1fr 1fr .8fr;gap:7px}.kz23-hierarchy article,.kz23-metric,.kz23-card{border:1px solid var(--kz23-line);border-radius:9px;background:#fff}.kz23-hierarchy article{padding:8px 9px;min-width:0}.kz23-label{display:block;color:#7a899f;font-size:8px;margin-bottom:3px}.kz23-value{display:block;font-size:10px;color:#24364f;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kz23-value.state{color:var(--kz23-green)}
      .kz23-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:7px}.kz23-metric{padding:8px 9px;min-width:0;background:#fbfcfe}.kz23-metric span{display:block;color:#7a899f;font-size:8px}.kz23-metric b{display:block;margin-top:2px;font-size:16px;color:#20344f;line-height:1.15}.kz23-metric small{display:block;margin-top:2px;color:#8592a5;font-size:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kz23-metric.good b{color:var(--kz23-green)}.kz23-metric.warn b{color:var(--kz23-amber)}.kz23-metric.bad b{color:var(--kz23-red)}
      .kz23-progress{height:4px;background:#edf1f6;border-radius:999px;overflow:hidden}.kz23-progress i{display:block;height:100%;border-radius:inherit;background:var(--kz23-blue);transition:width .25s ease}
      .kz23-project-workflow{border:1px solid #dfe7f2;border-radius:9px;background:#f8faff;padding:8px 9px}.kz23-project-flow{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:5px}.kz23-project-flow div{position:relative;border:1px solid #e1e8f2;border-radius:7px;background:#fff;padding:6px 7px;text-align:center;min-width:0}.kz23-project-flow div:not(:last-child):after{content:'→';position:absolute;right:-7px;top:50%;transform:translateY(-50%);color:#98a7ba;font-weight:800;z-index:2}.kz23-project-flow b{display:block;font-size:9px;color:#27415f}.kz23-project-flow span{display:block;margin-top:2px;font-size:7px;color:#7c8ba0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .kz23-projects{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.kz23-project{appearance:none;text-align:left;border:1px solid #e1e8f2;border-radius:9px;background:#fff;padding:9px;min-width:0;cursor:pointer;transition:border-color .15s,box-shadow .15s,transform .15s}.kz23-project:hover{border-color:#a9c6f2;box-shadow:0 4px 12px rgba(36,95,211,.08);transform:translateY(-1px)}.kz23-project-head{display:flex;justify-content:space-between;gap:7px;align-items:flex-start}.kz23-project-head b{font-size:10px;color:#263c59}.kz23-project-state{font-size:7px;padding:2px 5px;border-radius:4px;background:#eef2f7;color:#66768c;white-space:nowrap}.kz23-project-state.active{background:#e8f7f0;color:#11724e}.kz23-project-state.ready{background:#edf3ff;color:#2b62c7}.kz23-project-state.partial{background:#fff4df;color:#8c5f1e}.kz23-project p{margin:5px 0;color:#6f7e93;font-size:8px;line-height:1.4;min-height:22px}.kz23-project-meta{display:flex;justify-content:space-between;gap:6px;color:#8794a6;font-size:7px}.kz23-project-bar{height:3px;margin-top:6px;background:#edf1f6;border-radius:999px;overflow:hidden}.kz23-project-bar i{display:block;height:100%;background:#4f7fe0;border-radius:999px}.kz23-project small{display:block;margin-top:5px;color:#98a3b2;font-size:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .kz23-main{display:grid;grid-template-columns:minmax(0,1.42fr) minmax(280px,.58fr);gap:9px;align-items:start}.kz23-card{padding:9px 10px;min-width:0}.kz23-card-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:7px}.kz23-card h4{margin:0;font-size:11px;color:#2b3e59}.kz23-card-head small{color:#8996a8;font-size:8px}
      .kz23-employees{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.kz23-employee{border:1px solid #e5eaf2;border-radius:8px;padding:7px 8px;background:#fcfdff;min-width:0}.kz23-employee-head{display:flex;justify-content:space-between;gap:5px;align-items:flex-start}.kz23-employee b{font-size:9px;color:#263a55}.kz23-state{font-size:7px;padding:2px 5px;border-radius:4px;background:#eef2f7;color:#66768c;white-space:nowrap}.kz23-state.active{background:#e9f7f1;color:#11724e}.kz23-state.assigned{background:#edf3ff;color:#2b62c7}.kz23-state.wait{background:#fff5e3;color:#90601f}.kz23-employee p{margin:5px 0 0;color:#78869a;font-size:8px;line-height:1.4;min-height:22px}.kz23-employee small{display:block;margin-top:4px;color:#9aa5b4;font-size:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .kz23-side{display:grid;gap:7px}.kz23-engine-row{display:grid;grid-template-columns:1fr 1fr;gap:6px}.kz23-engine{border:1px solid #e3e9f3;border-radius:7px;padding:7px 8px;background:#f8faff}.kz23-engine b{display:block;font-size:9px;color:#29415f}.kz23-engine span{display:block;margin-top:3px;font-size:7px;color:#7e8ca0;line-height:1.35}
      .kz23-chain{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}.kz23-chain div{background:var(--kz23-soft);border:1px solid #e5eaf2;border-radius:7px;padding:6px;text-align:center}.kz23-chain b{display:block;font-size:12px;color:#243a58}.kz23-chain span{display:block;margin-top:2px;font-size:7px;color:#7c8a9e}.kz23-chain .formal b{color:#2a61c5}
      .kz23-next{border-left:3px solid #5e8ee8;background:#f6f9ff;border-radius:7px;padding:7px 8px;color:#596b84;font-size:8px;line-height:1.45}.kz23-truth{font-size:8px;line-height:1.5;color:#6c7b90;background:#f7f9fc;border-radius:7px;padding:6px 8px}
      .kz23-identity{border:1px solid #dce8fd;background:#f5f8ff;border-radius:8px;padding:8px 9px;display:flex;gap:10px;align-items:flex-start}.kz23-identity b{font-size:10px;color:#2454aa;white-space:nowrap}.kz23-identity span{font-size:8px;line-height:1.5;color:#5c6f8a}
      .kz23-details{border:1px solid var(--kz23-line);border-radius:8px;background:#fafbfd;overflow:hidden}.kz23-details>summary{cursor:pointer;list-style:none;padding:8px 10px;font-size:9px;font-weight:700;color:#52667f;display:flex;align-items:center;justify-content:space-between;gap:10px}.kz23-details>summary::-webkit-details-marker{display:none}.kz23-details>summary:after{content:'展开';font-size:7px;color:#8a98ab;font-weight:500}.kz23-details[open]>summary:after{content:'收起'}.kz23-details-content{padding:0 9px 9px}.kz23-tech-table{width:100%;border-collapse:collapse;font-size:8px;background:#fff;border:1px solid #e7ebf2}.kz23-tech-table th,.kz23-tech-table td{padding:5px 6px;border-bottom:1px solid #edf1f5;text-align:left;vertical-align:top}.kz23-tech-table th{color:#78869a;background:#fafbfd;font-weight:600}.kz23-ok{color:var(--kz23-green)}.kz23-wait{color:var(--kz23-amber)}
      .kz23-legacy-home{margin-top:8px}.kz23-legacy-home .kz23-details-content{display:grid;gap:8px}.kz23-legacy-home .welcome,.kz23-legacy-home .stat-grid,.kz23-legacy-home .dashboard-grid,.kz23-legacy-home #dash-human-panel{margin:0!important}
      .kz23-legacy-slot{display:grid;gap:7px}.kz23-legacy-slot .kz22-panel{margin:0;box-shadow:none;border-color:#e3e8f0}.kz23-legacy-slot .kz22-head{background:#f4f7fb;color:#2b3e59;padding:9px 10px}.kz23-legacy-slot .kz22-head small,.kz23-legacy-slot .kz22-head p{color:#78869a;opacity:1}.kz23-legacy-slot .kz22-head h3{font-size:13px}.kz23-legacy-slot .kz22-grid{padding:8px 9px}.kz23-legacy-slot .kz22-body{padding:0 9px 9px}.kz23-legacy-ledger{border:1px solid #e4e9f1;border-radius:8px;padding:9px;background:#fff}

      /* The red-marked repeated block was caused by both panels living directly under <main>.
         R8-23.1 now scopes the full Mission strip + owner cockpit to the boss monitor only. */
      #dashboard>.mission-command-strip{margin:0 0 8px!important;border-radius:12px;box-shadow:0 4px 14px rgba(35,62,110,.045)}
      #dashboard>.mission-command-strip .mission-bar{grid-template-columns:minmax(300px,1.25fr) minmax(210px,.72fr) auto;gap:10px;padding:10px 12px}
      #dashboard>.mission-command-strip .mission-eyebrow{font-size:9px;margin-bottom:2px}
      #dashboard>.mission-command-strip .mission-title-row{gap:7px}
      #dashboard>.mission-command-strip .mission-title-row strong{font-size:13px}
      #dashboard>.mission-command-strip .mission-title-row span{font-size:10px}
      #dashboard>.mission-command-strip .mission-identity p{display:none}
      #dashboard>.mission-command-strip .mission-now{padding:7px 9px;border-radius:9px;gap:3px 6px}
      #dashboard>.mission-command-strip .mission-now b{font-size:10px}
      #dashboard>.mission-command-strip .mission-now small{display:none}
      #dashboard>.mission-command-strip .mission-state{padding:3px 6px;font-size:9px}
      #dashboard>.mission-command-strip .mission-actions{gap:5px}
      #dashboard>.mission-command-strip .mission-actions a,#dashboard>.mission-command-strip .mission-actions button{padding:5px 7px;border-radius:7px;font-size:9px}
      #dashboard>.mission-command-strip .mission-ai-gateway{padding:5px 7px;font-size:9px}
      #dashboard>.mission-command-strip .mission-human{padding:5px 7px;font-size:9px}
      #dashboard>.mission-command-strip .mission-detail{padding:12px}

      #r820-growth-panel.kz23-seo-polished{border-color:#e2e8f1;box-shadow:none;border-radius:10px}#r820-growth-panel.kz23-seo-polished .r820-head{background:#fff;color:#20324b;border-bottom:1px solid #e5eaf1;padding:10px 12px}#r820-growth-panel.kz23-seo-polished .r820-head p{color:#607da8}#r820-growth-panel.kz23-seo-polished .r820-head small{color:#78869a}#r820-growth-panel.kz23-seo-polished .r820-tabs button{background:#f5f7fb;color:#53667f;border-color:#dde4ee}#r820-growth-panel.kz23-seo-polished .r820-tabs button.active{background:#245fd3;color:#fff;border-color:#245fd3}#r820-growth-panel.kz23-seo-polished .r820-body{padding:10px 12px}#r820-growth-panel.kz23-seo-polished .r820-kpis{grid-template-columns:repeat(4,minmax(0,1fr))}#r820-growth-panel.kz23-seo-polished .r820-chart{height:155px}#r820-growth-panel.kz23-seo-polished .r820-grid{gap:8px;margin-top:8px}#r820-growth-panel.kz23-seo-polished .r820-card{border-radius:8px}
      .kz23-seo-advanced{margin-top:8px;border:1px solid #e1e7f0;border-radius:8px;background:#fafbfd}.kz23-seo-advanced>summary{cursor:pointer;padding:8px 10px;color:#586b83;font-size:9px;font-weight:700}.kz23-seo-advanced-body{padding:0 8px 8px}

      .kz23-geo-details{margin:9px 0;border:1px solid #dfe6f0;border-radius:10px;background:#fff;overflow:hidden}.kz23-geo-details>summary{cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;font-size:11px;font-weight:800;color:#334b69;background:#fbfcfe}.kz23-geo-details>summary::-webkit-details-marker{display:none}.kz23-geo-details>summary:after{content:'展开';font-size:9px;color:#8492a7;font-weight:600}.kz23-geo-details[open]>summary:after{content:'收起'}.kz23-geo-details-body{padding:0 10px 10px}.kz23-geo-details-body>.geo-auto,.kz23-geo-details-body>.geo3,.kz23-geo-details-body>.r820,.kz23-geo-details-body>.r821-connect,.kz23-geo-details-body>.panel,.kz23-geo-details-body>.geo-grid{margin:0!important;box-shadow:none!important}
      #geo-growth-pane.kz23-geo-polished>.geo-control{margin-bottom:9px;padding:12px 14px}
      #geo-growth-pane.kz23-geo-polished>.geo-kpis{gap:7px;margin-bottom:8px}
      #geo-growth-pane.kz23-geo-polished>.geo-kpis article{padding:8px 9px}
      #geo-growth-pane.kz23-geo-polished>.geo-mode-grid{gap:7px;margin:8px 0}
      #geo-growth-pane.kz23-geo-polished>.geo-actionbar{margin:8px 0;gap:6px}
      #geo-growth-pane.kz23-geo-polished>.geo-truth-banner{margin:8px 0;padding:8px 10px}
      #geo-growth-pane.kz23-geo-polished .r821-connect-table-wrap{max-height:300px}
      #geo-growth-pane.kz23-geo-polished .geo-table-wrap{max-height:360px}

      #connections.page.active .integration-grid{gap:10px}
      #connections.page.active article{border-radius:10px}
      #decision-center.page.active .decision-hero{margin-bottom:12px}
      #decision-center.page.active .decision-grid{gap:12px}

      @media(max-width:1250px){.kz23-employees{grid-template-columns:repeat(2,minmax(0,1fr))}.kz23-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.kz23-projects{grid-template-columns:repeat(2,minmax(0,1fr))}.kz23-project-flow{grid-template-columns:repeat(3,minmax(0,1fr))}.kz23-project-flow div:after{display:none}.kz23-hierarchy{grid-template-columns:1fr 1fr}.kz23-main{grid-template-columns:1fr}#dashboard>.mission-command-strip .mission-bar{grid-template-columns:1fr 1fr}#dashboard>.mission-command-strip .mission-actions{grid-column:1/-1;justify-content:flex-start}}
      @media(max-width:760px){.kz23-top{display:block}.kz23-projects{grid-template-columns:1fr}.kz23-project-flow{grid-template-columns:1fr 1fr}.kz23-live{display:inline-flex;margin-top:8px}.kz23-hierarchy,.kz23-metrics,.kz23-employees{grid-template-columns:1fr 1fr}.kz23-chain{grid-template-columns:1fr}.kz23-engine-row{grid-template-columns:1fr}#dashboard>.mission-command-strip .mission-bar{grid-template-columns:1fr}}
      @media(max-width:520px){.kz23-hierarchy,.kz23-metrics,.kz23-employees{grid-template-columns:1fr}}
    `;
    document.head.appendChild(node);
  }

  function ownerRoot(){
    return byId('dashboard') || document.querySelector('.page.active') || document.querySelector('main') || document.body;
  }

  function scopeOwnerPanels(){
    const root = byId('dashboard');
    if(!root) return;
    const strip = byId('mission-command-strip');
    const cockpit = byId('kz-r8-23-growth-os');
    if(strip && strip.parentElement !== root) root.prepend(strip);
    if(cockpit && cockpit.parentElement !== root){
      if(strip && strip.parentElement === root) strip.insertAdjacentElement('afterend',cockpit);
      else root.prepend(cockpit);
    }else if(cockpit && strip && strip.parentElement === root && cockpit.previousElementSibling !== strip){
      strip.insertAdjacentElement('afterend',cockpit);
    }
  }

  function foldLegacyHomepage(){
    const root=byId('dashboard');
    const cockpit=byId('kz-r8-23-growth-os');
    if(!root||!cockpit)return;
    let details=byId('kz-r8-24-legacy-home');
    if(!details){
      details=document.createElement('details');
      details.id='kz-r8-24-legacy-home';
      details.className='kz23-details kz23-legacy-home';
      const summary=document.createElement('summary');
      summary.textContent='历史基础面板 · 默认收起';
      const body=document.createElement('div');
      body.className='kz23-details-content';
      details.append(summary,body);
      cockpit.insertAdjacentElement('afterend',details);
    }
    const body=details.querySelector('.kz23-details-content');
    if(!body)return;
    const candidates=[
      ...root.querySelectorAll(':scope > .welcome.command-welcome'),
      ...root.querySelectorAll(':scope > .stat-grid'),
      ...root.querySelectorAll(':scope > .dashboard-grid'),
      ...root.querySelectorAll(':scope > #dash-human-panel'),
    ];
    candidates.forEach(node=>{ if(node.parentElement!==body) body.appendChild(node); });
  }

  function host(){
    let panel = byId('kz-r8-23-growth-os');
    if(!panel){
      panel = document.createElement('section');
      panel.id = 'kz-r8-23-growth-os';
      panel.className = 'kz23';
    }
    const root = ownerRoot();
    const strip = byId('mission-command-strip');
    if(root && strip && strip.parentElement === root){
      if(panel.parentElement !== root || panel.previousElementSibling !== strip) strip.insertAdjacentElement('afterend',panel);
    }else if(root && panel.parentElement !== root){
      root.prepend(panel);
    }
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

  const OWNER_PROJECTS = [
    {id:'geo',name:'GEO 自动增长',owner:'SEO/GEO 增长员',target:'r813-seo-geo',caps:['doubao_cloud','local_model','seo_website','formal_geo_browser','search_submission']},
    {id:'seo',name:'SEO 搜索增长',owner:'SEO/GEO 增长员',target:'r813-seo-geo',caps:['local_model','seo_website','search_submission','remote_agent']},
    {id:'content',name:'内容生产',owner:'内容运营员',target:'content-studio',caps:['local_model','doubao_cloud','seo_website']},
    {id:'video',name:'视频 / 视觉生产',owner:'短视频运营员',target:'operational-hub',caps:['local_model','doubao_cloud','rtx3060']},
    {id:'distribution',name:'发布与分发',owner:'社媒运营员',target:'operational-hub',caps:['seo_website','search_submission','social_distribution','remote_agent']},
    {id:'local',name:'本地增长 / 小程序',owner:'本地增长员',target:'analytics',caps:['maps_local','mini_program','business_data']},
    {id:'conversion',name:'转化与经营结果',owner:'用户转化员',target:'analytics',caps:['business_data','mini_program','local_model']},
    {id:'review',name:'总控复盘 / 自进化',owner:'数据复盘员',target:'r810-evolution',caps:['chatgpt_controller','business_data','local_model','doubao_cloud']},
  ];

  function projectCards(growth){
    const caps = capsArray(growth.capabilities);
    const lookup = Object.fromEntries(caps.map(cap=>[String(cap.id||''),cap]));
    const now = Date.now();
    return OWNER_PROJECTS.map(project=>{
      const rows = project.caps.map(id=>lookup[id]).filter(Boolean);
      const usable = rows.filter(cap=>cap.ready===true || (cap.ready==null && !['not_configured','waiting_connector','not_detected','error'].includes(String(cap.state||''))));
      const blocked = rows.filter(cap=>cap.ready===false || ['not_configured','waiting_connector','not_detected','error'].includes(String(cap.state||'')));
      const used = rows.filter(cap=>Number((cap.utilization||{}).invoke_count||0)>0);
      const latest = used.sort((a,b)=>timestamp((b.utilization||{}).last_invoked_at)-timestamp((a.utilization||{}).last_invoked_at))[0];
      const at = timestamp((latest?.utilization||{}).last_invoked_at);
      const recent = at>0 && now-at<30*60*1000;
      const ratio = rows.length ? Math.round(usable.length*100/rows.length) : 0;
      const state = recent ? ['最近执行','active'] : blocked.length ? ['部分待连接','partial'] : ['能力就绪','ready'];
      const detail = recent && latest ? `最近调用：${latest.name||latest.id}` : blocked.length ? `待连接：${blocked.slice(0,2).map(x=>x.name||x.id).join('、')}` : '等待 Mission / 触发条件';
      return `<button type="button" class="kz23-project" data-kz23-target="${esc(project.target)}"><div class="kz23-project-head"><b>${esc(project.name)}</b><span class="kz23-project-state ${state[1]}">${state[0]}</span></div><p>${esc(detail)}</p><div class="kz23-project-meta"><span>${esc(project.owner)}</span><span>能力 ${usable.length}/${rows.length}</span></div><div class="kz23-project-bar"><i style="width:${ratio}%"></i></div><small>${esc(latest ? `最近 ${shortTime((latest.utilization||{}).last_invoked_at)}` : `已登记 ${rows.length} 项执行能力`)}</small></button>`;
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

  function findLedger(){
    const headings = [...document.querySelectorAll('h1,h2,h3,h4')];
    const heading = headings.find(node => String(node.textContent||'').includes('MISSION CONTROL LEDGER'));
    if(!heading) return null;
    let container = heading.closest('article,.panel,.wide');
    if(!container) container = heading.parentElement;
    if(!container || container.id === 'kz-r8-23-growth-os' || container.contains(byId('kz-r8-23-growth-os'))) return null;
    return container;
  }

  function render(growth, autonomy, seo){
    scopeOwnerPanels();
    const panel = host();
    const preservedR22 = byId('kz-r8-22-autonomy');
    const preservedLedger = findLedger();
    if(preservedR22 && panel.contains(preservedR22)) preservedR22.remove();
    if(preservedLedger && panel.contains(preservedLedger)) preservedLedger.remove();

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
    const identity = growth.identity || {};
    const platformImprovement = growth.platform_improvement || {};
    const systemState = Number(progress.running||0) > 0 ? '任务执行中' : Number(progress.queued||0) > 0 ? '自治巡检 · 等待计划时点' : command.command_id ? '持续监听中' : '等待老板目标';
    const failures = Number(progress.failed||0);

    panel.innerHTML = `
      <div class="kz23-top"><div><div class="kz23-eyebrow">R8-24 · 老板全项目执行总览</div><h3>${esc(identity.name || 'ChatGPT 总脑')} · 自治增长工作台</h3><p>${esc(identity.mission || '这里仅在“老板监控”显示；其他业务页面只保留自己的工作内容，不再重复整套总览。')}</p></div><span class="kz23-live"><i></i>${esc(systemState)}</span></div>
      <div class="kz23-body">
        <div class="kz23-identity"><b>运行身份</b><span>${esc(identity.authority || '按已登记能力与授权边界调度。')} ${esc(identity.learning || '')} 每日单界面微调建议：${Number(platformImprovement.used_today || 0)} / ${Number(platformImprovement.daily_limit || 1)}；${esc(platformImprovement.rule || '不自动改代码、构建或发布安装包。')}</span></div>
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
        <div class="kz23-project-workflow"><div class="kz23-card-head"><h4>主页工作流 · 从目标到结果</h4><small>每个项目按真实能力、调用和回执推进</small></div><div class="kz23-project-flow"><div><b>老板目标 / Mission</b><span>ChatGPT总控</span></div><div><b>项目识别</b><span>SEO / GEO / 内容 / 视频</span></div><div><b>能力路由</b><span>豆包 / 本地模型 / RTX3060</span></div><div><b>执行与发布</b><span>AI员工 / 平台能力</span></div><div><b>Receipt / Evidence</b><span>真实结果回流</span></div><div><b>复盘 / 下一轮</b><span>自动调整优先级</span></div></div></div>
        <div class="kz23-card"><div class="kz23-card-head"><h4>全项目执行能力总览</h4><small>点击项目进入对应工作区 · 状态来自真实能力与最近调用</small></div><div class="kz23-projects">${projectCards(growth)}</div></div>
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
        <details class="kz23-details" id="kz-r8-23-legacy"><summary>技术主线与历史审计 · 默认收起</summary><div class="kz23-details-content kz23-legacy-slot"><div id="kz-r8-23-r22-slot"></div><div id="kz-r8-23-ledger-slot"></div></div></details>
      </div>`;

    panel.querySelectorAll('[data-kz23-target]').forEach(button=>{
      button.addEventListener('click',()=>{
        const target=button.dataset.kz23Target;
        const nav=document.querySelector(`.r810-nav-button[data-target="${target}"]`);
        if(nav) nav.click();
      });
    });

    const r22slot = byId('kz-r8-23-r22-slot');
    const ledgerslot = byId('kz-r8-23-ledger-slot');
    if(preservedR22 && r22slot){ r22slot.appendChild(preservedR22); preservedR22.classList.add('kz23-embedded-legacy'); }
    if(preservedLedger && ledgerslot){ preservedLedger.classList.add('kz23-legacy-ledger'); ledgerslot.appendChild(preservedLedger); }
    foldLegacy();
    foldLegacyHomepage();
    polishSeo();
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

  function wrapDetails(node,id,title){
    if(!node || byId(id)) return;
    const details = document.createElement('details');
    details.id = id;
    details.className = 'kz23-geo-details';
    const summary = document.createElement('summary');
    summary.textContent = title;
    const body = document.createElement('div');
    body.className = 'kz23-geo-details-body';
    node.parentNode.insertBefore(details,node);
    details.appendChild(summary);
    details.appendChild(body);
    body.appendChild(node);
  }

  function polishGeo(){
    const pane = byId('geo-growth-pane');
    if(!pane) return;
    pane.classList.add('kz23-geo-polished');

    const browser = pane.querySelector('.geo-browser-workbench');
    wrapDetails(browser,'kz23-geo-browser-details','真实外部 AI 网页验证工作台');

    const grids = [...pane.querySelectorAll(':scope > .geo-grid')];
    const mainGrid = grids.find(x=>!x.classList.contains('lower'));
    const lowerGrid = grids.find(x=>x.classList.contains('lower'));
    wrapDetails(mainGrid,'kz23-geo-question-details','固定 50 问与执行队列');
    wrapDetails(lowerGrid,'kz23-geo-evidence-details','Evidence / Receipt 与本地 C级预检');

    const manual = byId('geo-manual-list')?.closest('.geo-panel');
    wrapDetails(manual,'kz23-geo-manual-details','人工授权事项（仅真正需要老板时展开）');

    wrapDetails(byId('geo-autonomy'),'kz23-geo-cloud-details','云端自动扫描 · C级辅助（高级工具）');
    wrapDetails(byId('geo-phase2-analysis'),'kz23-geo-phase2-details','GEO Phase 2 分析（高级）');
    wrapDetails(byId('geo-phase3-panel'),'kz23-geo-phase3-details','GEO Phase 3 优化闭环（高级）');

    const matrix = [...pane.querySelectorAll('[data-r821-connect]')][0];
    wrapDetails(matrix,'kz23-geo-router-details','SEO/GEO 统一连接路由矩阵（高级）');
    wrapDetails(byId('r820-growth-panel'),'kz23-geo-trend-details','90天趋势、治理与运行保障（高级）');
  }

  function polishSeo(){
    const panel = byId('r820-growth-panel');
    if(panel){
      panel.classList.add('kz23-seo-polished');
      if(panel.dataset.kz23Folded !== '1'){
        const body = panel.querySelector('.r820-body');
        const grids = body ? [...body.querySelectorAll(':scope > .r820-grid')] : [];
        if(body && grids.length >= 4){
          const details = document.createElement('details');
          details.className = 'kz23-seo-advanced';
          details.innerHTML = '<summary>高级分析、内容治理与运行保障（展开查看）</summary><div class="kz23-seo-advanced-body"></div>';
          const target = details.querySelector('.kz23-seo-advanced-body');
          grids.slice(2).forEach(grid => target.appendChild(grid));
          const actions = body.querySelector('.r820-actions');
          body.insertBefore(details, actions || null);
          panel.dataset.kz23Folded = '1';
        }
      }
    }
    polishGeo();
  }

  async function refresh(){
    try{
      scopeOwnerPanels();
      // The complete SEO/GEO truth snapshot can be expensive on an established
      // installation because it assembles history, governance and evidence.
      // It must not make the owner workbench look unavailable while that
      // independent report is still loading.  Render the Mission and employee
      // control plane first, retain the last verified SEO snapshot, then update
      // the SEO metrics when the report arrives.
      const [growth, autonomy] = await Promise.all([
        json('/api/r8-23/growth-os'),
        json('/api/r8-22/autonomy'),
      ]);
      render(growth||{},autonomy||{},latestSeo);
      if(!seoRequest){
        seoRequest = json('/api/r8-20/seo-geo?days=30')
          .then(seo => {
            latestSeo = seo || {};
            render(growth||{},autonomy||{},latestSeo);
          })
          .catch(error => {
            // SEO/GEO has its own detailed workspace and retry loop.  Keep the
            // owner cockpit usable if that optional overview refresh is slow or
            // temporarily unavailable.
            console.warn('SEO/GEO overview refresh deferred', error);
          })
          .finally(() => { seoRequest = null; });
      }
    }catch(error){
      const panel = host();
      panel.innerHTML = `<div class="kz23-top"><div><div class="kz23-eyebrow">R8-23.1 · OWNER COCKPIT</div><h3>运营总览暂不可读</h3><p>${esc(error.message||error)}</p></div><span class="kz23-live"><i></i>等待恢复</span></div>`;
      foldLegacy();
      scopeOwnerPanels();
      polishSeo();
    }
  }

  function boot(){
    style();
    scopeOwnerPanels();
    polishSeo();
    refresh();
    foldLegacyHomepage();
    if(timer) clearInterval(timer);
    timer = setInterval(refresh,15000);
    if(observer) observer.disconnect();
    observer = new MutationObserver(()=>{ scopeOwnerPanels(); foldLegacy(); foldLegacyHomepage(); polishSeo(); });
    observer.observe(document.body,{childList:true,subtree:true});
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
})();
