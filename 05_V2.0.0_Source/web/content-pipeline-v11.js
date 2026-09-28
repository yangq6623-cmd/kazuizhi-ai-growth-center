(() => {
  'use strict';
  if (window.__KZ_CONTENT_PIPELINE_V11_SAFE__) return;
  window.__KZ_CONTENT_PIPELINE_V11_SAFE__ = true;

  const PIPELINE_KEY = 'kazuizhi.content-pipeline.v1';
  const REF_KEY = 'kazuizhi.reference-center.v1';
  const CREATIVE_KEY = 'kazuizhi.content-creative-card.v1';
  const ROUTER_URL = 'http://127.0.0.1:17777/v1/chat/completions';
  const ROUTER_MODEL = 'kazuizhi-auto';
  const byId = id => document.getElementById(id);
  const now = () => new Date().toISOString();
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let activeController = null;
  let operationToken = 0;

  function readJson(key, fallback) {
    try { const value = JSON.parse(localStorage.getItem(key) || 'null'); return value ?? fallback; }
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
    const value = readJson(REF_KEY, {items:[]});
    return value && typeof value === 'object' ? value : {items:[]};
  }
  function getReference(id='') {
    const store = readReferenceStore();
    const refId = id || store.selectedId || store.selected || '';
    return (store.items || []).find(item => item.id === refId) || (store.items || [])[0] || null;
  }
  function route(name) {
    if (typeof window.changePage === 'function') window.changePage(name);
  }
  function cancelPending() {
    operationToken += 1;
    if (activeController) {
      try { activeController.abort(); } catch (_) {}
      activeController = null;
    }
  }
  function toast(message, type='blue') {
    let node = byId('kz-safe-pipeline-toast');
    if (!node) {
      node = document.createElement('div');
      node.id = 'kz-safe-pipeline-toast';
      node.className = 'kz-safe-pipeline-toast';
      document.body.appendChild(node);
    }
    node.textContent = message;
    node.dataset.type = type;
    node.classList.add('show');
    clearTimeout(node._timer);
    node._timer = setTimeout(() => node.classList.remove('show'), 2600);
  }

  function installStyles() {
    if (byId('kz-safe-pipeline-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-safe-pipeline-style';
    style.textContent = `
      .kz-pipeline-progress{display:flex;align-items:center;gap:6px;padding:7px 14px;background:#fff;border:1px solid #dfe7f1;border-top:0;border-radius:0 0 8px 8px;overflow-x:auto}
      .kz-pipeline-progress b{font-size:12px;color:#17324f;margin-right:4px;white-space:nowrap}.kz-pipeline-step{height:26px;padding:0 8px;border-radius:4px;display:inline-flex;align-items:center;font-size:11px;white-space:nowrap;background:#edf3fb;color:#55708e}.kz-pipeline-step.done{background:#e8f7f0;color:#16875c}.kz-pipeline-step.active{background:#e8f1ff;color:#1768e5}
      .kz-trace{margin:0 0 12px;background:#f7faff;border:1px solid #dce7f4;border-radius:8px;padding:10px 12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}.kz-trace b{font-size:12px;color:#17324f}.kz-trace span{font-size:12px;color:#6c7f96}.kz-trace code{font:11px ui-monospace,SFMono-Regular,Consolas,monospace;color:#1768e5;background:#eef5ff;padding:3px 6px;border-radius:4px}
      .kz-creative-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 12px}.kz-creative-card{background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:14px}.kz-creative-card.selected{border-color:#1768e5;box-shadow:0 0 0 2px rgba(23,104,229,.08)}.kz-creative-card h4{margin:0 0 7px;font-size:14px}.kz-creative-card p{margin:5px 0;font-size:12px;line-height:1.55;color:#53677e}.kz-creative-card small{color:#6c7f96}.kz-creative-card button,.kz-confirm{height:36px;border-radius:4px;padding:0 12px;border:1px solid #1768e5;background:#1768e5;color:#fff;font-weight:700;cursor:pointer}
      .kz-director-result{margin-top:12px;background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:14px}.kz-director-result h3{font-size:14px;margin:0 0 8px}.kz-plan-summary{font-size:12px;color:#53677e;line-height:1.6;margin-bottom:10px}.kz-shot-list{display:grid;gap:8px}.kz-shot{border:1px solid #e1e8f1;border-radius:6px;padding:10px 12px;background:#fbfdff}.kz-shot-head{display:flex;justify-content:space-between;gap:8px}.kz-shot-head b{font-size:13px}.kz-shot-head span{font-size:11px;color:#1768e5}.kz-shot-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:7px}.kz-shot-grid div{font-size:11px;color:#61748c}.kz-shot-grid strong{display:block;color:#203b59;font-size:11px}.kz-shot-text{margin-top:7px;font-size:12px;color:#3f5873;line-height:1.5}.kz-shot-tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}.kz-shot-tags span{font-size:10px;padding:3px 6px;background:#edf3fb;color:#4e6782;border-radius:4px}.kz-director-actions{display:flex;justify-content:flex-end;margin-top:12px}
      .kz-safe-pipeline-toast{position:fixed;right:24px;bottom:24px;z-index:9999;max-width:420px;padding:10px 14px;border-radius:6px;background:#17324f;color:#fff;font-size:12px;opacity:0;transform:translateY(8px);pointer-events:none;transition:.15s}.kz-safe-pipeline-toast.show{opacity:1;transform:none}.kz-safe-pipeline-toast[data-type="red"]{background:#c53b3b}.kz-safe-pipeline-toast[data-type="green"]{background:#16875c}.kz-safe-pipeline-toast[data-type="amber"]{background:#9a671c}
      @media(max-width:1100px){.kz-creative-grid{grid-template-columns:1fr}.kz-shot-grid{grid-template-columns:1fr 1fr}}
    `;
    document.head.appendChild(style);
  }

  function ensureProgress() {
    const shell = document.querySelector('.studio-shell');
    if (!shell || byId('kz-pipeline-progress')) return;
    const bar = document.createElement('div');
    bar.id = 'kz-pipeline-progress';
    bar.className = 'kz-pipeline-progress';
    bar.innerHTML = '<b>生产进度</b><span class="kz-pipeline-step" data-stage="reference">参考分析</span><span class="kz-pipeline-step" data-stage="creative">创意方案</span><span class="kz-pipeline-step" data-stage="director">AI导演</span><span class="kz-pipeline-step" data-stage="storyboard">分镜</span><span class="kz-pipeline-step" data-stage="production">生产</span>';
    shell.appendChild(bar);
    updateProgress(readPipeline());
  }
  function updateProgress(state) {
    const done = {
      reference: !!state.reference?.analysis,
      creative: !!state.selectedCreative,
      director: !!state.directorPlan,
      storyboard: !!state.directorPlan?.shots?.length,
      production: !!state.productionProjectId,
    };
    let active = false;
    document.querySelectorAll('#kz-pipeline-progress [data-stage]').forEach(node => {
      const key = node.dataset.stage;
      node.className = 'kz-pipeline-step';
      if (done[key]) {
        node.classList.add('done');
        node.textContent = `${({reference:'参考分析',creative:'创意方案',director:'AI导演',storyboard:'分镜',production:'生产'})[key]} ✓`;
      } else if (!active) {
        active = true;
        node.classList.add('active');
        node.textContent = `${({reference:'参考分析',creative:'创意方案',director:'AI导演',storyboard:'分镜',production:'生产'})[key]} · 下一步`;
      }
    });
  }

  function referencePayload(item) {
    return item ? {id:item.id,title:item.title||'未命名参考',platform:item.platform||'',source:item.url||'',rights:item.rights||'',analysis:item.analysis||null} : null;
  }
  function creativeList(item) {
    const list = item?.creative?.versions || item?.analysis?.kazuizhi_versions || [];
    return list.map((v,index) => ({
      id:`CR-${item.id}-${index+1}`,
      name:v.name || `创意 ${index+1}`,
      topic:item.title || v.name || '卡嘴子原创内容',
      idea:v.idea || v.summary || '',
      hook:v.hook || '',
      format:v.format || '真实案例',
      audience:v.audience || '涟水本地用户',
      duration:v.duration || '30 秒',
      cta:v.cta || '需要本地服务时进入卡嘴子咨询或下单',
    }));
  }
  function selectCreative(creative, reference) {
    const selected = {...creative,id:creative.id || `CR-${Date.now()}`,referenceId:reference?.id || '',updatedAt:now()};
    localStorage.setItem(CREATIVE_KEY, JSON.stringify(selected));
    writePipeline({reference, selectedCreative:selected, directorPlan:null, productionProjectId:''});
    hydrateCreative(selected);
    return selected;
  }
  function hydrateCreative(card) {
    if (!card) return;
    if (byId('creative-topic')) byId('creative-topic').value = card.topic || card.name || '';
    if (byId('creative-format')) {
      const select = byId('creative-format');
      const match = [...select.options].find(o => card.format && (o.value === card.format || card.format.includes(o.value)));
      if (match) select.value = match.value;
    }
    if (byId('creative-audience')) byId('creative-audience').value = card.audience || '';
    if (byId('creative-duration')) {
      const select = byId('creative-duration');
      const match = [...select.options].find(o => String(card.duration||'').includes(o.value.replace(' 秒','')));
      if (match) select.value = match.value;
    }
    if (byId('creative-core')) byId('creative-core').value = card.idea || card.core || card.hook || '';
  }
  function readCreativeForm() {
    const old = readPipeline().selectedCreative || {};
    return {
      ...old,
      id:old.id || `CR-${Date.now()}`,
      topic:byId('creative-topic')?.value.trim() || old.topic || '',
      name:old.name || byId('creative-topic')?.value.trim() || '卡嘴子原创方案',
      format:byId('creative-format')?.value || old.format || '真实案例',
      audience:byId('creative-audience')?.value.trim() || old.audience || '涟水本地用户',
      duration:byId('creative-duration')?.value || old.duration || '30 秒',
      idea:byId('creative-core')?.value.trim() || old.idea || '',
      referenceId:old.referenceId || readPipeline().reference?.id || '',
      updatedAt:now(),
    };
  }
  function renderCreativeChoices(list, selectedId='') {
    let panel = byId('kz-creative-choices');
    const page = byId('creative');
    if (!page) return;
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'kz-creative-choices';
      const head = page.querySelector('.studio-page-head');
      head?.insertAdjacentElement('afterend', panel);
    }
    if (!list?.length) { panel.innerHTML = ''; return; }
    panel.innerHTML = `<div class="kz-trace"><b>参考已进入创意策划</b><span>请选择一个原创方向，或在下方继续手工修改。</span></div><div class="kz-creative-grid">${list.map((v,i)=>`<article class="kz-creative-card ${v.id===selectedId?'selected':''}"><h4>${esc(v.name)}</h4><p>${esc(v.idea||'')}</p><small>${esc(v.format||'')} · ${esc(v.hook||'')}</small><p><button type="button" data-kz-pick-creative="${i}">采用这套创意</button></p></article>`).join('')}</div>`;
    panel.querySelectorAll('[data-kz-pick-creative]').forEach(button => button.addEventListener('click', () => {
      const creative = list[Number(button.dataset.kzPickCreative)];
      const state = readPipeline();
      selectCreative(creative, state.reference);
      renderCreativeChoices(list, creative.id);
      toast('已采用该创意，可继续编辑后交给 AI 导演。','green');
    }, {once:true}));
  }

  function handoffReference(id) {
    const item = getReference(id);
    if (!item) { toast('没有找到参考内容。','red'); return; }
    const list = creativeList(item);
    if (!list.length) { toast('请先在参考内容页完成拆解并生成卡嘴子创意方案。','amber'); return; }
    const reference = referencePayload(item);
    writePipeline({reference,creatives:list,selectedCreative:null,directorPlan:null,productionProjectId:''});
    renderCreativeChoices(list);
    hydrateCreative(list[0]);
    route('creative');
    toast('参考内容已进入创意策划，请选择或修改原创方向。','green');
  }

  function sendCreativeToDirector() {
    const creative = readCreativeForm();
    if (!creative.topic && !creative.idea) { toast('请先填写创意主题或核心观点。','amber'); return; }
    localStorage.setItem(CREATIVE_KEY, JSON.stringify(creative));
    const state = writePipeline({selectedCreative:creative,directorPlan:null,productionProjectId:''});
    const brief = [
      creative.topic && `主题：${creative.topic}`,
      creative.idea && `核心观点：${creative.idea}`,
      creative.format && `表现形式：${creative.format}`,
      creative.audience && `目标用户：${creative.audience}`,
      creative.duration && `目标时长：${creative.duration}`,
      creative.hook && `开头钩子：${creative.hook}`,
      creative.cta && `CTA：${creative.cta}`,
      state.reference?.title && `参考来源：${state.reference.title}（只学习结构与方法）`,
    ].filter(Boolean).join('\n');
    if (byId('director-brief')) byId('director-brief').value = brief;
    route('director');
    toast('创意卡已交给 AI 导演。','green');
  }

  function parseDuration(value) {
    const n = Number(String(value||'30').match(/\d+/)?.[0] || 30);
    return Math.max(12, Math.min(n, 60));
  }
  function distribute(total) {
    const weights = [0.1,0.16,0.18,0.22,0.16,0.18];
    let used = 0;
    const result = weights.map((w,i) => {
      if (i === weights.length - 1) return Math.max(1,total-used);
      const value = Math.max(1,Math.round(total*w)); used += value; return value;
    });
    return result;
  }
  function fallbackPlan(creative, form) {
    const total = parseDuration(creative.duration);
    const d = distribute(total);
    const character = form.character || '授权维修师傅';
    const scene = form.scene || '本地真实维修场景';
    const topic = creative.topic || creative.name || '本地维修主题';
    const shots = [
      {purpose:'前三秒钩子',narration:creative.hook || `${topic}，先别急着按经验处理。`,duration_seconds:d[0],shot_type:'特写',motion:'轻微推进',candidate_count:3,character:'',scene,props:[],action:'先展示真实故障或结果',generation_method:'真实素材优先',consistency_locks:['场景风格'],negative_constraints:['水印','乱码','品牌错误']},
      {purpose:'问题与人物进入',narration:`说明用户遇到的具体问题，并让${character}进入场景。`,duration_seconds:d[1],shot_type:'中景',motion:'稳定跟拍',candidate_count:3,character,scene,props:['工具箱'],action:'人物到场并开始检查',generation_method:'真实素材/图生视频',consistency_locks:['人物','服装','场景'],negative_constraints:['人脸变形','多手指','水印']},
      {purpose:'专业判断',narration:creative.idea || '解释最容易误判的原因和正确判断方法。',duration_seconds:d[2],shot_type:'中近景',motion:'固定机位',candidate_count:3,character,scene,props:['维修工具'],action:'检查故障点并解释原因',generation_method:'真人口播+真实素材',consistency_locks:['人物','声音','服装'],negative_constraints:['口型异常','字幕乱码']},
      {purpose:'解决过程',narration:'展示处理步骤，用真实维修过程建立可信度。',duration_seconds:d[3],shot_type:'近景/特写',motion:'局部跟随',candidate_count:3,character,scene,props:['维修工具'],action:'执行维修或处理步骤',generation_method:'真实素材优先，缺口AI补镜',consistency_locks:['人物','场景','工具'],negative_constraints:['动作畸形','多余工具','水印']},
      {purpose:'结果证明',narration:'展示维修后的结果或前后对比。',duration_seconds:d[4],shot_type:'中景',motion:'轻微拉远',candidate_count:3,character,scene,props:[],action:'确认故障解决并展示结果',generation_method:'真实素材/图生视频',consistency_locks:['场景','人物'],negative_constraints:['结果不一致','品牌错误']},
      {purpose:'品牌CTA',narration:creative.cta || '涟水本地有维修需求，可通过卡嘴子咨询或下单。',duration_seconds:d[5],shot_type:'品牌收尾',motion:'固定',candidate_count:2,character:'',scene:'品牌结尾',props:['卡嘴子Logo','小程序码'],action:'显示品牌和行动引导',generation_method:'品牌模板+剪辑',consistency_locks:['Logo','联系方式','二维码'],negative_constraints:['电话号码错误','二维码不可识别','Logo变形']},
    ];
    return {id:`DP-${Date.now()}`,summary:`围绕“${topic}”制作 ${total} 秒${form.style}内容，真实素材优先，不足镜头再调用本地 AI 补充。`,source:'本地规则降级方案',shots,createdAt:now()};
  }
  function cleanArray(value) { return Array.isArray(value) ? value.map(v=>String(v)).filter(Boolean).slice(0,8) : value ? [String(value)] : []; }
  function normalizePlan(raw, creative, form) {
    const shots = (Array.isArray(raw?.shots) ? raw.shots : []).slice(0,8).map((s,index) => ({
      purpose:String(s.purpose || `镜头 ${index+1}`),
      narration:String(s.narration || s.dialogue || ''),
      duration_seconds:Math.max(1,Math.min(12,Number(s.duration_seconds || s.seconds || 4))),
      shot_type:String(s.shot_type || '中景'),
      motion:String(s.motion || '固定'),
      candidate_count:Math.max(1,Math.min(4,Number(s.candidate_count || 3))),
      character:String(s.character || form.character || ''),
      scene:String(s.scene || form.scene || ''),
      props:cleanArray(s.props),
      action:String(s.action || ''),
      generation_method:String(s.generation_method || '真实素材优先，缺口AI补镜'),
      consistency_locks:cleanArray(s.consistency_locks),
      negative_constraints:cleanArray(s.negative_constraints),
    })).filter(s => s.purpose || s.narration);
    if (shots.length < 5) return fallbackPlan(creative, form);
    return {id:`DP-${Date.now()}`,summary:String(raw.director_summary || raw.summary || `AI 导演已生成 ${shots.length} 个结构化镜头。`),source:'本地 Router',shots,createdAt:now()};
  }
  async function routerPlan(creative, form, token) {
    const controller = new AbortController();
    activeController = controller;
    const timeout = setTimeout(() => controller.abort(), 35000);
    try {
      const prompt = `为卡嘴子本地服务生成 5-8 个可执行短视频分镜。只能输出 JSON，不要 Markdown。\n创意：${JSON.stringify(creative)}\n视频目标：${form.goal}\n全片风格：${form.style}\n默认人物：${form.character}\n默认场景：${form.scene}\n导演说明：${form.brief}\n要求真实素材优先；缺口才用图生视频、文生视频或数字人；每镜头 1-12 秒；不要声称已生成视频。输出结构：{"director_summary":"","shots":[{"purpose":"","narration":"","duration_seconds":4,"shot_type":"","motion":"","candidate_count":3,"character":"","scene":"","props":[],"action":"","generation_method":"","consistency_locks":[],"negative_constraints":[]}]}。`;
      const response = await fetch(ROUTER_URL,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({model:ROUTER_MODEL,temperature:0.35,messages:[{role:'system',content:'你是卡嘴子AI导演。只输出合法JSON，不虚构外部事实。'},{role:'user',content:prompt}]})});
      if (!response.ok) throw new Error(`Router ${response.status}`);
      const data = await response.json();
      if (token !== operationToken) throw new DOMException('stale','AbortError');
      let text = String(data?.choices?.[0]?.message?.content || data?.response || '').trim().replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'');
      const first=text.indexOf('{'), last=text.lastIndexOf('}');
      if(first<0||last<=first) throw new Error('Router未返回JSON');
      return JSON.parse(text.slice(first,last+1));
    } finally { clearTimeout(timeout); if (activeController===controller) activeController=null; }
  }
  function readDirectorForm() {
    return {goal:byId('director-goal')?.value || '获得咨询',style:byId('director-style')?.value || '真实纪实',character:byId('director-character')?.value.trim() || '',scene:byId('director-scene')?.value.trim() || '',brief:byId('director-brief')?.value.trim() || ''};
  }
  async function generateDirectorPlan() {
    const state = readPipeline();
    const creative = state.selectedCreative || readCreativeForm();
    if (!creative.topic && !creative.idea) { toast('请先从创意策划选择或填写一套创意。','amber'); return; }
    const form = readDirectorForm();
    const button = byId('director-to-production');
    if (button) { button.disabled=true; button.textContent='AI 导演生成中…'; }
    cancelPending();
    const token = ++operationToken;
    let plan;
    try {
      const raw = await routerPlan(creative, form, token);
      if (token !== operationToken) return;
      plan = normalizePlan(raw, creative, form);
      toast(`AI 导演已生成 ${plan.shots.length} 个镜头，请确认。`,'green');
    } catch (error) {
      if (error?.name === 'AbortError') return;
      plan = fallbackPlan(creative, form);
      toast('本地 Router 未返回可用分镜，已生成可编辑的本地降级方案。','amber');
    } finally {
      if (button) { button.disabled=false; button.textContent='生成导演分镜'; }
    }
    if (!plan) return;
    plan = {...plan,goal:form.goal,style:form.style,character:form.character,scene:form.scene,creativeId:creative.id,referenceId:state.reference?.id || creative.referenceId || ''};
    writePipeline({selectedCreative:creative,directorPlan:plan,productionProjectId:''});
    renderDirectorPlan(plan);
  }
  function renderDirectorPlan(plan) {
    const page=byId('director'); if(!page||!plan?.shots?.length)return;
    let root=byId('kz-director-result');
    if(!root){root=document.createElement('section');root.id='kz-director-result';root.className='kz-director-result';page.appendChild(root);}
    root.innerHTML=`<h3>导演分镜预览 · ${esc(plan.source||'')}</h3><div class="kz-plan-summary">${esc(plan.summary||'')}</div><div class="kz-shot-list">${plan.shots.map((s,i)=>`<article class="kz-shot"><div class="kz-shot-head"><b>镜头 ${String(i+1).padStart(2,'0')} · ${esc(s.purpose)}</b><span>${esc(s.duration_seconds)} 秒 · 候选 ${esc(s.candidate_count)}</span></div><div class="kz-shot-grid"><div><strong>人物</strong>${esc(s.character||'无')}</div><div><strong>场景</strong>${esc(s.scene||'未指定')}</div><div><strong>景别/运镜</strong>${esc(s.shot_type)} / ${esc(s.motion)}</div><div><strong>生成方式</strong>${esc(s.generation_method)}</div></div><div class="kz-shot-text"><b>动作：</b>${esc(s.action||'')}<br><b>台词/旁白：</b>${esc(s.narration||'')}</div><div class="kz-shot-tags">${[...(s.consistency_locks||[]),...(s.negative_constraints||[])].map(v=>`<span>${esc(v)}</span>`).join('')}</div></article>`).join('')}</div><div class="kz-director-actions"><button class="kz-confirm" id="kz-confirm-storyboard" type="button">确认分镜并进入生产</button></div>`;
    byId('kz-confirm-storyboard')?.addEventListener('click', importToProduction, {once:true});
  }
  async function importToProduction() {
    const state = readPipeline(), plan = state.directorPlan, creative = state.selectedCreative;
    if (!plan?.shots?.length) { toast('请先生成导演分镜。','amber'); return; }
    const button=byId('kz-confirm-storyboard'); if(button){button.disabled=true;button.textContent='正在导入生产…';}
    try {
      const payload={name:`${creative?.topic||creative?.name||state.reference?.title||'内容项目'} · AI导演`,script:plan.shots.map(s=>s.narration).filter(Boolean).join('\n'),ratio:'9:16',reference_id:state.reference?.id||'',creative_id:creative?.id||'',director_plan_id:plan.id,director_goal:plan.goal||'',director_style:plan.style||'',director_summary:plan.summary||'',shots:plan.shots};
      const response=await fetch('/api/ai-content-center/director/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data=await response.json().catch(()=>({}));
      if(!response.ok) throw new Error(data.detail||data.error||`HTTP ${response.status}`);
      const projectId=data?.project?.id||data?.project_id||'';
      writePipeline({productionProjectId:projectId,productionImportedAt:now()});
      route('content');
      setTimeout(()=>{try{window.aiProductionCenterActivate?.();}catch(_){}},80);
      toast(`已导入 ${plan.shots.length} 个结构化镜头，等待候选生成。`,'green');
    } catch(error) {
      toast(`导入生产失败：${error.message}`,'red');
      if(button){button.disabled=false;button.textContent='确认分镜并进入生产';}
    }
  }

  function handleCapture(event) {
    const target = event.target.closest?.('button');
    if (!target) return;
    const refButton = target.closest('[data-ref-production]');
    if (refButton) {
      event.preventDefault(); event.stopImmediatePropagation();
      handoffReference(refButton.getAttribute('data-ref-production') || '');
      return;
    }
    if (target.id === 'creative-save') {
      event.preventDefault(); event.stopImmediatePropagation();
      const creative=readCreativeForm(); localStorage.setItem(CREATIVE_KEY,JSON.stringify(creative)); writePipeline({selectedCreative:creative}); toast('创意卡已保存。','green');
      return;
    }
    if (target.id === 'creative-to-director') {
      event.preventDefault(); event.stopImmediatePropagation(); sendCreativeToDirector(); return;
    }
    if (target.id === 'director-to-production') {
      event.preventDefault(); event.stopImmediatePropagation(); generateDirectorPlan(); return;
    }
    const routeButton=target.closest('.studio-tab[data-route]');
    if(routeButton){cancelPending();const next=routeButton.dataset.route;setTimeout(()=>{if(next==='creative'){const st=readPipeline();hydrateCreative(st.selectedCreative||readJson(CREATIVE_KEY,null));renderCreativeChoices(st.creatives||[],st.selectedCreative?.id||'');}if(next==='director'&&readPipeline().directorPlan)renderDirectorPlan(readPipeline().directorPlan);},0);}
  }

  function init() {
    installStyles(); ensureProgress();
    const directorButton=byId('director-to-production'); if(directorButton) directorButton.textContent='生成导演分镜';
    document.addEventListener('click', handleCapture, true);
    const state=readPipeline();
    if(state.selectedCreative) hydrateCreative(state.selectedCreative);
    if(state.creatives?.length) renderCreativeChoices(state.creatives,state.selectedCreative?.id||'');
    if(state.directorPlan) renderDirectorPlan(state.directorPlan);
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init,{once:true}); else init();
})();
