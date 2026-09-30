(() => {
  'use strict';
  if (window.__KZ_R813_SEO_GEO_BRIDGE__) return;
  window.__KZ_R813_SEO_GEO_BRIDGE__ = true;

  const PAGE_ID = 'r813-seo-geo';
  const WORKSPACE_KEY = 'kz-search-growth-workspace';
  let desiredWorkspace = 'seo';

  function installStyle(){
    if(document.getElementById('r813-integrated-growth-style'))return;
    const style=document.createElement('style');
    style.id='r813-integrated-growth-style';
    style.textContent=`
      #${PAGE_ID}{padding:0!important;background:#f4f7fb;min-height:0!important}
      .r813-growth-shell{background:#f4f7fb;width:100%;min-width:0}
      .r813-growth-tabs{display:flex;gap:8px;align-items:center;padding:12px 14px;background:#fff;border:1px solid #dfe7f1;border-radius:10px;margin:0 0 10px}
      .r813-growth-tab{min-width:180px;text-align:left;border:1px solid #d6dfec;background:#fff;color:#31506f;border-radius:8px;padding:10px 14px;cursor:pointer;font:inherit}
      .r813-growth-tab b{display:block;font-size:13px}.r813-growth-tab span{display:block;font-size:11px;color:#7a8ba0;margin-top:2px}
      .r813-growth-tab.active{border-color:#2563eb;background:#eef4ff;color:#1f5dcc;box-shadow:0 0 0 2px rgba(37,99,235,.06)}
      .r813-growth-pane{display:block}.r813-growth-pane[hidden]{display:none!important}
      .r813-growth-frame{display:block;width:100%;height:calc(100vh - 300px);min-height:720px;max-height:980px;border:0;background:#f4f7fb;border-radius:10px;overflow:auto}
      @media(max-width:900px){.r813-growth-tabs{padding:8px}.r813-growth-tab{min-width:0;flex:1}.r813-growth-frame{height:calc(100vh - 250px);min-height:640px}}
    `;
    document.head.appendChild(style);
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
    }catch(error){console.warn('SEO legacy decoration deferred',error)}
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
            <iframe id="r813-seo-frame" class="r813-growth-frame" title="SEO增长中心" src="/r8_13_seo_geo.html?embed=1" scrolling="auto"></iframe>
          </div>
          <div class="r813-growth-pane" data-r813-pane="geo" hidden>
            <iframe id="r813-geo-frame" class="r813-growth-frame" title="GEO增长中心" src="about:blank" data-src="/geo.html?embed=1" scrolling="auto"></iframe>
          </div>
        </div>`;
      document.querySelector('main')?.appendChild(page);
      page.querySelectorAll('[data-r813-workspace]').forEach(button=>button.addEventListener('click',()=>activateWorkspace(button.dataset.r813Workspace)));
      const seoFrame=page.querySelector('#r813-seo-frame');
      seoFrame?.addEventListener('load',()=>decorateLegacySeo(seoFrame));
      if(seoFrame?.contentDocument?.readyState==='complete')decorateLegacySeo(seoFrame);
    }
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

  function loadGeoIfNeeded(){
    const frame=document.getElementById('r813-geo-frame');
    if(!frame)return;
    const wanted=frame.dataset.src||'/geo.html?embed=1';
    if(frame.dataset.kzLoaded==='1')return;
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
    if(target==='geo')loadGeoIfNeeded();
    desiredWorkspace=target;
    try{localStorage.setItem(WORKSPACE_KEY,target)}catch(_){}
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
  }

  window.KZR813SeoGeoBridge={open:activate,openGeo:()=>activateWorkspace('geo'),openSeo:()=>activateWorkspace('seo'),refresh};

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
