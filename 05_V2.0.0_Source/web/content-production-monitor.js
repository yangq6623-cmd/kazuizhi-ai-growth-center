(() => {
  'use strict';
  if (window.__KZ_PRODUCTION_MONITOR__) return;
  window.__KZ_PRODUCTION_MONITOR__ = true;

  const PIPELINE_KEY = 'kazuizhi.content-pipeline.v1';
  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;'}[c]));
  const json = (url, options={}) => fetch(url, options).then(async response => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.detail || data.message || `HTTP ${response.status}`);
    return data;
  });
  const readPipeline = () => {
    try { return JSON.parse(localStorage.getItem(PIPELINE_KEY) || '{}') || {}; }
    catch { return {}; }
  };
  const post = (url, body) => json(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  let last = null;
  let timer = null;
  let installAttempts = 0;

  function installStyle() {
    if (byId('kz-production-monitor-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-production-monitor-style';
    style.textContent = `
      .kz-prod-monitor{margin-top:14px;border:1px solid #d8e3f0;border-radius:8px;background:#f8fbff;padding:14px;display:grid;gap:12px}
      .kz-prod-monitor-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.kz-prod-monitor-head h4{margin:0 0 4px;font-size:14px;color:#17324f}.kz-prod-monitor-head p{margin:0;color:#6d7f96;font-size:11px}.kz-prod-live{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#16875c;background:#e9f7f0;padding:5px 8px;border-radius:999px;white-space:nowrap}.kz-prod-live i{width:7px;height:7px;border-radius:50%;background:#21a56f}
      .kz-prod-summary{display:grid;grid-template-columns:1.25fr repeat(4,minmax(0,.75fr));gap:8px}.kz-prod-metric{background:#fff;border:1px solid #e2e9f2;border-radius:6px;padding:10px;min-width:0}.kz-prod-metric small{display:block;color:#8292a5;font-size:10px;margin-bottom:4px}.kz-prod-metric b{display:block;color:#17324f;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kz-prod-metric span{font-size:10px;color:#6d7f96}
      .kz-prod-progress{background:#fff;border:1px solid #e2e9f2;border-radius:6px;padding:10px}.kz-prod-progress-top{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:#53677e;margin-bottom:7px}.kz-prod-track{height:8px;background:#eaf0f7;border-radius:999px;overflow:hidden}.kz-prod-track>i{display:block;height:100%;background:#1768e5;border-radius:999px;transition:width .25s ease}.kz-prod-stages{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.kz-prod-stage{font-size:10px;padding:4px 7px;background:#edf3fb;color:#60758d;border-radius:4px}.kz-prod-stage.done{background:#e8f7f0;color:#16875c}.kz-prod-stage.active{background:#e8f1ff;color:#1768e5;font-weight:700}
      .kz-shot-review{display:grid;gap:8px}.kz-shot-review-title{display:flex;justify-content:space-between;gap:10px;align-items:end}.kz-shot-review-title h4{margin:0;font-size:13px;color:#17324f}.kz-shot-review-title span{font-size:10px;color:#74869b}.kz-review-shot{background:#fff;border:1px solid #e1e8f1;border-radius:7px;padding:10px}.kz-review-shot.selected{border-color:#8cc8aa}.kz-review-shot-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.kz-review-shot-head b{font-size:12px;color:#17324f}.kz-review-shot-head span{font-size:10px;color:#6d7f96}.kz-review-shot p{margin:5px 0 8px;font-size:11px;line-height:1.5;color:#53677e}.kz-candidate-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.kz-candidate{min-height:88px;border:1px dashed #ccd9e7;border-radius:6px;padding:8px;background:#fbfdff;display:flex;flex-direction:column;gap:6px}.kz-candidate.ready{border-style:solid;background:#fff}.kz-candidate.chosen{border-color:#1b9a64;box-shadow:0 0 0 1px rgba(27,154,100,.1)}.kz-candidate video{width:100%;max-height:145px;border-radius:4px;background:#0e1e31}.kz-candidate strong{font-size:11px;color:#17324f}.kz-candidate small{font-size:10px;color:#7b8ca0}.kz-candidate-actions{display:flex;gap:5px;margin-top:auto}.kz-candidate-actions button,.kz-shot-actions button,.kz-final-btn{height:28px;border-radius:4px;border:1px solid #b9cbe0;background:#fff;color:#24496f;font-size:10px;padding:0 8px;cursor:pointer}.kz-candidate-actions button.primary,.kz-final-btn{background:#1768e5;border-color:#1768e5;color:#fff}.kz-shot-actions{display:flex;gap:6px;margin-top:8px}.kz-final-row{display:flex;justify-content:space-between;gap:10px;align-items:center;background:#fff;border:1px solid #e2e9f2;border-radius:6px;padding:10px}.kz-final-row span{font-size:11px;color:#53677e}.kz-final-btn{height:34px;font-weight:700}.kz-final-btn:disabled{opacity:.45;cursor:not-allowed}.kz-prod-error{font-size:11px;color:#b33d3d;background:#fff0f0;border:1px solid #efc0c0;border-radius:6px;padding:8px}
      @media(max-width:1050px){.kz-prod-summary{grid-template-columns:1fr 1fr}.kz-candidate-grid{grid-template-columns:1fr}.kz-prod-monitor-head{flex-direction:column}}
    `;
    document.head.appendChild(style);
  }

  function ensureRoot() {
    const simple = byId('kz-simple-root');
    if (!simple) return false;
    if (byId('kz-production-monitor')) return true;
    const root = document.createElement('section');
    root.id = 'kz-production-monitor';
    root.className = 'kz-prod-monitor';
    const actions = simple.querySelector('.kz-simple-actions');
    if (actions) actions.insertAdjacentElement('afterend', root);
    else simple.appendChild(root);
    root.innerHTML = '<div class="kz-prod-monitor-head"><div><h4>生产任务实时监控</h4><p>只显示后台真实状态，不用假进度。</p></div><span class="kz-prod-live"><i></i>正在连接后台状态</span></div>';
    return true;
  }

  function formatElapsed(seconds) {
    seconds = Math.max(0, Number(seconds || 0));
    const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = Math.floor(seconds % 60);
    if (h) return `${h}小时${m}分`;
    if (m) return `${m}分${s}秒`;
    return `${s}秒`;
  }

  function outputUrl(item) {
    const value = String(item?.url || item?.file_url || item?.preview_url || '').trim();
    return /^(https?:\/\/|\/)/i.test(value) ? value : '';
  }

  function stageState(pipeline, monitor) {
    const production = monitor?.production || {};
    const project = production.project;
    const tasks = production.tasks || [];
    const outputs = production.outputs || [];
    const finalTask = tasks.find(x => x.kind === '完整成片合成');
    const stages = [
      {key:'understand',label:'理解内容',done:!!pipeline.reference?.analysis},
      {key:'rewrite',label:'原创改写',done:!!pipeline.selectedCreative},
      {key:'director',label:'AI导演 / 5镜头',done:!!pipeline.directorPlan?.shots?.length},
      {key:'candidates',label:'镜头候选',done:Number(production.confirmed_shots||0) >= 5},
      {key:'compose',label:'配音剪辑',done:!!finalTask && /已完成|完成/.test(String(finalTask.status||''))},
      {key:'finish',label:'质检 / 完成',done:outputs.some(x => /成片|final/i.test(String(x.kind||x.type||'')) && /完成|已通过/.test(String(x.status||'')))},
    ];
    let activeFound = false;
    stages.forEach(stage => {
      stage.active = !stage.done && !activeFound;
      if (stage.active) activeFound = true;
    });
    const doneCount = stages.filter(x=>x.done).length;
    return {stages, doneCount, total:stages.length, project};
  }

  function currentWork(pipeline, monitor) {
    const ai = monitor?.text_ai || {};
    if (ai.status === 'running') {
      if (!pipeline.reference?.analysis) return '理解内容 · 本地文本 AI';
      if (!pipeline.selectedCreative) return '原创改写 · 本地文本 AI';
      if (!pipeline.directorPlan?.shots?.length) return 'AI 导演 · 生成 5 个镜头';
      return '本地文本 AI';
    }
    const task = (monitor?.production?.tasks || []).find(x => !/已完成|完成|已确认/.test(String(x.status||'')));
    if (task) return `${task.kind} · ${task.status}`;
    if (Number(monitor?.production?.confirmed_shots||0) >= 5) return '等待完整成片合成';
    if (monitor?.production?.project) return '镜头候选选择';
    return '等待开始';
  }

  function renderCandidate(candidate, shot, index) {
    if (!candidate) {
      return `<div class="kz-candidate"><strong>候选 ${String.fromCharCode(65+index)}</strong><small>等待真实候选文件</small></div>`;
    }
    const url = outputUrl(candidate);
    const chosen = candidate.selected === true || ['已采用','已确认'].includes(String(candidate.status||''));
    return `<div class="kz-candidate ready ${chosen?'chosen':''}"><strong>候选 ${String.fromCharCode(65+index)} ${chosen?'· 已采用':''}</strong>${url?`<video controls preload="metadata" src="${esc(url)}"></video>`:`<small>${esc(candidate.name||candidate.filename||candidate.id||'真实候选已记录')}</small>`}<small>${esc(candidate.status||'待选择')}</small><div class="kz-candidate-actions"><button class="primary" data-kz-select="${esc(candidate.id)}" data-shot="${esc(shot.id)}">采用这个</button><button data-kz-revise="${esc(shot.id)}" data-candidate="${esc(candidate.id)}">告诉AI怎么改</button></div></div>`;
  }

  function renderShot(shot, outputs) {
    const candidates = outputs.filter(x => x.shot_id === shot.id).slice(0,3);
    const chosen = candidates.some(x => x.selected === true || ['已采用','已确认'].includes(String(x.status||'')));
    const count = Math.max(2, Math.min(3, Number(shot.candidate_count || 3)));
    const slots = Array.from({length:count}, (_,i)=>renderCandidate(candidates[i], shot, i)).join('');
    return `<article class="kz-review-shot ${chosen?'selected':''}"><div class="kz-review-shot-head"><b>镜头 ${String(shot.order||'').padStart(2,'0')} · ${esc(shot.purpose||'')}</b><span>${esc(shot.status||'待处理')} · 计划 ${count} 个候选</span></div><p>${esc(shot.narration||shot.action||'')}</p><div class="kz-candidate-grid">${slots}</div><div class="kz-shot-actions"><button data-kz-queue="${esc(shot.id)}">${candidates.length?'再生成一组':'开始生成候选'}</button><button data-kz-revise="${esc(shot.id)}">告诉AI怎么改这个镜头</button></div></article>`;
  }

  function render(monitor) {
    if (!ensureRoot()) return;
    const root = byId('kz-production-monitor');
    const pipeline = readPipeline();
    const gpu = monitor?.gpu || {};
    const ai = monitor?.text_ai || {};
    const production = monitor?.production || {};
    const stage = stageState(pipeline, monitor);
    const work = currentWork(pipeline, monitor);
    const width = Math.round(stage.doneCount / stage.total * 100);
    const shots = (production.shots || []).slice(0,5);
    const outputs = production.outputs || [];
    const confirmed = Number(production.confirmed_shots || 0);
    const model = (ai.loaded_models || [])[0] || (ai.status === 'running' ? '本地模型工作中' : '未驻留');
    const gpuText = gpu.available ? `${Math.round(gpu.utilization_percent||0)}%` : '未读取';
    const vramText = gpu.available ? `${(Number(gpu.memory_used_mb||0)/1024).toFixed(1)} / ${(Number(gpu.memory_total_mb||0)/1024).toFixed(1)} GB` : '未读取';
    root.innerHTML = `
      <div class="kz-prod-monitor-head"><div><h4>生产任务实时监控</h4><p>质量优先模式：允许长时间串行运行；只显示后台真实状态。</p></div><span class="kz-prod-live"><i></i>${ai.status==='running'?'后台正在工作':'后台已连接'}</span></div>
      <div class="kz-prod-summary">
        <div class="kz-prod-metric"><small>当前工作模块</small><b>${esc(work)}</b><span>${esc(ai.message||'')}</span></div>
        <div class="kz-prod-metric"><small>GPU 利用率</small><b>${esc(gpuText)}</b><span>${gpu.available?`${esc(gpu.temperature_c)} °C`:'需要 NVIDIA 驱动支持'}</span></div>
        <div class="kz-prod-metric"><small>显存</small><b>${esc(vramText)}</b><span>RTX 3060 串行调度</span></div>
        <div class="kz-prod-metric"><small>当前模型</small><b>${esc(model)}</b><span>用完自动释放</span></div>
        <div class="kz-prod-metric"><small>本轮运行时间</small><b>${esc(formatElapsed(ai.elapsed_seconds||0))}</b><span>${ai.status==='running'?'正常运行中':'等待下一任务'}</span></div>
      </div>
      <div class="kz-prod-progress"><div class="kz-prod-progress-top"><b>总任务阶段 ${stage.doneCount}/${stage.total}</b><span>镜头已确认 ${confirmed}/5 · 不显示虚假 ETA</span></div><div class="kz-prod-track"><i style="width:${width}%"></i></div><div class="kz-prod-stages">${stage.stages.map(x=>`<span class="kz-prod-stage ${x.done?'done':x.active?'active':''}">${esc(x.label)}${x.done?' ✓':x.active?' · 当前':''}</span>`).join('')}</div></div>
      ${ai.last_error?`<div class="kz-prod-error">最近一次异常：${esc(ai.last_error)}</div>`:''}
      <div class="kz-shot-review"><div class="kz-shot-review-title"><h4>5 个镜头 · 每镜头 2～3 个候选</h4><span>只在真实候选文件出现后允许“采用这个”</span></div>${shots.length?shots.map(s=>renderShot(s,outputs)).join(''):'<div class="kz-prod-metric"><small>分镜选择区</small><b>等待 AI 导演生成并导入 5 个镜头</b><span>镜头出现后，可逐个挑选、重做或告诉 AI 怎么改。</span></div>'}</div>
      ${production.project?`<div class="kz-final-row"><span>5 个镜头全部选定后，再统一进入配音、字幕、剪辑和最终质检。</span><button id="kz-final-render" class="kz-final-btn" ${confirmed===5?'':'disabled'}>确认5个镜头并生成完整视频</button></div>`:''}
    `;
    bindActions(monitor);
  }

  function bindActions(monitor) {
    const refresh = () => poll(true);
    document.querySelectorAll('[data-kz-queue]').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try { await post('/api/ai-content-center/candidates/queue',{shot_id:button.dataset.kzQueue,asset_ids:[]}); await refresh(); }
      catch (e) { alert(`候选任务未建立：${e.message}`); button.disabled=false; }
    }, {once:true}));
    document.querySelectorAll('[data-kz-select]').forEach(button => button.addEventListener('click', async () => {
      button.disabled=true;
      try { await post('/api/ai-content-center/candidates/select',{shot_id:button.dataset.shot,candidate_id:button.dataset.kzSelect}); await refresh(); }
      catch (e) { alert(`候选未采用：${e.message}`); button.disabled=false; }
    }, {once:true}));
    document.querySelectorAll('[data-kz-revise]').forEach(button => button.addEventListener('click', async () => {
      const instruction = prompt('告诉 AI 这个镜头怎么改：\n例如：人物不变，镜头拉近一点；换成真实家庭配电箱；动作自然一些。');
      if (!instruction) return;
      button.disabled=true;
      try { await post('/api/ai-content-center/candidates/revise',{shot_id:button.dataset.kzRevise,instruction,candidate_id:button.dataset.candidate||''}); await refresh(); }
      catch (e) { alert(`修改任务未建立：${e.message}`); button.disabled=false; }
    }, {once:true}));
    byId('kz-final-render')?.addEventListener('click', async event => {
      const projectId = monitor?.production?.project?.id;
      if (!projectId) return;
      event.currentTarget.disabled=true;
      try { await post('/api/ai-content-center/final/queue',{project_id:projectId}); await refresh(); }
      catch (e) { alert(`完整视频任务未建立：${e.message}`); event.currentTarget.disabled=false; }
    }, {once:true});
  }

  async function poll(force=false) {
    if (!ensureRoot()) return;
    if (!force && document.hidden) return;
    try {
      last = await json('/api/production-monitor');
      render(last);
    } catch (error) {
      const root = byId('kz-production-monitor');
      if (root) root.innerHTML = `<div class="kz-prod-monitor-head"><div><h4>生产任务实时监控</h4><p>后台状态暂时读取失败。</p></div></div><div class="kz-prod-error">${esc(error.message)}</div>`;
    }
  }

  function install() {
    installStyle();
    if (!ensureRoot()) {
      if (++installAttempts < 60) setTimeout(install, 500);
      return;
    }
    poll(true);
    if (!timer) timer = setInterval(()=>poll(false), 3000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true});
  else install();
})();
