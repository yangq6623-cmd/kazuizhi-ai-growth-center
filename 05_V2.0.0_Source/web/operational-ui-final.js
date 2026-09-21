(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const ACTIVE=new Set(['等待ChatGPT策划','等待素材路由','等待生产','生产中','技术质检','等待ChatGPT质检','等待人工审核','退回重做','已授权发布','等待账号','等待最佳时间','发布执行中','异常待处理']);

  function factory(){return window.state?.factory||{}}
  function growthId(){return String(window.getActiveGrowthId?.()||factory().active_campaign_id||factory().campaigns?.[0]?.id||'').trim()}
  function campaign(){const id=growthId();return (factory().campaigns||[]).find(x=>x.id===id)||null}
  function video(){const id=growthId();return (factory().videos||[]).find(x=>x.campaign_id===id&&ACTIVE.has(x.status))||null}
  function device(){
    const d=window.state?.device||{};
    const list=Array.isArray(d.devices)?d.devices:[];
    return list.find(x=>x?.device_id===d.primary_device_id&&x?.connected)||list.find(x=>x?.connected)||null;
  }
  function go(page){window.changeOperationalPage?.(page)}

  function make(tag,className,html){const el=document.createElement(tag);if(className)el.className=className;if(html!==undefined)el.innerHTML=html;return el}

  function dashboard(){
    const page=byId('dashboard');if(!page)return;
    page.classList.add('final-dashboard');
    const goal=byId('order-goal');if(goal)goal.textContent='经营数据待接入';
    const box=page.querySelector('.goal');
    if(box){
      const small=box.querySelector('small');if(small)small.textContent='本月真实订单';
      const tail=box.querySelector(':scope>span');if(tail)tail.textContent='目标 50 单 · 接入经营数据后自动显示';
    }
    const migration=page.querySelector('.migration-strip');
    if(migration){const b=migration.querySelector('b');if(b)b.textContent='✓ 数据与配置已安全保留'}
  }

  function campaigns(){
    const page=byId('campaigns');if(!page)return;
    const current=campaign(),task=video();
    let hero=byId('final-current-campaign');
    if(!hero){
      hero=make('section','final-current-campaign');hero.id='final-current-campaign';
      const intro=page.querySelector('.page-intro');intro?.insertAdjacentElement('afterend',hero);
    }
    if(current){
      hero.hidden=false;
      hero.innerHTML=`<div><span class="eyebrow">当前增长战役 · 全站共用同一个 Growth ID</span><h3>${esc(current.title||'未命名增长战役')}</h3><div class="meta"><span>${esc(current.id)}</span><span>${esc(current.region||'未标注区域')}</span><span>${esc(current.service||'未标注服务')}</span></div><span class="status">当前状态：${esc(task?.status||'等待创建内容任务')}。内容、账号、发布、咨询、订单和 SEO/GEO 都沿用这个增长ID。</span></div><div class="actions"><button class="primary" data-final-ui-go="content">继续当前战役</button><button data-final-ui-new-campaign>创建新战役</button></div>`;
    }else{
      hero.hidden=true;
    }

    const pair=page.querySelector(':scope>.two-col')||page.querySelector('.two-col');
    if(pair&&!pair.closest('.final-new-campaign')){
      const details=make('details','final-new-campaign');details.open=!current;
      const summary=make('summary','',current?'创建新的增长战役':'创建第一个增长战役');
      pair.parentElement.insertBefore(details,pair);details.append(summary,pair);
    }
    const details=page.querySelector('.final-new-campaign');
    if(details&&current&&!details.dataset.ownerOpened)details.open=false;
    const oldWide=page.querySelector(':scope>.panel.wide');if(oldWide)oldWide.classList.add('final-campaign-history');
  }

  function contentStage(status){
    if(!status)return 0;
    if(['等待ChatGPT策划','等待素材路由'].includes(status))return 1;
    if(['等待生产','生产中','技术质检','等待ChatGPT质检','退回重做','异常待处理'].includes(status))return 2;
    if(status==='等待人工审核')return 3;
    if(['已授权发布','等待账号','等待最佳时间','发布执行中','已验证发布'].includes(status))return 4;
    return 1;
  }

  function content(){
    const page=byId('content');if(!page)return;
    const current=campaign(),task=video();
    const oldFlow=byId('content-flow-summary');if(oldFlow)oldFlow.style.display='none';
    let hero=byId('final-task-hero');
    if(!hero){hero=make('section','final-task-hero');hero.id='final-task-hero';const intro=page.querySelector('.page-intro');intro?.insertAdjacentElement('afterend',hero)}
    if(current){
      hero.hidden=false;
      hero.innerHTML=`<div><small>当前内容任务 · ${esc(current.id)}</small><b>${esc(current.title||'当前增长战役')}</b><span>${esc(current.region||'')} · ${esc(current.service||'')} · 本地素材可选，缺素材不会阻塞生产</span></div><span class="task-state">${esc(task?.status||'等待开始生产')}</span>`;
    }else{
      hero.hidden=false;hero.innerHTML='<div><small>当前内容任务</small><b>尚未建立增长战役</b><span>先建立一个真实业务问题，再由 ChatGPT 自动完成内容生产链。</span></div><button class="primary" data-final-ui-go="campaigns">建立增长战役</button>';
    }
    const steps=[...page.querySelectorAll('.factory-steps article')];
    const active=contentStage(task?.status);
    steps.forEach((step,index)=>{
      step.classList.toggle('final-active-stage',!!task&&index===active);
      step.classList.toggle('final-done-stage',!!task&&index<active);
    });
    const grid=page.querySelector('.three-col');if(grid)grid.classList.add('final-content-grid');
    const third=grid?.querySelector(':scope>.panel:nth-child(3)');
    if(third&&!third.querySelector('.final-execution-details')){
      const children=[...third.childNodes];
      const details=make('details','final-execution-details');
      const summary=make('summary','', '系统执行详情');
      const body=make('div','final-execution-body');children.forEach(node=>body.appendChild(node));
      details.append(summary,body);third.appendChild(details);
    }
    const material=byId('optional-materials');
    if(material&&!material.closest('.final-materials-details')){
      const details=make('details','final-materials-details');const summary=make('summary','', '本地素材投递箱');
      material.parentElement.insertBefore(details,material);details.append(summary,material);
    }
    const script=byId('video-script');
    if(script){script.placeholder='可留空。ChatGPT 会根据增长目标、真实边界和平台规则自动生成深层脚本；如需人工补充，可在这里输入。'}
    const create=byId('create-video');if(create&&!task&&current)create.textContent='开始 AI 自动生产';
  }

  function accounts(){
    const page=byId('accounts');if(!page)return;
    const form=byId('account-form');if(!form)return;
    const status=byId('account-status');const label=status?.closest('label');if(label)label.style.display='none';
    let card=form.querySelector('.final-account-status');
    if(!card){card=make('div','final-account-status');const submit=form.querySelector('button[type="submit"]');submit?.insertAdjacentElement('beforebegin',card)}
    const d=device();
    const social=factory().social_truth||{};
    const socialAccounts=Array.isArray(social.accounts)?social.accounts:[];
    const verified=socialAccounts.find(a=>a.login_status==='authorized'&&a.risk_level!=='attention'&&a.risk_level!=='high'&&!a.automation_paused);
    const human=socialAccounts.find(a=>['needs_human','logged_out'].includes(a.login_status)||['attention','high'].includes(a.risk_level));
    let title='请先连接真实手机',detail='平台验证状态不可手工选择。连接真机后，再在平台 App 内完成登录。';
    if(d&&verified){title='已验证可发布';detail=`真实终端 ${d.model||d.device_id} 在线，账号授权与风险状态通过。`}
    else if(d&&human){title='需要人工处理';detail='账号存在验证码、人脸、登录失效或平台风险提示，请到真机完成处理。'}
    else if(d){title='待平台登录验证';detail=`已连接 ${d.model||d.device_id}。请在真实平台 App 中登录，验证通过后系统自动更新状态。`}
    card.innerHTML=`<div><small>真实连接状态 · 只读</small><b>${esc(title)}</b><span>${esc(detail)}</span></div><button type="button" data-final-ui-go="device">去终端登录</button>`;
    const submit=form.querySelector('button[type="submit"]');if(submit)submit.textContent=d?'保存账号并绑定真机':'连接真机后建立账号';
  }

  function devicePage(){
    const page=byId('device');if(!page)return;page.classList.add('final-device-page');
    const status=page.querySelector('#device-business-context');if(status)status.classList.add('final-device-context');
  }

  function conversion(){const page=byId('conversion');if(page)page.classList.add('final-conversion-page')}
  function search(){const page=byId('search');if(page)page.classList.add('final-search-page')}

  function health(){
    const page=byId('health');if(!page)return;
    const list=byId('health-list')||page.querySelector('.check-list');
    if(!list)return;
    const items=[...list.querySelectorAll('.check-item')];
    let normal=0,human=0,config=0;
    items.forEach(item=>{
      const text=(item.textContent||'');
      const strong=item.querySelector('strong')?.textContent||'';
      if(item.classList.contains('health-normal')||strong==='通过')normal++;
      else if(item.classList.contains('health-human')||text.includes('人工')||text.includes('登录'))human++;
      else config++;
    });
    let summary=byId('final-health-summary');
    if(!summary){summary=make('section','final-health-summary');summary.id='final-health-summary';const intro=page.querySelector('.page-intro');intro?.insertAdjacentElement('afterend',summary)}
    summary.innerHTML=`<div class="main"><small>系统总体状态</small><b>${human?'存在人工事项':'核心运行正常'}</b><span>${human?'先处理人工验证，再继续自动执行。':'配置建设项不会冒充日常人工阻塞。'}</span></div><div><small>正常</small><b>${normal}</b><span>已通过检查</span></div><div><small>需人工</small><b>${human}</b><span>登录 / 验证 / 风控</span></div><div><small>待配置</small><b>${config}</b><span>SEO / 数据链等建设项</span></div>`;
  }

  function simplifyCopy(){
    const intros={
      campaigns:['增长战役','从一个真实业务问题开始','后续内容、发布、咨询、订单和 SEO/GEO 都围绕同一个 Growth ID 自动推进。'],
      content:['内容工厂','从增长目标直接到最终成片','ChatGPT 负责策划与质检，本地引擎负责执行；你只在最终成片阶段做决定。'],
      device:['终端与真机','真实手机执行终端','画面、点击与平台登录都来自真实 Android 手机；验证码、人脸和风控仍由人工处理。'],
      accounts:['账号与发布','真实账号、真实终端、真实发布','账号验证状态只来自平台与终端检测，不能人工伪造“已验证可发布”。'],
      conversion:['咨询与订单','从内容一直追到真实经营结果','只有可验证的平台链接、咨询、需求、报价和订单才进入归因。'],
      search:['SEO / GEO','一个问题，同时覆盖搜索与 AI 答案','生成、部署、抓取、收录和 AI 引用分开记录，不把“生成了”当成“上线了”。'],
      health:['系统体检','先看真正需要处理的异常','正常项默认弱化；人工事项和建设项分开显示。']
    };
    Object.entries(intros).forEach(([id,[p,h,s]])=>{
      const intro=byId(id)?.querySelector('.page-intro');if(!intro)return;
      const pe=intro.querySelector('p'),he=intro.querySelector('h2'),se=intro.querySelector(':scope>span');
      if(pe)pe.textContent=p;if(he)he.textContent=h;if(se)se.textContent=s;
    });
  }

  function apply(){
    document.body.classList.add('r8-ui-final');
    dashboard();campaigns();content();devicePage();accounts();conversion();search();health();simplifyCopy();
  }

  document.addEventListener('click',event=>{
    const goButton=event.target.closest('[data-final-ui-go]');if(goButton){event.preventDefault();go(goButton.dataset.finalUiGo);return}
    const newButton=event.target.closest('[data-final-ui-new-campaign]');if(newButton){
      event.preventDefault();const details=byId('campaigns')?.querySelector('.final-new-campaign');if(details){details.open=true;details.dataset.ownerOpened='1';details.scrollIntoView({behavior:'smooth',block:'start'})}
    }
  });
  window.addEventListener('operational:refreshed',apply);
  window.addEventListener('operational:device-status',apply);
  window.addEventListener('operational:page-changed',apply);
  apply();
  window.setTimeout(apply,300);
  window.setTimeout(apply,1000);
})();
