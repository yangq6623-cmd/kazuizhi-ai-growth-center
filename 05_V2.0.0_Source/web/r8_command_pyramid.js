(() => {
  'use strict';
  const GROUPS = [
    ['一、总控与决策', ['dashboard','workflow']],
    ['二、团队与设备', ['social-center','connections']],
    ['三、增长执行', ['r8-final-center','operational-hub','promotion','automation']],
    ['四、数据反馈', ['analytics','insights','summary','review']],
    ['五、复盘与沉淀', ['plan','history','memory','handoff']],
  ];
  const LABELS = {
    ready:'已就绪', pass:'已通过', pending:'待完成', blocked:'被阻塞', not_configured:'未配置',
    pending_connector:'待授权平台', pending_device:'待连接真机', waiting_first_case:'待首条真实任务',
    pending_worker:'待配置视频模型', waiting_first_receipt:'待真实发布回执', waiting_first_message:'待真实消息',
    waiting_metrics:'待效果数据', waiting_learning_cycle:'待首轮复盘', new:'新建', routed:'已路由',
    no_matching_account:'无匹配账号', candidate_needs_authorization:'候选账号待授权', planning:'策划中',
    content_pending_approval:'内容待审核', content_approved:'内容已通过', approved:'已审核', rejected:'已退回',
    revision_requested:'待修改', queued:'排队中', waiting_worker:'等待视频模型', running:'执行中',
    awaiting_owner_review:'等待老板审核', published:'已发布', failed:'失败', closed:'已结束',
    qualified:'有效线索', conversion:'转化', search:'搜索增长', education:'知识科普', brand:'品牌', recruitment:'招募',
    low:'低', medium:'中', high:'高', normal:'正常', attention:'需注意', human_required:'转人工',
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function organiseNavigation(){
    const nav=document.querySelector('aside nav'); if(!nav)return;
    const buttons=[...nav.querySelectorAll('button.nav')];
    if(!buttons.find(x=>x.dataset.page==='r8-final-center')||!buttons.find(x=>x.dataset.page==='social-center'))return;
    nav.querySelectorAll('.nav-group').forEach(x=>x.remove());
    const map=new Map(buttons.map(x=>[x.dataset.page,x]));
    GROUPS.forEach(([title,pages])=>{
      const group=document.createElement('small');group.className='nav-group';group.textContent=title;nav.appendChild(group);
      pages.forEach(page=>{const button=map.get(page);if(button)nav.appendChild(button);});
    });
    buttons.filter(x=>!GROUPS.some(([,pages])=>pages.includes(x.dataset.page))).forEach(x=>nav.appendChild(x));
    nav.dataset.pyramidReady='1';
  }

  function injectStyles(){
    if(document.getElementById('r8-pyramid-style'))return;
    const style=document.createElement('style');style.id='r8-pyramid-style';style.textContent=`
      .r8-command-pyramid{margin:16px 0;padding:18px;border:1px solid #dfe6f2;border-radius:18px;background:#fff}
      .r8-command-pyramid header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:14px}.r8-command-pyramid h3{margin:4px 0}.r8-command-pyramid p{margin:0;color:#69778b}
      .r8-pyramid-layers{display:flex;flex-direction:column;align-items:center;gap:8px}.r8-pyramid-layer{border:0;border-radius:12px;padding:12px 18px;color:#fff;text-align:left;cursor:pointer;box-shadow:0 5px 16px rgba(26,60,120,.10)}
      .r8-pyramid-layer b,.r8-pyramid-layer small{display:block}.r8-pyramid-layer small{opacity:.88;margin-top:3px}.r8-pyramid-layer:nth-child(1){width:42%;background:#174ba4}.r8-pyramid-layer:nth-child(2){width:56%;background:#2864cc}.r8-pyramid-layer:nth-child(3){width:70%;background:#3b77dc}.r8-pyramid-layer:nth-child(4){width:84%;background:#4d8ae6}.r8-pyramid-layer:nth-child(5){width:96%;background:#6099ec}
      .r8-loop-return{margin-top:12px;padding:10px;border-radius:10px;background:#eef5ff;text-align:center;color:#285ba6}.r8-loop-score{white-space:nowrap;padding:7px 10px;border-radius:999px;background:#eef5ff;color:#285ba6;font-weight:700}
      .r8-action-feedback{margin:0 0 12px;padding:11px 13px;border-radius:10px;background:#eef5ff;color:#285ba6}.r8-action-feedback.error{background:#fdeaea;color:#a12d2d}.r8-action-feedback.ok{background:#e8f7ee;color:#187342}
      .r8-inline-config{display:grid;grid-template-columns:1fr 1fr auto;gap:9px;margin:12px 0;padding:12px;background:#f7f9fc;border-radius:12px}.r8-inline-config input{min-width:0;border:1px solid #d8e0ec;border-radius:8px;padding:9px}.r8-inline-config button{white-space:nowrap}
      .r8-diagnostic-grid{display:grid;gap:8px;margin:12px 0}.r8-diagnostic-row{display:grid;grid-template-columns:70px 150px 1fr auto;gap:10px;align-items:center;padding:10px;border:1px solid #e1e7f0;border-radius:10px;background:#fff}.r8-diagnostic-row small{color:#69778b}.r8-diagnostic-row em{font-style:normal;color:#8b6100}
      @media(max-width:760px){.r8-pyramid-layer{width:100%!important}.r8-inline-config,.r8-diagnostic-row{grid-template-columns:1fr}.r8-command-pyramid header{display:block}}
    `;document.head.appendChild(style);
  }

  async function request(path, options){const response=await fetch(path,options||{cache:'no-store'});let body={};try{body=await response.json();}catch{}if(!response.ok)throw new Error(body.error||`请求失败 ${response.status}`);return body;}

  function ensurePyramid(){
    const dashboard=document.getElementById('dashboard');if(!dashboard||document.getElementById('r8-command-pyramid'))return;
    const card=document.createElement('section');card.id='r8-command-pyramid';card.className='r8-command-pyramid';
    card.innerHTML=`<header><div><label>总控制台工作链</label><h3>从老板目标到员工执行，再由真实数据回流分析</h3><p>点击任一层，直接进入对应工作区。</p></div><span id="r8-pyramid-score" class="r8-loop-score">正在体检</span></header><div class="r8-pyramid-layers">
      <button class="r8-pyramid-layer" data-pyramid-page="dashboard"><b>① 老板总控与 AI 决策</b><small>下达目标、确定边界、查看关键阻塞</small></button>
      <button class="r8-pyramid-layer" data-pyramid-page="workflow"><b>② 八名 AI 员工协作</b><small>拆解任务、联合策划、审批与交接</small></button>
      <button class="r8-pyramid-layer" data-pyramid-page="r8-final-center"><b>③ 内容、视频、社媒执行</b><small>真机、账号、内容审核、视频工厂与发布</small></button>
      <button class="r8-pyramid-layer" data-pyramid-page="analytics"><b>④ 真实数据与发布回执</b><small>经营数据、平台 URL、线索、订单与效果指标</small></button>
      <button class="r8-pyramid-layer" data-pyramid-page="review"><b>⑤ 复盘学习回到总控</b><small>24小时 / 72小时 / 7天复盘，形成下一轮调整</small></button>
    </div><div id="r8-loop-return" class="r8-loop-return">真实反馈 → 双向运营桥 → ChatGPT 分析 → 下一轮老板决策</div>`;
    const anchor=dashboard.querySelector('.command-welcome')||dashboard.firstElementChild;anchor?.insertAdjacentElement('afterend',card);
    card.querySelectorAll('[data-pyramid-page]').forEach(button=>button.onclick=()=>typeof openPage==='function'&&openPage(button.dataset.pyramidPage));
    refreshPyramid();
  }

  async function refreshPyramid(){
    const score=document.getElementById('r8-pyramid-score'),loop=document.getElementById('r8-loop-return');if(!score)return;
    try{const result=await request('/api/r8/growth/diagnostics');score.textContent=`闭环得分 ${result.score ?? 0}/10`;const blocker=result.first_blocker;loop.textContent=blocker?`当前首要阻塞：第 ${blocker.step} 步 ${blocker.name}。${blocker.action}`:'闭环已经具备真实上线条件，可继续观察效果数据。';}
    catch(error){score.textContent='体检待刷新';if(loop)loop.textContent='闭环状态读取失败：'+error.message;}
  }

  function localizeR8(){
    const root=document.getElementById('r8-final-center');if(!root)return;
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
    nodes.forEach(node=>{const raw=node.nodeValue.trim();if(!raw)return;if(LABELS[raw])node.nodeValue=node.nodeValue.replace(raw,LABELS[raw]);else if(/^Gate\s+\d+$/.test(raw))node.nodeValue=node.nodeValue.replace(raw,raw.replace('Gate','关口'));});
    const hero=root.querySelector('.r8-final-hero small');if(hero)hero.textContent='R8 最终版 · 全链路增长运营';
  }

  function enhanceWorkerForm(){
    const button=document.getElementById('r8-worker-config');if(!button||document.getElementById('r8-worker-inline-config'))return;
    button.style.display='none';const form=document.createElement('div');form.id='r8-worker-inline-config';form.className='r8-inline-config';
    form.innerHTML='<input id="r8-worker-model-path" placeholder="本地视频模型目录，例如 D:\\AI模型"><input id="r8-worker-output-root" placeholder="成片输出目录，例如 D:\\成片"><button id="r8-worker-save" class="primary-small">验证并保存配置</button>';
    (document.querySelector('.r8-worker')||button.parentElement).insertAdjacentElement('afterend',form);
    form.querySelector('#r8-worker-save').onclick=async()=>{const save=form.querySelector('#r8-worker-save');save.disabled=true;save.textContent='正在验证…';try{await request('/api/r8/growth/video-worker',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({configured:true,model_path:form.querySelector('#r8-worker-model-path').value.trim(),output_root:form.querySelector('#r8-worker-output-root').value.trim()})});if(typeof toast==='function')toast('视频模型与成片目录已验证并保存');if(window.loadR8FinalCenter)window.loadR8FinalCenter();}catch(error){if(typeof toast==='function')toast(error.message,'error');}finally{save.disabled=false;save.textContent='验证并保存配置';}};
  }

  function showDiagnostics(result){
    const root=document.getElementById('r8-final-body');if(!root)return;let box=document.getElementById('r8-diagnostic-result');if(box)box.remove();
    const evidence=result.evidence||{},business=evidence.business_summary||{};const realData=business.users?`用户 ${business.users.total||0}、订单 ${business.orders?.total||0}、小程序访问 ${business.mini_program?.visit_uv||0}`:'未接入或未读到真实经营数据';
    box=document.createElement('article');box.id='r8-diagnostic-result';box.className='wide';box.innerHTML=`<div class="article-head"><div><label>0→10 全链路验收</label><h3>闭环得分 ${esc(result.score)}/10</h3></div><span class="r8-state ${result.status==='closed_loop_ready'?'ready':'pending'}">${result.status==='closed_loop_ready'?'真实闭环已通':'仍有真实阻塞'}</span></div><div class="r8-truth">${esc(result.truth)}</div><div class="grid three"><div class="r8-final-note"><b>已收集真实数据</b><br>${esc(realData)}</div><div class="r8-final-note"><b>已生成/已发布</b><br>内容任务 ${evidence.content_drafts||0}；成片 ${evidence.video_outputs?.length||0}；真实发布 ${evidence.published_urls?.length||0}</div><div class="r8-final-note"><b>搜索收录验证</b><br>${esc(evidence.indexing_status||'待检查')}</div></div><div class="r8-diagnostic-grid">${(result.checks||[]).map(row=>`<div class="r8-diagnostic-row"><b>第 ${row.step} 步</b><span>${esc(row.name)}</span><small>${esc(row.detail)}</small><em>${row.status==='pass'?'已通过':esc(row.action)}</em></div>`).join('')}</div>`;root.prepend(box);box.scrollIntoView({behavior:'smooth',block:'start'});
  }

  function bindEnhancements(){
    const root=document.getElementById('r8-final-center');if(!root||root.dataset.commandEnhancements)return;root.dataset.commandEnhancements='1';
    root.addEventListener('click',async event=>{
      const diagnostic=event.target.closest('#r8-diagnostics');if(diagnostic){event.preventDefault();event.stopImmediatePropagation();diagnostic.disabled=true;diagnostic.textContent='正在逐项检查…';try{const result=await request('/api/r8/growth/diagnostics');showDiagnostics(result);refreshPyramid();if(typeof toast==='function')toast(`0→10 闭环体检完成：${result.score}/10`);}catch(error){if(typeof toast==='function')toast(error.message,'error');}finally{diagnostic.disabled=false;diagnostic.textContent='运行 0→10 闭环体检';}return;}
      const account=event.target.closest('[data-r8-open-accounts]');if(account){if(typeof openPage==='function')openPage('social-center');if(typeof toast==='function')toast('已打开社媒中心，请绑定账号并在真机完成登录');}
    },true);
  }

  function enhanceR8(){
    const root=document.getElementById('r8-final-center');if(!root)return;
    localizeR8();enhanceWorkerForm();bindEnhancements();
    const diagnostics=document.getElementById('r8-diagnostics');if(diagnostics)diagnostics.textContent='运行 0→10 闭环体检';
    const overview=[...root.querySelectorAll('article')].find(x=>x.textContent.includes('真实账号授权状态'));
    if(overview&&!overview.querySelector('[data-r8-open-accounts]'))overview.insertAdjacentHTML('beforeend','<button class="primary-small" data-r8-open-accounts="1" style="margin-top:12px">去绑定和授权平台账号</button>');
  }

  function boot(){injectStyles();ensurePyramid();setTimeout(()=>{organiseNavigation();enhanceR8();},700);setTimeout(()=>{organiseNavigation();enhanceR8();},1800);const observer=new MutationObserver(()=>enhanceR8());const target=document.querySelector('main');if(target)observer.observe(target,{subtree:true,childList:true});}
  window.R8CommandPyramid={refresh:refreshPyramid,organiseNavigation,showDiagnostics};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
