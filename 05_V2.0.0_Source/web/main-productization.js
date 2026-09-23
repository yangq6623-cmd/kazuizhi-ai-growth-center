(() => {
  'use strict';

  const ALLOWED_SHELL_CHILDREN = new Set(['r810-nav-title','r810-primary-nav','r810-secondary-nav']);

  function businessCopy(){
    document.title='卡嘴子 AI 自治运营工作台 · R8-10';
    const baseline=document.querySelector('.baseline');
    if(baseline&&!document.body.classList.contains('r810-workbench')){
      baseline.innerHTML='<b>R8-10 · #398 开发版</b><br><span>单工作台 · 真实执行 · 真实回执</span><code>基于 #397 稳定底座</code>';
    }
    const badge=document.querySelector('#dashboard .welcome-badge');
    if(badge&&!badge.textContent.includes('老板总控'))badge.textContent='卡嘴子 AI · 今日运营总控';
    const heading=document.querySelector('#dashboard .command-welcome h2');
    if(heading&&!document.body.classList.contains('r810-workbench'))heading.textContent='从今天要完成的结果出发，统一管理任务、内容、终端和经营反馈。';
    const workflowLabel=document.querySelector('#workflow .page-title small');
    if(workflowLabel&&!document.body.classList.contains('r810-workbench'))workflowLabel.textContent='稳定运营底座';
  }

  function injectSingleShellStyle(){
    if(document.getElementById('r810-product-shell-lock'))return;
    const style=document.createElement('style');
    style.id='r810-product-shell-lock';
    style.textContent=`
      body.r810-workbench aside nav .r810-legacy-route,
      body.r810-workbench aside nav button.nav,
      body.r810-workbench aside nav .nav-group,
      body.r810-workbench aside nav details.nav-more,
      body.r810-workbench aside nav .operational-entry,
      body.r810-workbench .r810-legacy-brain-entry{display:none!important}
      .r810-connection-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0 14px}
      .r810-connection-summary>div{background:#fff;border:1px solid #e4eaf2;border-radius:12px;padding:13px;min-width:0}
      .r810-connection-summary small{display:block;color:#8693a6;font-size:9px;margin-bottom:5px}
      .r810-connection-summary b{display:block;color:#24324a;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .r810-connection-summary span{display:block;color:#738299;font-size:10px;margin-top:4px;line-height:1.45}
      .r810-tech-toggle{margin:0 0 12px;border:1px solid #dfe7f2;background:#fff;color:#365a91;border-radius:8px;padding:8px 10px;font-size:10px;font-weight:700;cursor:pointer}
      @media(max-width:900px){.r810-connection-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:620px){.r810-connection-summary{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function lockSingleShell(){
    const nav=document.querySelector('aside nav');
    if(!nav)return;
    nav.querySelectorAll('button.nav,.nav-group,details.nav-more,.operational-entry').forEach(node=>node.classList.add('r810-legacy-route'));
    [...nav.children].forEach(child=>{
      const allowed=[...ALLOWED_SHELL_CHILDREN].some(cls=>child.classList?.contains(cls));
      if(document.body.classList.contains('r810-workbench')&&!allowed)child.classList.add('r810-legacy-route');
    });
    document.querySelectorAll('.operational-entry').forEach(node=>node.remove());
  }

  function hideLegacyBrainEntry(){
    document.querySelectorAll('button,a,[role="button"]').forEach(node=>{
      const text=String(node.textContent||'').replace(/\s+/g,'').trim();
      if(text.includes('AI大脑')&&text.includes('一次配置')){
        node.classList.add('r810-legacy-brain-entry');
        node.hidden=true;
        node.setAttribute('aria-hidden','true');
      }
    });
  }

  function normalizeMissionIdentity(){
    const title=document.getElementById('r810-mission-title');
    const host=title?.closest('.r810-mission-main');
    const label=host?.querySelector('small');
    if(!title||!label)return;
    const raw=String(title.textContent||'').trim();
    if(/^KZ-[A-Z0-9]+/i.test(raw)){
      label.textContent='Growth ID / 当前增长任务';
      host.dataset.identityKind='growth';
    }else if(/^MISSION-/i.test(raw)){
      label.textContent='当前 Mission';
      host.dataset.identityKind='mission';
    }else{
      label.textContent='当前任务';
      host.dataset.identityKind='task';
    }
  }

  function connectionStateText(){
    const text=document.getElementById('r810-connector-status')?.textContent?.trim();
    return text||'未验证连接';
  }

  function localStateText(){
    const text=document.getElementById('service-text')?.textContent?.trim()||'';
    if(/正常|已连接|运行中/.test(text))return ['正常','本地服务与自治执行可用'];
    if(/失败|异常|断开/.test(text))return ['异常','请运行系统体检查看原因'];
    return ['待体检','等待本地运行状态确认'];
  }

  function businessStateText(){
    const candidates=[document.getElementById('analytics-badge'),document.getElementById('dash-data-badge')].filter(Boolean);
    const text=candidates.map(x=>x.textContent||'').join(' ');
    if(/7\/7|已验证|真实/.test(text))return ['已验证','经营数据来源已通过验证'];
    if(/未接入|不可用|失败/.test(text))return ['未接入','当前没有完整真实经营数据'];
    return ['待验证','等待经营数据状态确认'];
  }

  function anomalyStateText(){
    const stage=document.getElementById('r810-stage-state')?.textContent?.trim()||'';
    const banner=[...document.querySelectorAll('main button,main span,main b')].map(x=>String(x.textContent||'').trim()).find(x=>/ChatGPT生产\/QC|异常待处理|自动恢复失败/.test(x));
    if(/异常/.test(stage)||banner)return ['需要处理',banner||stage.replace(/^阶段：/,'')];
    return ['正常','暂无需要老板介入的系统异常'];
  }

  function ensureConnectionOwnerSummary(){
    const page=document.getElementById('connections');
    const card=document.getElementById('r810-connector-card');
    if(!page||!card)return;
    let summary=document.getElementById('r810-owner-connection-summary');
    if(!summary){
      summary=document.createElement('div');
      summary.id='r810-owner-connection-summary';
      summary.className='r810-connection-summary';
      summary.innerHTML=`
        <div><small>ChatGPT 总控</small><b id="r810-owner-chatgpt">未验证连接</b><span>只有真实双向往返验证通过才显示已连接</span></div>
        <div><small>本地自治执行</small><b id="r810-owner-local">待体检</b><span id="r810-owner-local-note">等待本地运行状态确认</span></div>
        <div><small>经营数据</small><b id="r810-owner-business">待验证</b><span id="r810-owner-business-note">等待经营数据状态确认</span></div>
        <div><small>当前异常</small><b id="r810-owner-anomaly">正常</b><span id="r810-owner-anomaly-note">暂无需要老板介入的系统异常</span></div>`;
      card.insertAdjacentElement('afterend',summary);
    }
    let toggle=document.getElementById('r810-tech-toggle');
    if(!toggle){
      toggle=document.createElement('button');
      toggle.id='r810-tech-toggle';
      toggle.className='r810-tech-toggle';
      toggle.type='button';
      toggle.textContent='查看高级技术详情';
      summary.insertAdjacentElement('afterend',toggle);
      toggle.addEventListener('click',()=>{
        const show=toggle.dataset.open!=='1';
        toggle.dataset.open=show?'1':'0';
        toggle.textContent=show?'收起高级技术详情':'查看高级技术详情';
        page.querySelectorAll('[data-r810-technical="1"]').forEach(node=>{node.hidden=!show;});
      });
    }
    const technical=[page.querySelector('#integration-grid'),page.querySelector('.connection-layout'),page.querySelector('.ai-command-card'),page.querySelector('#bridge-panel')].filter(Boolean);
    technical.forEach(node=>{
      node.dataset.r810Technical='1';
      if(toggle.dataset.open!=='1')node.hidden=true;
    });
    syncConnectionSummary();
  }

  function syncConnectionSummary(){
    const chatgpt=document.getElementById('r810-owner-chatgpt');
    if(chatgpt)chatgpt.textContent=connectionStateText();
    const [local,localNote]=localStateText();
    const [business,businessNote]=businessStateText();
    const [anomaly,anomalyNote]=anomalyStateText();
    const localNode=document.getElementById('r810-owner-local');if(localNode)localNode.textContent=local;
    const localText=document.getElementById('r810-owner-local-note');if(localText)localText.textContent=localNote;
    const businessNode=document.getElementById('r810-owner-business');if(businessNode)businessNode.textContent=business;
    const businessText=document.getElementById('r810-owner-business-note');if(businessText)businessText.textContent=businessNote;
    const anomalyNode=document.getElementById('r810-owner-anomaly');if(anomalyNode)anomalyNode.textContent=anomaly;
    const anomalyText=document.getElementById('r810-owner-anomaly-note');if(anomalyText)anomalyText.textContent=anomalyNote;
  }

  function foldGatePanel(){
    const grid=document.querySelector('#r8-final-center .r8-gate-grid');if(!grid||grid.closest('details.r8-gate-details'))return false;
    const gates=[...grid.querySelectorAll('.r8-gate')];
    const ready=gates.filter(g=>g.querySelector('.r8-state.ready')).length;
    const details=document.createElement('details');details.className='r8-gate-details';
    const summary=document.createElement('summary');summary.innerHTML=`<div><b>系统验收明细</b><span>${ready}/${gates.length||0} 个关口已就绪；默认折叠，异常优先处理</span></div><strong>查看明细</strong>`;
    grid.parentNode.insertBefore(details,grid);details.append(summary,grid);
    const label=details.previousElementSibling?.querySelector('label');if(label)label.textContent='系统验收';
    return true;
  }

  function ensureSourceMeta(){
    const page=document.getElementById('r8-final-center');if(!page)return;
    page.querySelectorAll('.r8-final-kpi').forEach(card=>{
      if(card.querySelector('.kpi-source'))return;
      const source=document.createElement('small');source.className='kpi-source';source.textContent='来源：R8真实运营数据';card.appendChild(source);
    });
  }

  function refreshEnhancements(){
    businessCopy();
    injectSingleShellStyle();
    lockSingleShell();
    hideLegacyBrainEntry();
    normalizeMissionIdentity();
    ensureConnectionOwnerSummary();
    syncConnectionSummary();
    foldGatePanel();
    ensureSourceMeta();
  }

  let attempts=0;
  const timer=setInterval(()=>{attempts+=1;refreshEnhancements();if(attempts>=30)clearInterval(timer)},250);
  const observer=new MutationObserver(()=>{
    clearTimeout(observer._timer);
    observer._timer=setTimeout(()=>{
      lockSingleShell();
      hideLegacyBrainEntry();
      normalizeMissionIdentity();
      ensureConnectionOwnerSummary();
      syncConnectionSummary();
    },80);
  });
  observer.observe(document.documentElement,{childList:true,subtree:true,characterData:true});

  document.addEventListener('click',event=>{
    if(event.target.closest('[data-r8-final-tab],.nav[data-page="r8-final-center"],#r8-final-refresh'))setTimeout(()=>{foldGatePanel();ensureSourceMeta()},80);
  },true);
  refreshEnhancements();
})();
