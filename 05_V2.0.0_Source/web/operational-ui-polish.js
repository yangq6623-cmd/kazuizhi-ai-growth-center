(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const ACTIVE_VIDEO_STATES=new Set(['等待ChatGPT策划','等待素材路由','等待生产','生产中','技术质检','等待ChatGPT质检','等待人工审核','退回重做','已授权发布','等待账号','等待最佳时间','发布执行中','异常待处理']);

  function deviceOnline(){
    const payload=window.state?.device||{};
    const devices=Array.isArray(payload.devices)?payload.devices:[];
    return devices.some(item=>item?.connected);
  }

  function ownerCount(){
    const center=window.state?.factory?.action_center||{};
    return Number(center.human_count||0);
  }

  function ensureOwnerNav(){
    const dashboard=document.querySelector('.nav[data-page="dashboard"]');
    if(!dashboard)return;
    let button=document.querySelector('.nav.ui-owner-todo');
    if(!button){
      button=document.createElement('button');
      button.type='button';
      button.className='nav ui-owner-todo';
      button.innerHTML='<span>待我处理</span><i class="ui-nav-badge zero">0</i>';
      dashboard.insertAdjacentElement('afterend',button);
      button.addEventListener('click',()=>{
        window.changeOperationalPage?.('dashboard');
        window.setTimeout(()=>byId('owner-todo')?.scrollIntoView({behavior:'smooth',block:'start'}),60);
      });
    }
    const badge=button.querySelector('.ui-nav-badge');
    const count=ownerCount();
    if(badge){badge.textContent=String(count);badge.classList.toggle('zero',count===0)}
  }

  function quietSamePageStep(pageName){
    const page=byId(pageName);if(!page)return;
    const step=page.querySelector(':scope > .page-next-step');
    if(!step)return;
    const button=step.querySelector('[data-final-target]');
    step.classList.toggle('ui-quiet-step',button?.dataset.finalTarget===pageName);
  }

  function polishCampaignPage(){
    const page=byId('campaigns');if(!page)return;
    page.classList.add('ui-campaigns');
    const intro=page.querySelector('.page-intro');
    if(intro){
      const h2=intro.querySelector('h2'),span=intro.querySelector('span');
      if(h2)h2.textContent='创建一个真实增长战役';
      if(span)span.textContent='告诉 ChatGPT 一个真实业务问题，后续内容、生产、发布和复盘自动沿同一个增长ID推进。';
    }
    const columns=page.querySelector('.two-col');
    const panels=columns?.querySelectorAll(':scope > .panel')||[];
    const main=panels[0],side=panels[1];
    if(main){
      main.classList.add('campaign-main');
      const h3=main.querySelector(':scope > h3');if(h3)h3.textContent='创建增长战役';
      if(!main.querySelector('.campaign-helper')){
        const helper=document.createElement('p');helper.className='campaign-helper';helper.innerHTML='<b>只需要填写真实问题。</b> 不需要提前准备脚本、素材或平台方案。';
        h3?.insertAdjacentElement('afterend',helper);
      }
      const submit=main.querySelector('button[type="submit"]');if(submit)submit.textContent='创建战役并自动开始';
    }
    if(side){
      side.classList.add('campaign-side');
      side.innerHTML='<p class="hint-title">ChatGPT 自动完成</p><h3>创建后无需管理中间步骤</h3><ul class="plain-list"><li>判断用户痛点、选题和内容方向</li><li>生成标题、深层脚本、分镜和平台版本</li><li>自动选择本地素材，缺素材时自动走安全替代方案</li><li>生产、质检、排期、发布与数据回流持续绑定增长ID</li></ul><p class="truth">最终经营结果仍以真实咨询、需求和订单为准，不把播放量直接当作成功。</p>';
    }
    const wide=page.querySelector(':scope > .panel.wide');
    if(wide){
      wide.classList.add('campaign-recent');
      const title=wide.querySelector('.panel-head h3');if(title)title.textContent='最近增长战役';
      const p=wide.querySelector('.panel-head p');if(p)p.textContent='历史与当前任务';
      const refresh=byId('refresh-campaigns');if(refresh)refresh.textContent='刷新战役';
    }
    quietSamePageStep('campaigns');
  }

  function ensureOptionalMaterials(producer,workspace){
    const intake=producer?.querySelector('.asset-intake');
    if(!intake||byId('optional-materials'))return;
    const panel=document.createElement('section');
    panel.id='optional-materials';
    panel.className='panel optional-materials';
    panel.innerHTML='<div class="optional-head"><div><p>可选增强资源</p><h3>本地素材投递箱</h3></div><span class="optional-badge">不上传也能正常生产</span></div>';
    panel.appendChild(intake);
    workspace?.insertAdjacentElement('afterend',panel);
    const cta=byId('video-cta')?.closest('label');
    if(cta){
      let details=panel.querySelector('.advanced-options');
      if(!details){details=document.createElement('details');details.className='advanced-options';details.innerHTML='<summary>高级选项</summary>';panel.appendChild(details)}
      details.appendChild(cta);
      const text=cta.childNodes[0];if(text)text.textContent='行动提示（可选，默认由 ChatGPT 判断）';
    }
    const script=byId('video-script')?.closest('label');
    if(script)script.remove();
  }

  function engineSummary(){
    const worker=window.state?.worker||{};
    const ok=!!worker.ffmpeg_found;
    const busy=!!worker.busy;
    const queue=Number(worker.queue_depth||0);
    const gpu=worker.gpu?.description||'RTX 3060';
    return {ok,busy,queue,gpu,encoding:worker.nvenc?'NVENC':'兼容编码'};
  }

  function ensureEngineDetails(engine){
    if(!engine)return;
    engine.classList.add('content-engine');
    let strip=engine.querySelector('.ui-engine-strip');
    if(!strip){strip=document.createElement('div');strip.className='ui-engine-strip';const h3=engine.querySelector(':scope > h3');h3?.insertAdjacentElement('afterend',strip)}
    const info=engineSummary();
    strip.innerHTML=`<strong>本地生产引擎</strong><span class="ui-engine-pill ${info.ok?'ok':'wait'}">${info.ok?(info.busy?'生产中':'正常'):'待检查'}</span><span>${esc(info.gpu)}</span><span>队列 ${info.queue}</span><span>${esc(info.encoding)}</span>`;
    let details=engine.querySelector(':scope > details.ui-engine-details');
    if(!details){
      details=document.createElement('details');details.className='ui-engine-details';details.innerHTML='<summary>查看技术详情与自动执行说明</summary>';
      engine.appendChild(details);
    }
    const worker=byId('video-worker-status');
    const list=engine.querySelector(':scope > .plain-list');
    const truth=engine.querySelector(':scope > .truth');
    const completion=byId('content-v2-status');
    [worker,completion,list,truth].forEach(node=>{if(node&&node.parentElement!==details)details.appendChild(node)});
  }

  function polishContentPage(){
    const page=byId('content');if(!page)return;
    page.classList.add('ui-content');
    const intro=page.querySelector('.page-intro');
    if(intro){
      const h2=intro.querySelector('h2'),span=intro.querySelector('span');
      if(h2)h2.textContent='从增长目标到最终成片';
      if(span)span.textContent='ChatGPT 负责策划、素材决策、平台适配与内容质检；本地程序和 RTX 3060 只负责执行。';
    }
    const workspace=page.querySelector('.three-col');
    if(!workspace)return;
    workspace.classList.add('content-workspace');
    const panels=workspace.querySelectorAll(':scope > .panel');
    const producer=panels[0],review=panels[1],engine=panels[2];
    if(producer){
      producer.classList.add('content-producer');
      const p=producer.querySelector(':scope > p'),h3=producer.querySelector(':scope > h3');
      if(p)p.textContent='生产控制';if(h3)h3.textContent='创建自动生产任务';
      const create=byId('create-video');if(create&&!create.dataset.deepLocked)create.textContent='开始 AI 自动生产';
      const note=create?.nextElementSibling;if(note?.tagName==='SMALL'&&!note.classList.contains('deep-task-lock'))note.textContent='本地素材是可选增强资源；没有素材也不会阻塞生产。';
    }
    if(review){
      review.classList.add('content-review');
      const p=review.querySelector(':scope > p'),h3=review.querySelector(':scope > h3');
      if(p)p.textContent='待我审核';if(h3)h3.textContent='只看最终成片';
    }
    if(engine){
      const p=engine.querySelector(':scope > p'),h3=engine.querySelector(':scope > h3');
      if(p)p.textContent='生产引擎';if(h3)h3.textContent='系统自动运行';
      ensureEngineDetails(engine);
    }
    ensureOptionalMaterials(producer,workspace);
    const select=byId('video-campaign');
    const active=window.state?.factory?.active_campaign_id;
    const campaigns=window.state?.factory?.campaigns||[];
    if(select&&!select.value){select.value=active||campaigns[0]?.id||''}
    quietSamePageStep('content');
  }

  function setButtonState(button,enabled,reason='',visibleReason=false){
    if(!button)return;
    button.disabled=!enabled;
    button.setAttribute('aria-disabled',enabled?'false':'true');
    button.title=enabled?'':reason;
    const key=button.id||button.dataset.pageTarget||'action';
    const parent=button.parentElement;
    let helper=parent?.querySelector(`.button-reason[data-for="${key}"]`);
    if(!enabled&&visibleReason&&parent){
      if(!helper){helper=document.createElement('small');helper.className='button-reason';helper.dataset.for=key;button.insertAdjacentElement('afterend',helper)}
      helper.textContent=reason;
    }else if(helper)helper.remove();
  }

  function syncActionStates(){
    const campaignTitle=byId('campaign-title')?.value?.trim()||'';
    const campaignSubmit=byId('campaign-form')?.querySelector('button[type="submit"]');
    setButtonState(campaignSubmit,!!campaignTitle,'请先填写用户问题或选题',true);

    const campaign=byId('video-campaign')?.value||window.state?.factory?.active_campaign_id||'';
    const activeTask=(window.state?.factory?.videos||[]).find(item=>item.campaign_id===campaign&&ACTIVE_VIDEO_STATES.has(item.status));
    if(activeTask){
      setButtonState(byId('create-video'),false,`已有任务 ${activeTask.id} · ${activeTask.status}`,true);
      const create=byId('create-video');if(create){create.dataset.deepLocked='1';create.textContent=`当前任务：${activeTask.status}`}
    }else{
      const create=byId('create-video');if(create?.dataset.deepLocked){delete create.dataset.deepLocked;create.textContent='开始 AI 自动生产'}
      setButtonState(create,!!campaign,'请先创建或选择增长战役',true);
    }

    const files=byId('asset-file')?.files||[];
    const consent=!!byId('asset-consent')?.checked;
    const assetReady=!!campaign&&files.length>0&&consent;
    const assetReason=!campaign?'请先选择增长战役':!files.length?'请选择或拖入照片、视频、音频':!consent?'请确认拥有素材使用权及必要授权':'';
    setButtonState(byId('asset-upload'),assetReady,assetReason,false);

    const searchCampaign=byId('search-campaign')?.value||window.state?.factory?.active_campaign_id||'';
    setButtonState(byId('search-pack'),!!searchCampaign,'请先建立增长战役',true);

    const online=deviceOnline();
    ['device-sync-start','device-sync-once','device-sync-stop'].forEach(id=>setButtonState(byId(id),online,'请先扫描并连接真实手机',false));
  }

  function bindStateInputs(){
    if(document.documentElement.dataset.uiPolishBound)return;
    document.documentElement.dataset.uiPolishBound='1';
    ['campaign-title','video-campaign','asset-file','asset-consent','search-campaign'].forEach(id=>{
      const node=byId(id);if(!node)return;
      node.addEventListener('input',syncActionStates);node.addEventListener('change',syncActionStates);
    });
  }

  function refresh(){
    ensureOwnerNav();
    polishCampaignPage();
    polishContentPage();
    syncActionStates();
  }

  bindStateInputs();
  refresh();
  window.addEventListener('operational:refreshed',refresh);
  window.addEventListener('operational:device-status',refresh);
  window.setTimeout(refresh,250);
  window.setTimeout(refresh,900);
})();
