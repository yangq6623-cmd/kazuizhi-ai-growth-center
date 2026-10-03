(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const ACTIVE_VIDEO_STATES=new Set(['等待ChatGPT策划','等待素材路由','等待生产','生产中','技术质检','等待ChatGPT质检','等待人工审核','退回重做','已授权发布','等待账号','等待最佳时间','发布执行中','异常待处理']);
  const PLATFORM_IDS={'抖音':'douyin','小红书':'xiaohongshu','快手':'kuaishou','视频号':'wechat_channels','微博':'weibo','哔哩哔哩':'bilibili','B站':'bilibili'};

  async function json(path,options){
    const response=await fetch(path,options);
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.error||`本地服务返回 ${response.status}`);
    return data;
  }
  function activeGrowthId(){
    const f=window.state?.factory||{};
    const active=String(f.active_campaign_id||'').trim();
    if(active)return active;
    return String((f.campaigns||[])[0]?.id||'');
  }
  window.getActiveGrowthId=activeGrowthId;

  function activeCampaign(){
    const id=activeGrowthId();
    return (window.state?.factory?.campaigns||[]).find(x=>x.id===id)||null;
  }
  function connectedDevice(){
    const d=window.state?.device||{};
    const list=Array.isArray(d.devices)?d.devices:[];
    return list.find(x=>x?.device_id===d.primary_device_id&&x?.connected)||list.find(x=>x?.connected)||null;
  }
  function activeVideo(campaignId=activeGrowthId()){
    return (window.state?.factory?.videos||[]).find(x=>x.campaign_id===campaignId&&ACTIVE_VIDEO_STATES.has(x.status))||null;
  }
  function finalVideoStage(){
    const video=activeVideo();
    if(!video)return activeCampaign()?0:-1;
    if(['等待人工审核'].includes(video.status))return 2;
    if(['已授权发布','等待账号','等待最佳时间','发布执行中'].includes(video.status))return 3;
    if(video.status==='已验证发布')return 4;
    return 1;
  }

  async function setActiveGrowthId(id,{silent=false}={}){
    id=String(id||'').trim();
    if(!id||id===activeGrowthId())return;
    try{
      await json('/api/content-factory/active-campaign',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({campaign_id:id})});
      if(window.state?.factory)window.state.factory.active_campaign_id=id;
      syncGlobalGrowthContext();
      if(!silent)window.notify?.(`当前增长ID已切换为 ${id}`);
    }catch(error){window.notify?.(error.message,'error')}
  }
  window.setActiveGrowthId=setActiveGrowthId;

  function syncGlobalGrowthContext(){
    const id=activeGrowthId();
    ['video-campaign','search-campaign'].forEach(selectId=>{
      const select=byId(selectId);if(!select||!id)return;
      const exists=[...select.options].some(o=>o.value===id);
      if(exists&&select.value!==id)select.value=id;
    });
    document.querySelectorAll('.context-strip span:first-child b').forEach(node=>{node.textContent=id||'未选择'});
    const campaign=activeCampaign();
    document.querySelectorAll('[data-active-growth-summary]').forEach(node=>{
      node.textContent=campaign?`${campaign.id} · ${campaign.region} · ${campaign.service} · ${campaign.title}`:'尚未建立增长战役';
    });
  }

  function actionCenter(){
    const center=window.state?.factory?.action_center;
    return center&&Array.isArray(center.human_items)?center:{human_count:0,human_items:[]};
  }
  function renderUnifiedOwnerActions(){
    const center=actionCenter();
    const count=Number(center.human_count||center.human_items.length||0);
    const nav=document.querySelector('.nav.ui-owner-todo');
    const badge=nav?.querySelector('.ui-nav-badge');
    if(badge){badge.textContent=String(count);badge.classList.toggle('zero',count===0)}
    const panel=byId('owner-todo');
    if(panel){
      panel.innerHTML=`<div class="panel-head"><div><p>只显示真正需要你决定或亲自验证的事项</p><h3>待我处理 ${count} 项</h3></div><span class="owner-ready ${count?'':'all-clear'}">${count?'需要处理':'当前无人工阻塞'}</span></div>${count?`<div class="owner-todo-list">${center.human_items.map(item=>`<article class="owner-todo-item human"><div><b>${esc(item.title)}</b><span>${esc(item.detail)}</span></div><button data-owner-target="${esc(item.page)}">${esc(item.action||'查看')}</button></article>`).join('')}</div>`:'<div class="owner-empty">当前没有必须由你处理的事项。SEO、数据接入等建设项继续在系统体检中显示，但不冒充日常人工阻塞。</div>'}`;
    }
    const dashboardStep=byId('dashboard')?.querySelector(':scope > .page-next-step');
    if(dashboardStep){
      const b=dashboardStep.querySelector('b'),span=dashboardStep.querySelector('span'),button=dashboardStep.querySelector('button');
      if(count){
        const first=center.human_items[0];
        if(b)b.textContent=`先处理 ${count} 项人工事项`;
        if(span)span.textContent=first?.title||'有事项需要人工决定。';
        if(button){button.textContent=first?.action||'查看待办';button.dataset.finalTarget=first?.page||'dashboard'}
      }else{
        if(b)b.textContent='今天没有人工阻塞';
        if(span)span.textContent='系统可以继续按已授权范围推进；建设项不计入日常待办。';
        if(button){button.textContent='查看体检';button.dataset.finalTarget='health'}
      }
    }
  }

  function syncDashboardTruth(){
    const dashboard=byId('dashboard');if(!dashboard)return;
    const goal=byId('order-goal');
    if(goal)goal.textContent='待接入 / 50';
    const goalBox=dashboard.querySelector('.goal');
    const goalLast=goalBox?.querySelector(':scope > span');
    if(goalLast)goalLast.textContent='真实经营数据接入后自动显示实际完成数';
    const stages=[...dashboard.querySelectorAll('.pipeline article')];
    stages.forEach(x=>x.classList.remove('focus','live-stage'));
    const index=finalVideoStage();
    if(index>=0&&stages[index])stages[index].classList.add('focus','live-stage');
    const migration=dashboard.querySelector('.migration-strip');
    if(migration){
      migration.classList.add('deep-migration-quiet');
      const b=migration.querySelector('b');if(b)b.textContent='✓ 数据与配置已安全保留';
    }
  }

  function syncContentTaskState(){
    const select=byId('video-campaign');
    const create=byId('create-video');
    if(!create)return;
    const campaignId=select?.value||activeGrowthId();
    const task=activeVideo(campaignId);
    if(task){
      create.disabled=true;create.setAttribute('aria-disabled','true');
      create.dataset.deepLocked='1';
      create.textContent=`当前任务：${task.status}`;
      create.title=`同一增长ID已有生产任务 ${task.id}，系统不会重复创建`;
      let hint=create.parentElement?.querySelector('.deep-task-lock');
      if(!hint){hint=document.createElement('small');hint.className='deep-task-lock';create.insertAdjacentElement('afterend',hint)}
      hint.textContent=`${task.id} 正在 ${task.status}；完成、发布或明确终止前不会重复创建。`;
    }else{
      if(create.dataset.deepLocked){
        create.disabled=!campaignId;create.setAttribute('aria-disabled',campaignId?'false':'true');
        create.textContent='开始 AI 自动生产';create.title=campaignId?'':'请先建立增长战役';delete create.dataset.deepLocked;
      }
      create.parentElement?.querySelector('.deep-task-lock')?.remove();
    }
  }

  async function uploadFiles(files){
    const campaignId=byId('video-campaign')?.value||activeGrowthId();
    const consent=!!byId('asset-consent')?.checked;
    const list=[...files||[]];
    if(!campaignId)return window.notify?.('请先建立增长战役','error');
    if(!list.length)return window.notify?.('请选择或拖入照片、视频、音频','error');
    if(!consent)return window.notify?.('请先确认你拥有这些素材的使用权及必要授权','error');
    const status=byId('asset-upload-status');
    const button=byId('asset-upload');if(button){button.disabled=true;button.textContent=`正在导入 0/${list.length}`}
    let ok=0;
    try{
      for(const file of list){
        if(status)status.textContent=`正在导入 ${ok+1}/${list.length}：${file.name}`;
        const response=await fetch('/api/content-factory/assets/upload',{method:'POST',headers:{
          'Content-Type':'application/octet-stream','X-Campaign-ID':encodeURIComponent(campaignId),
          'X-Filename':encodeURIComponent(file.name),'X-Consent-Confirmed':'true'
        },body:file});
        const data=await response.json().catch(()=>({}));
        if(!response.ok)throw new Error(`${file.name}：${data.error||response.status}`);
        ok+=1;if(button)button.textContent=`正在导入 ${ok}/${list.length}`;
      }
      const input=byId('asset-file');if(input)input.value='';
      if(status)status.textContent=`已导入 ${ok} 个素材。系统自动识别类型、去重和索引；是否采用由 ChatGPT 决定。`;
      await window.refreshAll?.();
      window.notify?.(`已批量导入 ${ok} 个素材`);
    }catch(error){
      if(status)status.textContent=`已完成 ${ok}/${list.length}；${error.message}`;
      window.notify?.(error.message,'error');
    }finally{
      if(button){button.disabled=false;button.textContent='批量导入素材'}
      syncContentTaskState();
    }
  }

  function setupMaterialDrop(){
    const panel=byId('optional-materials');if(!panel||panel.dataset.deepReady)return;
    panel.dataset.deepReady='1';
    const kind=byId('asset-kind');if(kind?.closest('label'))kind.closest('label').hidden=true;
    const input=byId('asset-file');
    if(input){input.multiple=true;input.accept='video/*,image/*,audio/*';const label=input.closest('label');if(label)label.childNodes[0].textContent='选择或批量拖入本地素材（可选）'}
    const consent=byId('asset-consent');if(consent?.parentElement)consent.parentElement.lastChild.textContent=' 我确认拥有本次上传素材的使用权及必要的拍摄/发布授权';
    const upload=byId('asset-upload');if(upload)upload.textContent='批量导入素材';
    panel.classList.add('deep-drop-zone');
    const helper=document.createElement('div');helper.className='deep-drop-helper';helper.innerHTML='<b>照片、视频、音频直接扔进来</b><span>支持多选与拖放；无需手工分类，系统自动识别、去重、索引和评分。</span>';
    panel.querySelector('.optional-head')?.insertAdjacentElement('afterend',helper);
    panel.addEventListener('dragover',event=>{event.preventDefault();panel.classList.add('dragging')});
    panel.addEventListener('dragleave',()=>panel.classList.remove('dragging'));
    panel.addEventListener('drop',event=>{event.preventDefault();panel.classList.remove('dragging');uploadFiles(event.dataTransfer?.files)});
  }

  function truthAccountStatus(){
    const label=byId('account-status')?.closest('label');
    if(label)label.hidden=true;
    const form=byId('account-form');if(!form)return;
    let box=form.querySelector('.deep-account-truth');
    if(!box){box=document.createElement('div');box.className='deep-account-truth full';const submit=form.querySelector('button[type="submit"]');submit?.insertAdjacentElement('beforebegin',box)}
    const device=connectedDevice();
    box.innerHTML=`<small>真实连接状态</small><b>${device?'待平台登录验证':'请先连接真实手机'}</b><span>${device?`将绑定 ${esc(device.model||device.device_id)}；“已验证可发布”只能由真实平台/终端验证器写入。`:'账号不能通过下拉框自行标记为“已验证可发布”。'}</span>`;
    const submit=form.querySelector('button[type="submit"]');if(submit)submit.textContent=device?'保存账号并绑定真机':'先连接真机再建账号';
  }

  async function submitRealAccount(form){
    const device=connectedDevice();
    if(!device){window.notify?.('请先到“终端与真机”连接真实手机','error');window.changeOperationalPage?.('device');return}
    const platformName=byId('account-platform')?.value||'';
    const platform=PLATFORM_IDS[platformName];
    const alias=byId('account-name')?.value?.trim()||'';
    if(!platform)return window.notify?.('当前平台暂未接入真实账号绑定','error');
    if(!alias)return window.notify?.('请填写账号名称','error');
    const button=form.querySelector('button[type="submit"]');if(button){button.disabled=true;button.textContent='正在绑定…'}
    try{
      await json('/api/r8/social/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        platform,device_id:device.device_id,alias,label:alias,role:'service',
        region:byId('account-region')?.value||'',service_category:byId('account-service')?.value||'',automation_level:'L2'
      })});
      await window.refreshAll?.();
      window.notify?.('账号已绑定真实终端；请在手机端完成登录，系统验证通过后才会开放发布');
    }catch(error){window.notify?.(error.message,'error')}
    finally{if(button){button.disabled=false;truthAccountStatus()}}
  }

  function setupAccountTruth(){
    truthAccountStatus();
    const list=byId('account-list');if(list)list.classList.add('truth-account-list');
  }

  function setupDeviceAdvanced(){
    const actions=document.querySelector('#device .phone-actions');if(!actions||actions.dataset.deepReady)return;
    actions.dataset.deepReady='1';
    const visible=new Set(['back','home','wake','recents']);
    const advanced=[...actions.querySelectorAll('button')].filter(btn=>{
      const action=btn.dataset.deviceAction||btn.dataset.finalDeviceAction||'';
      return !visible.has(action);
    });
    if(advanced.length){
      const details=document.createElement('details');details.className='deep-device-more';details.innerHTML='<summary>更多设备控制</summary><div></div>';
      advanced.forEach(btn=>details.querySelector('div').appendChild(btn));actions.appendChild(details);
    }
    localizeDeviceStates();
  }
  function localizeDeviceStates(){
    ['device-business-context','device-adb'].forEach(id=>{
      const root=byId(id);if(!root)return;
      root.querySelectorAll('b,span,p').forEach(node=>{if(node.textContent.trim()==='unknown')node.textContent='未验证'});
    });
  }

  function toneSystemLink(){
    const link=document.querySelector('.r7-console-link');if(!link)return;
    const b=link.querySelector('b'),small=link.querySelector('small');
    if(b)b.textContent='高级设置 / 系统管理';
    if(small)small.textContent='任务、数据、历史与系统配置';
    link.classList.add('deep-system-link');
  }

  function hideUnownedFloatingControls(){
    // Only remove controls that explicitly identify themselves as decorative /
    // unbound assistants. Browser extensions are outside the app DOM and are untouched.
    document.querySelectorAll('[data-assistant-placeholder],.assistant-placeholder,.floating-assistant-placeholder').forEach(node=>node.remove());
  }

  function refreshDeep(){
    syncGlobalGrowthContext();
    renderUnifiedOwnerActions();
    syncDashboardTruth();
    syncContentTaskState();
    setupMaterialDrop();
    setupAccountTruth();
    setupDeviceAdvanced();
    localizeDeviceStates();
    toneSystemLink();
    hideUnownedFloatingControls();
  }

  document.addEventListener('change',event=>{
    if(event.target?.id==='video-campaign'||event.target?.id==='search-campaign')setActiveGrowthId(event.target.value,{silent:true});
  });
  document.addEventListener('click',event=>{
    if(event.target?.closest?.('#asset-upload')){event.preventDefault();event.stopImmediatePropagation();uploadFiles(byId('asset-file')?.files);}
  },true);
  document.addEventListener('submit',event=>{
    const form=event.target?.closest?.('#account-form');if(!form)return;
    event.preventDefault();event.stopImmediatePropagation();submitRealAccount(form);
  },true);

  window.addEventListener('operational:refreshed',refreshDeep);
  window.addEventListener('operational:device-status',refreshDeep);
  window.addEventListener('operational:search-updated',refreshDeep);
  refreshDeep();
  window.setTimeout(refreshDeep,300);
  window.setTimeout(refreshDeep,1000);
})();
