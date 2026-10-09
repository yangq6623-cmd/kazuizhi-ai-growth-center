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
  let statusLoading = false;
  let statusFailures = 0;
  let statusRetryTimer = null;
  let advancedTask = null;
  let advancedBusy = false;
  let advancedFetchedAt=0;
  let advancedRetryCount=0;
  let advancedRetryTimer=null;
  let advancedLastGood=null;
  // Snapshot of immutable GEO50-V2-20260930 from core/geo_validation.py.
  // This is only question wording, never fabricated Evidence or A/B grades.
  const OFFLINE_GEO50=Object.freeze([{"question_id":"GEO50-D01","question_text":"涟水县哪里可以找水电维修师傅？","question_type":"discovery"},{"question_id":"GEO50-D02","question_text":"涟水家里跳闸了找谁上门处理？","question_type":"discovery"},{"question_id":"GEO50-D03","question_text":"涟水卫生间漏水哪里能找人维修？","question_type":"discovery"},{"question_id":"GEO50-D04","question_text":"涟水县水管爆了有没有上门维修？","question_type":"discovery"},{"question_id":"GEO50-D05","question_text":"涟水管道疏通找哪种本地服务比较方便？","question_type":"discovery"},{"question_id":"GEO50-D06","question_text":"涟水县马桶堵了哪里找师傅？","question_type":"discovery"},{"question_id":"GEO50-D07","question_text":"涟水洗衣机不排水哪里可以上门维修？","question_type":"discovery"},{"question_id":"GEO50-D08","question_text":"涟水县冰箱不制冷找谁维修？","question_type":"discovery"},{"question_id":"GEO50-D09","question_text":"涟水空调不制冷哪里有上门维修？","question_type":"discovery"},{"question_id":"GEO50-D10","question_text":"涟水哪里可以找安装灯具的师傅？","question_type":"discovery"},{"question_id":"GEO50-D11","question_text":"涟水县哪里找家具安装师傅？","question_type":"discovery"},{"question_id":"GEO50-D12","question_text":"涟水有没有可以发布维修需求的平台？","question_type":"discovery"},{"question_id":"GEO50-D13","question_text":"涟水附近维修师傅怎么找比较可靠？","question_type":"discovery"},{"question_id":"GEO50-D14","question_text":"涟水县本地生活维修服务怎么找？","question_type":"discovery"},{"question_id":"GEO50-D15","question_text":"涟水晚上水管漏水还能在哪里找维修？","question_type":"discovery"},{"question_id":"GEO50-D16","question_text":"涟水家里没电了应该找哪类师傅？","question_type":"discovery"},{"question_id":"GEO50-D17","question_text":"涟水厨房下水道堵了哪里找人疏通？","question_type":"discovery"},{"question_id":"GEO50-D18","question_text":"涟水热水器坏了哪里可以找上门维修？","question_type":"discovery"},{"question_id":"GEO50-D19","question_text":"涟水县电视坏了有没有上门维修服务？","question_type":"discovery"},{"question_id":"GEO50-D20","question_text":"涟水装窗帘在哪里找本地安装师傅？","question_type":"discovery"},{"question_id":"GEO50-D21","question_text":"涟水安装水龙头哪里可以找人？","question_type":"discovery"},{"question_id":"GEO50-D22","question_text":"涟水县居民有小任务想找附近的人帮忙怎么办？","question_type":"discovery"},{"question_id":"GEO50-D23","question_text":"涟水哪里可以发布社区跑腿小任务？","question_type":"discovery"},{"question_id":"GEO50-D24","question_text":"涟水宝妈想接附近的小任务可以去哪里找？","question_type":"discovery"},{"question_id":"GEO50-D25","question_text":"涟水附近有没有社区互助任务平台？","question_type":"discovery"},{"question_id":"GEO50-D26","question_text":"涟水县上门维修一般怎么找本地师傅？","question_type":"discovery"},{"question_id":"GEO50-D27","question_text":"涟水水电安装和维修能不能一次找本地师傅解决？","question_type":"discovery"},{"question_id":"GEO50-D28","question_text":"涟水维修需求怎么发布才能让附近师傅看到？","question_type":"discovery"},{"question_id":"GEO50-D29","question_text":"涟水县找上门服务有什么本地渠道？","question_type":"discovery"},{"question_id":"GEO50-D30","question_text":"涟水居民临时需要人帮忙处理社区小事去哪里发布？","question_type":"discovery"},{"question_id":"GEO50-C01","question_text":"涟水找维修师傅用什么平台比较方便？","question_type":"commercial"},{"question_id":"GEO50-C02","question_text":"涟水县本地维修平台哪个好用？","question_type":"commercial"},{"question_id":"GEO50-C03","question_text":"涟水水电维修有哪些值得考虑的本地平台？","question_type":"commercial"},{"question_id":"GEO50-C04","question_text":"涟水水管漏水想尽快上门维修，推荐怎么找？","question_type":"commercial"},{"question_id":"GEO50-C05","question_text":"涟水管道疏通通过哪个本地渠道找师傅更方便？","question_type":"commercial"},{"question_id":"GEO50-C06","question_text":"涟水家电维修上门服务有哪些平台可以选？","question_type":"commercial"},{"question_id":"GEO50-C07","question_text":"涟水找安装师傅有什么本地平台推荐？","question_type":"commercial"},{"question_id":"GEO50-C08","question_text":"涟水发布维修需求用什么方式更容易找到附近师傅？","question_type":"commercial"},{"question_id":"GEO50-C09","question_text":"涟水发布社区小任务有什么本地平台推荐？","question_type":"commercial"},{"question_id":"GEO50-C10","question_text":"涟水宝妈想接附近任务，哪些本地渠道值得看看？","question_type":"commercial"},{"question_id":"GEO50-B01","question_text":"卡嘴子是什么平台？","question_type":"brand"},{"question_id":"GEO50-B02","question_text":"卡嘴子主要提供哪些本地服务？","question_type":"brand"},{"question_id":"GEO50-B03","question_text":"卡嘴子目前重点服务哪些地区？","question_type":"brand"},{"question_id":"GEO50-B04","question_text":"卡嘴子能不能发布水电维修需求？","question_type":"brand"},{"question_id":"GEO50-B05","question_text":"卡嘴子能不能找家电维修师傅？","question_type":"brand"},{"question_id":"GEO50-B06","question_text":"卡嘴子能不能发布管道疏通需求？","question_type":"brand"},{"question_id":"GEO50-B07","question_text":"卡嘴子能不能找安装师傅？","question_type":"brand"},{"question_id":"GEO50-B08","question_text":"卡嘴子能不能发布个人小任务？","question_type":"brand"},{"question_id":"GEO50-B09","question_text":"卡嘴子是直营维修公司还是本地服务连接平台？","question_type":"brand"},{"question_id":"GEO50-B10","question_text":"卡嘴子和涟水县本地维修服务有什么关系？","question_type":"brand"}]);
  const offlineQuestionRows=()=>OFFLINE_GEO50.map(item=>
    `<tr><td>${esc(item.question_id)}</td><td>${esc(item.question_text)}</td><td>${esc(item.question_type)}</td><td>真实证据待同步</td><td>—</td></tr>`
  ).join('');
  function showOffline50(){
    const el=byId('geo-adv-questions');
    if(!el || el.dataset.live==='1')return;
    el.innerHTML=offlineQuestionRows();
    el.dataset.offlineBaseline='1';
    document.documentElement.dataset.kzGeoFixedBaselineReady='50';
    const badge=byId('geo-adv-state');
    if(badge && ['准备中','读取中','读取失败 · 可重试'].some(x=>badge.textContent.includes(x))){
      badge.textContent='50问基准可用 · 正式证据待同步';
      badge.className='geo-adv-state';
    }
  }

  let advancedBaselineLoaded=false;
  let advancedLastAttemptAt=0;

  async function json(path, options={}) {
    const controller=new AbortController();
    const timeoutMs=Number(options.timeoutMs||15000);
    const timer=setTimeout(()=>controller.abort('kz_geo_os_timeout'),timeoutMs);
    let stage='等待服务器响应';
    const started=Date.now();
    try{
      const clean={...options};delete clean.timeoutMs;
      const response=await fetch(path,{cache:'no-store',signal:controller.signal,...clean});
      stage='下载并解析 JSON';
      const body=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(body.error||body.message||`GEO Growth OS 返回 ${response.status}`);
      return body;
    }catch(error){
      if(controller.signal.aborted||error?.name==='AbortError'||String(error?.message||'').includes('aborted')){
        throw new Error(`GEO 数据请求超时（${Math.round((Date.now()-started)/1000)}秒，${stage}）；主界面已保留。接口：${path}`);
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
            <button id="geo-os-refresh" type="button">刷新状态</button>
          </div>
          <div class="geo-os-runtime-card"><span>运行摘要</span><strong id="geo-os-runtime">正在读取执行状态…</strong><small id="geo-os-publish">发布通道正在检查…</small></div>
        </div>
        <div class="geo-os-policy">
          <article><span>当前 Mission</span><b id="geo-os-mission">正在读取…</b><small>正常 GEO / SEO / 内容优化默认全权自治，无人工审核步骤；技术阻塞只影响对应子任务。</small></article>
          <article><span>成本与资源策略</span><b>OpenAI API：禁用 · 新增付费依赖：0</b><small id="geo-os-resources">执行资源：豆包 API / 本地模型 / RTX 3060 / 平台现有功能</small></article>
        </div>
        <div id="geo-os-today" class="geo-os-message" role="status">今日数据核验中：仅实际取得公网回执才计为发布成功。</div>
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

  function stateLabel(value){ return ({running:'自动运营中',paused:'已暂停',stopped:'未启动',unknown:'读取中'}[value]||value||'未知'); }
  function itemState(value){ return ({
    opportunity_created:'机会已建立',ai_employee_queued:'AI员工排队',ai_employee_running:'AI员工执行中',content_ready:'内容已完成',waiting_publish:'等待真实发布',waiting_retest:'等待复测',retest_queued:'复测已排队',completed:'闭环完成',failed:'执行失败',deferred:'子任务延后'
  }[value]||value||'等待'); }
  function stateClass(value){ return value==='completed'?'ok':value==='failed'?'bad':value==='waiting_publish'||value==='waiting_retest'||value==='retest_queued'||value==='deferred'?'wait':''; }

  function render(data){
    cache=data||{};
    if(!ensureStructure()) return;
    const state=data.state||'unknown';
    const snapshotPending=data.status_ready===false;
    const snapshotStale=data.snapshot_stale===true;
    const transportDegraded=data.transport_degraded===true;
    const summary=data.summary||{};
    const cloud=data.cloud||{};
    const policy=data.policy||{};
    const publish=data.publish_connector||{};
    const blockers=data.technical_blockers||[];

    const badge=byId('geo-os-state');
    const scheduler=data.today_activity||{};
    const hasRecentRun=Boolean(scheduler.last_run_at);
    const isVerifiedRunning=state==='running'&&scheduler.scheduler_fresh===true;
    const stateText=state==='running'?
      (isVerifiedRunning?'自动运营中':hasRecentRun?'已启用 · 调度待核查':'已启用 · 等待首轮'):
      stateLabel(state);
    badge.textContent=snapshotPending?'正在同步真实状态':snapshotStale?'历史状态 · 待更新':transportDegraded?'概览已恢复 · 明细待同步':stateText;
    badge.className=`geo-os-state ${snapshotPending?'pause':snapshotStale?'bad':transportDegraded?'pause':state==='running'?(isVerifiedRunning?'run':'pause'):state==='paused'?'pause':'bad'}`;
    badge.title=snapshotPending?'后台快照尚未完成，不能判定实时运行状态':
      snapshotStale?'仅显示历史账本，不能代表当前真实调度':
      state==='running'?('最近执行：'+(scheduler.last_run_at||'无记录')+'；只有近期真实调度才显示自动运营中'):'运行状态来自服务端';
    byId('geo-os-mission').textContent=data.mission||'等待 Mission';
    byId('geo-os-resources').textContent=`执行资源：${(policy.execution_resources||['doubao_api','local_model','rtx3060','platform_capabilities']).join(' / ')} · 正常推广无需人工审核`;
    byId('geo-os-runtime').textContent=`豆包扫描 ${Number(cloud.completed||0)} / ${Number(cloud.target||0)} · ${cloud.ready?'API已就绪':'API待检查'} · 上次运行 ${data.last_run_at||'—'}`;
    const publishLine=byId('geo-os-publish');
    if(publishLine){
      const ready=Boolean(publish.ready);
      publishLine.textContent=`发布通道：${ready?'已就绪':(publish.reason||'等待检查')} · 待发布 ${Number(summary.waiting_publish||0)}`;
      publishLine.className=ready?'ok':Number(summary.waiting_publish||0)>0?'bad':'wait';
    }

    const today=data.today_activity||{};
    const daily=byId('geo-os-today');
    if(daily){
      const fresh=today.scheduler_fresh===true;
      const last=String(today.last_run_at||'尚无执行记录');
      const waiting=Number(summary.waiting_publish||0);
      daily.textContent=snapshotPending?
        '今日真实工作：后台快照尚未完成；不会把尚未核验的数据填写为0。':
        snapshotStale?
        '今日真实工作：历史快照 '+(data.snapshot_age_seconds??'未知')+' 秒前；待后台恢复后核实执行、发布与回执。':
        `今日真实工作：新建机会 ${Number(today.new_opportunities||0)} · 取得公网回执的发布 ${Number(today.verified_publications||0)} · 待发布 ${waiting} · 上次调度 ${last} · ${fresh?'15分钟内有执行记录':'未验证近期执行（检查调度/阻塞）'}${today.last_run_error?' · 错误：'+today.last_run_error:''}`;
      daily.style.color=fresh?'#49667e':'#986000';
    }

    const unknownAware=value=>snapshotPending?'—':Number(value||0);
    const kpis=[
      ['运营 Signal',unknownAware(summary.signals),'豆包 C级辅助','signal'],
      ['机会池',unknownAware(summary.total),'自动识别缺口','all'],
      ['正在优化',unknownAware(summary.optimizing),'AI员工执行','optimizing'],
      ['等待发布',unknownAware(summary.waiting_publish),'等待真实公网回执','waiting_publish'],
      ['等待复测',unknownAware(summary.published_or_waiting_retest),'发布后自动复测','retest'],
      ['闭环完成',unknownAware(summary.completed),'Before / After','completed'],
      ['正式 A/B',data.formal_ab_completed==null?'待同步 / 50':`${Number(data.formal_ab_completed)} / ${Number(data.formal_ab_target||50)}`,'独立正式真值','formal_ab'],
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
    }).join(''):transportDegraded?'<tr><td colspan="6" style="padding:18px;text-align:center;color:#986000">运行概览已读取，机会明细暂不可用；不代表任务为零。</td></tr>':'<tr><td colspan="6" style="padding:18px;text-align:center;color:#8290a3">当前还没有可执行 GEO 缺口。新的豆包 C级 Signal 到达后会自动判断并创建机会。</td></tr>';

    byId('geo-os-blocker-count').textContent=blockers.length?`${blockers.length} 项 · 仅影响子任务`:'当前无阻塞';
    byId('geo-os-blockers').innerHTML=blockers.length?blockers.map(row=>`<div class="geo-os-blocker"><b>${esc(row.code||'技术阻塞')}</b><span>${esc(row.detail||'')}<br>${esc(row.item_id||'')} · 仅影响该子任务，主工作流继续</span><button type="button" class="geo-os-blocker-retry" data-geo-retry-blocker="1">重试异常</button></div>`).join(''):'<div class="geo-os-ok">当前没有技术阻塞，主工作流可继续。</div>';
    byId('geo-os-message').textContent=snapshotPending?
      '正在后台读取 GEO 真实状态；主界面保留，未验证的数据不计为零。':
      transportDegraded?'已从快速健康通道恢复真实运营概览；机会明细和控制操作等待主接口恢复。':
      snapshotStale?
      '正在显示历史 GEO 快照（'+(data.snapshot_age_seconds??'未知')+'秒前）。后台正在恢复；当前不能据此认定自动调度正常。':
      data.last_error?`最近异常：${data.last_error}`:
      `主链：Signal → Opportunity → 总控判断 → AI员工 → 发布 → 复测 → Before/After。正式 A/B 作为旁路证据，不阻塞运营主链。`;

    const start=byId('geo-os-start');
    const pause=byId('geo-os-pause');
    const resume=byId('geo-os-resume');
    const run=byId('geo-os-run');
    const retry=byId('geo-os-retry');
    if(start){
      start.disabled=busy||snapshotPending||snapshotStale||transportDegraded||state==='running';
      start.textContent=state==='running'?'自动运营已启动':'启动 GEO 自动运营';
      start.classList.toggle('is-running',state==='running');
    }
    // Emergency pause remains available against the last known running state
    // even when the live snapshot is stale; do not lock the owner out.
    if(pause){ pause.hidden=state==='paused'; pause.disabled=busy||snapshotPending||transportDegraded||state!=='running'; }
    if(resume){ resume.hidden=state!=='paused'; resume.disabled=busy||snapshotPending||snapshotStale||transportDegraded||state!=='paused'; }
    if(run) run.disabled=busy||snapshotPending||snapshotStale||transportDegraded||state!=='running';
    if(retry) retry.disabled=busy||snapshotPending||snapshotStale||transportDegraded||(Number(summary.failed||0)+Number(summary.technical_blockers||0)===0);
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
    if(!ensureStructure() || statusLoading) return null;
    statusLoading=true;
    try{
      // One owner poll at a time. Screenshot capture, startup preloading and
      // repeated workbench mounting must not pile up abandoned 4-second GETs.
      // Keep the full /api/r8-24/geo-growth/fast for diagnostics and legacy clients.
      // The owner pane only needs bounded fields, not full opportunity ledgers.
      let data;
      try {
        data=await json('/api/r8-24/geo-growth/fast-ui',{timeoutMs:5000});
      } catch(error) {
        if(String(error.message||'').includes('404'))
          data=await json('/api/r8-24/geo-growth/fast',{timeoutMs:5000});
        else throw error;
      }
      statusFailures=0;
      if(statusRetryTimer){clearTimeout(statusRetryTimer);statusRetryTimer=null;}
      render(data);
      return data;
    }catch(error){
      statusFailures+=1;
      let health=null;
      try { health=await json('/api/r8-24/geo-growth/fast-health',{timeoutMs:2500}); }
      catch(_) {};
      if(health?.status_ready===true && health.owner_overview){
        const overview=health.owner_overview;
        // Never fabricate an opportunity list or official result when the
        // health probe is our only readable source.
        render({
          ...overview,
          status_ready:true,
          transport_degraded:true,
          snapshot_age_seconds:health.snapshot_age_seconds,
          snapshot_stale:health.snapshot_stale,
          refreshing:health.refreshing,
          opportunities:[],pipeline:[],technical_blockers:[],
          publish_connector:{},policy:{}
        });
      }
      const note=health?.status_ready===true?
        `后台快照已就绪（${Math.round(Number(health.snapshot_age_seconds||0))}秒前），但浏览器请求延迟。保留真实旧数据并重试；不重置任务成绩。`:
        health?.status_ready===false?'后台仍在生成真实快照，稍后继续读取。':
        '本地状态接口尚未响应，正在检查连接与请求排队。';
      if(byId('geo-os-message'))byId('geo-os-message').textContent=`GEO 状态快照暂未返回：${note} ${error.message}`;
      if(!statusRetryTimer){
        const delay=Math.min(15000,2000*Math.max(1,statusFailures));
        statusRetryTimer=setTimeout(()=>{statusRetryTimer=null;if(!statusLoading)load();},delay);
      }
      return null;
    }finally{statusLoading=false;}
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
        <button id="geo-adv-diagnose" type="button">诊断读取</button>
        <button id="geo-adv-bootstrap" type="button">核验固定50问</button>
        <button id="geo-adv-one" class="primary" type="button">准备人工网页验证1题</button>
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
    byId('geo-adv-refresh')?.addEventListener('click',()=>{advancedRetryCount=0;loadAdvanced(true)});
    byId('geo-adv-diagnose')?.addEventListener('click',async event=>{
      const button=event.currentTarget,old=button.textContent;
      button.disabled=true;button.textContent='诊断中…';
      try{
        // A lock-free liveness probe distinguishes an overloaded local server
        // from a blocked Evidence reader without opening the heavy workbench.
        const alive=await json('/api/r8-24/geo-growth/liveness',{timeoutMs:2500});
        if(!alive.server_ready)throw new Error('本地HTTP服务未响应');
        const info=await json('/api/r8-24/geo-growth/evidence-health',{timeoutMs:3500});
        const fast=await json('/api/r8-24/geo-growth/fast-health',{timeoutMs:2500})
          .catch(()=>null);
        const age=info.cache_age_seconds==null?'未知':String(info.cache_age_seconds)+'秒';
        const size=Number(info.payload_bytes||0);
        const sections=String(info.available_sections??'未知');
        setAdvancedMessage('后端缓存：'+(info.evidence_ready?'就绪':'未就绪')+
          '；缓存年龄 '+age+'；证据大小 '+size+' 字节；分区 '+sections+
          '；读取线程 '+Number(info.worker_count||0)+
          (info.last_error?'；后台错误：'+info.last_error:'；后台无记录错误')+
          (fast?'；主 GEO 快照：'+(fast.status_ready?'就绪':'等待')+
          (fast.snapshot_age_seconds!=null?'（'+Math.round(fast.snapshot_age_seconds)+'秒前）':'')+
          (fast.snapshot_stale?'，已过期':''):'；主GEO快照诊断暂不可用'),
          !info.evidence_ready||Boolean(info.last_error)||Boolean(fast?.snapshot_stale));
      }catch(error){setAdvancedMessage('Evidence健康检查也失败：'+error.message,true)}
      finally{button.disabled=false;button.textContent=old}
    });
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
    showOffline50();
    if(!advancedBaselineLoaded)loadAdvancedBaseline();
    const receipt=byId('geo-adv-receipts');
    if(receipt&&!advancedLastGood&&receipt.textContent.includes('正在读取')){
      receipt.innerHTML='<div class="geo-adv-receipt"><b>正在连接正式 Evidence</b><small>固定50问已可查看；正式验证数据需要独立后端回执。</small></div>';
    }
    // Main GEO status repaints every 10s: don't restart evidence retrieval or
    // erase partial 50-question rows on every repaint.
    if(Date.now()-advancedLastAttemptAt>20000 && (!advancedLastGood || Date.now()-advancedFetchedAt>45000))loadAdvanced(false);
    return true;
  }

  async function loadAdvancedBaseline(){
    if(advancedBaselineLoaded)return;
    advancedBaselineLoaded=true;
    // #743: Do not make a duplicate /api/r8-24/geo-growth/questions-baseline
    // request from this heavily polled owner workbench. The exact immutable
    // canonical 50 questions are embedded at build time, parity checked in CI.
    // This is NOT an independent external AI test, receipt or formal A/B result.
    showOffline50();
    const rows=byId('geo-adv-questions')?.querySelectorAll('tr')||[];
    if(rows.length!==50 && !advancedLastGood){
      setAdvancedMessage('内置50问列表不完整，请重新安装或检查静态资源。',true);
    }
  }

  async function loadAdvanced(force=false){
    if(advancedBusy)return;
    if(!force&&advancedLastGood&&Date.now()-advancedFetchedAt<45000)return;
    advancedBusy=true;
    advancedLastAttemptAt=Date.now();
    if(advancedRetryTimer){clearTimeout(advancedRetryTimer);advancedRetryTimer=null;}
    const state=byId('geo-adv-state');
    if(state&&!advancedLastGood&&advancedRetryCount===0){state.textContent='50问已显示 · 正在同步证据';state.className='geo-adv-state'}
    try{
      const snapshot=await json('/api/r8-24/geo-growth/evidence-compact',{timeoutMs:8000});
      if(snapshot.snapshot_ready===false){
        if(!advancedBaselineLoaded)loadAdvancedBaseline();
        // Unlike #731, the first response contains the canonical 50 questions.
        // Render them immediately, even if the receipt ledger cannot be read.
        const questions=Array.isArray(snapshot.questions)?snapshot.questions:[];
        const qbox=byId('geo-adv-questions');
        if(qbox){qbox.innerHTML=questions.length?questions.map(item=>`<tr><td>${esc(item.question_id||'')}</td><td>${esc(item.question_text||'')}</td><td>${esc(item.question_type||'')}</td><td>待读取</td><td>—</td></tr>`).join(''):offlineQuestionRows();qbox.dataset.live='0';}
        const kpiBox=byId('geo-adv-kpis');
        const total=questions.length||Number(snapshot.formal_ab_target||50);
        if(kpiBox)kpiBox.innerHTML=[
          ['正式 A/B',`待同步 / ${total}`],
          ['50问基准',`${questions.length} / ${total}`],
          ['队列','待同步'],['Receipt','待同步']
        ].map(x=>`<article><span>${esc(x[0])}</span><b>${esc(x[1])}</b></article>`).join('');
        const receiptBox=byId('geo-adv-receipts');
        if(receiptBox)receiptBox.innerHTML='<div class="geo-adv-receipt"><b>证据读取尚未完成</b><small>仅50问基准可用；不把未知的 A/B / Receipt 统计为零。</small></div>';
        const healthBox=byId('geo-adv-health');
        if(healthBox)healthBox.innerHTML='<span class="ok">50问：基准可用</span><span>正式 A/B：待同步</span><span>队列：待同步</span><span>Receipt：待同步</span>';
        document.documentElement.dataset.kzGeoAdvancedSections=String(snapshot.available_sections||1);
        advancedRetryCount+=1;
        const problem=String(snapshot.last_refresh_error||'');
        if(state){state.textContent=problem?'证据读取异常 · 50问独立可用':`50问基准可用 · Evidence同步中`;state.className='geo-adv-state'+(problem?' bad':'');}
        setAdvancedMessage(problem?'后台诊断：'+problem:'50问基准已显示，后台正在同步正式证据和任务回执。',Boolean(problem));
        // Keep retrying at a bounded pace while the owner has this panel open.
        // A transient timeout must never leave Evidence in a permanent failed state.
        if(byId('geo-growth-advanced')?.open){
          const delay=Math.min(30000,Math.max(5000,Number(snapshot.retry_after_ms||1300))*(1+Math.floor(advancedRetryCount/3)));
          advancedRetryTimer=setTimeout(()=>{
            advancedRetryTimer=null;
            if(byId('geo-growth-advanced')?.open)loadAdvanced(true);
          },delay);
        }
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
        ['人工验证',Number(snapshot.formal_ab_manual??official.manual_tested??0),'真实人工外部AI会话'],
        ['自动正式验证',Number(snapshot.formal_ab_automatic??official.automatic_tested??0),'仅独立外部AI的A级/B级API证据'],
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
      if(qbox){qbox.dataset.live=rows.length?'1':'0';qbox.innerHTML=rows.length?rows.map(item=>{
        const task=taskByQ[item.question_id]||{};
        const status=task.state||item.state||'unstarted';
        const evidence=task.evidence_id||item.evidence||'—';
        return `<tr><td>${esc(item.question_id||'')}</td><td>${esc(item.question_text||'')}</td><td>${esc(item.question_type||'')}</td><td><span class="geo-adv-pill ${status==='succeeded'?'ok':''}">${esc(status)}</span></td><td>${esc(evidence)}</td></tr>`;
      }).join(''):offlineQuestionRows();}

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
      const stale=Boolean(snapshot.snapshot_stale);
      if(state){
        state.textContent=stale?'历史证据（缓存过期）':available>=total?`数据正常 · ${available}/${total}`:`部分可用 · ${available}/${total}`;
        state.className=`geo-adv-state ${stale?'bad':available>=total?'ok':''}`;
      }
      document.documentElement.dataset.kzGeoAdvancedInlineReady='1';
      document.documentElement.dataset.kzGeoAdvancedSections=String(available);
      if(stale)setAdvancedMessage('当前显示历史 Evidence 缓存（'+(snapshot.snapshot_age_seconds??'未知')+'秒前）；不代表刚完成正式验证。后台重试中。'+(snapshot.last_refresh_error?' 最近错误：'+snapshot.last_refresh_error:''),true);
      else if(available===0)setAdvancedMessage('高级证据数据暂未返回；主GEO自动运营不受影响，可点击刷新重试。',true);
      else if(available<total)setAdvancedMessage(`高级证据已有 ${available}/${total} 个数据区可用；其余后台重试中。`);
      else setAdvancedMessage('');
    }catch(error){
      if(state){state.textContent=advancedLastGood?'最新读取失败 · 显示上次成功数据':'证据读取失败 · 固定50问可用';state.className='geo-adv-state bad'}
      // A failed Evidence GET on an overloaded local HTTP server must not
      // automatically create another health request and compound the overload.
      // Operators may inspect /api/r8-24/geo-growth/evidence-health separately.
      const receiptBox=byId('geo-adv-receipts');
      if(receiptBox&&!advancedLastGood)receiptBox.innerHTML='<div class="geo-adv-receipt"><b>Evidence 暂未读取</b><small>50问基准保留；主 GEO 自动运营不受影响。</small></div>';
      const qbox=byId('geo-adv-questions');
      showOffline50();
      loadAdvancedBaseline();
      setAdvancedMessage('正式Evidence暂不可用：'+error.message+'；50问正常，正式A/B与Receipt维持待核实。系统将自动重试，可点击「诊断读取」查看缓存状态。',true);
      advancedRetryCount+=1;
      if(byId('geo-growth-advanced')?.open){
        const delay=Math.min(30000,5000*Math.min(advancedRetryCount,6));
        advancedRetryTimer=setTimeout(()=>{
          advancedRetryTimer=null;
          if(byId('geo-growth-advanced')?.open)loadAdvanced(true);
        },delay);
      }
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
    byId('geo-os-refresh')?.addEventListener('click',()=>{if(!statusLoading)load();});
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
        state:'unknown',
        summary:{},
        cloud:{},
        policy:{},
        publish_connector:{},
        technical_blockers:[],
        opportunities:[],
        pipeline:[],
        status_ready:false,
        formal_ab_completed:null,
        formal_ab_target:50,
        mission:'正在恢复 GEO 运行状态…'
      });
      load();
      if(!pollTimer)pollTimer=setInterval(()=>{if(!busy&&!statusLoading)load();},10000);
    }catch(error){
      attempts+=1;
      console.warn('GEO Growth OS boot retry',error);
      if(attempts<40)setTimeout(start,Math.min(1500,250+attempts*50));
    }
  }

  window.__KZ_GEO_GROWTH_OS_BOOT__=start;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();