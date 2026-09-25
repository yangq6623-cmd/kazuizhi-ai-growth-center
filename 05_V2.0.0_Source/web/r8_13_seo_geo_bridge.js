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

  function ensureUiStyle(doc){
    if(doc.getElementById('kz-seo-action-style'))return;
    const style=doc.createElement('style');
    style.id='kz-seo-action-style';
    style.textContent=`
      .kz-seo-action-toast{position:fixed;right:22px;bottom:22px;z-index:2147483646;max-width:min(520px,calc(100vw - 44px));padding:13px 16px;border-radius:12px;background:#173f91;color:#fff;box-shadow:0 14px 42px rgba(14,42,91,.28);font:600 13px/1.55 Inter,"Microsoft YaHei",sans-serif;opacity:0;transform:translateY(10px);pointer-events:none;transition:.16s ease}.kz-seo-action-toast.show{opacity:1;transform:none}.kz-seo-action-toast.ok{background:#16734f}.kz-seo-action-toast.error{background:#b42318}
      .kz-seo-modal-backdrop{position:fixed;inset:0;z-index:2147483645;background:rgba(10,25,50,.42);display:flex;align-items:center;justify-content:center;padding:18px}.kz-seo-modal{width:min(720px,96vw);max-height:90vh;overflow:auto;background:#fff;border-radius:18px;border:1px solid #dfe6f2;box-shadow:0 24px 70px rgba(9,27,61,.28);padding:22px}.kz-seo-modal h2{margin:0 0 6px;font-size:22px}.kz-seo-modal p{margin:6px 0;color:#66748a}.kz-seo-field{display:grid;gap:6px;margin-top:14px}.kz-seo-field label{font-weight:700;color:#243b61}.kz-seo-field input{width:100%;padding:11px 12px;border:1px solid #ced9e9;border-radius:10px;font:inherit}.kz-seo-hint{margin-top:12px;padding:11px 12px;border-radius:10px;background:#eef5ff;color:#355176;font-size:12px;line-height:1.7}.kz-seo-modal-actions{display:flex;gap:9px;justify-content:flex-end;flex-wrap:wrap;margin-top:18px}.kz-seo-modal-actions button{border:1px solid #cbd7ea;background:#fff;color:#2457bd;border-radius:9px;padding:9px 13px;font-weight:700;cursor:pointer}.kz-seo-modal-actions button.primary{background:#2563eb;color:#fff;border-color:#2563eb}.kz-seo-modal-msg{min-height:20px;margin-top:10px;font-size:12px;color:#355176}.kz-seo-modal-msg.error{color:#b42318}
    `;
    doc.head.appendChild(style);
  }

  function ensureToast(doc){
    ensureUiStyle(doc);
    let node=doc.getElementById('kz-seo-action-toast');
    if(node)return node;
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

  function baseModal(frame,html){
    const doc=frame.contentDocument;
    ensureUiStyle(doc);
    const backdrop=doc.createElement('div');
    backdrop.className='kz-seo-modal-backdrop';
    backdrop.innerHTML=`<div class="kz-seo-modal">${html}</div>`;
    doc.body.appendChild(backdrop);
    backdrop.addEventListener('click',event=>{if(event.target===backdrop)backdrop.remove()});
    return backdrop;
  }

  async function ensureGoogleAppCredentials(frame){
    const status=await jsonApi('/api/r8-12/auth/app-credentials/status?platform=google_search_console');
    if(status.configured)return true;
    return new Promise(resolve=>{
      const callback=status.redirect_uri || 'http://127.0.0.1:8876/api/r8-12/oauth/callback/google_search_console';
      const modal=baseModal(frame,`
        <h2>配置 Google Search Console</h2>
        <p>只需配置一次 Google OAuth Web 应用。Client Secret 会写入当前 Windows 用户的 DPAPI 加密凭据库，不进入 GitHub、日志或普通配置文件。</p>
        <div class="kz-seo-field"><label>Google OAuth Client ID</label><input id="kz-google-client-id" autocomplete="off" spellcheck="false" placeholder="...apps.googleusercontent.com"></div>
        <div class="kz-seo-field"><label>Google OAuth Client Secret</label><input id="kz-google-client-secret" type="password" autocomplete="new-password" spellcheck="false" placeholder="输入后本页不会回显"></div>
        <div class="kz-seo-field"><label>Google Cloud 中必须登记的重定向 URI</label><input value="${callback.replace(/&/g,'&amp;').replace(/"/g,'&quot;')}" readonly></div>
        <div class="kz-seo-hint">Google Cloud：启用 Search Console API → 创建 OAuth 2.0 Client（Web application）→ Authorized redirect URIs 添加上面这一整行。测试阶段可先把你自己的 Google 账号加入 OAuth 测试用户。</div>
        <div class="kz-seo-modal-msg" id="kz-google-msg"></div>
        <div class="kz-seo-modal-actions"><button id="kz-google-console">打开 Google Cloud</button><button id="kz-google-cancel">取消</button><button class="primary" id="kz-google-save">保存并继续授权</button></div>
      `);
      const msg=modal.querySelector('#kz-google-msg');
      modal.querySelector('#kz-google-console').onclick=()=>window.open('https://console.cloud.google.com/apis/credentials','_blank','noopener,noreferrer');
      modal.querySelector('#kz-google-cancel').onclick=()=>{modal.remove();resolve(false)};
      modal.querySelector('#kz-google-save').onclick=async()=>{
        const save=modal.querySelector('#kz-google-save');
        const clientId=modal.querySelector('#kz-google-client-id').value.trim();
        const clientSecret=modal.querySelector('#kz-google-client-secret').value.trim();
        if(!clientId||!clientSecret){msg.textContent='Client ID 和 Client Secret 都必须填写。';msg.className='kz-seo-modal-msg error';return}
        setBusy(save,true,'保存中…');
        msg.textContent='正在写入 Windows DPAPI 安全凭据库…';msg.className='kz-seo-modal-msg';
        try{
          const saved=await post('/api/r8-12/auth/app-credentials',{platform:'google_search_console',client_id:clientId,client_secret:clientSecret});
          if(!saved.configured)throw new Error('凭据保存后仍未进入就绪状态');
          modal.remove();
          toast(frame,'Google OAuth 应用凭据已安全保存，下一步进入 Google 官方授权。','ok',6000);
          resolve(true);
        }catch(error){msg.textContent=`保存失败：${error.message||String(error)}`;msg.className='kz-seo-modal-msg error';setBusy(save,false)}
      };
    });
  }

  async function configureBaidu(frame){
    return new Promise(resolve=>{
      const modal=baseModal(frame,`
        <h2>配置百度搜索资源平台</h2>
        <p>请在百度搜索资源平台打开“资源提交 → 普通收录 → API提交”，复制完整“接口调用地址”粘贴到下面。准入密钥只会保存到本机 Windows DPAPI。</p>
        <div class="kz-seo-field"><label>百度完整 API 接口调用地址</label><input id="kz-baidu-endpoint" type="password" autocomplete="off" spellcheck="false" placeholder="http://data.zz.baidu.com/urls?site=...&token=..."></div>
        <div class="kz-seo-hint">不要把准入密钥发到聊天、GitHub 或截图中。这里直接粘贴百度页面当前显示的完整接口地址，程序会自动提取 site 和 token。</div>
        <div class="kz-seo-modal-msg" id="kz-baidu-msg"></div>
        <div class="kz-seo-modal-actions"><button id="kz-baidu-console">打开百度平台</button><button id="kz-baidu-cancel">取消</button><button class="primary" id="kz-baidu-save">保存并真实提交</button></div>
      `);
      const msg=modal.querySelector('#kz-baidu-msg');
      modal.querySelector('#kz-baidu-console').onclick=()=>window.open('https://ziyuan.baidu.com/site/index','_blank','noopener,noreferrer');
      modal.querySelector('#kz-baidu-cancel').onclick=()=>{modal.remove();resolve(false)};
      modal.querySelector('#kz-baidu-save').onclick=async()=>{
        const button=modal.querySelector('#kz-baidu-save');
        const raw=modal.querySelector('#kz-baidu-endpoint').value.trim();
        let parsed;
        try{parsed=new URL(raw)}catch(error){msg.textContent='接口地址格式不正确，请从百度后台完整复制。';msg.className='kz-seo-modal-msg error';return}
        const site=(parsed.searchParams.get('site')||'').trim();
        const token=(parsed.searchParams.get('token')||'').trim();
        if(parsed.hostname!=='data.zz.baidu.com'||!site||!token){msg.textContent='没有识别到百度 API 的 site/token，请重新复制完整接口调用地址。';msg.className='kz-seo-modal-msg error';return}
        setBusy(button,true,'配置中…');
        msg.textContent='正在加密保存并执行一次真实提交验证…';msg.className='kz-seo-modal-msg';
        try{
          await post('/api/r8-16/search-submit/config',{baidu_site:site,baidu_token:token,allow_baidu_http_submission:true});
          const result=await post('/api/r8-16/search-submit/run',{limit:20});
          await refreshFrame(frame);
          const count=Number(result?.submitted_count||result?.submitted?.length||0);
          const failed=Number(result?.failed_count||result?.failed?.length||0);
          modal.remove();
          toast(frame,count>0?`百度 API 已连接，并取得 ${count} 个真实提交回执。`:`百度配置已保存；本轮提交 ${count} 个，失败 ${failed} 个。请按提示检查百度返回状态。`,count>0?'ok':'info',8000);
          resolve(true);
        }catch(error){msg.textContent=`百度配置/提交失败：${error.message||String(error)}`;msg.className='kz-seo-modal-msg error';setBusy(button,false)}
      };
    });
  }

  async function openSearchAuth(frame,platform){
    if(platform==='baidu_search_resource'){
      return configureBaidu(frame);
    }
    if(platform==='google_search_console'){
      const ready=await ensureGoogleAppCredentials(frame);
      if(!ready)return false;
    }
    const local=frame.contentWindow?.KZAuthUI;
    if(local?.open){
      await local.open({platform});
      return true;
    }
    const center=window.KZR812AccountCenter;
    if(center){
      center.open(document.querySelector('.r810-execution-tabs button[data-execution-page="accounts"]'));
      const accountFrame=document.getElementById('r812-account-center-frame');
      const open=()=>accountFrame?.contentWindow?.KZAuthUI?.open({platform});
      if(accountFrame?.contentWindow?.KZAuthUI) await open();
      else accountFrame?.addEventListener('load',()=>open()?.catch?.(error=>console.warn('search authorization panel failed',error)),{once:true});
      return true;
    }
    const popup=window.open('/r8_12_account_center.html','_blank','noopener,noreferrer');
    if(!popup)throw new Error('浏览器阻止了授权窗口，请允许卡嘴子 AI 打开本地授权页面');
    return true;
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
          setBusy(auth,true,platform==='baidu_search_resource'?'配置中…':'正在打开…');
          toast(frame,platform==='baidu_search_resource'?'正在打开百度 API 安全配置。':'正在准备 Google 官方授权。');
          try{
            const opened=await openSearchAuth(frame,platform);
            if(opened && platform!=='baidu_search_resource')toast(frame,'授权入口已打开；请只在 Google 官方页面完成登录和授权。','ok',5200);
          }catch(error){
            toast(frame,`搜索平台配置失败：${error.message||String(error)}`,'error',7000);
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
    if(!frame)return;
    openSearchAuth(frame,platform).catch(error=>toast(frame,`搜索平台配置失败：${error.message||String(error)}`,'error',7000));
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
