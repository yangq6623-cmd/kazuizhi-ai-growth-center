(() => {
  'use strict';
  if (window.__KZ_R813_SEO_GEO_BRIDGE__) return;
  window.__KZ_R813_SEO_GEO_BRIDGE__ = true;

  const PAGE_ID = 'r813-seo-geo';
  const FRAME_ID = 'r813-seo-geo-frame';

  async function jsonApi(path, options) {
    const response = await fetch(path, {cache:'no-store', ...(options || {})});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || payload.message || `HTTP ${response.status}`);
    return payload.data || payload;
  }

  function post(path, body={}) {
    return jsonApi(path, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body || {}),
    });
  }

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

  function injectAuthUi(frame){
    try{
      const doc=frame.contentDocument;
      if(!doc||doc.getElementById('r812-search-auth-script'))return;
      const script=doc.createElement('script');
      script.id='r812-search-auth-script';
      script.src='/r8_12_multi_account_auth_ui.js';
      doc.body.appendChild(script);
    }catch(error){console.warn('SEO/GEO auth UI inject deferred',error)}
  }

  function ensureToast(doc){
    let node=doc.getElementById('kz-seo-action-toast');
    if(node)return node;
    const style=doc.createElement('style');
    style.id='kz-seo-action-toast-style';
    style.textContent='.kz-seo-action-toast{position:fixed;right:22px;bottom:22px;z-index:2147483646;max-width:min(520px,calc(100vw - 44px));padding:13px 16px;border-radius:12px;background:#173f91;color:#fff;box-shadow:0 14px 42px rgba(14,42,91,.28);font:600 13px/1.55 Inter,"Microsoft YaHei",sans-serif;opacity:0;transform:translateY(10px);pointer-events:none;transition:.16s ease}.kz-seo-action-toast.show{opacity:1;transform:none}.kz-seo-action-toast.ok{background:#16734f}.kz-seo-action-toast.error{background:#b42318}';
    doc.head.appendChild(style);
    node=doc.createElement('div');
    node.id='kz-seo-action-toast';
    node.className='kz-seo-action-toast';
    node.setAttribute('role','status');
    node.setAttribute('aria-live','polite');
    doc.body.appendChild(node);
    return node;
  }

  function toast(frame,message,kind='info',hold=4200){
    try{
      const doc=frame.contentDocument;
      const node=ensureToast(doc);
      node.textContent=message || '';
      node.className=`kz-seo-action-toast show ${kind==='error'?'error':kind==='ok'?'ok':''}`;
      clearTimeout(node.__kzTimer);
      node.__kzTimer=setTimeout(()=>node.classList.remove('show'),hold);
      const localStatus=doc.getElementById('action-status');
      if(localStatus){
        localStatus.textContent=message || '';
        localStatus.classList.toggle('error',kind==='error');
      }
    }catch(error){console.warn('SEO/GEO feedback deferred',error)}
  }

  function setBusy(button,busy,text){
    if(!button)return;
    if(busy){
      if(!button.dataset.kzOldText)button.dataset.kzOldText=button.textContent;
      button.disabled=true;
      button.textContent=text || '正在执行…';
      button.setAttribute('aria-busy','true');
    }else{
      button.disabled=false;
      button.textContent=button.dataset.kzOldText || button.textContent;
      delete button.dataset.kzOldText;
      button.removeAttribute('aria-busy');
    }
  }

  async function refreshFrame(frame){
    try{
      if(typeof frame.contentWindow?.load==='function')await frame.contentWindow.load();
      const refresh=frame.contentDocument?.getElementById('r814-refresh');
      if(refresh && !refresh.disabled) refresh.click();
    }catch(error){console.warn('SEO/GEO refresh deferred',error)}
  }

  async function openSearchAuth(frame,platform){
    const local=frame.contentWindow?.KZAuthUI;
    if(local?.open){
      await local.open({platform});
      return;
    }
    const center=window.KZR812AccountCenter;
    if(center){
      center.open(document.querySelector('.r810-execution-tabs button[data-execution-page="accounts"]'));
      const accountFrame=document.getElementById('r812-account-center-frame');
      const open=()=>accountFrame?.contentWindow?.KZAuthUI?.open({platform});
      if(accountFrame?.contentWindow?.KZAuthUI) await open();
      else accountFrame?.addEventListener('load',()=>open()?.catch?.(error=>console.warn('search authorization panel failed',error)),{once:true});
      return;
    }
    const popup=window.open('/r8_12_account_center.html','_blank','noopener,noreferrer');
    if(!popup)throw new Error('浏览器阻止了授权窗口，请允许卡嘴子 AI 打开本地授权页面');
  }

  function installControlReliability(frame){
    try{
      const doc=frame.contentDocument;
      if(!doc||doc.__KZ_SEO_CONTROL_RELIABILITY__)return;
      doc.__KZ_SEO_CONTROL_RELIABILITY__=true;
      ensureToast(doc);

      doc.addEventListener('click',async event=>{
        const target=event.target?.closest?.('button');
        if(!target)return;

        const auth=target.closest('[data-search-auth]');
        if(auth){
          event.preventDefault();
          event.stopImmediatePropagation();
          const platform=String(auth.dataset.searchAuth||'').trim();
          setBusy(auth,true,'正在打开…');
          toast(frame,'正在打开官方授权配置。');
          try{
            await openSearchAuth(frame,platform);
            toast(frame,'授权入口已打开；请只在平台官方页面完成登录或授权。','ok',5200);
          }catch(error){
            toast(frame,`授权入口打开失败：${error.message||String(error)}`,'error',7000);
          }finally{setBusy(auth,false)}
          return;
        }

        const init=target.closest('[data-search-init]');
        if(init){
          event.preventDefault();
          event.stopImmediatePropagation();
          setBusy(init,true,'初始化中…');
          toast(frame,'正在生成并验证 IndexNow Key，请稍候。');
          try{
            const initialized=await post('/api/r8-16/search-submit/initialize',{});
            if(initialized?.ok===false)throw new Error(initialized.reason||initialized.error||'IndexNow 公网验证未通过');
            toast(frame,'IndexNow Key 已通过公网验证，正在提交待提交 URL。','ok');
            const submitted=await post('/api/r8-16/search-submit/run',{limit:20});
            await refreshFrame(frame);
            const count=Number(submitted?.submitted_count||submitted?.submitted?.length||0);
            const failed=Number(submitted?.failed_count||submitted?.failed?.length||0);
            toast(frame,count>0?`IndexNow 已取得真实提交回执：${count} 个 URL。`:`IndexNow 已就绪；本轮真实提交 ${count} 个，失败 ${failed} 个。`,'ok',7000);
          }catch(error){
            toast(frame,`IndexNow 初始化/提交失败：${error.message||String(error)}`,'error',8000);
          }finally{setBusy(init,false)}
          return;
        }

        if(target.id==='run-btn'){
          event.preventDefault();
          event.stopImmediatePropagation();
          setBusy(target,true,'正在运行…');
          toast(frame,'正在运行完整 SEO/GEO 自治循环：本地生成 → 公网发布 → 搜索提交。');
          try{
            const result=await post('/api/r8-14/seo-geo/autonomy/run',{force:true});
            await refreshFrame(frame);
            const submitted=Number(result?.today?.submitted_urls||result?.search_submit?.submitted_count||0);
            toast(frame,submitted>0?`自治循环完成，本轮已取得搜索提交回执：${submitted}。`:'自治循环已完成并刷新真实状态；未取得回执的步骤不会标记成功。','ok',7000);
          }catch(error){
            toast(frame,`自治循环执行失败：${error.message||String(error)}`,'error',8000);
          }finally{setBusy(target,false)}
          return;
        }
      },true);
    }catch(error){console.warn('SEO/GEO control reliability install deferred',error)}
  }

  function ensurePage(){
    let page=document.getElementById(PAGE_ID);
    if(!page){
      page=document.createElement('section');
      page.id=PAGE_ID;
      page.className='page';
      page.innerHTML=`<iframe id="${FRAME_ID}" title="SEO/GEO增长中心" src="/r8_13_seo_geo.html?embed=1" style="width:100%;min-height:1400px;border:0;background:#f4f7fb;pointer-events:auto" scrolling="no"></iframe>`;
      document.querySelector('main')?.appendChild(page);
      const frame=page.querySelector('iframe');
      frame?.addEventListener('load',()=>{
        try{
          const doc=frame.contentDocument;
          if(!doc)return;
          injectAutonomy(frame);
          injectAuthUi(frame);
          installControlReliability(frame);
          const resize=()=>{frame.style.height=`${Math.max(1300,doc.documentElement.scrollHeight,doc.body?.scrollHeight||0)+20}px`};
          resize();
          if(window.ResizeObserver){new ResizeObserver(resize).observe(doc.documentElement)}
        }catch(error){console.warn('SEO/GEO iframe setup deferred',error)}
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

  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.data?.type !== 'kz-r8-search-auth') return;
    const platform=String(event.data.platform||'google_search_console');
    const frame=document.getElementById(FRAME_ID);
    openSearchAuth(frame,platform).catch(error=>{
      if(frame)toast(frame,`授权入口打开失败：${error.message||String(error)}`,'error',7000);
    });
  });

  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.data?.type !== 'kz-r813-focus') return;
    const targetId=String(event.data.target||'');
    const frame=document.getElementById(FRAME_ID);
    const target=frame?.contentDocument?.getElementById(targetId);
    if (!frame || !target) return;
    const frameRect=frame.getBoundingClientRect();
    const targetRect=target.getBoundingClientRect();
    window.scrollTo({top:window.scrollY+frameRect.top+targetRect.top-84,behavior:'smooth'});
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
