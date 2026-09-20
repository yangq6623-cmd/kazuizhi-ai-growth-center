(() => {
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const statusTone=value=>value==='已验证可发布'||value==='通过'?'ok':String(value||'').includes('人工')||String(value||'').includes('登录')?'human':'wait';

  function renderAccountWorkbench(){
    const box=byId('account-list');
    if(!box)return;
    const accounts=window.state?.factory?.accounts||[];
    box.classList.add('account-workbench');
    box.innerHTML=accounts.length?accounts.map(item=>`<article class="account-card"><div class="account-card-head"><div><small>${esc(item.platform||'未设置平台')}</small><b>${esc(item.account_name||'未命名账号')}</b></div><span class="account-state ${statusTone(item.connection_status)}">${esc(item.connection_status||'待配置')}</span></div><div class="account-grid"><div><small>区域</small><b>${esc(item.region||'未绑定')}</b></div><div><small>服务主线</small><b>${esc(item.service||'未设置')}</b></div><div><small>每日发布上限</small><b>${esc(item.daily_limit||1)} 条</b></div><div><small>发布能力</small><b>${item.connection_status==='已验证可发布'?'可进入排期':'暂不允许自动发布'}</b></div></div><div class="account-actions">${item.connection_status==='已验证可发布'?'<button data-owner-target="content">查看待发布内容</button>':'<button data-owner-target="device">去真机登录/处理</button>'}<button data-owner-target="health">查看体检</button></div></article>`).join(''):'<div class="empty workbench-empty"><b>还没有可运营账号</b><span>先建立账号档案，再通过真实手机完成人工登录授权。系统不会保存平台明文密码。</span><button data-owner-target="device">进入真机终端</button></div>';
  }

  function ensureConversionWorkbench(){
    const page=byId('conversion');if(!page)return;
    let workbench=byId('conversion-workbench');
    if(!workbench){workbench=document.createElement('section');workbench.id='conversion-workbench';workbench.className='conversion-workbench';page.appendChild(workbench)}
    const factory=window.state?.factory||{};
    const verified=Number(factory.verified_publications||0);
    const metrics=[['真实发布',verified,'已验证平台回执'],['有效咨询','未接入','等待真实咨询来源'],['小程序需求','未接入','等待小程序来源标识'],['师傅报价','未接入','等待业务系统回流'],['完成订单','未接入','等待履约结果回流']];
    workbench.innerHTML=`<div class="conversion-metrics">${metrics.map(([name,value,note])=>`<article><small>${esc(name)}</small><b class="${value==='未接入'?'muted-value':''}">${esc(value)}</b><span>${esc(note)}</span></article>`).join('')}</div><div class="two-col conversion-lower"><article class="panel"><div class="panel-head"><div><p>真实归因接入状态</p><h3>哪些链路已经有数据，哪些还没有</h3></div></div><div class="source-status"><div><b>平台内容链接 / 内容ID</b><span class="${verified?'ready':'waiting'}">${verified?'已有真实发布回执':'等待首条真实发布'}</span></div><div><b>小程序访问来源</b><span class="waiting">尚未接入</span></div><div><b>团长码 / 微信线索</b><span class="waiting">尚未接入</span></div><div><b>师傅报价 / 履约订单</b><span class="waiting">尚未接入</span></div></div></article><article class="panel"><div class="panel-head"><div><p>下一步</p><h3>只在真实数据出现后进入经营结果</h3></div></div><ul class="plain-list"><li>每条发布保留平台真实链接和增长ID。</li><li>小程序访问必须携带来源标识，不能靠人工猜测归因。</li><li>咨询、报价、订单需要业务系统回流后再计数。</li><li>退款、改价、补贴、提现等资金动作继续保持人工处理。</li></ul><button class="workbench-primary" data-owner-target="health">检查数据链路</button></article></div>`;
  }

  function ensureSearchSummary(){
    const page=byId('search');if(!page)return;
    let summary=byId('search-summary');
    if(!summary){summary=document.createElement('section');summary.id='search-summary';summary.className='search-summary';const intro=page.querySelector('.page-intro');intro?.insertAdjacentElement('afterend',summary)}
    const data=window.state?.search||{};
    const packs=Array.isArray(data.packs)?data.packs:[];
    const audit=data.latest_audit;
    const deployed=packs.filter(item=>String(item.deployment_status||'').startsWith('已')).length;
    const indexed=packs.filter(item=>String(item.indexing_status||'').startsWith('已')).length;
    summary.innerHTML=`<article><small>内容包</small><b>${packs.length}</b><span>已绑定增长ID</span></article><article><small>官网技术底座</small><b class="${audit?.result==='ready'?'good':'warn'}">${audit?.result==='ready'?'通过':'待处理'}</b><span>${audit?`堵点 ${audit.blockers?.length||0} 项`:'尚未检查'}</span></article><article><small>已标记部署</small><b>${deployed}</b><span>仅统计明确部署状态</span></article><article><small>已标记收录</small><b>${indexed}</b><span>只记录真实观察结果</span></article>`;
  }

  function refresh(){renderAccountWorkbench();ensureConversionWorkbench();ensureSearchSummary()}
  window.addEventListener('operational:refreshed',refresh);
  window.addEventListener('operational:search-updated',ensureSearchSummary);
  window.addEventListener('operational:device-status',refresh);
  refresh();
  window.setTimeout(refresh,500);
})();
