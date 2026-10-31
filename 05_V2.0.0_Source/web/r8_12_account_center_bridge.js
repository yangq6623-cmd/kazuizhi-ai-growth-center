(() => {
  'use strict';

  const WRAP_ID = 'r812-account-center-wrap';
  const FRAME_ID = 'r812-account-center-frame';

  function hub(){ return document.getElementById('operational-hub'); }
  function oldFrame(){ return document.getElementById('operational-frame'); }

  function ensureStyle(){
    if(document.getElementById('r812-account-center-style')) return;
    const style=document.createElement('style');
    style.id='r812-account-center-style';
    style.textContent=`
      #${WRAP_ID}{display:none;margin-top:16px;width:100%;min-height:920px}
      #${WRAP_ID}.active{display:block}
      #${FRAME_ID}{width:100%;min-height:920px;border:0;border-radius:16px;background:#f4f7fb}
      #operational-hub.r812-account-mode #operational-frame{display:none!important}
    `;
    document.head.appendChild(style);
  }

  function ensureAccountCenter(){
    const root=hub(); if(!root) return null;
    ensureStyle();
    let wrap=document.getElementById(WRAP_ID);
    if(!wrap){
      wrap=document.createElement('div');
      wrap.id=WRAP_ID;
      wrap.innerHTML=`<iframe id="${FRAME_ID}" title="统一账号资产中心" src="/r8_12_account_center.html?embed=1"></iframe>`;
      const frame=oldFrame();
      if(frame?.parentNode) frame.parentNode.insertBefore(wrap,frame.nextSibling);
      else root.appendChild(wrap);
    }
    return wrap;
  }

  function setOuterTabActive(button){
    document.querySelectorAll('.r810-execution-tabs button').forEach(x=>x.classList.toggle('active',x===button));
  }

  function openAccountCenter(button){
    const root=hub(); const wrap=ensureAccountCenter();
    if(!root||!wrap) return;
    root.classList.add('r812-account-mode');
    wrap.classList.add('active');
    setOuterTabActive(button);
    wrap.scrollIntoView({behavior:'smooth',block:'start'});
  }

  function closeAccountCenter(){
    const root=hub(); const wrap=document.getElementById(WRAP_ID);
    root?.classList.remove('r812-account-mode');
    wrap?.classList.remove('active');
  }

  // R8-11 still owns all other execution tabs with a document-capture listener.
  // Register the R8-12 owner account route on WINDOW capture, which is earlier
  // in the event path than document capture, so “平台账号” deterministically opens
  // the durable account center instead of the retired Region+Service+bind-phone form.
  window.addEventListener('click',event=>{
    const button=event.target?.closest?.('.r810-execution-tabs button[data-execution-page]');
    if(!button) return;
    if(button.dataset.executionPage==='accounts'){
      event.preventDefault();
      event.stopImmediatePropagation();
      openAccountCenter(button);
      return;
    }
    closeAccountCenter();
  },true);

  // Also retire direct links/buttons that point to the legacy account page from
  // the parent owner shell. Technical compatibility APIs remain available only
  // as migration inputs; they are not the owner's normal operating surface.
  document.addEventListener('click',event=>{
    const button=event.target?.closest?.('[data-r812-account-center]');
    if(!button) return;
    event.preventDefault();
    openAccountCenter(document.querySelector('.r810-execution-tabs button[data-execution-page="accounts"]'));
  },true);

  window.KZR812AccountCenter={open:openAccountCenter,close:closeAccountCenter};
})();
