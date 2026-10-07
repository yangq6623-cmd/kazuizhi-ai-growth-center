(() => {
  'use strict';
  if (window.__KZ_R813_SEO_GEO_BRIDGE__) return;
  window.__KZ_R813_SEO_GEO_BRIDGE__ = true;

  const PAGE_ID = 'r813-seo-geo';
  const WORKSPACE_KEY = 'kz-search-growth-workspace';
  const FINAL_CSS = '/seo-geo-phase1-final.css';
  const FINAL_JS = '/seo-geo-phase1-final.js';
  const FINISH_CSS = '/seo-geo-phase1-finish.css';
  const FINISH_JS = '/seo-geo-phase1-finish.js';
  let desiredWorkspace = 'seo';

  function installStyle(){
    if(document.getElementById('r813-integrated-growth-style'))return;
    const style=document.createElement('style');
    style.id='r813-integrated-growth-style';
    style.textContent=`
      #${PAGE_ID}{padding:0!important;background:#f4f7fb;min-height:0!important;overflow:visible!important}
      .r813-growth-shell{background:#f4f7fb;width:100%;min-width:0;overflow:visible}
      .r813-growth-tabs{display:flex;gap:8px;align-items:center;padding:12px 14px;background:#fff;border:1px solid #dfe7f1;border-radius:10px;margin:0 0 10px}
      .r813-growth-tab{min-width:180px;text-align:left;border:1px solid #d6dfec;background:#fff;color:#31506f;border-radius:8px;padding:10px 14px;cursor:pointer;font:inherit}
      .r813-growth-tab b{display:block;font-size:13px}.r813-growth-tab span{display:block;font-size:11px;color:#7a8ba0;margin-top:2px}
      .r813-growth-tab.active{border-color:#2563eb;background:#eef4ff;color:#1f5dcc;box-shadow:0 0 0 2px rgba(37,99,235,.06)}
      .r813-growth-pane{display:block;overflow:visible}.r813-growth-pane[hidden]{display:none!important}
      .r813-growth-frame{display:block;width:100%;height:720px;min-height:720px;max-height:none;border:0;background:#f4f7fb;border-radius:10px;overflow:hidden}
      @media(max-width:900px){.r813-growth-tabs{padding:8px}.r813-growth-tab{min-width:0;flex:1}.r813-growth-frame{min-height:720px}}
    `;
    document.head.appendChild(style);
  }

  function measureFrameDocument(frame){
    try{
      const doc=frame?.contentDocument;
      if(!doc?.body||!doc?.documentElement)return 720;
      const nodes=[doc.body,doc.documentElement,doc.querySelector('.wrap'),doc.querySelector('#search'),doc.querySelector('.geo-direct-main')].filter(Boolean);
      let expected=720;
      for(const node of nodes){
        expected=Math.max(expected,node.scrollHeight||0,node.offsetHeight||0,node.getBoundingClientRect?.().bottom||0);
      }
      const pipeline=doc.getElementById('pipeline-section');
      if(pipeline){
        const rect=pipeline.getBoundingClientRect();
        expected=Math.max(expected,Math.ceil(rect.bottom+(doc.defaultView?.scrollY||0)+32));
      }
      return Math.min(16000,Math.ceil(expected+8));
    }catch(_){return 720}
  }

  function fitFrame(frame){
    if(!frame||frame.hidden)return 720;
    const height=measureFrameDocument(frame);
    const current=Math.round(frame.getBoundingClientRect().height||0);
    if(Math.abs(current-height)>8)frame.style.height=`${height}px`;
    try{
      const doc=frame.contentDocument;
      if(doc?.documentElement)doc.documentElement.dataset.kzEmbeddedHeight=String(height);
    }catch(_){}
    return height;
  }

  function scheduleFrameFit(frame){
    if(!frame)return;
    [0,80,180,360,700,1200,2200,3600,5600,8200,11800].forEach(delay=>{
      window.setTimeout(()=>fitFrame(frame),delay);
    });
  }

  function fitActiveFrame(){
    const id=desiredWorkspace==='geo'?'r813-geo-frame':'r813-seo-frame';
    const frame=document.getElementById(id);
    fitFrame(frame);
  }

  function injectAsset(doc, tag, key, url){
    if(doc.querySelector(`[data-kz-growth-${key}]`))return;
    if(tag==='link'){
      const link=doc.createElement('link');
      link.rel='stylesheet';link.href=url;link.dataset[`kzGrowth${key[0].toUpperCase()+key.slice(1)}`]='1';
      doc.head.appendChild(link);
      return;
    }
    const script=doc.createElement('script');
    script.src=url;script.dataset[`kzGrowth${key[0].toUpperCase()+key.slice(1)}`]='1';
    doc.body.appendChild(script);
  }

  function injectFinalUx(frame){
    try{
      const doc=frame?.contentDocument;
      if(!doc||!doc.head||!doc.body)return;
      injectAsset(doc,'link','final',FINAL_CSS);
      injectAsset(doc,'script','final',FINAL_JS);
      injectAsset(doc,'link','finish',FINISH_CSS);
      injectAsset(doc,'script','finish',FINISH_JS);
      scheduleFrameFit(frame);
    }catch(error){console.warn('SEO/GEO final UX injection deferred',error)}
  }

  function decorateLegacySeo(frame){
    try{
      const doc=frame.contentDocument;if(!doc)return;
      [...doc.querySelectorAll('h2,h3')].forEach(node=>{
        const text=(node.textContent||'').trim();
        if(text==='SEO/GEO自治运行')node.textContent='SEO自治运行';
        if(text==='GEO / AI 50问验证')node.textContent='GEO 联动摘要（只读）';
      });
      if(!doc.getElementById('r813-seo-readonly-note')){
        const geoCard=[...doc.querySelectorAll('.card')].find(card=>/GEO\s*\/\s*AI\s*50问验证|GEO 联动摘要/.test(card.textContent||''));
        if(geoCard){
          const note=doc.createElement('div');
          note.id='r813-seo-readonly-note';
          note.style.cssText='margin-top:10px;padding:9px 11px;border-radius:8px;background:#eef5ff;border:1px solid #d8e6ff;color:#315d9f;font-size:12px';
          note.textContent='这里只显示 GEO 联动摘要；真实网页验证、50问和 Evidence / Receipt 请切换上方“GEO 增长”。';
          geoCard.appendChild(note);
        }
      }
      injectFinalUx(frame);
      scheduleFrameFit(frame);
    }catch(error){console.warn('SEO legacy decoration deferred',error)}
  }

  function wireFrame(frame, kind){
    if(!frame||frame.dataset.kzFinalWired==='1')return;
    frame.dataset.kzFinalWired='1';
    frame.setAttribute('scrolling','no');
    frame.addEventListener('load',()=>{
      if(kind==='seo')decorateLegacySeo(frame); else injectFinalUx(frame);
      scheduleFrameFit(frame);
      try{
        frame.contentWindow?.addEventListener('focus',()=>scheduleFrameFit(frame));
        frame.contentWindow?.addEventListener('resize',()=>scheduleFrameFit(frame));
      }catch(_){}
    });
  }

  function ensurePage(){
    installStyle();
    let page=document.getElementById(PAGE_ID);
    if(!page){
      page=document.createElement('section');
      page.id=PAGE_ID;
      page.className='page';
      page.innerHTML=`
        <div class="r813-growth-shell">
          <div class="r813-growth-tabs" role="tablist" aria-label="SEO/GEO增长工作区">
            <button type="button" class="r813-growth-tab active" data-r813-workspace="seo" role="tab"><b>SEO 增长</b><span>保持现有 SEO 全功能运行</span></button>
            <button type="button" class="r813-growth-tab" data-r813-workspace="geo" role="tab"><b>GEO 增长</b><span>R8-19 · 浏览器真实验证</span></button>
          </div>
          <div class="r813-growth-pane" data-r813-pane="seo">
            <iframe id="r813-seo-frame" class="r813-growth-frame" title="SEO增长中心" src="about:blank" data-src="/r8_13_seo_geo.html?embed=1" scrolling="no"></iframe>
          </div>
          <div class="r813-growth-pane" data-r813-pane="geo" hidden>
            <iframe id="r813-geo-frame" class="r813-growth-frame" title="GEO增长中心" src="about:blank" data-src="/geo.html?embed=1" scrolling="no"></iframe>
          </div>
        </div>`;
      document.querySelector('main')?.appendChild(page);
      page.querySelectorAll('[data-r813-workspace]').forEach(button=>button.addEventListener('click',()=>activateWorkspace(button.dataset.r813Workspace)));
    }
    const seoFrame=page.querySelector('#r813-seo-frame');
    const geoFrame=page.querySelector('#r813-geo-frame');
    wireFrame(seoFrame,'seo');wireFrame(geoFrame,'geo');
    if(seoFrame?.dataset.kzLoaded==='1'&&seoFrame?.contentDocument?.readyState==='complete'){decorateLegacySeo(seoFrame);scheduleFrameFit(seoFrame)}
    if(geoFrame?.dataset.kzLoaded==='1'&&geoFrame?.contentDocument?.readyState==='complete'){injectFinalUx(geoFrame);scheduleFrameFit(geoFrame)}

    const legacy=document.querySelector('aside nav');
    if(legacy&&!legacy.querySelector(`.nav[data-page="${PAGE_ID}"]`)){
      const proxy=document.createElement('button');
      proxy.className='nav r810-legacy-route';
      proxy.dataset.page=PAGE_ID;
      proxy.dataset.title='SEO/GEO增长';
      proxy.dataset.subtitle='SEO 与 GEO 分离运行，共享同一主平台入口';
      proxy.hidden=true;
      proxy.textContent='SEO/GEO增长';
      legacy.appendChild(proxy);
    }
    return page;
  }

  function loadWorkspaceIfNeeded(kind){
    const target=kind==='geo'?'geo':'seo';
    const frame=document.getElementById(target==='geo'?'r813-geo-frame':'r813-seo-frame');
    if(!frame)return;
    wireFrame(frame,target);
    const wanted=frame.dataset.src||(target==='geo'?'/geo.html?embed=1':'/r8_13_seo_geo.html?embed=1');
    if(frame.dataset.kzLoaded==='1'){scheduleFrameFit(frame);return}
    frame.dataset.kzLoaded='1';
    frame.src=wanted;
  }

  function renderWorkspace(name){
    const page=ensurePage();
    const target=name==='geo'?'geo':'seo';
    page.querySelectorAll('[data-r813-workspace]').forEach(button=>{
      const active=button.dataset.r813Workspace===target;
      button.classList.toggle('active',active);
      button.setAttribute('aria-selected',String(active));
    });
    page.querySelectorAll('[data-r813-pane]').forEach(pane=>{pane.hidden=pane.dataset.r813Pane!==target;});
    loadWorkspaceIfNeeded(target);
    desiredWorkspace=target;
    try{localStorage.setItem(WORKSPACE_KEY,target)}catch(_){}
    const frame=document.getElementById(target==='geo'?'r813-geo-frame':'r813-seo-frame');
    scheduleFrameFit(frame);
    window.setTimeout(()=>{
      try{frame?.contentWindow?.__KZ_GROWTH_RESIZE__?.()}catch(_){}
      fitFrame(frame);
    },180);
  }

  function activate(){
    const page=ensurePage();
    if(typeof window.openPage==='function')window.openPage(PAGE_ID);
    else document.querySelectorAll('.page').forEach(node=>node.classList.toggle('active',node.id===PAGE_ID));
    document.querySelectorAll('.r810-nav-button').forEach(btn=>btn.classList.toggle('active',btn.dataset.target===PAGE_ID));
    let saved=desiredWorkspace;
    try{saved=localStorage.getItem(WORKSPACE_KEY)||saved}catch(_){}
    renderWorkspace(saved);
    page.scrollIntoView({block:'start',behavior:'auto'});
  }

  function activateWorkspace(name){
    desiredWorkspace=name==='geo'?'geo':'seo';
    const page=ensurePage();
    if(!page.classList.contains('active')){
      if(typeof window.openPage==='function')window.openPage(PAGE_ID);
      else document.querySelectorAll('.page').forEach(node=>node.classList.toggle('active',node.id===PAGE_ID));
    }
    document.querySelectorAll('.r810-nav-button').forEach(btn=>btn.classList.toggle('active',btn.dataset.target===PAGE_ID));
    renderWorkspace(desiredWorkspace);
  }

  function refresh(){
    const seo=document.getElementById('r813-seo-frame');
    const geo=document.getElementById('r813-geo-frame');
    try{seo?.contentWindow?.searchGrowthActivate?.()}catch(error){console.warn('SEO refresh deferred',error)}
    try{geo?.contentWindow?.searchGrowthActivate?.()}catch(error){console.warn('GEO refresh deferred',error)}
    scheduleFrameFit(seo);scheduleFrameFit(geo);
    window.setTimeout(()=>{
      try{seo?.contentWindow?.__KZ_GROWTH_RESIZE__?.();geo?.contentWindow?.__KZ_GROWTH_RESIZE__?.()}catch(_){}
      fitFrame(seo);fitFrame(geo);
    },220);
  }

  window.KZR813SeoGeoBridge={open:activate,openGeo:()=>activateWorkspace('geo'),openSeo:()=>activateWorkspace('seo'),refresh,fitFrame:fitActiveFrame};

  document.addEventListener('click',event=>{
    const button=event.target.closest?.('#geo-decision-open');
    if(!button)return;
    event.preventDefault();event.stopImmediatePropagation();
    activateWorkspace('geo');
  },true);

  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.data?.type !== 'kz-r8-search-auth') return;
    const platform = String(event.data.platform || 'google_search_console');
    const center = window.KZR812AccountCenter;
    if (!center) return;
    center.open(document.querySelector('.r810-execution-tabs button[data-execution-page="accounts"]'));
    const frame = document.getElementById('r812-account-center-frame');
    const openAuth = () => frame?.contentWindow?.KZAuthUI?.open({platform}).catch(error => console.warn('search authorization panel failed', error));
    if (frame?.contentWindow?.KZAuthUI) openAuth(); else frame?.addEventListener('load', openAuth, {once:true});
  });

  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.data?.type !== 'kz-r813-focus') return;
    const targetId = String(event.data.target || '');
    const sourceFrame=[document.getElementById('r813-seo-frame'),document.getElementById('r813-geo-frame')]
      .find(frame=>frame?.contentWindow===event.source);
    const target=sourceFrame?.contentDocument?.getElementById(targetId);
    try{target?.scrollIntoView({block:'start',behavior:'smooth'})}catch(_){}
  });

  window.addEventListener('resize',()=>window.setTimeout(fitActiveFrame,140));

  function ensureNav(){
    const primary=document.querySelector('.r810-primary-nav');
    if(!primary||primary.querySelector('[data-target="r813-seo-geo"]'))return;
    const button=document.createElement('button');
    button.className='r810-nav-button';
    button.dataset.target=PAGE_ID;
    button.innerHTML='<span class="r810-icon">搜</span><span>SEO/GEO增长</span>';
    const evolution=primary.querySelector('[data-target="r810-evolution"]');
    if(evolution)primary.insertBefore(button,evolution); else primary.appendChild(button);
    button.addEventListener('click',event=>{event.preventDefault();event.stopImmediatePropagation();activate()},{capture:true});
  }

  ensurePage();
  ensureNav();
  window.addEventListener('kz:app-ready',()=>{ensurePage();ensureNav()});
  window.addEventListener('r810:workbench-ready',()=>{ensurePage();ensureNav()});
})();
