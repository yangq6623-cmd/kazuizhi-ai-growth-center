(() => {
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  function relabelNavigation(){
    const link=document.querySelector('.r7-console-link');
    if(link){
      const title=link.querySelector('b'), note=link.querySelector('small');
      if(title)title.textContent='返回总控中心';
      if(note)note.textContent='总控、任务、数据与系统设置';
    }
    const labels=[...document.querySelectorAll('.nav-label')];
    if(labels[0])labels[0].textContent='总控与生产';
    if(labels[1])labels[1].textContent='社媒与转化';
    if(labels[2])labels[2].textContent='增长与系统';
  }

  function deviceOnline(){
    const payload=window.state?.device||{};
    const devices=Array.isArray(payload.devices)?payload.devices:[];
    return devices.some(item=>item?.connected);
  }

  function ownerItems(){
    const factory=window.state?.factory||{};
    const videos=factory.videos||[];
    const accounts=factory.accounts||[];
    const items=[];
    const reviews=videos.filter(item=>item.status==='等待人工审核').length;
    const accountNeeds=accounts.filter(item=>item.connection_status!=='已验证可发布').length;
    if(reviews)items.push({tone:'human',title:`${reviews} 条视频等待审核`,detail:'需要老板确认后，系统才允许进入发布排期。',page:'content',action:'去审核'});
    if(accountNeeds)items.push({tone:'human',title:`${accountNeeds} 个账号需要登录或授权`,detail:'验证码、人脸和平台风控只允许人工完成。',page:'accounts',action:'去处理'});
    if(!deviceOnline())items.push({tone:'config',title:'真机终端当前未在线',detail:'需要连接 USB 并确认调试授权；连接成功后设备状态会在全系统同步。',page:'device',action:'检查手机'});
    const audit=window.state?.search?.latest_audit;
    if(!audit||audit.result!=='ready')items.push({tone:'config',title:'SEO / GEO 技术底座尚未完全通过',detail:audit?.blockers?.length?`仍有 ${audit.blockers.length} 个技术堵点待处理。`:'尚未完成官网抓取和技术底座检查。',page:'search',action:'查看'});
    return items;
  }

  function renderOwnerTodo(){
    const dashboard=byId('dashboard');
    if(!dashboard)return;
    let panel=byId('owner-todo');
    if(!panel){
      panel=document.createElement('section');
      panel.id='owner-todo';
      panel.className='owner-todo panel';
      const anchor=dashboard.querySelector('.migration-strip');
      if(anchor)anchor.insertAdjacentElement('afterend',panel);else dashboard.prepend(panel);
    }
    const items=ownerItems();
    panel.innerHTML=`<div class="panel-head"><div><p>今天只处理真正需要人工决定的事项</p><h3>待我处理 ${items.length} 项</h3></div><span class="owner-ready ${items.length?'':'all-clear'}">${items.length?'需要处理':'当前无人工阻塞'}</span></div>${items.length?`<div class="owner-todo-list">${items.map(item=>`<article class="owner-todo-item ${esc(item.tone)}"><div><b>${esc(item.title)}</b><span>${esc(item.detail)}</span></div><button data-owner-target="${esc(item.page)}">${esc(item.action)}</button></article>`).join('')}</div>`:'<div class="owner-empty">当前没有需要老板立即处理的事项。系统可以继续按已授权范围推进。</div>'}`;
  }

  function enhanceHealth(){
    const health=byId('health-list');
    if(!health)return;
    health.querySelectorAll('.check-item').forEach(item=>{
      const text=item.textContent||'';
      const status=item.querySelector('strong')?.textContent||'';
      item.classList.remove('health-normal','health-config','health-human');
      if(status==='通过')item.classList.add('health-normal');
      else if(text.includes('人工')||text.includes('登录')||text.includes('验证码'))item.classList.add('health-human');
      else item.classList.add('health-config');
      if(item.querySelector('.health-action'))return;
      let page='';
      if(text.includes('手机与真机'))page='device';
      else if(text.includes('社媒账号'))page='accounts';
      else if(text.includes('SEO与GEO'))page='search';
      else if(text.includes('订单归因'))page='conversion';
      if(page){
        const button=document.createElement('button');
        button.className='health-action';
        button.dataset.ownerTarget=page;
        button.textContent=status==='通过'?'查看':'去处理';
        item.appendChild(button);
      }
    });
  }

  function loadWorkbench(){
    if(document.querySelector('script[data-v221-workbench]'))return;
    const script=document.createElement('script');
    script.src='/operational-workbench.js';
    script.defer=true;
    script.dataset.v221Workbench='1';
    document.head.appendChild(script);
  }

  function refresh(){renderOwnerTodo();enhanceHealth()}

  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-owner-target]');
    if(!button)return;
    window.changeOperationalPage?.(button.dataset.ownerTarget);
  });

  const originalRefresh=window.refreshAll;
  if(typeof originalRefresh==='function')window.refreshAll=async(...args)=>{const result=await originalRefresh(...args);refresh();return result};
  const originalSync=window.syncOperationalDeviceStatus;
  window.syncOperationalDeviceStatus=payload=>{originalSync?.(payload);refresh()};

  relabelNavigation();
  refresh();
  loadWorkbench();
  window.setTimeout(refresh,400);
})();
