(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const labels={dashboard:'执行总览',campaigns:'增长目标',content:'AI 内容生产中心',accounts:'发布准备',conversion:'咨询与订单',search:'SEO / GEO 增长',health:'运行健康'};

  function keepOneProductionFlow(){
    // 内容页已经有“总控分配台”。旧版又叠加一张蓝色说明卡，造成同一流程讲两遍。
    // 只保留原有的四步总控卡，并删除历史版本留下的重复卡。
    byId('execution-local-strip')?.remove();
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
    keepOneProductionFlow();
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
