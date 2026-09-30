(() => {
  'use strict';
  if (window.__KZ_R813_SEO_GEO_BRIDGE__) return;
  window.__KZ_R813_SEO_GEO_BRIDGE__ = true;

  const PAGE_ID = 'r813-seo-geo';
  const WORKSPACE_KEY = 'kz-search-growth-workspace';
  let desiredWorkspace = null;

  function injectAutonomy(frame){
    try{
      const doc=frame.contentDocument;
      if(!doc||doc.getElementById('r814-autonomy-script'))return;
      const script=doc.createElement('script');
      script.id='r814-autonomy-script';
      script.src='/r8_14_seo_geo_autonomy_ui.js';
      doc.body.appendChild(script);
    }catch(error){console.warn('SEO/GEO autonomy UI inject deferred',error)}
  }

  function ensureSearchHost(doc){
    let host=doc.getElementById('search');
    if(host)return host;
    host=doc.createElement('section');
    host.id='search';
    host.className='page active';
    const movable=[...doc.body.childNodes].filter(node=>!(node.nodeType===1&&['SCRIPT','STYLE','LINK'].includes(node.tagName)));
    doc.body.insertBefore(host,doc.body.firstChild);
    movable.forEach(node=>host.appendChild(node));
    return host;
  }

  function ensureStyle(doc,id,href){
    if(doc.getElementById(id))return;
    const link=doc.createElement('link');
    link.id=id;link.rel='stylesheet';link.href=href;
    doc.head.appendChild(link);
  }

  function scheduleResize(frame){
    [0,50,150,350,800].forEach(delay=>setTimeout(()=>setupResize(frame),delay));
  }

  function switchFrameWorkspace(name){
    const frame=document.getElementById('r813-seo-geo-frame');
    const doc=frame?.contentDocument;
    const target=name==='geo'?'geo':'seo';
    const button=doc?.querySelector(`[data-growth-tab="${target}"]`);
    if(button){
      button.click();
      scheduleResize(frame);
      return true;
    }
    return false;
  }

  function installGrowthWorkspace(frame){
    try{
      const doc=frame.contentDocument;
      if(!doc)return;
      ensureSearchHost(doc);
      ensureStyle(doc,'r819-growth-workspace-style','/operational-search.css');
      injectAutonomy(frame);
      const selectRequested=()=>{
        let saved='seo';
        try{saved=desiredWorkspace||localStorage.getItem(WORKSPACE_KEY)||'seo'}catch(_){saved=desiredWorkspace||'seo'}
        switchFrameWorkspace(saved);
        scheduleResize(frame);
      };
      if(doc.getElementById('r819-growth-workspace-script')){selectRequested();return}
      const script=doc.createElement('script');
      script.id='r819-growth-workspace-script';
      script.src='/operational-search.js';
      script.addEventListener('load',()=>setTimeout(selectRequested,0),{once:true});
      doc.body.appendChild(script);
    }catch(error){console.warn('R8-19 integrated SEO/GEO workspace inject deferred',error)}
  }

  function setupResize(frame){
    try{
      const doc=frame?.contentDocument;if(!doc)return;
      const resize=()=>{
        const htmlHeight=doc.documentElement?.scrollHeight||0;
        const bodyHeight=doc.body?.scrollHeight||0;
        const searchHeight=doc.getElementById('search')?.scrollHeight||0;
        const seoPane=doc.getElementById('seo-growth-pane');
        const geoPane=doc.getElementById('geo-growth-pane');
        const activePaneHeight=!seoPane?.hidden?(seoPane?.scrollHeight||0):(geoPane?.scrollHeight||0);
        frame.style.height=`${Math.max(1300,htmlHeight,bodyHeight,searchHeight,activePaneHeight)+32}px`;
      };
      resize();
      if(window.ResizeObserver&&!frame.__kzGrowthResizeObserver){
        const observer=new ResizeObserver(()=>resize());
        [doc.documentElement,doc.body,doc.getElementById('search')].filter(Boolean).forEach(node=>observer.observe(node));
        frame.__kzGrowthResizeObserver=observer;
      }
      if(window.MutationObserver&&!frame.__kzGrowthMutationObserver&&doc.body){
        const observer=new MutationObserver(()=>resize());
        observer.observe(doc.body,{subtree:true,childList:true,attributes:true,characterData:false});
        frame.__kzGrowthMutationObserver=observer;
      }
    }catch(error){console.warn('SEO/GEO iframe resize deferred',error)}
  }

  function ensurePage(){
    let page=document.getElementById(PAGE_ID);
    if(!page){
      page=document.createElement('section');
      page.id=PAGE_ID;
      page.className='page';
      page.innerHTML='<iframe id="r813-seo-geo-frame" title="SEO/GEO增长中心" src="/r8_13_seo_geo.html?embed=1" style="width:100%;min-height:1400px;border:0;background:#f4f7fb" scrolling="no"></iframe>';
      document.querySelector('main')?.appendChild(page);
      const frame=page.querySelector('iframe');
      frame?.addEventListener('load',()=>{installGrowthWorkspace(frame);setupResize(frame);scheduleResize(frame)});
    }
    const frame=page.querySelector('#r813-seo-geo-frame');
    if(frame?.contentDocument?.readyState==='complete'){installGrowthWorkspace(frame);setupResize(frame);scheduleResize(frame)}
    const legacy=document.querySelector('aside nav');
    if(legacy&&!legacy.querySelector(`.nav[data-page="${PAGE_ID}"]`)){
      const proxy=document.createElement('button');
      proxy.className='nav r810-legacy-route';
      proxy.dataset.page=PAGE_ID;
      proxy.dataset.title='SEO/GEO增长';
      proxy.dataset.subtitle='SEO保持完整运行；GEO第一阶段真实验证已合并到主平台';
      proxy.hidden=true;
      proxy.textContent='SEO/GEO增长';
      legacy.appendChild(proxy);
    }
    return page;
  }

  function activate(){
    ensurePage();
    if(typeof window.openPage==='function') window.openPage(PAGE_ID);
    else document.querySelectorAll('.page').forEach(node=>node.classList.toggle('active',node.id===PAGE_ID));
    document.querySelectorAll('.r810-nav-button').forEach(btn=>btn.classList.toggle('active',btn.dataset.target===PAGE_ID));
    setTimeout(()=>switchFrameWorkspace(desiredWorkspace||'seo'),0);
    const frame=document.getElementById('r813-seo-geo-frame');
    if(frame)scheduleResize(frame);
  }

  function activateWorkspace(name){
    desiredWorkspace=name==='geo'?'geo':'seo';
    try{localStorage.setItem(WORKSPACE_KEY,desiredWorkspace)}catch(_){}
    activate();
    const frame=document.getElementById('r813-seo-geo-frame');
    if(!switchFrameWorkspace(desiredWorkspace)&&frame){
      const retry=()=>switchFrameWorkspace(desiredWorkspace);
      frame.addEventListener('load',()=>setTimeout(retry,0),{once:true});
    }
    if(frame)scheduleResize(frame);
  }

  function refresh(){
    const frame=document.getElementById('r813-seo-geo-frame');
    try{frame?.contentWindow?.searchGrowthActivate?.()}catch(error){console.warn('SEO/GEO workspace refresh deferred',error)}
    if(frame)scheduleResize(frame);
  }

  window.KZR813SeoGeoBridge={
    open:activate,
    openGeo:()=>activateWorkspace('geo'),
    openSeo:()=>activateWorkspace('seo'),
    refresh
  };

  // AI决策中心的“打开GEO工作区”必须回到主平台，不再跳独立浏览器页面。
  document.addEventListener('click',event=>{
    const button=event.target.closest?.('#geo-decision-open');
    if(!button)return;
    event.preventDefault();event.stopImmediatePropagation();
    activateWorkspace('geo');
  },true);

  // The integrated SEO iframe cannot directly control the owner-shell account iframe.
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
    const frame = document.getElementById('r813-seo-geo-frame');
    const target = frame?.contentDocument?.getElementById(targetId);
    if (!frame || !target) return;
    const frameRect = frame.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    window.scrollTo({top: window.scrollY + frameRect.top + targetRect.top - 84, behavior:'smooth'});
  });

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
