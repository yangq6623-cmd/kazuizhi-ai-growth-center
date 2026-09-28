(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const labels={dashboard:'执行总览',campaigns:'增长目标',content:'AI 内容生产中心',accounts:'发布准备',conversion:'咨询与订单',search:'SEO / GEO 增长',health:'运行健康'};

  function localStrip(){
    const page=byId('content');
    if(!page)return;
    let strip=byId('execution-local-strip');
    if(!strip){
      strip=document.createElement('section');
      strip.id='execution-local-strip';
      strip.className='execution-local-strip';
      const anchor=byId('final-task-hero')||page.querySelector('.page-intro');
      anchor?.insertAdjacentElement('afterend',strip);
    }
    strip.innerHTML='<article><small>生产方式</small><b>ChatGPT 总控，本地节点执行</b><span>总控拆解目标、标题、脚本、分镜与验收标准。</span></article><article><small>本地执行</small><b>模型、语音、剪辑按任务分工</b><span>Ollama、本地语音和剪辑工具只处理已下达任务。</span></article><article><small>质量闸门</small><b>只生成候选，不虚报完成</b><span>质量检查不通过自动退回，不进入发布队列。</span></article><article><small>发布边界</small><b>人工确认后才可对外</b><span>登录、验证码、平台发布与真实回执始终由本人确认。</span></article>';
  }

  function accountNote(){
    const page=byId('accounts');
    if(!page||byId('execution-account-note'))return;
    const note=document.createElement('div');
    note.id='execution-account-note';note.className='execution-local-note';
    note.innerHTML='<b>发布准备不依赖 USB。</b>系统可完成内容候选、排期建议和质量检查；账号登录、验证码、人脸验证和最终发布仍由本人在对应平台完成。';
    (page.querySelector('.page-intro')||page.firstElementChild)?.insertAdjacentElement('afterend',note);
  }

  function replaceLegacyTargets(){
    document.querySelectorAll('[data-final-target="device"],[data-owner-target="device"],[data-usability-go="device"],[data-final-ui-go="device"]').forEach(button=>{
      if(button.dataset.finalTarget!==undefined)button.dataset.finalTarget='accounts';
      if(button.dataset.ownerTarget!==undefined)button.dataset.ownerTarget='accounts';
      if(button.dataset.usabilityGo!==undefined)button.dataset.usabilityGo='accounts';
      if(button.dataset.finalUiGo!==undefined)button.dataset.finalUiGo='accounts';
      if(/真机|手机|终端/.test(button.textContent||''))button.textContent='查看发布准备';
    });
  }

  function removeDeviceHealthGate(){
    const list=byId('health-list');
    if(!list)return;
    [...list.querySelectorAll('.check-item')].forEach(item=>{
      if(/手机与真机|终端与真机|真机执行/.test(item.textContent||''))item.remove();
    });
  }

  function apply(){
    document.body.classList.add('r8-execution-simplified');
    document.querySelectorAll('.nav[data-page]').forEach(button=>{
      const page=button.dataset.page;
      if(page==='device'){button.hidden=true;return;}
      if(labels[page]&&button.textContent!==labels[page])button.textContent=labels[page];
    });
    byId('device')?.setAttribute('hidden','');
    replaceLegacyTargets();
    removeDeviceHealthGate();
    localStrip();
    accountNote();
  }

  document.addEventListener('click',event=>{
    const go=event.target.closest('[data-owner-target="device"],[data-final-target="device"],[data-usability-go="device"],[data-final-ui-go="device"]');
    if(!go)return;
    event.preventDefault();event.stopImmediatePropagation();
    window.changeOperationalPage?.('accounts');
  },true);
  window.addEventListener('operational:refreshed',apply);
  window.addEventListener('operational:page-changed',apply);
  apply();window.setTimeout(apply,350);window.setTimeout(apply,1100);
})();
