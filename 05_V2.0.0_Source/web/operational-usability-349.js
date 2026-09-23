(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const ACTIVE=new Set(['等待ChatGPT策划','等待素材路由','等待生产','生产中','技术质检','后期增强中','等待ChatGPT质检','等待人工审核','退回重做','已授权发布','等待账号','等待最佳时间','发布执行中','异常待处理']);

  if(!document.querySelector('link[data-r8-usability-349]')){
    const link=document.createElement('link');
    link.rel='stylesheet';link.href='/operational-usability-349.css';link.dataset.r8Usability349='1';document.head.appendChild(link);
  }

  function growthId(){const f=window.state?.factory||{};return String(window.getActiveGrowthId?.()||f.active_campaign_id||f.campaigns?.[0]?.id||'').trim()}
  function campaign(){const id=growthId();return (window.state?.factory?.campaigns||[]).find(x=>x.id===id)||null}
  function task(){const id=growthId();return (window.state?.factory?.videos||[]).find(x=>x.campaign_id===id&&ACTIVE.has(x.status))||null}
  function device(){const d=window.state?.device||{};const list=Array.isArray(d.devices)?d.devices:[];return list.find(x=>x?.device_id===d.primary_device_id&&x?.connected)||list.find(x=>x?.connected)||null}
  function go(page){window.changeOperationalPage?.(page)}
  function text(el,value){if(el)el.textContent=value}

  function handoffMessage(video){
    if(!video)return '';
    const handoff=video.chatgpt_handoff||{};
    const retries=Number(handoff.retry_count||0),max=Number(handoff.max_retries||3);
    if(video.plan_received_at||video.production_plan)return 'ChatGPT 生产合同已返回，正在进入本地执行。';
    if(video.status==='等待ChatGPT质检'&&handoff.phase==='waiting_response')return `成片质检请求已写入同步桥 · 等待 ChatGPT 返回 · 自动重试 ${retries}/${max}`;
    if(handoff.phase==='bridge_unavailable')return '尚未发送给 ChatGPT：双向同步桥未连接。系统会持续检查，恢复后自动发送。';
    if(handoff.phase==='retry_exhausted'||video.status==='异常待处理')return `ChatGPT 请求连续重发仍未返回 · 已停止无限等待 · 需要检查桥接/自动化。`;
    if(handoff.phase==='waiting_response')return `请求已写入 ChatGPT 同步桥 · 等待结构化返回 · 自动重试 ${retries}/${max}`;
    if(['等待ChatGPT策划','退回重做'].includes(video.status))return '正在准备把生产请求写入 ChatGPT 同步桥；当前不能证明 ChatGPT 已接收。';
    return [video.status,video.bottleneck].filter(Boolean).join(' · ');
  }

  function fixPlanningTruth(){
    const hero=byId('final-task-hero');if(!hero)return;
    let note=hero.querySelector('.hotfix-planning-truth');
    if(!note){note=document.createElement('small');note.className='hotfix-planning-truth';hero.appendChild(note)}
    const current=task();
    note.hidden=!current;
    note.classList.toggle('is-blocked',current?.chatgpt_handoff?.phase==='bridge_unavailable'||current?.chatgpt_handoff?.phase==='retry_exhausted'||current?.status==='异常待处理');
    note.classList.toggle('is-connected',current?.chatgpt_handoff?.phase==='waiting_response');
    if(current)note.textContent=handoffMessage(current);
  }

  function compactDashboard(){
    const page=byId('dashboard');if(!page)return;
    page.classList.add('usability-dashboard');
    const migration=page.querySelector('.migration-strip');if(migration)migration.hidden=true;
    const funnel=byId('funnel');if(funnel)funnel.hidden=true;
    const title=byId('page-title');if(window.state?.currentPage==='dashboard'&&title)title.textContent='今天要什么结果、现在卡在哪里';
    const current=task();
    const list=byId('today-tasks');
    if(list){
      const line=current?handoffMessage(current):'当前没有活动内容任务。';
      list.innerHTML=`<div class="usability-current-bottleneck"><small>当前卡点</small><b>${current?current.status:'无活动任务'}</b><span>${line}</span></div>${current?.auto_action?`<div class="usability-auto-action"><small>系统下一步</small><span>${current.auto_action}</span></div>`:''}`;
    }
  }

  function campaignEntry(){
    const page=byId('campaigns');if(!page)return;
    page.classList.add('usability-campaigns');
    const duplicate=page.querySelector('[data-final-ui-new-campaign]');if(duplicate)duplicate.hidden=true;
    const details=page.querySelector('.final-new-campaign');
    const summary=details?.querySelector(':scope>summary');
    if(summary)summary.textContent=campaign()?'＋ 创建新增长战役':'＋ 创建第一个增长战役';
  }

  function materialIntake(){
    const kind=byId('asset-kind');if(kind?.closest('label')){kind.closest('label').hidden=true;kind.closest('label').style.display='none'}
    const input=byId('asset-file');if(input){input.multiple=true;input.accept='image/*,video/*,audio/*'}
    const zone=byId('optional-materials')||input?.closest('.asset-intake');if(!zone)return;
    zone.classList.add('usability-material-drop');
    let helper=zone.querySelector('.usability-material-helper');
    if(!helper){helper=document.createElement('div');helper.className='usability-material-helper';helper.innerHTML='<b>把照片、视频或音频直接拖到这里</b><span>本地素材是可选增强；支持多文件，系统自动识别类型、去重、索引和评分。</span>';zone.prepend(helper)}
    if(zone.dataset.usabilityDropReady)return;zone.dataset.usabilityDropReady='1';
    zone.addEventListener('dragover',event=>{event.preventDefault();zone.classList.add('dragging')});
    zone.addEventListener('dragleave',()=>zone.classList.remove('dragging'));
    zone.addEventListener('drop',event=>{
      event.preventDefault();zone.classList.remove('dragging');
      if(!input||!event.dataTransfer?.files?.length)return;
      try{input.files=event.dataTransfer.files;byId('asset-upload')?.click()}catch(_){window.notify?.('浏览器未允许直接接收拖放文件，请使用“选择文件”多选上传','error')}
    });
  }

  function accountFlow(){
    const page=byId('accounts'),form=byId('account-form');if(!page||!form)return;
    page.classList.add('usability-accounts');
    let flow=page.querySelector('.usability-account-flow');
    if(!flow){
      flow=document.createElement('div');flow.className='usability-account-flow';
      flow.innerHTML='<span>1 连接真机</span><span>2 平台登录</span><span>3 系统验证</span><span>4 建立账号</span><span>5 获得发布资格</span>';
      form.closest('.two-col')?.insertAdjacentElement('beforebegin',flow);
    }
    const d=device(),submit=form.querySelector('button[type="submit"],button[data-usability-go]');
    const fields=[...form.querySelectorAll('input,select')].filter(el=>el.id!=='account-status');
    if(!d){
      fields.forEach(el=>{el.disabled=true;el.title='请先连接真实手机'});
      if(submit){submit.type='button';submit.dataset.usabilityGo='device';submit.textContent='去连接手机';submit.disabled=false;submit.title='进入“终端与真机”，连接USB并完成调试授权'}
      flow.dataset.stage='device';
    }else{
      fields.forEach(el=>{el.disabled=false;el.removeAttribute('title')});
      if(submit){submit.type='submit';delete submit.dataset.usabilityGo;submit.textContent='保存账号并绑定真机';submit.disabled=false;submit.title='保存账号档案；发布资格仍由真实平台验证决定'}
      flow.dataset.stage='login';
    }
  }

  function disabledReasons(){
    const d=device();
    const reason=d?'当前状态尚未满足该操作条件':'请先连接 USB，并在手机上允许调试，然后点击“扫描手机”';
    document.querySelectorAll('#device button:disabled').forEach(button=>{button.title=reason;button.setAttribute('aria-label',`${button.textContent.trim()}：${reason}`)});
    document.querySelectorAll('button:disabled').forEach(button=>{if(!button.title)button.title='当前条件未满足；完成页面提示的前置步骤后会自动开放'});
    const toolbar=byId('device')?.querySelector('.device-toolbar');
    let hint=toolbar?.querySelector('.usability-device-hint');
    if(toolbar&&!d){if(!hint){hint=document.createElement('small');hint.className='usability-device-hint';toolbar.appendChild(hint)}hint.textContent='其余按钮暂不可用：先连接 USB → 手机允许调试 → 点击“扫描手机”。'}
    else hint?.remove();
  }

  function healthCategories(){
    const page=byId('health');if(!page)return;
    page.classList.add('usability-health');
    const items=[...page.querySelectorAll('.check-item')];
    items.forEach(item=>{
      const value=item.textContent||'';
      item.classList.remove('usability-human','usability-auto','usability-build');
      if(value.includes('社媒账号授权')||value.includes('验证码')||value.includes('人脸'))item.classList.add('usability-human');
      else if(value.includes('小程序与订单归因')||value.includes('SEO与GEO技术底座'))item.classList.add('usability-build');
      else if(value.includes('手机与真机执行'))item.classList.add('usability-auto');
      const button=item.querySelector('button');
      if(button&&!button.dataset.usabilityGo){
        if(value.includes('手机与真机'))button.dataset.usabilityGo='device';
        else if(value.includes('社媒账号'))button.dataset.usabilityGo='accounts';
        else if(value.includes('小程序与订单'))button.dataset.usabilityGo='conversion';
        else if(value.includes('SEO'))button.dataset.usabilityGo='search';
      }
    });
    const summary=byId('final-health-summary');
    if(summary){
      const human=items.filter(x=>x.classList.contains('usability-human')&&!x.textContent.includes('通过')).length;
      const auto=items.filter(x=>x.classList.contains('usability-auto')&&!x.textContent.includes('通过')).length;
      const build=items.filter(x=>x.classList.contains('usability-build')&&!x.textContent.includes('通过')).length;
      const boxes=[...summary.children];
      if(boxes[0])boxes[0].innerHTML=`<small>系统总体状态</small><b>${human?'有人工事项':'没有人工阻塞'}</b><span>人工 ${human} · 自动处理中 ${auto} · 建设项 ${build}</span>`;
      if(boxes[1])boxes[1].innerHTML=`<small>需人工</small><b>${human}</b><span>登录 / 验证 / 风控</span>`;
      if(boxes[2])boxes[2].innerHTML=`<small>自动处理中</small><b>${auto}</b><span>设备检查 / 自动恢复</span>`;
      if(boxes[3])boxes[3].innerHTML=`<small>建设项</small><b>${build}</b><span>SEO / 数据链 / 归因</span>`;
    }
  }

  function apply(){
    document.body.classList.add('r8-usability-349');
    fixPlanningTruth();compactDashboard();campaignEntry();materialIntake();accountFlow();disabledReasons();healthCategories();
  }

  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-usability-go]');
    if(button){event.preventDefault();event.stopImmediatePropagation();go(button.dataset.usabilityGo)}
  },true);

  const later=()=>window.setTimeout(apply,0);
  window.addEventListener('operational:refreshed',later);
  window.addEventListener('operational:device-status',later);
  window.addEventListener('operational:page-changed',later);
  window.addEventListener('operational:search-updated',later);
  apply();window.setTimeout(apply,350);window.setTimeout(apply,1200);
})();
