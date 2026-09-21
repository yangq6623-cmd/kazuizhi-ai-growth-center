(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const nowText=()=>new Intl.DateTimeFormat('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date());
  const connectedDevice=()=>{
    const payload=window.state?.device||{};
    const list=Array.isArray(payload.devices)?payload.devices:[];
    return list.find(x=>x?.device_id===payload.primary_device_id&&x?.connected)||list.find(x=>x?.connected)||null;
  };
  const latestCampaign=()=>{
    const list=window.state?.factory?.campaigns||[];
    const selected=byId('video-campaign')?.value;
    return list.find(x=>x.id===selected)||list[list.length-1]||null;
  };

  function unifyNavigation(){
    const labels=[...document.querySelectorAll('.nav-label')];
    if(labels[0])labels[0].textContent='今日与生产';
    if(labels[1])labels[1].textContent='社媒与经营';
    if(labels[2])labels[2].textContent='增长与系统';
    const names={dashboard:'今日总控',campaigns:'增长战役',content:'内容工厂',device:'终端与真机',accounts:'账号与发布',conversion:'咨询与订单',search:'SEO / GEO',health:'系统体检'};
    document.querySelectorAll('.nav[data-page]').forEach(btn=>{if(names[btn.dataset.page])btn.textContent=names[btn.dataset.page]});
    const link=document.querySelector('.r7-console-link');
    if(link){
      link.classList.add('system-console-link');
      const b=link.querySelector('b'),small=link.querySelector('small');
      if(b)b.textContent='系统总控';
      if(small)small.textContent='任务、数据、历史与系统设置';
      const footer=document.querySelector('.side-footer');
      if(footer&&!footer.contains(link))footer.before(link);
    }
    const footer=document.querySelector('.side-footer');
    if(footer){const b=footer.querySelector('b'),span=footer.querySelector('span');if(b)b.textContent='V2.2.1 产品化版';if(span)span.textContent='真实数据 · 可追溯 · 异常转人工'}
    document.querySelectorAll('[data-device-mode]').forEach(btn=>{if(btn.dataset.deviceMode==='r8')btn.textContent='自动控制';if(btn.dataset.deviceMode==='human')btn.textContent='人工接管';if(btn.dataset.deviceMode==='paused')btn.textContent='暂停'});
  }

  function pageNextStep(page){
    const f=window.state?.factory||{},d=connectedDevice(),campaigns=f.campaigns||[],videos=f.videos||[],accounts=f.accounts||[];
    const pendingReview=videos.filter(v=>v.status==='等待人工审核').length;
    const unverified=accounts.filter(a=>a.connection_status!=='已验证可发布').length;
    const map={
      dashboard: pendingReview?['先处理等待你确认的内容',`${pendingReview} 条视频等待人工审核。`,'content','去审核']:!d?['先让执行终端上线','真机未在线，自动发布与人工接管都会受阻。','device','检查终端']:['今天没有人工阻塞','系统可以继续按已授权范围推进。','health','查看体检'],
      campaigns: campaigns.length?['选择一个增长战役继续推进','所有内容、发布和结果都应绑定同一个增长ID。','content','进入内容工厂']:['先建立一个真实增长战役','从真实用户问题开始，不从“我要发什么内容”开始。','campaigns','开始建立'],
      content: !campaigns.length?['先建立增长战役','没有增长ID时不创建孤立内容任务。','campaigns','去建立战役']:pendingReview?['完成老板审核',`${pendingReview} 条成片等待确认，通过后才进入发布。`,'content','查看审核']:['继续生产下一条可验证内容','素材、脚本、成片、审核和发布保持同一增长ID。','content','继续'],
      device: !d?['连接真实手机','USB调试授权成功后，再进行连续同步与平台登录。','device','扫描手机']:['确认终端绑定关系','检查当前平台、账号和任务是否与这台真机一致。','accounts','查看账号'],
      accounts: unverified?['完成真实账号授权',`${unverified} 个账号仍需登录、验证或人工处理。`,'device','去真机处理']:['检查今天待发布内容','已授权账号可以进入内容审核与排期。','content','查看内容'],
      conversion:['先补齐真实来源数据','咨询、报价、订单未回流前，不把曝光算成经营结果。','health','检查数据链路'],
      search:['先确认技术底座，再扩大内容量','抓取、部署、收录和AI引用必须分别记录真实状态。','search','检查SEO/GEO'],
      health:['先处理异常，再看正常项','正常项默认折叠；需要配置和需要人工的项目优先显示。','dashboard','返回待办']
    };
    return map[page]||['确认下一步','只执行当前页面能完成的工作。',page,'继续'];
  }

  function ensureNextStep(page){
    const section=byId(page);if(!section)return;
    let card=section.querySelector(':scope > .page-next-step');
    if(!card){card=document.createElement('section');card.className='page-next-step';const anchor=section.querySelector('.page-intro')||section.querySelector('.hero');if(anchor)anchor.insertAdjacentElement('afterend',card);else section.prepend(card)}
    const [title,detail,target,action]=pageNextStep(page);
    card.innerHTML=`<div><small>下一步</small><b>${esc(title)}</b><span>${esc(detail)}</span></div><button data-final-target="${esc(target)}">${esc(action)}</button>`;
  }

  function ensureContextStrip(page){
    const section=byId(page);if(!section||page==='dashboard')return;
    let strip=section.querySelector(':scope > .context-strip');
    if(!strip){strip=document.createElement('div');strip.className='context-strip';const step=section.querySelector(':scope > .page-next-step');(step||section.firstElementChild)?.insertAdjacentElement('afterend',strip)}
    const c=latestCampaign(),d=connectedDevice();
    const growth=c?.id||'未选择';
    const task=(d?.current_task||'无执行任务');
    strip.innerHTML=`<span><small>增长ID</small><b>${esc(growth)}</b></span><span><small>任务</small><b>${esc(task)}</b></span><span><small>数据来源</small><b>本地真实接口</b></span><span><small>更新时间</small><b>${esc(nowText())}</b></span>`;
  }

  function ensureContentFlow(){
    const page=byId('content');if(!page)return;
    let box=byId('content-flow-summary');
    if(!box){box=document.createElement('section');box.id='content-flow-summary';box.className='content-flow-summary';const steps=page.querySelector('.factory-steps');steps?.insertAdjacentElement('afterend',box)}
    const videos=window.state?.factory?.videos||[];
    const count=label=>videos.filter(v=>String(v.status||'').includes(label)).length;
    const has=videos.length>0;
    page.classList.toggle('content-no-tasks',!has);
    const stages=[['素材/脚本',has?videos.length:0],['生产中',count('生产')],['待审核',count('审核')],['待发布',count('最佳时间')+count('排期')],['已验证',Number(window.state?.factory?.verified_publications||0)]];
    box.innerHTML=`<div class="flow-head"><div><small>任务流水线</small><b>${has?'按状态推进，不跳步骤':'暂无生产任务'}</b></div><span>${has?`${videos.length} 个任务`:'建立增长战役后再创建任务'}</span></div><div class="flow-stages">${stages.map(([name,n],i)=>`<div class="flow-stage ${n?'active':''}"><small>0${i+1}</small><b>${esc(name)}</b><span>${esc(n)}</span></div>`).join('')}</div>`;
    const worker=byId('video-worker-status');
    if(worker&&!worker.querySelector('.worker-separation-note'))worker.insertAdjacentHTML('beforeend','<small class="worker-separation-note">硬件识别、模型/组件就绪、实际可生产是三个不同状态；只有全部通过才进入自动生产。</small>');
  }

  async function manualDeviceAction(action){
    const d=connectedDevice();if(!d)return window.notify?.('请先连接真实手机','error');
    const response=await fetch('/api/r8/device/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,action,actor:'owner'})});
    const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`设备操作返回 ${response.status}`);
    window.notify?.('真机操作已执行');
  }

  function ensureDeviceTools(){
    const page=byId('device');if(!page)return;
    const actions=page.querySelector('.phone-actions');
    if(actions&&!actions.querySelector('[data-final-device-action]')){
      [['recents','最近任务'],['volume_up','音量+'],['volume_down','音量-'],['rotate_left','左旋转'],['rotate_right','右旋转'],['keep_awake_on','保持亮屏'],['keep_awake_off','恢复休眠']].forEach(([action,label])=>{
        const btn=document.createElement('button');btn.dataset.finalDeviceAction=action;btn.textContent=label;actions.appendChild(btn);
      });
    }
    let context=byId('device-business-context');
    if(!context){context=document.createElement('section');context.id='device-business-context';context.className='device-business-context';page.querySelector('.device-toolbar')?.insertAdjacentElement('afterend',context)}
    const d=connectedDevice();
    context.innerHTML=`<div><small>当前终端</small><b>${esc(d?.model||'未连接')}</b></div><div><small>平台</small><b>${esc(d?.platform||'未绑定')}</b></div><div><small>账号</small><b>${esc(d?.account||'未绑定')}</b></div><div><small>当前任务</small><b>${esc(d?.current_task||'无')}</b></div><div><small>风险状态</small><b>${esc(d?.risk_level||'未验证')}</b></div>`;
  }

  function ensureSocialBinding(){
    const page=byId('accounts');if(!page)return;
    let box=byId('terminal-account-binding');
    if(!box){box=document.createElement('section');box.id='terminal-account-binding';box.className='terminal-account-binding panel';const intro=page.querySelector('.page-intro');intro?.insertAdjacentElement('afterend',box)}
    const d=connectedDevice();
    const accounts=window.state?.factory?.accounts||[];
    box.innerHTML=`<div class="panel-head"><div><p>平台 → 终端 → 账号</p><h3>真实执行绑定关系</h3></div><span class="binding-state ${d?'ok':'wait'}">${d?'终端在线':'终端未连接'}</span></div>${d?`<div class="binding-grid"><div><small>平台</small><b>${esc(d.platform||'未绑定')}</b></div><div><small>真机</small><b>${esc(d.model||d.device_id)}</b></div><div><small>账号</small><b>${esc(d.account||'未绑定')}</b></div><div><small>当前任务</small><b>${esc(d.current_task||'无')}</b></div></div>`:'<div class="empty">先连接真实手机，再完成人工登录；系统不保存平台明文密码。</div>'}<div class="binding-note">已登记账号 ${accounts.length} 个。只有“真机在线 + 账号已验证 + 风险正常”同时满足时，才允许自动发布。</div>`;
  }

  function ensureConversionCRM(){
    const page=byId('conversion');if(!page)return;
    let box=byId('lead-crm-workbench');
    if(!box){box=document.createElement('section');box.id='lead-crm-workbench';box.className='panel wide lead-crm-workbench';page.appendChild(box)}
    const leads=Array.isArray(window.state?.factory?.leads)?window.state.factory.leads:[];
    box.innerHTML=`<div class="panel-head"><div><p>线索工作台</p><h3>真实咨询与跟进记录</h3></div><span class="data-chip">来源：业务回流 · ${esc(nowText())}</span></div><div class="crm-table"><div class="crm-row crm-head"><span>来源/增长ID</span><span>需求</span><span>负责人</span><span>状态</span><span>最近联系</span><span>下一步</span></div>${leads.length?leads.map(x=>`<div class="crm-row"><span>${esc(x.growth_id||x.source||'--')}</span><span>${esc(x.summary||x.service||'--')}</span><span>${esc(x.owner||'未分配')}</span><span>${esc(x.status||'待跟进')}</span><span>${esc(x.last_contact_at||'未记录')}</span><span>${esc(x.next_action||'待确认')}</span></div>`).join(''):'<div class="crm-empty">尚未接入真实咨询/线索回流，因此不生成虚构客户记录。接入后这里会显示负责人、跟进状态、最近联系时间和下一步。</div>'}</div>`;
  }

  function ensureSearchOperations(){
    const page=byId('search');if(!page)return;
    let box=byId('search-ops-table');
    if(!box){box=document.createElement('section');box.id='search-ops-table';box.className='panel wide search-ops-table';const summary=byId('search-summary');(summary||page.querySelector('.page-intro'))?.insertAdjacentElement('afterend',box)}
    const packs=window.state?.search?.packs||[];
    box.innerHTML=`<div class="panel-head"><div><p>结果管理</p><h3>页面、抓取、收录与 AI 引用分开验证</h3></div><span class="data-chip">来源：搜索增长接口 · ${esc(nowText())}</span></div><div class="ops-table"><div class="ops-row ops-head"><span>增长ID / 页面</span><span>部署</span><span>最近抓取</span><span>收录</span><span>AI引用</span><span>更新时间</span></div>${packs.length?packs.map(p=>`<div class="ops-row"><span><b>${esc(p.campaign_id||p.growth_id||'未标注')}</b><small>${esc(p.page_title||'未命名页面')}</small></span><span>${esc(p.deployment_status||'未验证')}</span><span>${esc(p.last_crawl_at||'未验证')}</span><span>${esc(p.indexing_status||'未验证')}</span><span>${esc(p.ai_citation_status||'未验证')}</span><span>${esc(p.updated_at||'未记录')}</span></div>`).join(''):'<div class="crm-empty">还没有搜索内容包。生成内容并不代表已经部署、收录或被 AI 引用；这些状态只记录真实验证结果。</div>'}</div>`;
  }

  function ensureHealthFold(){
    const page=byId('health'),list=byId('health-list');if(!page||!list)return;
    let bar=byId('health-filter-bar');
    if(!bar){bar=document.createElement('div');bar.id='health-filter-bar';bar.className='health-filter-bar';bar.innerHTML='<div><b>优先显示需要处理的项目</b><span>正常项默认折叠，减少信息噪音。</span></div><button id="toggle-health-normal">显示正常项</button>';list.before(bar);byId('toggle-health-normal')?.addEventListener('click',()=>{page.classList.toggle('show-health-normal');const shown=page.classList.contains('show-health-normal');byId('toggle-health-normal').textContent=shown?'隐藏正常项':'显示正常项'})}
    list.querySelectorAll('.check-item').forEach(item=>item.classList.toggle('normal-collapsible',item.classList.contains('health-normal')||item.querySelector('.pass')));
  }

  function normalizeUnknownValues(){
    document.querySelectorAll('.metric b').forEach(node=>{if(node.textContent.trim()==='--'){node.textContent='未接入';node.classList.add('muted-value')}});
  }

  function enhanceAll(){
    unifyNavigation();
    ['dashboard','campaigns','content','device','accounts','conversion','search','health'].forEach(page=>{ensureNextStep(page);ensureContextStrip(page)});
    ensureContentFlow();ensureDeviceTools();ensureSocialBinding();ensureConversionCRM();ensureSearchOperations();ensureHealthFold();normalizeUnknownValues();
  }

  document.addEventListener('click',event=>{
    const target=event.target.closest('[data-final-target]');if(target){window.changeOperationalPage?.(target.dataset.finalTarget);return}
    const device=event.target.closest('[data-final-device-action]');if(device){device.disabled=true;manualDeviceAction(device.dataset.finalDeviceAction).catch(error=>window.notify?.(error.message,'error')).finally(()=>{device.disabled=false})}
  });
  window.addEventListener('operational:refreshed',enhanceAll);
  window.addEventListener('operational:device-status',enhanceAll);
  window.addEventListener('operational:search-updated',enhanceAll);
  enhanceAll();window.setTimeout(enhanceAll,500);
})();
