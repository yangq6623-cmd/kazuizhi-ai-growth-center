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

  function ownerItems(){
    const center=window.state?.factory?.action_center||{};
    return Array.isArray(center.human_items)?center.human_items.map(item=>({
      tone:'human',title:item.title,detail:item.detail,page:item.page,action:item.action
    })):[];
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

  function loadFinalization(){
    if(!document.querySelector('link[data-v221-finalization]')){
      const link=document.createElement('link');
      link.rel='stylesheet';link.href='/operational-finalization.css';link.dataset.v221Finalization='1';document.head.appendChild(link);
    }
    if(document.querySelector('script[data-v221-finalization]'))return;
    const script=document.createElement('script');
    script.src='/operational-finalization.js';
    script.defer=true;
    script.dataset.v221Finalization='1';
    document.head.appendChild(script);
  }

  function loadUiPolish(){
    if(!document.querySelector('link[data-r8-ui-polish]')){
      const link=document.createElement('link');
      link.rel='stylesheet';link.href='/operational-ui-polish.css';link.dataset.r8UiPolish='1';document.head.appendChild(link);
    }
    if(document.querySelector('script[data-r8-ui-polish]'))return;
    const script=document.createElement('script');
    script.src='/operational-ui-polish.js';
    script.defer=true;
    script.dataset.r8UiPolish='1';
    document.head.appendChild(script);
  }

  function loadDeepProductization(){
    if(!document.querySelector('link[data-r8-deep-productization]')){
      const link=document.createElement('link');
      link.rel='stylesheet';link.href='/operational-deep-productization.css';link.dataset.r8DeepProductization='1';document.head.appendChild(link);
    }
    if(document.querySelector('script[data-r8-deep-productization]'))return;
    const script=document.createElement('script');
    script.src='/operational-deep-productization.js';
    script.defer=true;
    script.dataset.r8DeepProductization='1';
    document.head.appendChild(script);
  }

  function refresh(){renderOwnerTodo();enhanceHealth()}

  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-owner-target]');
    if(!button)return;
    window.changeOperationalPage?.(button.dataset.ownerTarget);
  });
  window.addEventListener('operational:refreshed',refresh);
  window.addEventListener('operational:device-status',refresh);

  relabelNavigation();
  refresh();
  loadWorkbench();
  loadFinalization();
  loadUiPolish();
  loadDeepProductization();
  window.setTimeout(refresh,400);
})();
