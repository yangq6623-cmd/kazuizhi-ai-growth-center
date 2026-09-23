(() => {
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const statusTone=value=>value==='已验证可发布'||value==='通过'?'ok':String(value||'').includes('人工')||String(value||'').includes('登录')?'human':'wait';

  function isLegacyOperationalPage(){
    return /(?:^|\/)operational\.html$/i.test(window.location.pathname||'');
  }

  // R8-10 has one owner-facing shell only. operational.html is retained as an
  // internal execution surface for compatibility, never as a second top-level app.
  if(window.top===window.self&&isLegacyOperationalPage()){
    window.location.replace('/index.html');
    return;
  }

  function installEmbeddedExecutionMode(){
    if(window.top===window.self)return;
    const apply=()=>{
      if(!document.body)return;
      document.body.classList.add('r810-embedded-operational');
      document.documentElement.classList.add('r810-embedded-operational');
      if(!byId('r810-embedded-operational-style')){
        const style=document.createElement('style');
        style.id='r810-embedded-operational-style';
        style.textContent=`
          html.r810-embedded-operational,body.r810-embedded-operational{height:auto!important;min-height:0!important;overflow:visible!important;background:transparent!important}
          body.r810-embedded-operational .app-shell{display:block!important;min-height:0!important;background:transparent!important}
          body.r810-embedded-operational .sidebar,body.r810-embedded-operational main>header{display:none!important}
          body.r810-embedded-operational main{width:100%!important;max-width:none!important;min-width:0!important;margin:0!important;padding:0!important;overflow:visible!important;background:transparent!important}
          body.r810-embedded-operational main>.page{padding:0 0 10px!important;min-height:0!important}
          body.r810-embedded-operational .feedback{margin-top:0!important}
        `;
        document.head.appendChild(style);
      }
      syncParentFrameHeight();
    };
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',apply,{once:true});else apply();
  }

  function syncParentFrameHeight(){
    if(window.top===window.self)return;
    const frame=window.frameElement;
    if(!frame)return;
    const active=document.querySelector('.page.active');
    const contentHeight=Math.max(
      720,
      Math.ceil(active?.scrollHeight||0)+28,
      Math.ceil(document.body?.scrollHeight||0)+28
    );
    frame.setAttribute('scrolling','no');
    frame.style.overflow='hidden';
    frame.style.width='100%';
    frame.style.height=`${contentHeight}px`;
    frame.style.minHeight='720px';
    frame.style.border='0';
  }

  installEmbeddedExecutionMode();

  function renderAccountWorkbench(){
    const box=byId('account-list');
    if(!box)return;
    const accounts=window.state?.factory?.accounts||[];
    box.classList.add('account-workbench');
    box.innerHTML=accounts.length?accounts.map(item=>`<article class="account-card"><div class="account-card-head"><div><small>${esc(item.platform||'未设置平台')}</small><b>${esc(item.account_name||'未命名账号')}</b></div><span class="account-state ${statusTone(item.connection_status)}">${esc(item.connection_status||'待配置')}</span></div><div class="account-grid"><div><small>区域</small><b>${esc(item.region||'未绑定')}</b></div><div><small>服务主线</small><b>${esc(item.service||'未设置')}</b></div><div><small>绑定终端</small><b>${esc(item.device_id||'未绑定')}</b></div><div><small>发布能力</small><b>${item.connection_status==='已验证可发布'?'真实验证通过':'暂不允许自动发布'}</b></div></div><div class="account-actions">${item.connection_status==='已验证可发布'?'<button data-owner-target="content">查看待发布内容</button>':'<button data-owner-target="device">去真机登录/处理</button>'}<button data-owner-target="health">查看体检</button></div></article>`).join(''):'<div class="empty workbench-empty"><b>还没有可运营账号</b><span>先建立账号档案并绑定真实手机，再在平台 App 内完成人工登录。系统不会保存平台明文密码，也不会让用户手工勾选“已验证”。</span><button data-owner-target="device">进入真机终端</button></div>';
  }

  function metricValue(value){return value===null||value===undefined?'未接入':value}
  function metricClass(value){return value===null||value===undefined?'muted-value':''}
  function ensureConversionWorkbench(){
    const page=byId('conversion');if(!page)return;
    let workbench=byId('conversion-workbench');
    if(!workbench){workbench=document.createElement('section');workbench.id='conversion-workbench';workbench.className='conversion-workbench';page.appendChild(workbench)}
    const factory=window.state?.factory||{};
    const summary=factory.conversion_summary||{};
    const verified=Number(factory.verified_publications||0);
    const consultations=summary.consultations??null;
    const mini=summary.mini_program_requests??null;
    const quotes=summary.quotes??null;
    const completed=summary.completed_orders??null;
    const metrics=[
      ['真实发布',verified,'只统计带平台真实回执'],
      ['有效咨询',metricValue(consultations),consultations===null?'等待真实咨询/线索回流':'R8真实线索账本'],
      ['小程序需求',metricValue(mini),mini===null?'等待小程序来源标识':'小程序真实来源数据'],
      ['师傅报价',metricValue(quotes),quotes===null?'等待业务系统报价回流':'真实报价数据'],
      ['完成订单',metricValue(completed),completed===null?'等待可验证订单归因':'已记录真实订单归因'],
    ];
    const active=factory.active_campaign_id||'未选择';
    workbench.innerHTML=`<div class="conversion-metrics">${metrics.map(([name,value,note])=>`<article><small>${esc(name)}</small><b class="${metricClass(value==='未接入'?null:value)}">${esc(value)}</b><span>${esc(note)}</span></article>`).join('')}</div><div class="two-col conversion-lower"><article class="panel"><div class="panel-head"><div><p>真实归因接入状态</p><h3>当前增长ID：${esc(active)}</h3></div></div><div class="source-status"><div><b>平台内容链接 / 内容ID</b><span class="${verified?'ready':'waiting'}">${verified?'已有真实发布回执':'等待首条真实发布'}</span></div><div><b>真实咨询 / 线索</b><span class="${consultations!==null?'ready':'waiting'}">${consultations!==null?`${consultations} 条已回流`:'尚无可验证线索'}</span></div><div><b>小程序访问来源</b><span class="waiting">${mini!==null?'已接入':'尚未接入'}</span></div><div><b>订单归因</b><span class="${completed!==null?'ready':'waiting'}">${completed!==null?'已有真实归因记录':'尚未接入/尚无记录'}</span></div></div></article><article class="panel"><div class="panel-head"><div><p>下一步</p><h3>只在真实数据出现后进入经营结果</h3></div></div><ul class="plain-list"><li>发布、咨询和订单沿同一个增长ID追踪。</li><li>每条发布保留平台真实链接和内容ID。</li><li>小程序访问必须携带来源标识，不能靠人工猜测归因。</li><li>退款、改价、补贴、提现等资金动作继续保持人工处理。</li></ul><button class="workbench-primary" data-owner-target="health">检查数据链路</button></article></div>`;
  }

  function ensureSearchSummary(){
    const page=byId('search');if(!page)return;
    let summary=byId('search-summary');
    if(!summary){summary=document.createElement('section');summary.id='search-summary';summary.className='search-summary';page.appendChild(summary)}
    const data=window.state?.search||{};
    const packs=Array.isArray(data.packs)?data.packs:[];
    const audit=data.latest_audit;
    const deployed=packs.filter(item=>String(item.deployment_status||'').startsWith('已')).length;
    const indexed=packs.filter(item=>String(item.indexing_status||'').startsWith('已')).length;
    summary.innerHTML=`<article><small>内容包</small><b>${packs.length}</b><span>已绑定增长ID</span></article><article><small>官网技术底座</small><b class="${audit?.result==='ready'?'good':'warn'}">${audit?.result==='ready'?'通过':'待处理'}</b><span>${audit?`堵点 ${audit.blockers?.length||0} 项`:'尚未检查'}</span></article><article><small>已标记部署</small><b>${deployed}</b><span>仅统计明确部署状态</span></article><article><small>已标记收录</small><b>${indexed}</b><span>只记录真实观察结果</span></article>`;
  }

  function refresh(){renderAccountWorkbench();ensureConversionWorkbench();ensureSearchSummary();syncParentFrameHeight()}
  window.addEventListener('operational:refreshed',refresh);
  window.addEventListener('operational:search-updated',ensureSearchSummary);
  window.addEventListener('operational:device-status',refresh);
  window.addEventListener('resize',syncParentFrameHeight);
  if(window.ResizeObserver&&document.body){
    const observer=new ResizeObserver(()=>syncParentFrameHeight());
    observer.observe(document.body);
  }
  refresh();
  window.setTimeout(refresh,500);
  window.setTimeout(syncParentFrameHeight,900);
})();