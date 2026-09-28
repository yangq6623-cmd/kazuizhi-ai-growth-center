(() => {
  const STORAGE_KEY = 'kazuizhi.reference-center.v1';
  const HANDOFF_KEY = 'kazuizhi.reference-production-handoff.v1';
  const ROUTER_URL = 'http://127.0.0.1:17777/v1/chat/completions';
  const ROUTER_MODEL = 'kazuizhi-auto';
  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const uid = () => `REF-${new Date().toISOString().slice(0,10).replaceAll('-','')}-${Math.random().toString(36).slice(2,7).toUpperCase()}`;
  const nowText = () => new Date().toLocaleString('zh-CN', {hour12:false});

  function readState(){
    try{
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return {items:Array.isArray(parsed.items)?parsed.items:[], selectedId:parsed.selectedId||''};
    }catch{return {items:[],selectedId:''};}
  }
  function writeState(next){
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }
  let store = readState();

  function inferPlatform(url=''){
    const value = String(url).toLowerCase();
    if(value.includes('douyin')) return '抖音';
    if(value.includes('xiaohongshu') || value.includes('xhslink')) return '小红书';
    if(value.includes('bilibili') || value.includes('b23.tv')) return 'B站';
    if(value.includes('weixin') || value.includes('channels')) return '视频号/微信';
    if(value.includes('kuaishou')) return '快手';
    if(value.includes('youtube') || value.includes('youtu.be')) return 'YouTube';
    return url ? '其他来源' : '未识别';
  }

  function toneFor(status=''){
    if(['已完成','已同步','正常','创意已生成','已送入生产'].some(x=>status.includes(x))) return 'green';
    if(['分析中','排队','处理中'].some(x=>status.includes(x))) return 'blue';
    if(['失败','异常'].some(x=>status.includes(x))) return 'red';
    return 'amber';
  }
  function chip(status){return `<span class="ref-chip ${toneFor(status)}">${esc(status||'待处理')}</span>`;}
  function selected(){return store.items.find(x=>x.id===store.selectedId) || store.items[0] || null;}
  function saveItem(item){
    const index = store.items.findIndex(x=>x.id===item.id);
    if(index>=0) store.items[index]=item; else store.items.unshift(item);
    store.selectedId=item.id;
    writeState(store);
    render();
  }
  function message(text,tone='info'){
    const box=byId('reference-feedback');
    if(!box)return;
    box.hidden=false;
    box.className=`reference-feedback ${tone}`;
    box.textContent=text;
    clearTimeout(message.timer);
    message.timer=setTimeout(()=>{box.hidden=true;},5200);
  }

  function buildShell(){
    if(byId('reference')) return;
    const content = byId('content');
    if(!content) return;

    const sidebarContent = document.querySelector('.sidebar .nav[data-page="content"]');
    if(sidebarContent && !document.querySelector('.sidebar .nav[data-page="reference"]')){
      const nav=document.createElement('button');
      nav.className='nav';
      nav.dataset.page='reference';
      nav.textContent='参考内容';
      sidebarContent.insertAdjacentElement('beforebegin',nav);
      nav.addEventListener('click',()=>window.changePage?.('reference'));
    }

    const workspaceContent=document.querySelector('.workspace-tab[data-workspace="content"]');
    if(workspaceContent && !document.querySelector('.workspace-tab[data-workspace="reference"]')){
      const tab=document.createElement('button');
      tab.className='workspace-tab';
      tab.dataset.workspace='reference';
      tab.innerHTML='<b>参考内容</b><span>链接导入、拆解与原创重构</span>';
      workspaceContent.insertAdjacentElement('beforebegin',tab);
      tab.addEventListener('click',()=>window.changePage?.('reference'));
    }

    const section=document.createElement('section');
    section.id='reference';
    section.className='page reference-page';
    section.innerHTML=`
      <div class="content-platform-switch" aria-label="AI内容创导平台流程">
        <div><small>卡嘴子 AI 内容创导平台</small><b>研究参考 → 创意重构 → AI 导演 → 内容生产</b></div>
        <nav>
          <button class="active" data-content-route="reference">参考内容中心</button>
          <button data-content-route="content">AI 内容生产</button>
        </nav>
      </div>
      <div class="reference-page-head">
        <div>
          <p>内容情报与参考中心</p>
          <h2>把优秀内容变成可追溯、可重构的卡嘴子原创生产方案</h2>
          <span>导入来源链接、视频、文案或历史作品；AI 只学习结构、节奏与方法，不把未授权原作品直接当成可发布素材。</span>
        </div>
        <div class="reference-head-actions">
          <button class="ref-secondary" id="reference-new">新建参考</button>
          <button class="ref-primary" id="reference-focus-import">粘贴内容链接</button>
        </div>
      </div>
      <div id="reference-feedback" class="reference-feedback" hidden></div>
      <section class="reference-kpis" id="reference-kpis"></section>
      <section class="reference-import-card">
        <div class="reference-section-title"><div><small>快速导入</small><h3>建立参考内容任务</h3></div><span>链接用于来源追踪；自动抓取能力必须以真实解析结果为准</span></div>
        <div class="reference-import-grid">
          <label class="reference-url-field">视频 / 内容链接<input id="reference-url" type="url" placeholder="粘贴抖音 / 视频号 / 小红书 / B站 / 网页链接"></label>
          <label>内容类型<select id="reference-kind"><option>视频</option><option>文章</option><option>图片</option><option>历史成片</option><option>其他</option></select></label>
          <label>使用边界<select id="reference-rights"><option value="reference_only">仅作参考，不直接复用原素材</option><option value="owned">公司自有素材</option><option value="authorized">已取得使用授权</option></select></label>
          <label class="reference-title-field">标题 / 备注<input id="reference-title" maxlength="160" placeholder="例如：维修类短视频参考案例"></label>
          <label class="reference-text-field">字幕 / 文案 / 摘要（建议粘贴，便于本地 AI 深度拆解）<textarea id="reference-text" rows="5" maxlength="12000" placeholder="可粘贴视频字幕、口播文案、文章正文或你自己的观察。URL 自动抓取未接通时，系统不会伪造解析结果。"></textarea></label>
          <div class="reference-import-actions">
            <button class="ref-primary" id="reference-create">建立参考任务</button>
            <button class="ref-secondary" id="reference-clear-form">清空</button>
          </div>
        </div>
      </section>
      <section class="reference-workspace">
        <aside class="reference-library">
          <div class="reference-section-title"><div><small>参考库</small><h3>已导入内容</h3></div><button class="ref-text" id="reference-clear-all">清空本机记录</button></div>
          <div class="reference-list" id="reference-list"></div>
        </aside>
        <main class="reference-analysis" id="reference-analysis"></main>
        <aside class="reference-director" id="reference-director"></aside>
      </section>`;
    content.insertAdjacentElement('beforebegin',section);

    if(!content.querySelector('.content-platform-switch')){
      const switcher=document.createElement('div');
      switcher.className='content-platform-switch compact';
      switcher.innerHTML=`<div><small>卡嘴子 AI 内容创导平台</small><b>参考内容与生产工作台分开运行</b></div><nav><button data-content-route="reference">参考内容中心</button><button class="active" data-content-route="content">AI 内容生产</button></nav>`;
      content.insertAdjacentElement('afterbegin',switcher);
    }

    document.querySelectorAll('[data-content-route="reference"]').forEach(btn=>btn.addEventListener('click',()=>window.changePage?.('reference')));
    document.querySelectorAll('[data-content-route="content"]').forEach(btn=>btn.addEventListener('click',()=>window.changePage?.('content')));
    bindStaticActions();
  }

  function bindStaticActions(){
    byId('reference-new')?.addEventListener('click',()=>{clearForm();byId('reference-url')?.focus();});
    byId('reference-focus-import')?.addEventListener('click',()=>byId('reference-url')?.focus());
    byId('reference-clear-form')?.addEventListener('click',clearForm);
    byId('reference-create')?.addEventListener('click',createReference);
    byId('reference-clear-all')?.addEventListener('click',()=>{
      if(!confirm('确认清空本机保存的参考内容记录？不会删除外部平台上的任何内容。'))return;
      store={items:[],selectedId:''};writeState(store);render();
    });
  }
  function clearForm(){
    ['reference-url','reference-title','reference-text'].forEach(id=>{const el=byId(id);if(el)el.value='';});
    if(byId('reference-kind'))byId('reference-kind').value='视频';
    if(byId('reference-rights'))byId('reference-rights').value='reference_only';
  }

  function createReference(){
    const url=byId('reference-url')?.value.trim()||'';
    const title=byId('reference-title')?.value.trim()||'';
    const text=byId('reference-text')?.value.trim()||'';
    if(!url && !text && !title){message('至少填写一个来源链接、标题或可分析文本。','warn');return;}
    const item={
      id:uid(),
      url,
      platform:inferPlatform(url),
      kind:byId('reference-kind')?.value||'视频',
      rights:byId('reference-rights')?.value||'reference_only',
      title:title||`${inferPlatform(url)}参考内容`,
      sourceText:text,
      status:text?'待分析':'待解析',
      createdAt:nowText(),
      updatedAt:nowText(),
      analysis:null,
      error:'',
      creative:null,
      handoff:null
    };
    saveItem(item);
    clearForm();
    message(text?'参考任务已建立，可调用本地 AI 深度拆解。':'参考任务已建立。当前只有来源链接，等待接入真实平台解析器或补充字幕/文案后再分析。','ok');
  }

  function render(){
    renderKpis();renderList();renderAnalysis();renderDirector();
    window.setTimeout(()=>window.dispatchEvent(new Event('resize')),30);
  }
  function renderKpis(){
    const root=byId('reference-kpis');if(!root)return;
    const total=store.items.length;
    const waiting=store.items.filter(x=>/待|警告/.test(x.status)).length;
    const active=store.items.filter(x=>/分析中|处理中|排队/.test(x.status)).length;
    const done=store.items.filter(x=>/已完成|创意已生成|已送入生产/.test(x.status)).length;
    root.innerHTML=`<article><small>参考内容</small><b>${total}</b><span>本机记录</span></article><article><small>待处理</small><b>${waiting}</b><span>等待解析 / 分析</span></article><article><small>处理中</small><b>${active}</b><span>本地 AI 任务</span></article><article><small>已完成</small><b>${done}</b><span>可进入创意 / 生产</span></article>`;
  }
  function renderList(){
    const root=byId('reference-list');if(!root)return;
    if(!store.items.length){root.innerHTML='<div class="reference-empty"><b>还没有参考内容</b><span>粘贴一个优秀视频链接，或先导入字幕/文案建立第一条参考任务。</span></div>';return;}
    root.innerHTML=store.items.map(item=>`<button class="reference-list-item ${item.id===selected()?.id?'active':''}" data-reference-id="${esc(item.id)}"><div><b>${esc(item.title)}</b>${chip(item.status)}</div><span>${esc(item.platform)} · ${esc(item.kind)}</span><small>${esc(item.createdAt)}</small></button>`).join('');
    root.querySelectorAll('[data-reference-id]').forEach(btn=>btn.addEventListener('click',()=>{store.selectedId=btn.dataset.referenceId;writeState(store);render();}));
  }

  function rightsText(value){return value==='owned'?'公司自有':value==='authorized'?'已授权':'仅作参考';}
  function structureRows(item){
    const rows=item.analysis?.structure;
    if(Array.isArray(rows)&&rows.length)return rows.map((row,index)=>`<div class="reference-structure-row"><span>${String(index+1).padStart(2,'0')}</span><b>${esc(row.stage||row.title||`阶段 ${index+1}`)}</b><p>${esc(row.detail||row.content||'')}</p></div>`).join('');
    return '<div class="reference-empty small"><b>还没有真实拆解结果</b><span>补充字幕/文案后点击“AI 深度拆解”。系统不会仅凭 URL 猜测原视频内容。</span></div>';
  }
  function arrayTags(values,empty='待分析'){
    return Array.isArray(values)&&values.length?values.map(x=>`<span>${esc(typeof x==='string'?x:(x.name||x.text||JSON.stringify(x)))}</span>`).join(''):`<em>${esc(empty)}</em>`;
  }

  function renderAnalysis(){
    const root=byId('reference-analysis');if(!root)return;
    const item=selected();
    if(!item){root.innerHTML='<div class="reference-empty hero"><b>选择或新建一条参考内容</b><span>这里会显示结构、镜头逻辑、风格 DNA、可借鉴方法与原创边界。</span></div>';return;}
    const a=item.analysis||{};
    root.innerHTML=`
      <div class="reference-section-title"><div><small>AI 参考拆解</small><h3>${esc(item.title)}</h3></div>${chip(item.status)}</div>
      <section class="reference-source-card">
        <div><small>来源平台</small><b>${esc(item.platform)}</b></div><div><small>内容类型</small><b>${esc(item.kind)}</b></div><div><small>使用边界</small><b>${esc(rightsText(item.rights))}</b></div><div><small>更新时间</small><b>${esc(item.updatedAt)}</b></div>
        ${item.url?`<p><span>来源链接</span><a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">打开原始来源 ↗</a></p>`:''}
      </section>
      ${item.error?`<div class="reference-error"><b>最近一次异常</b><span>${esc(item.error)}</span></div>`:''}
      <div class="reference-action-row">
        <button class="ref-primary" data-ref-analyze="${esc(item.id)}">AI 深度拆解</button>
        <button class="ref-secondary" data-ref-draft="${esc(item.id)}">生成本地结构草案</button>
        <button class="ref-text" data-ref-delete="${esc(item.id)}">删除参考</button>
      </div>
      <section class="reference-analysis-block"><div class="reference-block-head"><b>内容摘要与开头钩子</b><small>只基于已导入的真实文本</small></div><p>${esc(a.summary||'待分析')}</p><blockquote>${esc(a.hook||'尚未识别')}</blockquote></section>
      <section class="reference-analysis-block"><div class="reference-block-head"><b>内容结构</b><small>拆成可复用的方法，而不是照搬原文</small></div><div class="reference-structure">${structureRows(item)}</div></section>
      <section class="reference-analysis-block"><div class="reference-block-head"><b>风格 DNA</b><small>节奏、镜头、视觉、字幕与情绪</small></div><div class="reference-tags">${arrayTags(a.style_dna)}</div></section>
      <section class="reference-boundary-grid">
        <article><b>可以学习</b><div class="reference-tags green">${arrayTags(a.learnable,'等待分析')}</div></article>
        <article><b>必须重新制作</b><div class="reference-tags amber">${arrayTags(a.must_recreate,['文案','画面','人物','配音'])}</div></article>
        <article><b>不要直接使用</b><div class="reference-tags red">${arrayTags(a.do_not_use,['未授权原视频画面','原作者声音','平台水印'])}</div></article>
      </section>`;
    root.querySelector('[data-ref-analyze]')?.addEventListener('click',()=>analyzeReference(item.id));
    root.querySelector('[data-ref-draft]')?.addEventListener('click',()=>generateLocalDraft(item.id));
    root.querySelector('[data-ref-delete]')?.addEventListener('click',()=>deleteReference(item.id));
  }

  function renderDirector(){
    const root=byId('reference-director');if(!root)return;
    const item=selected();
    if(!item){root.innerHTML='<div class="reference-empty"><b>AI 导演交接</b><span>完成参考拆解后，系统会在这里生成原创方向并送入生产工作台。</span></div>';return;}
    const versions=item.creative?.versions || item.analysis?.kazuizhi_versions || [];
    root.innerHTML=`
      <div class="reference-section-title"><div><small>AI 导演</small><h3>卡嘴子原创重构</h3></div></div>
      <div class="reference-director-flow"><span class="done">参考</span><i>→</i><span class="${item.analysis?'done':'wait'}">拆解</span><i>→</i><span class="${versions.length?'done':'wait'}">创意</span><i>→</i><span class="${item.handoff?'done':'wait'}">生产</span></div>
      <div class="reference-director-note"><b>原创原则</b><p>学习主题、结构、节奏和表达方法；重新生成卡嘴子的文案、人物、声音和画面。真实素材优先，AI 只补缺口。</p></div>
      <div class="reference-version-list">${versions.length?versions.map((v,index)=>`<article class="reference-version ${index===0?'recommended':''}"><div><b>${esc(v.name||`方案 ${index+1}`)}</b>${index===0?'<span>推荐</span>':''}</div><p>${esc(v.idea||v.summary||'')}</p><small>${esc(v.format||'原创重构')} · ${esc(v.hook||'由 AI 导演生成开头')}</small></article>`).join(''):'<div class="reference-empty small"><b>还没有原创方案</b><span>先完成拆解，再生成“真实案例 / 师傅科普 / 数字人口播”等卡嘴子版本。</span></div>'}</div>
      <div class="reference-director-actions">
        <button class="ref-primary" data-ref-creative="${esc(item.id)}">生成卡嘴子创意方案</button>
        <button class="ref-secondary" data-ref-production="${esc(item.id)}" ${versions.length?'':'disabled'}>送入 AI 内容生产</button>
      </div>
      <details class="reference-tech"><summary>本地执行引擎</summary><p>AI 分析优先调用 <code>${ROUTER_MODEL}</code> · ${ROUTER_URL}</p><p>链接自动抓取属于独立解析能力；未拿到真实字幕/正文时不伪造分析结果。</p></details>`;
    root.querySelector('[data-ref-creative]')?.addEventListener('click',()=>generateCreative(item.id));
    root.querySelector('[data-ref-production]')?.addEventListener('click',()=>handoffToProduction(item.id));
  }

  function deleteReference(id){
    store.items=store.items.filter(x=>x.id!==id);
    store.selectedId=store.items[0]?.id||'';
    writeState(store);render();message('参考记录已从本机参考库移除。','ok');
  }

  function sentences(text){
    return String(text||'').split(/(?<=[。！？!?；;\n])/).map(x=>x.trim()).filter(Boolean);
  }
  function localAnalysis(item){
    const parts=sentences(item.sourceText);
    const hook=parts[0]?.slice(0,100)||item.title;
    const count=Math.max(1,parts.length);
    const slice=(start,end)=>parts.slice(Math.floor(count*start),Math.max(Math.floor(count*end),Math.floor(count*start)+1)).join(' ').slice(0,220);
    return {
      summary:(item.sourceText||item.title).slice(0,260),
      hook,
      structure:[
        {stage:'开头钩子',detail:slice(0,.18)||'待补充'},
        {stage:'问题 / 场景',detail:slice(.18,.38)||'待补充'},
        {stage:'核心信息',detail:slice(.38,.68)||'待补充'},
        {stage:'结果 / 证明',detail:slice(.68,.86)||'待补充'},
        {stage:'行动引导',detail:slice(.86,1)||'待补充'}
      ],
      style_dna:['节奏待 AI 判断','镜头风格待 AI 判断','字幕样式待 AI 判断','情绪基调待 AI 判断'],
      learnable:['主题方向','内容结构','节奏方法','用户痛点'],
      must_recreate:['卡嘴子原创文案','人物与声音','画面与镜头','品牌与 CTA'],
      do_not_use:['未授权原视频画面','原作者真人肖像/声音','平台水印','授权不明音乐'],
      kazuizhi_versions:[]
    };
  }
  function generateLocalDraft(id){
    const item=store.items.find(x=>x.id===id);if(!item)return;
    if(!item.sourceText){message('当前只有来源链接。请先补充字幕/文案，或等待后续接入真实平台解析器。','warn');return;}
    item.analysis=localAnalysis(item);item.status='已完成';item.updatedAt=nowText();item.error='';saveItem(item);message('已基于你粘贴的真实文本生成结构草案；风格与镜头判断仍建议调用本地 AI。','ok');
  }

  function stripJsonFence(text=''){
    const trimmed=String(text).trim();
    const fenced=trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
    return fenced?fenced[1].trim():trimmed;
  }
  async function callRouter(prompt){
    const response=await fetch(ROUTER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:ROUTER_MODEL,messages:[{role:'system',content:'你是卡嘴子 AI 内容创导平台的内容研究员和 AI 导演。严格区分参考学习与直接复制；没有输入事实时不要编造。只输出要求的 JSON。'},{role:'user',content:prompt}],temperature:.35})});
    if(!response.ok)throw new Error(`本地 Router 返回 ${response.status}`);
    const data=await response.json();
    return data?.choices?.[0]?.message?.content||data?.message?.content||'';
  }
  function analysisPrompt(item){return `请分析下面由用户主动导入的参考内容。只基于给出的文本，不要声称你已经打开或下载了来源链接。\n\n来源平台：${item.platform}\n来源链接：${item.url||'无'}\n标题：${item.title}\n使用边界：${rightsText(item.rights)}\n文本：\n${item.sourceText}\n\n输出严格 JSON：\n{\n  "summary":"不超过120字",\n  "hook":"概括开头钩子，不长段复刻原文",\n  "structure":[{"stage":"开头钩子","detail":"..."},{"stage":"问题/冲突","detail":"..."},{"stage":"核心价值","detail":"..."},{"stage":"结果/证明","detail":"..."},{"stage":"CTA","detail":"..."}],\n  "style_dna":["..."],\n  "learnable":["可借鉴的方法"],\n  "must_recreate":["必须重新制作的内容"],\n  "do_not_use":["不应直接复用的资产"],\n  "kazuizhi_versions":[{"name":"真实案例版","idea":"如何改成卡嘴子自己的原创内容","format":"真人/真实素材优先","hook":"新的原创钩子思路"},{"name":"师傅科普版","idea":"...","format":"师傅口播+维修B-roll","hook":"..."},{"name":"数字人口播版","idea":"...","format":"数字人+素材补镜","hook":"..."}]\n}`;}

  async function analyzeReference(id){
    const item=store.items.find(x=>x.id===id);if(!item)return;
    if(!item.sourceText){item.status='警告';item.error='只有来源链接，尚未取得可验证的字幕/正文。';item.updatedAt=nowText();saveItem(item);message('不能只根据 URL 猜测视频内容。请粘贴字幕/文案，或后续接入真实平台解析器。','warn');return;}
    item.status='分析中';item.error='';item.updatedAt=nowText();saveItem(item);
    try{
      const raw=await callRouter(analysisPrompt(item));
      const parsed=JSON.parse(stripJsonFence(raw));
      item.analysis=parsed;item.status='已完成';item.updatedAt=nowText();item.error='';saveItem(item);message('本地 AI 已完成参考内容深度拆解。','ok');
    }catch(error){
      item.status='异常';item.error=`本地 AI 分析失败：${error.message}`;item.updatedAt=nowText();saveItem(item);message('本地 AI Router 未完成分析。任务已保留，可检查 17777 服务后重试。','error');
    }
  }

  function fallbackVersions(item){
    const theme=item.analysis?.summary||item.title;
    return [
      {name:'真实案例版',idea:`围绕“${theme.slice(0,50)}”改写为涟水真实服务场景，用真实维修素材证明问题和解决过程。`,format:'真实素材 + AI 补镜',hook:'先展示真实问题，再让师傅给出反常识或避坑判断。'},
      {name:'师傅科普版',idea:'由固定维修师傅解释用户最容易误判的一点，中段展示工具和处理步骤，最后给出本地服务 CTA。',format:'师傅口播 + B-roll',hook:'用一个具体错误认知开场，而不是品牌自我介绍。'},
      {name:'数字人口播版',idea:'用授权数字人快速讲清问题和判断方法，插入真实现场/AI辅助镜头，适合批量测试不同标题。',format:'数字人 + 图生视频/真实素材',hook:'前三秒直接抛出用户问题和结果承诺。'}
    ];
  }
  function generateCreative(id){
    const item=store.items.find(x=>x.id===id);if(!item)return;
    if(!item.analysis){message('先完成参考拆解，再生成原创方案。','warn');return;}
    const versions=Array.isArray(item.analysis.kazuizhi_versions)&&item.analysis.kazuizhi_versions.length?item.analysis.kazuizhi_versions:fallbackVersions(item);
    item.creative={versions,createdAt:nowText()};item.status='创意已生成';item.updatedAt=nowText();saveItem(item);message('已形成卡嘴子原创重构方案，可选择后送入 AI 内容生产。','ok');
  }

  function handoffToProduction(id){
    const item=store.items.find(x=>x.id===id);if(!item)return;
    const versions=item.creative?.versions||item.analysis?.kazuizhi_versions||[];
    if(!versions.length){message('还没有可交接的创意方案。','warn');return;}
    const chosen=versions[0];
    const brief=[
      `【参考来源】${item.title}（${item.platform}，${rightsText(item.rights)}）`,
      `【原创方向】${chosen.name||'卡嘴子原创版'}`,
      `【创意说明】${chosen.idea||''}`,
      `【表现形式】${chosen.format||''}`,
      `【开头思路】${chosen.hook||''}`,
      '【生产原则】真实素材优先；不足部分再用 AI 图片/图生视频/文生视频补镜；不得直接复用未授权原视频画面、原作者声音、平台水印。'
    ].join('\n');
    const payload={referenceId:item.id,source:item.url,title:item.title,brief,createdAt:nowText()};
    localStorage.setItem(HANDOFF_KEY,JSON.stringify(payload));
    item.handoff=payload;item.status='已送入生产';item.updatedAt=nowText();saveItem(item);
    const script=byId('video-script');if(script)script.value=brief;
    window.changePage?.('content');
    window.setTimeout(()=>{
      byId('video-script')?.scrollIntoView({behavior:'smooth',block:'center'});
      message('创意方案已送入 AI 内容生产工作台。','ok');
    },120);
  }

  function install(){buildShell();render();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();