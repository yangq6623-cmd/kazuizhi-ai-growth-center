(() => {
  'use strict';

  function businessCopy(){
    document.title='卡嘴子 AI 运营增长中心';
    const baseline=document.querySelector('.baseline');
    if(baseline)baseline.innerHTML='<b>稳定运营底座</b><br><span>真实数据 · 自动执行 · 异常转人工</span><code>V2.2.1</code>';
    const badge=document.querySelector('#dashboard .welcome-badge');
    if(badge)badge.textContent='卡嘴子 AI · 今日运营总控';
    const heading=document.querySelector('#dashboard .command-welcome h2');
    if(heading)heading.textContent='从今天要完成的结果出发，统一管理任务、内容、终端和经营反馈。';
    const workflowLabel=document.querySelector('#workflow .page-title small');
    if(workflowLabel)workflowLabel.textContent='稳定运营底座';
    const r8Nav=document.querySelector('.nav[data-page="r8-final-center"]');
    if(r8Nav){r8Nav.dataset.title='增长运营总控';r8Nav.dataset.subtitle='从真实需求到发布、线索、订单和学习回写';r8Nav.innerHTML='<span>◆</span>增长运营总控'}
  }

  function addOperationalEntry(){
    const nav=document.querySelector('aside nav');if(!nav||nav.querySelector('.operational-entry'))return;
    const link=document.createElement('a');
    link.className='operational-entry';
    link.href='/operational.html';
    link.innerHTML='<span>▶</span><div><b>真实运营工作台</b><small>战役 · 内容 · 终端 · 账号 · 订单 · 搜索</small></div>';
    nav.prepend(link);
  }

  function simplifyNavigation(){
    const nav=document.querySelector('aside nav');if(!nav||nav.querySelector('details.nav-more'))return;
    const keep=new Set(['dashboard','workflow','connections','r8-final-center']);
    const detail=document.createElement('details');detail.className='nav-more';
    detail.innerHTML='<summary>更多运营工具 <span>展开</span></summary><div class="nav-more-body"></div>';
    const body=detail.querySelector('.nav-more-body');
    const buttons=[...nav.querySelectorAll('button.nav')];
    buttons.filter(btn=>!keep.has(btn.dataset.page)).forEach(btn=>body.appendChild(btn));
    [...nav.querySelectorAll('.nav-group')].forEach(label=>label.remove());
    nav.appendChild(detail);
    body.addEventListener('click',event=>{if(event.target.closest('button.nav'))detail.open=true});
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

  function refreshEnhancements(){businessCopy();addOperationalEntry();simplifyNavigation();foldGatePanel();ensureSourceMeta()}

  let attempts=0;
  const timer=setInterval(()=>{attempts+=1;refreshEnhancements();if(attempts>=20)clearInterval(timer)},300);
  document.addEventListener('click',event=>{
    if(event.target.closest('[data-r8-final-tab],.nav[data-page="r8-final-center"],#r8-final-refresh'))setTimeout(()=>{foldGatePanel();ensureSourceMeta()},80);
  },true);
  refreshEnhancements();
})();
