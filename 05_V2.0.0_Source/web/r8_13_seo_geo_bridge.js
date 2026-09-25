(() => {
  'use strict';
  if (window.__KZ_R813_SEO_GEO_BRIDGE__) return;
  window.__KZ_R813_SEO_GEO_BRIDGE__ = true;

  const PAGE_ID = 'r813-seo-geo';

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

  function ensurePage(){
    let page=document.getElementById(PAGE_ID);
    if(!page){
      page=document.createElement('section');
      page.id=PAGE_ID;
      page.className='page';
      page.innerHTML='<iframe id="r813-seo-geo-frame" title="SEO/GEO增长中心" src="/r8_13_seo_geo.html?embed=1" style="width:100%;min-height:1400px;border:0;background:#f4f7fb" scrolling="no"></iframe>';
      document.querySelector('main')?.appendChild(page);
      const frame=page.querySelector('iframe');
      frame?.addEventListener('load',()=>{
        try{
          const doc=frame.contentDocument;
          if(!doc)return;
          injectAutonomy(frame);
          const resize=()=>{frame.style.height=`${Math.max(1300,doc.documentElement.scrollHeight,doc.body?.scrollHeight||0)+20}px`};
          resize();
          if(window.ResizeObserver){new ResizeObserver(resize).observe(doc.documentElement)}
        }catch(error){console.warn('SEO/GEO iframe resize deferred',error)}
      });
    }
    const legacy=document.querySelector('aside nav');
    if(legacy&&!legacy.querySelector(`.nav[data-page="${PAGE_ID}"]`)){
      const proxy=document.createElement('button');
      proxy.className='nav r810-legacy-route';
      proxy.dataset.page=PAGE_ID;
      proxy.dataset.title='SEO/GEO增长';
      proxy.dataset.subtitle='关键词、页面、技术SEO、索引收录、GEO可见性与归因';
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
  }

  // The SEO iframe cannot directly control the owner-shell account iframe.
  // Bridge its explicit authorization request to the durable account center and
  // open the official-provider chooser for the requested platform.
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
