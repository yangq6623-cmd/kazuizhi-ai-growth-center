(() => {
  'use strict';
  const kzGeoParams = new URLSearchParams(location.search);
  if (kzGeoParams.get('advanced') === '1') {
    // #725: the embedded advanced view is the legacy Evidence/browser toolbox.
    // Do not mount a second Growth OS core inside it; operational-search.js owns
    // the advanced tools and the parent page owns the main GEO Growth OS.
    window.__KZ_GEO_GROWTH_OS__ = true;
    window.__KZ_GEO_GROWTH_OS_BOOT__ = () => false;
    return;
  }
  if (window.__KZ_GEO_GROWTH_OS__ && typeof window.__KZ_GEO_GROWTH_OS_BOOT__ === 'function') {
    // A healthy bundled copy already finished initialization. Reuse it.
    try { window.__KZ_GEO_GROWTH_OS_BOOT__(); } catch (_) {}
    return;
  }
  // #692 recovery rule: a bundled copy may set the sentinel and then fail
  // before exporting BOOT. The direct copy must complete initialization in
  // that stale-sentinel state instead of returning forever.
  window.__KZ_GEO_GROWTH_OS__ = true;

  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  let cache = null;
  let busy = false;
  let attempts = 0;
  let activeFilter = "all";
  let pollTimer = null;
  let advancedTask = null;
  let advancedBusy = false;
  let advancedFetchedAt=0;
  let advancedRetryCount=0;
  let advancedRetryTimer=null;
  let advancedLastGood=null;

  async function json(path, options={}) {
    const controller=new AbortController();
    const timeoutMs=Number(options.timeoutMs||15000);
    const timer=setTimeout(()=>controller.abort('kz_geo_os_timeout'),timeoutMs);
    try{
      const clean={...options};delete clean.timeoutMs;
      const response=await fetch(path,{cache:'no-store',signal:controller.signal,...clean});
      const body=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(body.error||body.message||`GEO Growth OS 返回 ${response.status}`);
      return body;
    }catch(error){
      if(controller.signal.aborted||error?.name==='AbortError'||String(error?.message||'').includes('aborted')){
        throw new Error(`GEO 自动增长数据等待超时（${Math.round(timeoutMs/1000)}秒）；主界面已保留，后台继续重试。`);
      }
      throw error;
    }finally{clearTimeout(timer)}
  }
  const post = (path, body={}) => json(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});

  function installStyle(){
    if(byId('geo-growth-os-style')) return;
    const style=document.createElement('style');
    style.id='geo-growth-os-style';
    style.textContent=`
      .geo-os{margin:0 0 18px;border:1px solid #cfdced;border-radius:14px;background:#fff;box-shadow:0 8px 28px rgba(35,67,114,.07);overflow:hidden}
      .geo-os-head{display:flex;justify-content:space-between;gap:22px;align-items:flex-start;padding:17px 18px 15px;border-bottom:1px solid #e6edf6;background:linear-gradient(135deg,#f7faff 0%,#fff 70%)}
      .geo-os-head p{margin:0 0 5px;color:#496ea7;font-size:10px;font-weight:850;letter-spacing:.11em}.geo-os-head h2{margin:0;font-size:20px;line-height:1.25;color:#17243b}.geo-os-head small{display:block;margin-top:6px;color:#63748b;line-height:1.55;max-width:980px}
      .geo-os-state{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:6px;background:#eef6ff;color:#1f5fbf;font-size:11px;font-weight:800;white-space:nowrap;flex:0 0 auto}.geo-os-state.run{background:#e9f8ef;color:#19733d}.geo-os-state.pause{background:#fff4df;color:#986000}.geo-os-state.bad{background:#fff0f0;color:#ad2c2c}
      .geo-os-body{padding:14px 16px 16px}
      .geo-os-toolbar{display:grid;grid-template-columns:minmax(500px,auto) minmax(300px,1fr);gap:12px;align-items:stretch}
      .geo-os-actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;min-width:0;padding:8px 0}
      .geo-os-actions button{min-height:36px;min-width:88px;border:1px solid #c8d6e9;border-radius:7px;background:#fff;color:#294d7d;padding:8px 12px;font-size:11px;font-weight:760;cursor:pointer;white-space:nowrap;line-height:1.2;box-sizing:border-box}.geo-os-actions button.primary{background:#2563dc;border-color:#2563dc;color:#fff}.geo-os-actions button.is-running{background:#e8f7ee;border-color:#b9e2c7;color:#1f7040}.geo-os-actions button:disabled{opacity:.55;cursor:not-allowed}.geo-os-actions button[hidden]{display:none!important}
      .geo-os-runtime-card{min-width:0;border:1px solid #e0e7f1;border-radius:9px;background:#fafcff;padding:9px 11px;display:grid;grid-template-columns:auto 1fr;column-gap:10px;row-gap:2px;align-content:center}.geo-os-runtime-card>span{grid-row:1/3;color:#75839a;font-size:9px;font-weight:700;white-space:nowrap}.geo-os-runtime-card>strong{min-width:0;color:#314865;font-size:10px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.geo-os-runtime-card>small{min-width:0;color:#7c8ca0;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.geo-os-runtime-card small.ok{color:#237345}.geo-os-runtime-card small.wait{color:#946100}.geo-os-runtime-card small.bad{color:#b12e2e}
      .geo-os-policy{margin-top:11px;display:grid;grid-template-columns:minmax(0,1.45fr) minmax(280px,.8fr);gap:9px}.geo-os-policy article{border:1px solid #e1e8f2;border-radius:9px;padding:10px 11px;background:#fbfcfe;min-width:0}.geo-os-policy span{display:block;color:#738196;font-size:10px}.geo-os-policy b{display:block;margin-top:3px;font-size:12px;color:#253a5a;line-height:1.45}.geo-os-policy small{display:block;margin-top:4px;color:#75849a;line-height:1.45}
      .geo-os-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px;margin-top:11px}.geo-os-kpis .geo-os-kpi{appearance:none;text-align:left;border:1px solid #e0e7f1;border-radius:9px;padding:9px 10px;min-width:0;background:#fff;cursor:pointer;transition:border-color .15s,box-shadow .15s,transform .15s}.geo-os-kpis .geo-os-kpi:hover{border-color:#a8c6f4;box-shadow:0 3px 10px rgba(37,99,220,.08);transform:translateY(-1px)}.geo-os-kpis .geo-os-kpi.active{border-color:#77a8f2;background:#f3f8ff}.geo-os-kpis span{display:block;color:#75839a;font-size:9px}.geo-os-kpis strong{display:block;margin-top:3px;font-size:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#17243b}.geo-os-kpis small{display:block;margin-top:2px;color:#8a96a7;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .geo-os-pipeline{display:grid;grid-template-columns:repeat(auto-fit,minmax(126px,1fr));gap:7px;margin-top:12px}.geo-os-step{appearance:none;text-align:left;position:relative;border:1px solid #e1e7f0;border-radius:9px;padding:9px;background:#fafbfd;min-width:0;cursor:pointer}.geo-os-step.active{border-color:#b9d2f8;background:#f3f8ff}.geo-os-step b{display:block;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.geo-os-step span{display:block;margin-top:4px;font-size:16px}.geo-os-step small{display:block;margin-top:2px;color:#8794a7;font-size:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .geo-os-grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(250px,.72fr);gap:10px;margin-top:12px}.geo-os-box{border:1px solid #e1e7f0;border-radius:9px;overflow:hidden;min-width:0}.geo-os-box-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 11px;background:#fafbfd;border-bottom:1px solid #e8edf4}.geo-os-box-head b{font-size:11px}.geo-os-box-head span{font-size:9px;color:#79889d;white-space:nowrap}.geo-os-table-wrap{overflow:auto;max-height:360px}.geo-os-table{width:100%;border-collapse:collapse;font-size:10px;table-layout:fixed;min-width:780px}.geo-os-table col.c1{width:25%}.geo-os-table col.c2{width:7%}.geo-os-table col.c3{width:25%}.geo-os-table col.c4{width:16%}.geo-os-table col.c5{width:13%}.geo-os-table col.c6{width:14%}.geo-os-table th,.geo-os-table td{padding:8px 9px;border-bottom:1px solid #edf1f6;text-align:left;vertical-align:top;overflow-wrap:anywhere}.geo-os-table th{position:sticky;top:0;background:#fff;color:#66768d;font-weight:700;z-index:1}.geo-os-table td>b{line-height:1.4}.geo-os-table small{display:block;margin-top:2px;color:#8592a4;line-height:1.4}.geo-os-score{display:inline-flex;min-width:26px;justify-content:center;padding:3px 5px;border-radius:4px;background:#eef4ff;color:#245fc1;font-weight:800}.geo-os-pill{display:inline-block;max-width:100%;padding:3px 6px;border-radius:4px;background:#f1f4f8;color:#53647c;font-weight:700;white-space:normal;cursor:default}.geo-os-mini-action,.geo-os-blocker-retry{margin-top:5px;border:1px solid #bfd0e7;border-radius:5px;background:#fff;color:#255da8;padding:4px 7px;font-size:9px;font-weight:750;cursor:pointer}.geo-os-mini-action:hover,.geo-os-blocker-retry:hover{border-color:#75a5e9;background:#f4f8ff}.geo-os-pill.ok{background:#eaf8ef;color:#237345}.geo-os-pill.wait{background:#fff5e5;color:#946100}.geo-os-pill.bad{background:#ffeded;color:#b12e2e}
      .geo-os-blockers{padding:8px 10px;max-height:360px;overflow:auto}.geo-os-blocker{padding:9px 0;border-bottom:1px solid #edf1f6}.geo-os-blocker:last-child{border-bottom:0}.geo-os-blocker b{display:block;font-size:10px;color:#a14c18}.geo-os-blocker span{display:block;margin-top:3px;font-size:9px;color:#758398;line-height:1.5}.geo-os-ok{padding:18px 8px;color:#39805a;font-size:10px;text-align:center}
      .geo-os-message{margin-top:9px;min-height:16px;font-size:10px;color:#5e6e84}.geo-os-truth{margin-top:8px;padding:8px 10px;border-radius:6px;background:#f7f9fc;color:#65758b;font-size:9px;line-height:1.5}
      #geo-growth-advanced{margin-top:14px;border:1px solid #dce4ef;border-radius:9px;background:#fff;overflow:hidden}#geo-growth-advanced>summary{cursor:pointer;list-style:none;padding:11px 13px;background:#f9fbfd;color:#52657f;font-size:11px;font-weight:800}#geo-growth-advanced>summary::-webkit-details-marker{display:none}#geo-growth-advanced>summary:after{content:'展开';float:right;color:#7c8aa0;font-size:9px}#geo-growth-advanced[open]>summary:after{content:'收起'}#geo-growth-advanced-body{padding:0 12px 12px}
      .geo-adv-inline{padding:12px 0 2px}.geo-adv-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:12px 14px;border:1px solid #dfe7f2;border-radius:8px;background:#f8fbff}.geo-adv-head h3{margin:0 0 4px;font-size:14px;color:#18345c}.geo-adv-head p{margin:0;color:#718096;font-size:10px;line-height:1.5}.geo-adv-state{padding:5px 8px;border-radius:5px;background:#eef4ff;color:#255dae;font-size:9px;font-weight:800;white-space:nowrap}.geo-adv-state.ok{background:#e9f8ef;color:#237345}.geo-adv-state.bad{background:#ffeded;color:#b12e2e}
      .geo-adv-toolbar{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0}.geo-adv-toolbar button,.geo-adv-form button{border:1px solid #bfd0e7;border-radius:6px;background:#fff;color:#285da8;padding:7px 10px;font-size:10px;font-weight:750;cursor:pointer}.geo-adv-toolbar button.primary,.geo-adv-form button.primary{background:#2563dc;border-color:#2563dc;color:#fff}.geo-adv-toolbar button:disabled,.geo-adv-form button:disabled{opacity:.55;cursor:not-allowed}
      .geo-adv-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:10px 0}.geo-adv-kpis article{border:1px solid #e2e9f2;border-radius:7px;background:#fff;padding:9px}.geo-adv-kpis span{display:block;color:#7b899d;font-size:9px}.geo-adv-kpis b{display:block;margin-top:3px;color:#203754;font-size:16px}.geo-adv-kpis small{display:block;margin-top:2px;color:#94a0af;font-size:8px}
      .geo-adv-grid{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr);gap:10px}.geo-adv-card{border:1px solid #e1e8f1;border-radius:8px;background:#fff;padding:11px}.geo-adv-card h4{margin:0 0 9px;color:#263b57;font-size:11px}.geo-adv-form{display:grid;grid-template-columns:1fr 1fr;gap:8px}.geo-adv-form label{display:grid;gap:4px;color:#6d7c90;font-size:9px}.geo-adv-form label.wide{grid-column:1/-1}.geo-adv-form input,.geo-adv-form select,.geo-adv-form textarea{width:100%;box-sizing:border-box;border:1px solid #ccd8e7;border-radius:6px;background:#fff;padding:7px 8px;color:#24384f;font:inherit}.geo-adv-form textarea{min-height:72px;resize:vertical}.geo-adv-form .actions{grid-column:1/-1;display:flex;gap:8px;align-items:center}.geo-adv-form .actions span{color:#7f8da0;font-size:9px}
      .geo-adv-table-wrap{max-height:360px;overflow:auto;border:1px solid #edf1f6;border-radius:6px}.geo-adv-table{width:100%;border-collapse:collapse;font-size:9px}.geo-adv-table th,.geo-adv-table td{padding:7px 8px;border-bottom:1px solid #edf1f6;text-align:left;vertical-align:top}.geo-adv-table th{position:sticky;top:0;background:#fafcff;color:#64748b}.geo-adv-pill{display:inline-block;padding:3px 5px;border-radius:4px;background:#eef4ff;color:#2c5fa8;font-weight:750}.geo-adv-pill.ok{background:#e9f8ef;color:#237345}.geo-adv-receipts{display:grid;gap:7px;max-height:360px;overflow:auto}.geo-adv-receipt{border:1px solid #edf1f6;border-radius:6px;padding:8px}.geo-adv-receipt b{display:block;color:#2a3f5d;font-size:10px}.geo-adv-receipt small{display:block;margin-top:3px;color:#8794a6;font-size:8px}.geo-adv-health{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.geo-adv-health span{padding:4px 6px;border-radius:4px;background:#f1f5f9;color:#607086;font-size:8px}.geo-adv-health span.ok{background:#e9f8ef;color:#237345}.geo-adv-message{margin-top:8px;min-height:16px;color:#65758b;font-size:9px}
      @media(max-width:980px){.geo-adv-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.geo-adv-grid{grid-template-columns:1fr}.geo-adv-form{grid-template-columns:1fr}}
      @media(max-width:1180px){.geo-os-toolbar{grid-template-columns:1fr}.geo-os-runtime-card{grid-template-columns:auto 1fr}.geo-os-grid{grid-template-columns:1fr}.geo-os-policy{grid-template-columns:1fr}}
      @media(max-width:760px){.geo-os-head{display:block}.geo-os-state{margin-top:8px}.geo-os-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.geo-os-actions button{width:100%;min-width:0}.geo-os-runtime-card{grid-template-columns:1fr}.geo-os-runtime-card>span{grid-row:auto}.geo-os-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.geo-os-pipeline{grid-template-columns:repeat(2,minmax(0,1fr))}}
    `;
    document.head.appendChild(style);
  }

  function panelMarkup(){
    return `<section id="geo-growth-os" class="geo-os">
      <header class="geo-os-head">
        <div><p>GEO GROWTH OS · R8-24</p><h2>GEO 自动增长工作台</h2><small>总控策略负责方向；豆包 API、本地模型、RTX 3060 与平台现有能力负责执行。发现缺口后自动建机会、派 AI 员工、推进真实发布、复测和 Before / After。</small></div>
        <span id="geo-os-state" class="geo-os-state">读取中</span>
      </header>
      <div class="geo-os-body">
        <div class="geo-os-toolbar">
          <div class="geo-os-actions">
            <button id="geo-os-start" class="primary" type="button">启动 GEO 自动运营</button>
            <button id="geo-os-pause" type="button">暂停</button>
            <button id="geo-os-resume" type="button">恢复</button>
            <button id="geo-os-run" type="button">立即运行一轮</button>
            <button id="geo-os-retry" type="button">重试异常</button>
          </div>
          <div class="geo-os-runtime-card"><span>运行摘要</span><strong id="geo-os-runtime">正在读取执行状态…</strong><small id="geo-os-publish">发布通道正在检查…</small></div>
        </div>
        <div class="geo-os-policy">
          <article><span>当前 Mission</span><b id="geo-os-mission">正在读取…</b><small>正常 GEO / SEO / 内容优化默认全权自治，无人工审核步骤；技术阻塞只影响对应子任务。</small></article>
          <article><span>成本与资源策略</span><b>OpenAI API：禁用 · 新增付费依赖：0</b><small id="geo-os-resources">执行资源：豆包 API / 本地模型 / RTX 3060 / 平台现有功能</small></article>
        </div>
        <div id="geo-os-kpis" class="geo-os-kpis"></div>
        <div id="geo-os-pipeline" class="geo-os-pipeline"></div>
        <div class="geo-os-grid">
          <section class="geo-os-box"><div class="geo-os-box-head"><b>GEO 机会池与自动执行</b><span>Opportunity Score 优先</span></div><div class="geo-os-table-wrap"><table class="geo-os-table"><colgroup><col class="c1"><col class="c2"><col class="c3"><col class="c4"><col class="c5"><col class="c6"></colgroup><thead><tr><th>机会 / 问题</th><th>评分</th><th>总控决策</th><th>AI员工</th><th>发布</th><th>复测 / 结果</th></tr></thead><tbody id="geo-os-rows"><tr><td colspan="6">等待运营 Signal。</td></tr></tbody></table></div></section>
          <section class="geo-os-box"><div class="geo-os-box-head"><b>技术阻塞</b><span id="geo-os-blocker-count">不阻塞主工作流</span></div><div id="geo-os-blockers" class="geo-os-blockers"><div class="geo-os-ok">正在检查。</div></div></section>
        </div>
        <div id="geo-os-message" class="geo-os-message"></div>
        <div class="geo-os-truth"><b>真值与运营分离：</b>豆包普通 API 结果固定为 C 级运营 Signal，可以驱动低风险优化、发布与运营复测；正式 GEO 成绩仍只统计真实外部 AI 的 A/B Evidence。C级结果、内容生成、发布动作都不会被冒充成正式 A/B 提升。</div>
      </div>
    </section>`;
  }

  function ensureStructure(){
    installStyle();
    const pane=byId('geo-growth-pane');
    if(!pane) return false;
    let panel=byId('geo-growth-os');
    if(!panel){
      const holder=document.createElement('div');
      holder.innerHTML=panelMarkup();
      panel=holder.firstElementChild;
      pane.insertBefore(panel,pane.firstChild);
      bind();
    }
    let advanced=byId('geo-growth-advanced');
    if(!advanced){
      advanced=document.createElement('details');
      advanced.id='geo-growth-advanced';
      advanced.innerHTML='<summary>高级证据 / 网页验证 / 开发验收工具</summary><div id="geo-growth-advanced-body"></div>';
      pane.insertBefore(advanced,panel.nextSibling);
    }
    const body=byId('geo-growth-advanced-body');
    // #727: the owner page no longer embeds geo.html for advanced tools.
    // Any legacy loading shell/iframe is removed; the native toolbox below is
    // mounted directly in this document and therefore cannot be blanked by an
    // iframe navigation race.
    [...pane.children].forEach(child=>{ if(child!==panel && child!==advanced) child.remove(); });
    if(advanced.dataset.kzInlineBound!=='1'){
      advanced.dataset.kzInlineBound='1';
      advanced.addEventListener('toggle',()=>{ if(advanced.open)mountAdvanced(); });
    }
    if(advanced.open)mountAdvanced();
    return true;
  }

  function stateLabel(value){ return ({running:'自动运营中',paused:'已暂停',stopped:'未启动'}[value]||value||'未知'); }
  function itemState(value){ return ({
    opportunity_created:'机会已建立',ai_employee_queued:'AI员工排队',ai_employee_running:'AI员工执行中',content_ready:'内容已完成',waiting_publish:'等待真实发布',waiting_retest:'等待复测',retest_queued:'复测已排队',completed:'闭环完成',failed:'执行失败',deferred:'子任务延后'
  }[value]||value||'等待'); }
  function stateClass(value){ return value==='completed'?'ok':value==='failed'?'bad':value==='waiting_publish'||value==='waiting_retest'||value==='retest_queued'||value==='deferred'?'wait':''; }

  function render(data){
    cache=data||{};
    if(!ensureStructure()) return;
    const state=data.state||'stopped';
    const summary=data.summary||{};
    const cloud=data.cloud||{};
    const policy=data.policy||{};
    const publish=data.publish_connector||{};
    const blockers=data.technical_blockers||[];

    const badge=byId('geo-os-state');
    badge.textContent=stateLabel(state);
    badge.className=`geo-os-state ${state==='running'?'run':state==='paused'?'pause':'bad'}`;
    byId('geo-os-mission').textContent=data.mission||'等待 Mission';
    byId('geo-os-resources').textContent=`执行资源：${(policy.execution_resources||['doubao_api','local_model','rtx3060','platform_capabilities']).join(' / ')} · 正常推广无需人工审核`;
    byId('geo-os-runtime').textContent=`豆包扫描 ${Number(cloud.completed||0)} / ${Number(cloud.target||0)} · ${cloud.ready?'API已就绪':'API待检查'} · 上次运行 ${data.last_run_at||'—'}`;
    const publishLine=byId('geo-os-publish');
    if(publishLine){
      const ready=Boolean(publish.ready);
      publishLine.textContent=`发布通道：${ready?'已就绪':(publish.reason||'等待检查')} · 待发布 ${Number(summary.waiting_publish||0)}`;
      publishLine.className=ready?'ok':Number(summary.waiting_publish||0)>0?'bad':'wait';
    }

    const kpis=[
      ['运营 Signal',summary.signals||0,'豆包 C级辅助','signal'],
      ['机会池',summary.total||0,'自动识别缺口','all'],
      ['正在优化',summary.optimizing||0,'AI员工执行','optimizing'],
      ['等待发布',summary.waiting_publish||0,'等待真实公网回执','waiting_publish'],
      ['等待复测',summary.published_or_waiting_retest||0,'发布后自动复测','retest'],
      ['闭环完成',summary.completed||0,'Before / After','completed'],
      ['正式 A/B',`${Number(data.formal_ab_completed||0)} / ${Number(data.formal_ab_target||50)}`,'独立正式真值','formal_ab'],
    ];
    byId('geo-os-kpis').innerHTML=kpis.map(x=>`<button type="button" class="geo-os-kpi ${activeFilter===x[3]?'active':''}" data-geo-filter="${esc(x[3])}"><span>${esc(x[0])}</span><strong>${esc(x[1])}</strong><small>${esc(x[2])}</small></button>`).join('');

    const pipelineFilters={signal:'signal',opportunity:'all',decision:'all',execute:'optimizing',publish:'waiting_publish',retest:'retest',learn:'completed'};
    byId('geo-os-pipeline').innerHTML=(data.pipeline||[]).map(step=>`<button type="button" data-geo-filter="${pipelineFilters[step.id]||'all'}" class="geo-os-step ${step.state==='active'?'active':''}"><b>${esc(step.label)}</b><span>${Number(step.count||0)}</span><small>${step.state==='active'?'正在形成闭环':'等待上游结果'}</small></button>`).join('');
    const rows=data.opportunities||[];
    byId('geo-os-rows').innerHTML=rows.length?rows.map(item=>{
      const delta=item.operating_delta==null?'—':`${Number(item.operating_delta)>=0?'+':''}${Number(item.operating_delta)}`;
      const result=item.state==='completed'?`${item.outcome||'完成'} · Δ ${delta}`:(item.retest_task_id?'复测排队':item.public_url?'等待复测':'等待');
      return `<tr data-geo-row-state="${esc(item.state||'')}" data-geo-row-stage="${esc(item.asset_stage||'')}">
        <td><b>${esc(item.gap_label||item.service||'GEO机会')}</b><small>${esc(item.question_text||item.question_id||'')}</small></td>
        <td><span class="geo-os-score">${Number(item.opportunity_score||0)}</span><small>${esc(item.priority||'')}</small></td>
        <td>${esc(item.decision||'自动判断')}<small>${esc(item.keyword||'')}</small></td>
        <td><span class="geo-os-pill ${item.job_state==='completed'?'ok':item.job_state==='failed'?'bad':'wait'}">${esc(itemState(item.state))}</span><small>${esc(item.job_id||'待派发')}</small></td>
        <td><span class="geo-os-pill ${item.public_url?'ok':item.asset_stage==='QC_PASSED'?'wait':''}">${esc(item.asset_stage||'等待')}</span><small>${item.public_url?esc(item.public_url):'必须有真实公网回执'}</small>${(item.state==='waiting_publish'||item.state==='deferred')?'<button type="button" class="geo-os-mini-action" data-geo-advance="1">立即推进</button>':''}</td>
        <td><span class="geo-os-pill ${stateClass(item.state)}">${esc(result)}</span><small>${item.operating_before_score==null?'C级运营复测，不改变正式A/B':`Before ${item.operating_before_score} → After ${item.operating_after_score}`}</small></td>
      </tr>`;
    }).join(''):'<tr><td colspan="6" style="padding:18px;text-align:center;color:#8290a3">当前还没有可执行 GEO 缺口。新的豆包 C级 Signal 到达后会自动判断并创建机会。</td></tr>';

    byId('geo-os-blocker-count').textContent=blockers.length?`${blockers.length} 项 · 仅影响子任务`:'当前无阻塞';
    byId('geo-os-blockers').innerHTML=blockers.length?blockers.map(row=>`<div class="geo-os-blocker"><b>${esc(row.code||'技术阻塞')}</b><span>${esc(row.detail||'')}<br>${esc(row.item_id||'')} · 仅影响该子任务，主工作流继续</span><button type="button" class="geo-os-blocker-retry" data-geo-retry-blocker="1">重试异常</button></div>`).join(''):'<div class="geo-os-ok">当前没有技术阻塞，主工作流可继续。</div>';
    byId('geo-os-message').textContent=data.last_error?`最近异常：${data.last_error}`:`主链：Signal → Opportunity → 总控判断 → AI员工 → 发布 → 复测 → Before/After。正式 A/B 作为旁路证据，不阻塞运营主链。`;

    const start=byId('geo-os-start');
    const pause=byId('geo-os-pause');
    const resume=byId('geo-os-resume');
    const run=byId('geo-os-run');
    const retry=byId('geo-os-retry');
    if(start){
      start.disabled=busy||state==='running';
      start.textContent=state==='running'?'自动运营已启动':'启动 GEO 自动运营';
      start.classList.toggle('is-running',state==='running');
    }
    if(pause){ pause.hidden=state==='paused'; pause.disabled=busy||state!=='running'; }
    if(resume){ resume.hidden=state!=='paused'; resume.disabled=busy||state!=='paused'; }
    if(run) run.disabled=busy||state!=='running';
    if(retry) retry.disabled=busy||(Number(summary.failed||0)+Number(summary.technical_blockers||0)===0);
    wireDashboardControls();
    applyFilter(activeFilter,false);
  }

  function applyFilter(filter,announce=true){
    activeFilter=filter||'all';
    document.querySelectorAll('[data-geo-filter]').forEach(button=>button.classList.toggle('active',button.dataset.geoFilter===activeFilter));
    if(activeFilter==='signal'||activeFilter==='formal_ab'){
      const advanced=byId('geo-growth-advanced');
      if(advanced){
        advanced.open=true;
        if(announce) advanced.scrollIntoView({behavior:'smooth',block:'start'});
      }
      if(announce&&byId('geo-os-message')) byId('geo-os-message').textContent=activeFilter==='formal_ab'?'已展开正式 A/B Evidence / 网页验证工具。':'已展开 C级 Signal / 高级证据工具。';
      return;
    }
    document.querySelectorAll('#geo-os-rows tr[data-geo-row-state]').forEach(row=>{
      const state=row.dataset.geoRowState||'';
      const stage=row.dataset.geoRowStage||'';
      let visible=true;
      if(activeFilter==='optimizing') visible=['opportunity_created','ai_employee_queued','ai_employee_running','content_ready'].includes(state);
      else if(activeFilter==='waiting_publish') visible=state==='waiting_publish'||stage==='QC_PASSED';
      else if(activeFilter==='retest') visible=['waiting_retest','retest_queued'].includes(state);
      else if(activeFilter==='completed') visible=state==='completed';
      row.hidden=!visible;
    });
  }

  function wireDashboardControls(){
    document.querySelectorAll('[data-geo-filter]').forEach(button=>{
      if(button.dataset.geoBound==='1')return;
      button.dataset.geoBound='1';
      button.addEventListener('click',()=>applyFilter(button.dataset.geoFilter||'all'));
    });
    document.querySelectorAll('[data-geo-advance]').forEach(button=>{
      if(button.dataset.geoBound==='1')return;
      button.dataset.geoBound='1';
      button.addEventListener('click',()=>mutate(button,'/api/r8-24/geo-growth/run',{force:true}));
    });
    document.querySelectorAll('[data-geo-retry-blocker]').forEach(button=>{
      if(button.dataset.geoBound==='1')return;
      button.dataset.geoBound='1';
      button.addEventListener('click',()=>mutate(button,'/api/r8-24/geo-growth/retry'));
    });
  }

  async function load(){
    if(!ensureStructure()) return null;
    try{
      const data=await json('/api/r8-24/geo-growth/fast',{timeoutMs:4000});
      render(data);
      return data;
    }catch(error){
      if(byId('geo-os-message')) byId('geo-os-message').textContent=`GEO 状态快照暂未返回：${error.message}；界面继续保留并自动重试。`;
      return null;
    }
  }

  async function mutate(button,path,body={}){
    if(busy) return;
    busy=true;
    render(cache||{});
    const old=button?.textContent||'';
    if(button){ button.disabled=true; button.textContent='处理中…'; button.setAttribute('aria-busy','true'); }
    try{
      const data=await post(path,body);
      render(data.growth||await json('/api/r8-24/geo-growth/fast',{timeoutMs:4000}));
    }catch(error){
      if(byId('geo-os-message')) byId('geo-os-message').textContent=error.message;
    }finally{
      busy=false;
      if(button){ button.textContent=old; button.removeAttribute('aria-busy'); }
      await load();
    }
  }

  function advancedMarkup(){
    return `<section id="geo-advanced-inline" class="geo-adv-inline">
      <div class="geo-adv-head"><div><h3>高级证据 / 网页验证 / 开发验收工具</h3><p>直接读取正式 A/B Evidence、固定 50 问、执行队列和 Receipt；不再通过嵌套 iframe 加载。</p></div><span id="geo-adv-state" class="geo-adv-state">准备中</span></div>
      <div class="geo-adv-toolbar">
        <button id="geo-adv-refresh" type="button">刷新证据</button>
        <button id="geo-adv-bootstrap" type="button">核验固定50问</button>
        <button id="geo-adv-one" class="primary" type="button">准备网页验证1题</button>
        <button id="geo-adv-ten" type="button">准备10题</button>
      </div>
      <div id="geo-adv-kpis" class="geo-adv-kpis"></div>
      <div class="geo-adv-grid">
        <article class="geo-adv-card">
          <h4>真实外部 AI 网页 → Evidence / Receipt</h4>
          <div class="geo-adv-form">
            <label>外部AI平台<select id="geo-adv-platform"><option value="chatgpt_web">ChatGPT 网页版</option><option value="gemini_web">Gemini 网页版</option><option value="copilot_web">Copilot 网页版</option><option value="qwen_web">通义千问网页版</option><option value="deepseek_web">DeepSeek 网页版</option><option value="doubao_web">豆包网页版</option><option value="custom_web">其他真实外部AI网页</option></select></label>
            <label>Task ID<input id="geo-adv-task" readonly placeholder="先准备网页验证任务"></label>
            <label class="wide">固定问题<textarea id="geo-adv-question" readonly placeholder="系统自动填入固定50问中的题目"></textarea></label>
            <label class="wide">真实外部页面 URL<input id="geo-adv-url" type="url" placeholder="https://真实外部AI会话地址"></label>
            <label class="wide">引用 URL（每行一个）<textarea id="geo-adv-citations" placeholder="https://example.com/source"></textarea></label>
            <label class="wide">外部 AI 完整原始回答<textarea id="geo-adv-answer" placeholder="粘贴真实外部AI完整回答"></textarea></label>
            <div class="actions"><button id="geo-adv-submit" class="primary" type="button">保存真实 Evidence / Receipt</button><span>只保存真实外部结果；不会把豆包普通 API 或本地模型冒充正式 A/B。</span></div>
          </div>
          <div id="geo-adv-message" class="geo-adv-message"></div>
        </article>
        <article class="geo-adv-card">
          <h4>最近 Evidence / Receipt</h4>
          <div id="geo-adv-receipts" class="geo-adv-receipts"><div>正在读取…</div></div>
          <div id="geo-adv-health" class="geo-adv-health"></div>
        </article>
      </div>
      <article class="geo-adv-card" style="margin-top:10px">
        <h4>固定 50 问与执行状态</h4>
        <div class="geo-adv-table-wrap"><table class="geo-adv-table"><thead><tr><th>ID</th><th>问题</th><th>类型</th><th>状态</th><th>证据</th></tr></thead><tbody id="geo-adv-questions"><tr><td colspan="5">正在读取…</td></tr></tbody></table></div>
      </article>
    </section>`;
  }

  function setAdvancedMessage(message,bad=false){
    const node=byId('geo-adv-message');
    if(node){node.textContent=message||'';node.style.color=bad?'#ad2c2c':'#65758b';}
  }

  function bindAdvanced(){
    const root=byId('geo-advanced-inline');
    if(!root||root.dataset.bound==='1')return;
    root.dataset.bound='1';
    byId('geo-adv-refresh')?.addEventListener('click',()=>loadAdvanced(true));
    byId('geo-adv-bootstrap')?.addEventListener('click',async e=>{
      e.currentTarget.disabled=true;
      try{await post('/api/r8-24/geo-growth/evidence/bootstrap',{});setAdvancedMessage('固定50问基准已核验。');await loadAdvanced(true)}
      catch(error){setAdvancedMessage(error.message,true)}
      finally{e.currentTarget.disabled=false}
    });
    byId('geo-adv-one')?.addEventListener('click',e=>prepareAdvancedBrowser(1,e.currentTarget));
    byId('geo-adv-ten')?.addEventListener('click',e=>prepareAdvancedBrowser(10,e.currentTarget));
    byId('geo-adv-submit')?.addEventListener('click',e=>submitAdvancedReceipt(e.currentTarget));
  }

  function mountAdvanced(){
    const body=byId('geo-growth-advanced-body');
    if(!body)return false;
    let root=byId('geo-advanced-inline');
    if(!root){
      body.innerHTML=advancedMarkup();
      root=byId('geo-advanced-inline');
    }
    bindAdvanced();
    if(!advancedLastGood || Date.now()-advancedFetchedAt>45000)loadAdvanced(false);
    return true;
  }

  async function loadAdvanced(force=false){
    if(advancedBusy)return;
    if(!force&&advancedLastGood&&Date.now()-advancedFetchedAt<45000)return;
    advancedBusy=true;
    if(advancedRetryTimer){clearTimeout(advancedRetryTimer);advancedRetryTimer=null;}
    const state=byId('geo-adv-state');
    if(state&&!advancedLastGood){state.textContent='正在准备证据快照';state.className='geo-adv-state'}
    try{
      const snapshot=await json('/api/r8-24/geo-growth/evidence',{timeoutMs:8000});
      if(snapshot.snapshot_ready===false){
        advancedRetryCount+=1;
        const problem=String(snapshot.last_refresh_error||'');
        if(state){state.textContent=advancedRetryCount>8?'读取延迟 · 可重试':'正在读取真实证据';state.className='geo-adv-state';}
        setAdvancedMessage(problem?'后台证据快照生成未完成：'+problem:'首次读取证据中，主 GEO 运营继续运行。',advancedRetryCount>8);
        if(advancedRetryCount<=8)advancedRetryTimer=setTimeout(()=>loadAdvanced(true),Number(snapshot.retry_after_ms||1400));
        return;
      }
      advancedRetryCount=0;
      advancedLastGood=snapshot;
      advancedFetchedAt=Date.now();
      const dashboard=snapshot.dashboard||{};
      const questions=snapshot.questions||[];
      const queue=snapshot.queue||[];
      const receipts=snapshot.receipts||[];
      const official=dashboard.official||{};
      const qset=snapshot.question_set||dashboard.question_set||{};
      const qsum=snapshot.queue_summary||dashboard.queue||{};
      const health=snapshot.health||{};
      const available=Number(snapshot.available_sections||0);
      const total=Number(snapshot.total_sections||4);
      const officialReceipts=receipts.filter(x=>x.official_truth);
      const formalCompleted=Math.max(Number(snapshot.formal_ab_completed||0),Number(official.tested||0));
      const formalTarget=Number(snapshot.formal_ab_target||qset.total||50);
      const kpis=[
        ['正式 A/B',`${formalCompleted} / ${formalTarget}`,'唯一正式GEO成绩'],
        ['Evidence',Number(official.evidence_count||officialReceipts.length),'可追溯正式证据'],
        ['排队',Number(qsum.queued||0),'等待执行'],
        ['执行中',Number(qsum.running||0),'真实验证任务'],
        ['待授权',Number(qsum.authorization_required||0),'仅真实阻塞'],
      ];
      const kpiBox=byId('geo-adv-kpis');
      if(kpiBox)kpiBox.innerHTML=kpis.map(x=>`<article><span>${esc(x[0])}</span><b>${esc(x[1])}</b><small>${esc(x[2])}</small></article>`).join('');

      const taskByQ={};
      queue.forEach(task=>{taskByQ[task.question_id]=task});
      const rows=questions.slice(0,50);
      const qbox=byId('geo-adv-questions');
      if(qbox)qbox.innerHTML=rows.length?rows.map(item=>{
        const task=taskByQ[item.question_id]||{};
        const status=task.state||item.state||'unstarted';
        const evidence=task.evidence_id||item.evidence||'—';
        return `<tr><td>${esc(item.question_id||'')}</td><td>${esc(item.question_text||'')}</td><td>${esc(item.question_type||'')}</td><td><span class="geo-adv-pill ${status==='succeeded'?'ok':''}">${esc(status)}</span></td><td>${esc(evidence)}</td></tr>`;
      }).join(''):'<tr><td colspan="5">固定问题库暂未返回。</td></tr>';

      const receiptBox=byId('geo-adv-receipts');
      if(receiptBox)receiptBox.innerHTML=receipts.slice(0,10).length?receipts.slice(0,10).map(item=>`<div class="geo-adv-receipt"><b>${esc(item.question_text||item.question_id||'GEO Evidence')}</b><small>${esc(item.provider||'--')} · ${esc(item.evidence_level||'C')}级 · ${esc(item.evidence_id||item.receipt_id||'--')}</small><small>${esc(item.tested_at||'')}</small></div>`).join(''):'<div class="geo-adv-receipt"><b>暂无正式 Receipt</b><small>真实外部验证完成后会自动出现在这里。</small></div>';

      const healthBox=byId('geo-adv-health');
      const labels={dashboard:'总览',questions:'50问',queue:'队列',receipts:'Receipt'};
      if(healthBox)healthBox.innerHTML=Object.keys(labels).map(key=>{
        const item=health[key]||{ok:false,error:'未返回'};
        return `<span class="${item.ok?'ok':''}" title="${esc(item.error||'')}">${labels[key]}：${item.ok?'正常':'重试中'}</span>`;
      }).join('');

      const running=[...queue].reverse().find(x=>x.state==='running'&&x.test_method==='browser');
      if(running&&!advancedTask){
        advancedTask=running;
        byId('geo-adv-task').value=running.task_id||'';
        byId('geo-adv-question').value=running.question_text||'';
      }
      if(state){
        state.textContent=snapshot.snapshot_stale?'历史快照 · 正在更新':available>=total?`数据正常 · ${available}/${total}`:`部分可用 · ${available}/${total}`;
        state.className=`geo-adv-state ${available>=total?'ok':''}`;
      }
      document.documentElement.dataset.kzGeoAdvancedInlineReady='1';
      document.documentElement.dataset.kzGeoAdvancedSections=String(available);
      if(available===0)setAdvancedMessage('高级证据数据暂未返回；主GEO自动运营不受影响，可点击刷新重试。',true);
      else if(available<total)setAdvancedMessage(`高级证据已有 ${available}/${total} 个数据区可用；其余后台重试中。`);
      else setAdvancedMessage('');
    }catch(error){
      if(state){state.textContent=advancedLastGood?'最新读取失败 · 显示上次成功数据':'读取失败 · 可重试';state.className='geo-adv-state bad'}
      const receiptBox=byId('geo-adv-receipts');
      if(receiptBox)receiptBox.innerHTML='<div class="geo-adv-receipt"><b>Evidence 暂未读取</b><small>主 GEO 自动运营继续工作；点击“刷新证据”即可重新读取。</small></div>';
      const qbox=byId('geo-adv-questions');
      if(qbox)qbox.innerHTML='<tr><td colspan="5">证据快照读取失败；主运营不受影响，可点击刷新证据。</td></tr>';
      setAdvancedMessage(error.message,true);
    }finally{advancedBusy=false}
  }

  async function prepareAdvancedBrowser(limit,button){
    button.disabled=true;
    const old=button.textContent;
    try{
      button.textContent='准备中…';
      await post('/api/r8-19/geo/bootstrap',{});
      const platform=byId('geo-adv-platform')?.value||'custom_web';
      const reply=await post('/api/r8-24/geo-growth/evidence/prepare',{limit,platform});
      const task=reply.result?.claim?.task||{};
      advancedTask=task;
      byId('geo-adv-task').value=task.task_id||'';
      byId('geo-adv-question').value=task.question_text||'';
      setAdvancedMessage(task.task_id?`已准备 ${limit} 题；当前 Task ${task.task_id}。`:'未取得可执行题目。',!task.task_id);
      await loadAdvanced(true);
    }catch(error){setAdvancedMessage(error.message,true)}
    finally{button.disabled=false;button.textContent=old}
  }

  async function submitAdvancedReceipt(button){
    button.disabled=true;
    const old=button.textContent;
    try{
      const taskId=String(byId('geo-adv-task')?.value||'').trim();
      const sessionUrl=String(byId('geo-adv-url')?.value||'').trim();
      const rawAnswer=String(byId('geo-adv-answer')?.value||'').trim();
      if(!taskId)throw new Error('请先准备网页验证任务。');
      if(!sessionUrl||!rawAnswer)throw new Error('请填写真实外部页面 URL 和完整原始回答。');
      const citationUrls=String(byId('geo-adv-citations')?.value||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
      button.textContent='保存中…';
      const reply=await post('/api/r8-24/geo-growth/evidence/receipt',{
        task_id:taskId,
        platform:byId('geo-adv-platform')?.value||'custom_web',
        session_url:sessionUrl,
        raw_answer:rawAnswer,
        citation_urls:citationUrls
      });
      ['geo-adv-task','geo-adv-question','geo-adv-url','geo-adv-citations','geo-adv-answer'].forEach(id=>{const node=byId(id);if(node)node.value=''});
      advancedTask=null;
      setAdvancedMessage(`已保存正式 ${reply.result?.evidence_level||'A'}级 Evidence：${reply.result?.evidence_id||''}`);
      await loadAdvanced(true);
    }catch(error){setAdvancedMessage(error.message,true)}
    finally{button.disabled=false;button.textContent=old}
  }

  window.KZGeoAdvancedInline={mount:mountAdvanced,refresh:()=>loadAdvanced(true)};

  function bind(){
    const panel=byId('geo-growth-os');
    if(!panel||panel.dataset.bound==='1')return;
    panel.dataset.bound='1';
    byId('geo-os-start')?.addEventListener('click',e=>mutate(e.currentTarget,'/api/r8-24/geo-growth/start'));
    byId('geo-os-pause')?.addEventListener('click',e=>mutate(e.currentTarget,'/api/r8-24/geo-growth/pause'));
    byId('geo-os-resume')?.addEventListener('click',e=>mutate(e.currentTarget,'/api/r8-24/geo-growth/resume'));
    byId('geo-os-run')?.addEventListener('click',e=>mutate(e.currentTarget,'/api/r8-24/geo-growth/run',{force:true}));
    byId('geo-os-retry')?.addEventListener('click',e=>mutate(e.currentTarget,'/api/r8-24/geo-growth/retry'));
  }

  function start(){
    try{
      if(!ensureStructure()){
        attempts+=1;
        if(attempts<40)setTimeout(start,250);
        return;
      }
      attempts=0;
      bind();
      // Paint the complete GEO shell before waiting for any API. A slow local
      // endpoint must never leave the owner staring at a blank 720px iframe.
      if(!cache)render({
        state:'stopped',
        summary:{},
        cloud:{},
        policy:{},
        publish_connector:{},
        technical_blockers:[],
        opportunities:[],
        pipeline:[],
        formal_ab_completed:0,
        formal_ab_target:50,
        mission:'正在恢复 GEO 运行状态…'
      });
      load();
      if(!pollTimer)pollTimer=setInterval(()=>{if(!busy)load();},10000);
    }catch(error){
      attempts+=1;
      console.warn('GEO Growth OS boot retry',error);
      if(attempts<40)setTimeout(start,Math.min(1500,250+attempts*50));
    }
  }

  window.__KZ_GEO_GROWTH_OS_BOOT__=start;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();