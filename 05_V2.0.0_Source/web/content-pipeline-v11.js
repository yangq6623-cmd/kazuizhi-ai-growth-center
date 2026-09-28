(() => {
  'use strict';
  if (window.__KZ_CONTENT_PIPELINE_V11__) return;
  window.__KZ_CONTENT_PIPELINE_V11__ = true;

  const PIPELINE_KEY = 'kazuizhi.content-pipeline.v1';
  const REF_KEY = 'kazuizhi.reference-center.v1';
  const ROUTER_URL = 'http://127.0.0.1:17777/v1/chat/completions';
  const ROUTER_MODEL = 'kazuizhi-auto';
  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const now = () => new Date().toISOString();

  function readJson(key, fallback) {
    try { const data = JSON.parse(localStorage.getItem(key) || 'null'); return data ?? fallback; }
    catch { return fallback; }
  }
  function readPipeline() {
    const value = readJson(PIPELINE_KEY, {});
    return value && typeof value === 'object' ? value : {};
  }
  function writePipeline(patch) {
    const next = {...readPipeline(), ...patch, updatedAt: now()};
    localStorage.setItem(PIPELINE_KEY, JSON.stringify(next));
    updateProgress(next);
    return next;
  }
  function readReferenceStore() {
    const value = readJson(REF_KEY, {items:[], selected:''});
    return value && typeof value === 'object' ? value : {items:[], selected:''};
  }
  function getReference(id='') {
    const store = readReferenceStore();
    const refId = id || store.selected || '';
    return (store.items || []).find(item => item.id === refId) || (store.items || [])[0] || null;
  }
  function route(name) {
    if (typeof window.changePage === 'function') window.changePage(name);
    else if (typeof window.changeOperationalPage === 'function') window.changeOperationalPage(name);
  }
  function notify(message, type='blue') {
    let node = byId('v11-toast');
    if (!node) {
      node = document.createElement('div'); node.id = 'v11-toast'; node.className = 'v11-toast'; document.body.appendChild(node);
    }
    node.textContent = message; node.dataset.type = type; node.classList.add('show');
    clearTimeout(node._timer); node._timer = setTimeout(() => node.classList.remove('show'), 3000);
  }

  function installStyles() {
    if (byId('v11-style')) return;
    const style = document.createElement('style'); style.id = 'v11-style';
    style.textContent = `
      .v11-progress{display:flex;align-items:center;gap:6px;padding:7px 14px;background:#fff;border:1px solid #dfe7f1;border-top:0;border-radius:0 0 8px 8px;overflow-x:auto}
      .v11-progress b{font-size:12px;color:#17324f;margin-right:4px;white-space:nowrap}.v11-step{height:26px;padding:0 8px;border-radius:4px;display:inline-flex;align-items:center;gap:5px;font-size:11px;white-space:nowrap;background:#edf3fb;color:#55708e}.v11-step.done{background:#e8f7f0;color:#16875c}.v11-step.active{background:#e8f1ff;color:#1768e5}.v11-step.warn{background:#fff4df;color:#9a671c}
      .v11-trace{margin:0 0 12px;background:#f7faff;border:1px solid #dce7f4;border-radius:8px;padding:10px 12px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}.v11-trace b{font-size:12px;color:#17324f}.v11-trace span{font-size:12px;color:#6c7f96}.v11-trace code{font:11px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;color:#1768e5;background:#eef5ff;padding:3px 6px;border-radius:4px}
      .v11-creative-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px}.v11-creative-card{background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:14px;position:relative}.v11-creative-card.selected{border-color:#1768e5;box-shadow:0 0 0 2px rgba(23,104,229,.08)}.v11-creative-card h4{margin:0 0 7px;font-size:14px}.v11-creative-card p{margin:5px 0;font-size:12px;line-height:1.55;color:#53677e}.v11-score{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0}.v11-score span{height:24px;padding:0 7px;border-radius:4px;background:#eef5ff;color:#1768e5;font-size:11px;display:inline-flex;align-items:center}.v11-score .amber{background:#fff4df;color:#9a671c}.v11-card-actions{display:flex;justify-content:flex-end;gap:7px;margin-top:10px}.v11-btn{height:36px;border-radius:4px;padding:0 12px;font-size:12px;cursor:pointer}.v11-btn.primary{background:#1768e5;color:#fff;border:1px solid #1768e5;font-weight:700}.v11-btn.secondary{background:#fff;color:#24496f;border:1px solid #b9cbe0}
      .v11-director-result{margin-top:12px;background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:14px}.v11-director-result h3{font-size:14px;margin:0 0 10px}.v11-plan-summary{font-size:12px;color:#53677e;line-height:1.6;margin-bottom:10px}.v11-shot-list{display:grid;gap:8px}.v11-shot{border:1px solid #e1e8f1;border-radius:6px;padding:10px 12px;background:#fbfdff}.v11-shot-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.v11-shot-head b{font-size:13px}.v11-shot-head span{font-size:11px;color:#1768e5}.v11-shot-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:7px}.v11-shot-grid div{font-size:11px;color:#61748c}.v11-shot-grid strong{display:block;color:#203b59;font-size:11px;margin-bottom:2px}.v11-shot-text{margin-top:7px;font-size:12px;color:#3f5873;line-height:1.5}.v11-shot-tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}.v11-shot-tags span{font-size:10px;padding:3px 6px;background:#edf3fb;color:#4e6782;border-radius:4px}
      .v11-production-trace{margin:0 0 10px;border:1px solid #dce7f4;background:#f7faff;border-radius:6px;padding:9px 10px;font-size:11px;color:#53677e;display:flex;gap:9px;flex-wrap:wrap}.v11-production-trace b{color:#17324f}.v11-shot-detail{border-top:1px solid #e8eef5;margin-top:8px;padding-top:8px}.v11-shot-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px 9px}.v11-shot-detail-grid span{font-size:10px;color:#667b92}.v11-shot-detail-grid b{color:#203b59;font-weight:600}.v11-toast{position:fixed;right:24px;bottom:24px;z-index:9999;max-width:420px;padding:10px 14px;border-radius:6px;background:#17324f;color:#fff;font-size:12px;opacity:0;transform:translateY(8px);pointer-events:none;transition:.18s}.v11-toast.show{opacity:1;transform:none}.v11-toast[data-type="red"]{background:#c53b3b}.v11-toast[data-type="green"]{background:#16875c}.v11-toast[data-type="amber"]{background:#9a671c}
      @media(max-width:1100px){.v11-creative-grid{grid-template-columns:1fr}.v11-shot-grid{grid-template-columns:1fr 1fr}}
    `;
    document.head.appendChild(style);
  }

  function ensureProgress() {
    const shell = document.querySelector('.studio-shell');
    if (!shell || byId('v11-progress')) return;
    const bar = document.createElement('div'); bar.id = 'v11-progress'; bar.className = 'v11-progress';
    bar.innerHTML = '<b>生产进度</b><span class="v11-step" data-stage="reference">参考分析</span><span class="v11-step" data-stage="creative">创意方案</span><span class="v11-step" data-stage="director">AI导演</span><span class="v11-step" data-stage="storyboard">分镜</span><span class="v11-step" data-stage="production">生产</span>';
    shell.appendChild(bar); updateProgress(readPipeline());
  }
  function updateProgress(pipeline = readPipeline()) {
    const done = {
      reference: !!pipeline.reference?.analysis,
      creative: !!pipeline.selectedCreative,
      director: !!pipeline.directorPlan,
      storyboard: !!pipeline.directorPlan?.shots?.length,
      production: !!pipeline.productionProjectId,
    };
    let activeAssigned = false;
    document.querySelectorAll('#v11-progress .v11-step').forEach(step => {
      const key = step.dataset.stage; step.className = 'v11-step';
      if (done[key]) { step.classList.add('done'); step.textContent = `${stageLabel(key)} ✓`; }
      else if (!activeAssigned) { step.classList.add('active'); step.textContent = `${stageLabel(key)} · 下一步`; activeAssigned = true; }
      else step.textContent = stageLabel(key);
    });
  }
  function stageLabel(key) { return ({reference:'参考分析',creative:'创意方案',director:'AI导演',storyboard:'分镜',production:'生产'})[key] || key; }

  async function routerJson(prompt, temperature=0.35) {
    const response = await fetch(ROUTER_URL, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({model:ROUTER_MODEL,temperature,messages:[{role:'system',content:'你是卡嘴子AI内容创导平台的本地内容专家。只输出合法JSON，不要Markdown，不虚构没有提供的外部事实。'},{role:'user',content:prompt}]})
    });
    if (!response.ok) throw new Error(`本地 Router 返回 ${response.status}`);
    const data = await response.json();
    let text = data?.choices?.[0]?.message?.content || data?.response || '';
    text = String(text).trim().replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'');
    const first = text.indexOf('{'), last = text.lastIndexOf('}');
    if (first < 0 || last <= first) throw new Error('本地 Router 没有返回可解析 JSON');
    return JSON.parse(text.slice(first, last + 1));
  }

  function referenceToPipeline(item) {
    if (!item) return null;
    return {
      id:item.id, title:item.title || '未命名参考', platform:item.platform || '', source:item.url || '', rights:item.rights || '',
      kind:item.kind || '', sourceText:item.sourceText || '', analysis:item.analysis || null, updatedAt:item.updatedAt || '',
    };
  }
  function existingCreatives(item) {
    const source = item?.creative?.versions || item?.analysis?.kazuizhi_versions || [];
    return source.map((v,index) => ({
      id:`CR-${item.id}-${index+1}`, name:v.name || `创意${index+1}`, idea:v.idea || '', hook:v.hook || '', format:v.format || '真实案例',
      audience:v.audience || '涟水本地用户', duration:v.duration || '30 秒', cta:v.cta || '', score:v.score || null,
      rationale:v.rationale || '', source:'参考拆解已有方案', createdAt:now(),
    }));
  }
  function syncReference(id='') {
    const item = getReference(id); if (!item) return null;
    const patch = {reference:referenceToPipeline(item)};
    const creatives = existingCreatives(item);
    if (creatives.length) patch.creatives = creatives;
    writePipeline(patch); return item;
  }

  async function generateCreatives() {
    const item = getReference(readPipeline().reference?.id || '');
    if (!item) throw new Error('请先在“参考内容”导入并选择一条内容');
    if (!item.analysis) throw new Error('请先完成参考内容 AI 拆解');
    const prompt = `基于下面这条已经拆解过的参考内容，为卡嘴子本地服务重新创作 4 套原创方向。只能学习结构、钩子、节奏和方法，不直接复用未授权原画面、原声音、原文案。\n参考标题：${item.title}\n平台：${item.platform}\n使用边界：${item.rights}\n参考拆解：${JSON.stringify(item.analysis)}\n请严格输出：{"creatives":[{"name":"","idea":"","hook":"","format":"真实案例/师傅科普/数字人口播/真实素材+AI补镜","audience":"","duration":"30 秒","cta":"","score":{"local_fit":0,"commercial_value":0,"material_readiness":0,"production_difficulty":0,"recommendation":0},"rationale":""}]}。评分0-100；production_difficulty 数值越高表示越难。不要声称知道未提供的播放量或平台数据。`;
    const result = await routerJson(prompt, 0.45);
    const list = Array.isArray(result.creatives) ? result.creatives.slice(0,5) : [];
    if (!list.length) throw new Error('本地 AI 没有返回可用创意方案');
    const creatives = list.map((v,index) => ({
      id:`CR-${item.id}-${Date.now()}-${index+1}`, name:String(v.name||`创意${index+1}`), idea:String(v.idea||''), hook:String(v.hook||''), format:String(v.format||'真实案例'),
      audience:String(v.audience||'涟水本地用户'), duration:String(v.duration||'30 秒'), cta:String(v.cta||''), score:v.score && typeof v.score==='object'?v.score:null,
      rationale:String(v.rationale||''), source:'本地 Router 创意生成', createdAt:now(),
    }));
    writePipeline({reference:referenceToPipeline(item), creatives, selectedCreative:null, directorPlan:null, productionProjectId:''});
    renderCreative(); return creatives;
  }

  function creativeScoreHtml(score) {
    if (!score) return '<span class="amber">未评分</span>';
    const s = key => Number.isFinite(Number(score[key])) ? Math.max(0,Math.min(100,Number(score[key]))) : null;
    return [
      ['本地',s('local_fit')],['商业',s('commercial_value')],['素材',s('material_readiness')],['推荐',s('recommendation')]
    ].map(([label,value])=>value===null?'':`<span>${label} ${value}</span>`).join('') + (s('production_difficulty')===null?'':`<span class="amber">难度 ${s('production_difficulty')}</span>`);
  }
  function ensureCreativePanel() {
    const page = byId('creative'); if (!page || byId('v11-creative-panel')) return;
    const panel = document.createElement('div'); panel.id='v11-creative-panel';
    const header = page.querySelector('.studio-page-head'); header?.insertAdjacentElement('afterend', panel);
  }
  function renderCreative() {
    ensureCreativePanel(); const root=byId('v11-creative-panel'); if(!root)return;
    const p=readPipeline(), ref=p.reference; const creatives=Array.isArray(p.creatives)?p.creatives:[];
    root.innerHTML=`<div class="v11-trace"><b>来源追溯</b>${ref?`<code>${esc(ref.id)}</code><span>${esc(ref.title)} · ${esc(ref.platform||'本地导入')}</span>`:'<span>尚未从参考内容继承数据</span>'}<button class="v11-btn secondary" id="v11-sync-reference">同步当前参考</button><button class="v11-btn primary" id="v11-generate-creatives">AI 生成 / 刷新创意</button></div>${creatives.length?`<div class="v11-creative-grid">${creatives.map(c=>`<article class="v11-creative-card${p.selectedCreative?.id===c.id?' selected':''}" data-creative-id="${esc(c.id)}"><h4>${esc(c.name)}</h4><p><b>钩子：</b>${esc(c.hook||'待补充')}</p><p>${esc(c.idea||'')}</p><p><b>形式：</b>${esc(c.format)} · ${esc(c.duration||'30 秒')}</p><div class="v11-score">${creativeScoreHtml(c.score)}</div>${c.rationale?`<p><b>理由：</b>${esc(c.rationale)}</p>`:''}<div class="v11-card-actions"><button class="v11-btn primary" data-adopt-creative="${esc(c.id)}">采用这套创意</button></div></article>`).join('')}</div>`:'<div class="studio-empty">先从“参考内容”完成拆解，或点击“AI 生成 / 刷新创意”。</div>'}`;
    byId('v11-sync-reference')?.addEventListener('click',()=>{syncReference();renderCreative();notify('已同步当前参考内容','green')});
    byId('v11-generate-creatives')?.addEventListener('click',async e=>{const b=e.currentTarget,before=b.textContent;b.disabled=true;b.textContent='本地 AI 生成中…';try{syncReference();await generateCreatives();notify('已生成原创创意方案','green')}catch(err){notify(err.message,'red')}finally{b.disabled=false;b.textContent=before}});
    root.querySelectorAll('[data-adopt-creative]').forEach(btn=>btn.addEventListener('click',()=>adoptCreative(btn.dataset.adoptCreative)));
  }
  function adoptCreative(id) {
    const p=readPipeline(), creative=(p.creatives||[]).find(c=>c.id===id); if(!creative)return;
    writePipeline({selectedCreative:creative, directorPlan:null, productionProjectId:''});
    if(byId('creative-topic'))byId('creative-topic').value=creative.name||'';
    if(byId('creative-audience'))byId('creative-audience').value=creative.audience||'';
    if(byId('creative-core'))byId('creative-core').value=creative.idea||'';
    const format=byId('creative-format'); if(format){const option=[...format.options].find(o=>creative.format.includes(o.value)||o.value.includes(creative.format));if(option)format.value=option.value;}
    const duration=byId('creative-duration'); if(duration){const option=[...duration.options].find(o=>String(creative.duration).includes(o.value.replace(' 秒','')));if(option)duration.value=option.value;}
    renderCreative(); notify('已采用创意，可进入 AI 导演','green');
  }

  function creativeFromForm() {
    return {id:`CR-MANUAL-${Date.now()}`,name:byId('creative-topic')?.value.trim()||'手工创意',idea:byId('creative-core')?.value.trim()||'',hook:'',format:byId('creative-format')?.value||'真实案例',audience:byId('creative-audience')?.value.trim()||'',duration:byId('creative-duration')?.value||'30 秒',cta:'',score:null,rationale:'手工确认',source:'手工创意卡',createdAt:now()};
  }
  function goDirector() {
    let p=readPipeline(); let creative=p.selectedCreative;
    if(!creative){creative=creativeFromForm();writePipeline({selectedCreative:creative,creatives:[...(p.creatives||[]),creative],directorPlan:null});p=readPipeline();}
    const notes=[creative.name&&`创意：${creative.name}`,creative.hook&&`开头钩子：${creative.hook}`,creative.idea&&`核心：${creative.idea}`,creative.format&&`形式：${creative.format}`,creative.audience&&`用户：${creative.audience}`].filter(Boolean).join('\n');
    if(byId('director-brief'))byId('director-brief').value=notes; route('director'); setTimeout(renderDirector,60);
  }

  function ensureDirectorPanel() {
    const page=byId('director');if(!page)return;
    if(!byId('v11-director-trace')){const trace=document.createElement('div');trace.id='v11-director-trace';page.querySelector('.studio-page-head')?.insertAdjacentElement('afterend',trace);}
    if(!byId('v11-director-result')){const result=document.createElement('div');result.id='v11-director-result';result.className='v11-director-result';page.appendChild(result);}
    const main=byId('director-to-production'); if(main)main.textContent='生成导演方案';
    if(main && !byId('v11-confirm-director')){const confirm=document.createElement('button');confirm.id='v11-confirm-director';confirm.className='studio-secondary';confirm.textContent='确认分镜并进入生产';confirm.style.marginLeft='8px';confirm.hidden=true;main.insertAdjacentElement('afterend',confirm);confirm.addEventListener('click',importDirectorPlan);}
  }
  function renderDirector() {
    ensureDirectorPanel(); const p=readPipeline(), c=p.selectedCreative, r=p.reference, plan=p.directorPlan;
    const trace=byId('v11-director-trace');if(trace)trace.innerHTML=`<div class="v11-trace"><b>创意继承</b>${r?`<code>${esc(r.id)}</code>`:''}${c?`<code>${esc(c.id)}</code><span>${esc(c.name)} · ${esc(c.format)}</span>`:'<span>尚未选择创意</span>'}</div>`;
    const root=byId('v11-director-result');if(!root)return;
    if(!plan){root.innerHTML='<h3>导演结果</h3><div class="studio-empty">点击“生成导演方案”，本地 AI 会输出全片结构和 5–8 个可直接生产的镜头。</div>';byId('v11-confirm-director')?.setAttribute('hidden','');return;}
    const shots=Array.isArray(plan.shots)?plan.shots:[];
    root.innerHTML=`<h3>导演结果 · ${shots.length} 镜头</h3><div class="v11-plan-summary"><b>${esc(plan.summary||'')}</b><br>${esc(plan.script||'')}</div><div class="v11-shot-list">${shots.map((s,i)=>`<article class="v11-shot"><div class="v11-shot-head"><b>镜头 ${String(i+1).padStart(2,'0')} · ${esc(s.purpose||'')}</b><span>${esc(s.duration_seconds||4)} 秒 · ${esc(s.generation_method||'真实素材优先')}</span></div><div class="v11-shot-grid"><div><strong>人物</strong>${esc(s.character||'无/按需')}</div><div><strong>场景</strong>${esc(s.scene||'待匹配')}</div><div><strong>景别</strong>${esc(s.shot_type||'中景')}</div><div><strong>运镜</strong>${esc(s.motion||'稳定')}</div></div><div class="v11-shot-text">${esc(s.narration||s.action||'')}</div><div class="v11-shot-tags">${(s.consistency_locks||[]).map(x=>`<span>锁定：${esc(x)}</span>`).join('')}${(s.negative_constraints||[]).map(x=>`<span>禁止：${esc(x)}</span>`).join('')}</div></article>`).join('')}</div>`;
    const confirm=byId('v11-confirm-director');if(confirm)confirm.hidden=!shots.length;
  }

  async function generateDirectorPlan() {
    const p=readPipeline(), creative=p.selectedCreative; if(!creative)throw new Error('请先选择一套创意方案');
    const goal=byId('director-goal')?.value||'获得咨询', style=byId('director-style')?.value||'真实纪实', character=byId('director-character')?.value.trim()||'', scene=byId('director-scene')?.value.trim()||'', notes=byId('director-brief')?.value.trim()||'';
    const prompt=`把下面创意转换成可直接进入视频生产的 AI 导演方案。真实素材优先，RTX3060按3-6秒短镜头生产；总时长尽量接近${creative.duration||'30秒'}；生成5-8个镜头。\n创意：${JSON.stringify(creative)}\n参考拆解：${JSON.stringify(p.reference?.analysis||{})}\n视频目标：${goal}\n全片风格：${style}\n默认人物：${character||'按内容决定'}\n默认场景：${scene||'按内容决定'}\n导演补充：${notes}\n严格输出JSON：{"id":"","summary":"","goal":"","style":"","ratio":"9:16","total_duration":30,"script":"完整口播/字幕文案","shots":[{"purpose":"","character":"","scene":"","props":[""],"action":"","narration":"","shot_type":"","motion":"","duration_seconds":4,"generation_method":"真实素材/图生视频/文生视频/数字人","candidate_count":3,"consistency_locks":[""],"negative_constraints":["无水印","无乱码"]}]}。不要声称已经生成文件。`;
    const result=await routerJson(prompt,0.3); const shots=Array.isArray(result.shots)?result.shots.slice(0,8):[]; if(shots.length<1)throw new Error('本地 AI 没有返回有效镜头');
    const plan={...result,id:result.id||`DIR-${Date.now()}`,goal:result.goal||goal,style:result.style||style,ratio:result.ratio||'9:16',shots,createdAt:now(),source:'本地 Router AI 导演'};
    writePipeline({directorPlan:plan,productionProjectId:''});renderDirector();return plan;
  }

  async function importDirectorPlan() {
    const p=readPipeline(), plan=p.directorPlan, creative=p.selectedCreative;if(!plan?.shots?.length||!creative){notify('请先生成并确认导演方案','amber');return;}
    const button=byId('v11-confirm-director');if(button){button.disabled=true;button.textContent='正在建立生产项目…';}
    try{
      const response=await fetch('/api/ai-content-center/director/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:creative.name||p.reference?.title||'AI导演项目',script:plan.script||'',ratio:plan.ratio||'9:16',reference_id:p.reference?.id||'',creative_id:creative.id||'',director_plan_id:plan.id||'',director_goal:plan.goal||'',director_style:plan.style||'',director_summary:plan.summary||'',owner_note:`来源参考：${p.reference?.title||'无'}；创意：${creative.name||''}`,shots:plan.shots})});
      const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`生产中心返回 ${response.status}`);
      const result=data.data||data; const project=result.project||{};
      writePipeline({productionProjectId:project.id||'',productionImportedAt:now()});notify(`已导入 ${result.storyboards?.length||plan.shots.length} 个镜头，进入生产工作台`,'green');route('content');setTimeout(()=>{window.dispatchEvent(new CustomEvent('operational:content'));enhanceProduction()},180);
    }catch(err){notify(err.message,'red')}finally{if(button){button.disabled=false;button.textContent='确认分镜并进入生产';}}
  }

  async function enhanceProduction() {
    const page=byId('content');if(!page?.classList.contains('active'))return;
    try{
      const response=await fetch('/api/ai-content-center',{cache:'no-store'});const raw=await response.json();if(!response.ok)return;const data=raw.data||raw,p=readPipeline();
      const project=(data.projects||[]).find(x=>x.id===p.productionProjectId)||(data.projects||[])[0];if(!project)return;
      const shell=page.querySelector('.apc-shell');if(shell&&!byId('v11-production-trace')){const trace=document.createElement('div');trace.id='v11-production-trace';trace.className='v11-production-trace';trace.innerHTML=`<b>V1.1 来源链</b>${project.reference_id?`<span>参考 ${esc(project.reference_id)}</span>`:''}${project.creative_id?`<span>创意 ${esc(project.creative_id)}</span>`:''}${project.director_plan_id?`<span>导演 ${esc(project.director_plan_id)}</span>`:''}<span>项目 ${esc(project.id)}</span>`;shell.querySelector('.apc-topbar')?.insertAdjacentElement('afterend',trace);}
      const shots=(data.storyboards||[]).filter(x=>x.project_id===project.id);
      document.querySelectorAll('.apc-shot').forEach(card=>{
        const button=card.querySelector('[data-queue]');const shot=shots.find(x=>x.id===button?.dataset.queue);if(!shot||card.querySelector('.v11-shot-detail'))return;
        const detail=document.createElement('div');detail.className='v11-shot-detail';detail.innerHTML=`<div class="v11-shot-detail-grid"><span><b>人物</b> ${esc(shot.character||'无/按需')}</span><span><b>场景</b> ${esc(shot.scene||'待匹配')}</span><span><b>动作</b> ${esc(shot.action||'—')}</span><span><b>生成</b> ${esc(shot.generation_method||'待导演确认')}</span><span><b>候选</b> ${esc(shot.candidate_count||2)} 个</span><span><b>物品</b> ${esc((shot.props||[]).join('、')||'—')}</span></div>`;card.appendChild(detail);
      });
    }catch(_){}
  }

  function interceptClicks(event) {
    const target=event.target.closest?.('button');if(!target)return;
    if(target.id==='creative-to-director'){
      event.preventDefault();event.stopImmediatePropagation();goDirector();return;
    }
    if(target.id==='director-to-production'){
      event.preventDefault();event.stopImmediatePropagation();const old=target.textContent;target.disabled=true;target.textContent='本地 AI 导演中…';generateDirectorPlan().then(()=>notify('导演方案已生成，请确认分镜','green')).catch(err=>notify(err.message,'red')).finally(()=>{target.disabled=false;target.textContent=old||'生成导演方案'});return;
    }
    if(target.hasAttribute('data-ref-production')){
      event.preventDefault();event.stopImmediatePropagation();const id=target.getAttribute('data-ref-production');syncReference(id);route('creative');setTimeout(renderCreative,60);notify('参考内容已送入创意策划，而不是直接生产','green');return;
    }
    if(target.hasAttribute('data-ref-creative')){
      const id=target.getAttribute('data-ref-creative');setTimeout(()=>{syncReference(id);renderCreative()},80);
    }
  }

  function updateReferenceActions() {
    document.querySelectorAll('[data-ref-production]').forEach(btn=>{btn.textContent='进入创意策划';btn.title='先形成原创创意，再交给 AI 导演与生产工作台';});
  }
  function renderForActiveRoute() {
    const active=document.querySelector('#studio-pages>.page.active')?.id;
    if(active==='creative')renderCreative();if(active==='director')renderDirector();if(active==='content')setTimeout(enhanceProduction,120);if(active==='reference')updateReferenceActions();updateProgress();
  }
  function install() {
    installStyles();ensureProgress();syncReference(readPipeline().reference?.id||'');renderForActiveRoute();
    document.addEventListener('click',interceptClicks,true);
    window.addEventListener('operational:content',()=>setTimeout(enhanceProduction,100));
    new MutationObserver(()=>{updateReferenceActions();renderForActiveRoute()}).observe(document.getElementById('studio-pages')||document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
    setTimeout(renderForActiveRoute,350);setTimeout(renderForActiveRoute,1000);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
