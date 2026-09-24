(() => {
  'use strict';
  if (window.__KZ_MULTI_ACCOUNT_AUTH_UI__) return;
  window.__KZ_MULTI_ACCOUNT_AUTH_UI__ = true;

  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const api=async(path,opt)=>{const r=await fetch(path,opt);const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||j.message||`HTTP ${r.status}`);return j.data||j};

  function style(){
    if(document.getElementById('kz-auth-ui-style'))return;
    const node=document.createElement('style');node.id='kz-auth-ui-style';node.textContent=`
      .kz-auth-add{background:#2563eb;color:#fff;border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer}
      .kz-auth-safety{margin:16px 0;padding:14px 16px;border:1px solid #d9e6ff;background:#eef5ff;border-radius:14px;color:#355176}.kz-auth-safety b{display:block;margin-bottom:6px}.kz-auth-safety span{display:block;font-size:13px;line-height:1.7}
      .kz-auth-backdrop{position:fixed;inset:0;background:rgba(10,25,50,.35);z-index:9998;display:flex;align-items:center;justify-content:center;padding:20px}.kz-auth-modal{width:min(960px,96vw);max-height:90vh;overflow:auto;background:#fff;border-radius:18px;box-shadow:0 24px 70px rgba(9,27,61,.24);padding:22px}
      .kz-auth-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.kz-auth-head h2{margin:0 0 6px}.kz-auth-close{background:#f2f5f9;border:0;border-radius:9px;padding:8px 12px;cursor:pointer}.kz-auth-slot{display:flex;gap:10px;align-items:center;margin:18px 0}.kz-auth-slot input{flex:1;border:1px solid #dce4f0;border-radius:10px;padding:11px 12px}
      .kz-auth-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.kz-provider{border:1px solid #e2e8f2;border-radius:14px;padding:15px;background:#fff}.kz-provider .top{display:flex;align-items:center;justify-content:space-between;gap:10px}.kz-provider .meta{font-size:12px;color:#78849a;margin:8px 0 12px;line-height:1.55}.kz-provider .urls{font-size:11px;color:#6b7280;word-break:break-all;background:#f8fafc;border-radius:9px;padding:8px;margin-bottom:10px}.kz-provider button{width:100%;background:#2563eb;color:#fff;border:0;border-radius:9px;padding:9px 12px;font-weight:700;cursor:pointer}.kz-tag{font-size:11px;border-radius:999px;padding:4px 8px;background:#e9f8ef;color:#187a42}.kz-tag.warn{background:#fff4df;color:#a66300}.kz-auth-msg{margin-top:14px;padding:11px 12px;border-radius:10px;background:#f7f9fc;color:#53627a}.kz-auth-msg.error{background:#fdecec;color:#a63a3a}.kz-auth-msg.ok{background:#e9f8ef;color:#187a42}
      @media(max-width:760px){.kz-auth-grid{grid-template-columns:1fr}}
    `;document.head.appendChild(node);
  }

  function browserRedirect(platform){return `${location.protocol}//${location.host}/api/r8-12/oauth/callback/${encodeURIComponent(platform)}`}

  async function openOfficialLogin(provider,slotLabel,accountId,msg){
    msg.className='kz-auth-msg';msg.textContent='正在准备官方登录入口…';
    try{
      const result=await api('/api/r8-12/auth/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({platform:provider.platform,slot_label:slotLabel,account_id:accountId||'',redirect_uri:browserRedirect(provider.platform)})});
      const url=result.authorization_url;if(!url)throw new Error('平台没有返回可用的官方入口');
      const win=window.open(url,'_blank','noopener,noreferrer');if(!win)throw new Error('浏览器阻止了新窗口，请允许本地卡嘴子页面打开官方登录窗口');
      if(result.ok){msg.className='kz-auth-msg ok';msg.textContent=`已打开 ${provider.name} 官方页面。请在官方页面完成登录/扫码/授权；卡嘴子不会读取账号密码。`}
      else{msg.className='kz-auth-msg error';msg.textContent=result.needs_app_credentials?`${provider.name} 尚缺官方应用 Client ID/Secret。已打开官方控制台；配置完成前不会标记账号已连接。`:result.needs_https_callback?`${provider.name} 需要平台允许的 HTTPS 回调地址。已打开官方控制台，配置完成后再授权。`:(result.truth||'官方授权尚未满足前置条件。')}
    }catch(error){msg.className='kz-auth-msg error';msg.textContent=error.message||String(error)}
  }

  async function showModal(options={}){
    const data=await api('/api/r8-12/auth/catalog');
    const reauth=Boolean(options.account_id);const selectedPlatform=String(options.platform||'');
    const providers=(data.providers||[]).filter(p=>!selectedPlatform||p.platform===selectedPlatform);
    const backdrop=document.createElement('div');backdrop.className='kz-auth-backdrop';
    backdrop.innerHTML=`<div class="kz-auth-modal">
      <div class="kz-auth-head"><div><h2>${reauth?'重新授权账号':'新增平台账号'}</h2><div class="muted">${reauth?'保留原 account_id 和历史归属，只更新官方授权。':'一个平台可以添加多个账号。每完成一次真实官方授权，就建立一个独立账号资产，不覆盖旧账号。'}</div></div><button class="kz-auth-close">关闭</button></div>
      <div class="kz-auth-slot"><label>账号备注</label><input id="kz-auth-slot-label" value="${esc(options.slot_label||'')}" placeholder="例如：百度账号1 / 百度账号2 / 抖音维修主号"></div>
      <div class="kz-auth-safety"><b>账号环境安全策略</b><span>固定账号尽量保持固定设备、浏览器与常用网络；不做代理轮换、不改指纹、不绕验证码/短信/人脸。出现风控或异常环境变化立即暂停，不自动切换其他账号绕过限制。</span></div>
      <div class="kz-auth-grid">${providers.map(p=>`<div class="kz-provider" data-platform="${esc(p.platform)}"><div class="top"><b>${esc(p.name)}</b><span class="kz-tag ${p.configured?'':'warn'}">${p.configured?'官方入口就绪':(String(p.auth_mode||'').startsWith('official_portal')?'官方门户':'需应用配置')}</span></div><div class="meta">${esc(p.notes||'')}<br>授权方式：${esc(p.auth_mode||'')}</div><div class="urls">官方授权入口：${esc(p.authorization_url||p.console_url||'未登记')}<br>官方API：${esc(p.api_base||'按平台能力另行验证')}</div><button data-login>${String(p.auth_mode||'').startsWith('official_portal')?'打开官方平台':(reauth?'重新授权':'新增此账号')}</button></div>`).join('')}</div>
      <div class="kz-auth-msg" id="kz-auth-msg">登录、扫码、验证码和授权都在平台官方页面完成；卡嘴子只保存授权结果和账号资产引用。</div>
    </div>`;
    document.body.appendChild(backdrop);backdrop.querySelector('.kz-auth-close').onclick=()=>backdrop.remove();backdrop.addEventListener('click',e=>{if(e.target===backdrop)backdrop.remove()});
    const msg=backdrop.querySelector('#kz-auth-msg');backdrop.querySelectorAll('[data-login]').forEach(btn=>btn.onclick=()=>{const card=btn.closest('.kz-provider');const provider=providers.find(x=>x.platform===card.dataset.platform);const label=backdrop.querySelector('#kz-auth-slot-label').value.trim();openOfficialLogin(provider,label,options.account_id||'',msg)});
  }

  function install(){
    style();const actions=document.querySelector('.top .actions');if(actions&&!document.getElementById('kz-add-account')){const btn=document.createElement('button');btn.id='kz-add-account';btn.className='kz-auth-add';btn.textContent='+ 新增账号';btn.onclick=()=>showModal().catch(e=>alert(e.message));actions.prepend(btn)}
    const panel=document.querySelector('.grid .panel');if(panel&&!document.getElementById('kz-account-safety-note')){const note=document.createElement('div');note.id='kz-account-safety-note';note.className='kz-auth-safety';note.innerHTML='<b>多账号原则</b><span>同一平台可保存账号1、账号2、账号3……；每个账号拥有独立 account_id、授权、环境档案和操作审计。重新授权不改历史归属。</span>';panel.insertBefore(note,panel.querySelector('#accounts'))}
  }

  window.addEventListener('message',event=>{if(event.origin!==location.origin)return;if(event.data?.type==='kz-auth-callback'){window.dispatchEvent(new CustomEvent('kz-auth-updated'))}});
  window.KZAuthUI={open:options=>showModal(options||{})};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
