(() => {
  'use strict';
  if (window.__KZ_PRODUCTION_MONITOR__) return;
  window.__KZ_PRODUCTION_MONITOR__ = true;

  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const json = (url, options={}) => fetch(url, options).then(async response => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.detail || data.message || `HTTP ${response.status}`);
    return data;
  });
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
      .kz-prod-monitor-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.kz-prod-monitor-head h4{margin:0 0 4px;font-size:14px;color:#17324f}.kz-prod-monitor-head p{margin:0;color:#6d7f96;font-size:11px}.kz-prod-live{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#16875c;background:#e9f7f0;padding:5px 8px;border-radius:999px;white-space:nowrap}.kz-prod-live i{width:7px;height:7px;border-radius:50%;background:#21a56f}.kz-prod-live.idle{color:#6d7f96;background:#edf2f7}.kz-prod-live.idle i{background:#9aaabd}.kz-prod-live.bad{color:#b33d3d;background:#fff0f0}.kz-prod-live.bad i{background:#d85a5a}
      .kz-prod-policy{display:grid;grid-template-columns:1.35fr .65fr;gap:10px;background:#fff;border:1px solid #e2e9f2;border-radius:7px;padding:11px}.kz-prod-policy h5{margin:0 0 7px;font-size:12px;color:#17324f}.kz-prod-mode-row{display:flex;gap:6px;flex-wrap:wrap}.kz-prod-mode-row button{height:31px;border:1px solid #c7d5e5;background:#fff;color:#47627f;border-radius:5px;padding:0 10px;font-size:11px;cursor:pointer}.kz-prod-mode-row button.active{background:#1768e5;border-color:#1768e5;color:#fff;font-weight:700}.kz-prod-quality select{width:100%;height:32px;border:1px solid #c7d5e5;border-radius:5px;background:#fff;color:#17324f;padding:0 8px}.kz-prod-policy small{display:block;margin-top:6px;color:#8190a3;font-size:10px;line-height:1.5}
      .kz-prod-summary{display:grid;grid-template-columns:1.15fr repeat(4,minmax(0,.8fr));gap:8px}.kz-prod-metric{background:#fff;border:1px solid #e2e9f2;border-radius:6px;padding:10px;min-width:0}.kz-prod-metric small{display:block;color:#8292a5;font-size:10px;margin-bottom:4px}.kz-prod-metric b{display:block;color:#17324f;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kz-prod-metric span{font-size:10px;color:#6d7f96}
      .kz-prod-progress{background:#fff;border:1px solid #e2e9f2;border-radius:6px;padding:10px}.kz-prod-progress-top{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:#53677e;margin-bottom:7px}.kz-prod-track{height:8px;background:#eaf0f7;border-radius:999px;overflow:hidden}.kz-prod-track>i{display:block;height:100%;background:#1768e5;border-radius:999px;transition:width .25s ease}.kz-prod-stages{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.kz-prod-stage{font-size:10px;padding:4px 7px;background:#edf3fb;color:#60758d;border-radius:4px}.kz-prod-stage.done{background:#e8f7f0;color:#16875c}.kz-prod-stage.active{background:#e8f1ff;color:#1768e5;font-weight:700}
      .kz-shot-review{display:grid;gap:8px}.kz-shot-review-title{display:flex;justify-content:space-between;gap:10px;align-items:end}.kz-shot-review-title h4{margin:0;font-size:13px;color:#17324f}.kz-shot-review-title span{font-size:10px;color:#74869b}.kz-review-shot{background:#fff;border:1px solid #e1e8f1;border-radius:7px;padding:10px}.kz-review-shot.selected{border-color:#8cc8aa}.kz-review-shot-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.kz-review-shot-head b{font-size:12px;color:#17324f}.kz-review-shot-head span{font-size:10px;color:#6d7f96}.kz-review-shot p{margin:5px 0 8px;font-size:11px;line-height:1.5;color:#53677e}.kz-candidate-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.kz-candidate{min-height:88px;border:1px dashed #ccd9e7;border-radius:6px;padding:8px;background:#fbfdff;display:flex;flex-direction:column;gap:6px}.kz-candidate.ready{border-style:solid;background:#fff}.kz-candidate.chosen{border-color:#1b9a64;box-shadow:0 0 0 1px rgba(27,154,100,.1)}.kz-candidate video{width:100%;max-height:145px;border-radius:4px;background:#0e1e31}.kz-candidate strong{font-size:11px;color:#17324f}.kz-candidate small{font-size:10px;color:#7b8ca0}.kz-candidate-actions{display:flex;gap:5px;margin-top:auto}.kz-candidate-actions button,.kz-shot-actions button,.kz-final-btn,.kz-queue-all{height:28px;border-radius:4px;border:1px solid #b9cbe0;background:#fff;color:#24496f;font-size:10px;padding:0 8px;cursor:pointer}.kz-candidate-actions button.primary,.kz-final-btn,.kz-queue-all{background:#1768e5;border-color:#1768e5;color:#fff}.kz-shot-actions{display:flex;gap:6px;margin-top:8px}.kz-final-row{display:flex;justify-content:space-between;gap:10px;align-items:center;background:#fff;border:1px solid #e2e9f2;border-radius:6px;padding:10px}.kz-final-row span{font-size:11px;color:#53677e}.kz-final-btn,.kz-queue-all{height:34px;font-weight:700}.kz-final-btn:disabled,.kz-queue-all:disabled{opacity:.45;cursor:not-allowed}.kz-prod-error{font-size:11px;color:#b33d3d;background:#fff0f0;border:1px solid #efc0c0;border-radius:6px;padding:8px}
      @media(max-width:1050px){.kz-prod-summary{grid-template-columns:1fr 1fr}.kz-candidate-grid{grid-template-columns:1fr}.kz-prod-monitor-head{flex-direction:column}.kz-prod-policy{grid-template-columns:1fr}}
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
    root.innerHTML = '<div class="kz-prod-monitor-head"><div><h4>生产任务实时监控</h4><p>GPT负责总控与导演；前台只显示真实任务、显卡和镜头状态。</p></div><span class="kz-prod-live idle"><i></i>正在连接后台状态</span></div>';
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

  function labels(policy={}) {
    return {
      mode:{auto:'全自动生产',assisted:'我提供内容',manual:'手动细调'}[policy.mode] || '我提供内容',
      quality:{fast:'快速测试',standard:'标准质量',high:'高质量',premium:'精品模式'}[policy.quality] || '高质量',
    };
  }

  function stageState(monitor) {
    const production = monitor?.production || {};
    const project = production.project;
    const tasks = production.tasks || [];
    const outputs = production.outputs || [];
    const textAI = monitor?.text_ai || {};
    const totalShots = Number(production.total_shots || 0);
    const confirmed = Number(production.confirmed_shots || 0);
    const finalTask = tasks.find(x => x.kind === '完整成片合成');
    const stages = [
      {label:'理解/改写',done:!!project || !!textAI.finished_at},
      {label:'GPT导演',done:totalShots > 0},
      {label:'镜头候选',done:totalShots > 0 && confirmed >= totalShots},
      {label:'配音剪辑',done:!!finalTask && /已完成|完成/.test(String(finalTask.status||''))},
      {label:'质检/成片',done:outputs.some(x => /成片|final/i.test(String(x.kind||x.type||'')) && /完成|已通过/.test(String(x.status||'')))},
    ];
    let activeFound = false;
    stages.forEach(stage => {
      if (!stage.done && !activeFound) { stage.active = true; activeFound = true; }
    });
    const doneCount = stages.filter(x=>x.done).length;
    return {stages, doneCount, percent:Math.round(doneCount / stages.length * 100)};
  }

  function currentWork(production={}) {
    const tasks = production.tasks || [];
    const shots = production.shots || [];
    const active = tasks.find(x => !/已完成|完成|失败|取消/.test(String(x.status||''))) || null;
    if (!active) return {text:production.total_shots ? '等待下一步' : '等待导演方案', shot:''};
    const shot = shots.find(x => x.id === active.shot_id);
    return {text:String(active.kind || active.status || '任务执行中'), shot:shot ? `镜头 ${shot.order}/${production.total_shots}` : ''};
  }

  function renderPolicy(policy={}) {
    const l = labels(policy);
    return `<section class="kz-prod-policy"><div><h5>生产方式</h5><div class="kz-prod-mode-row">${[
      ['auto','全自动生产'],['assisted','我提供内容'],['manual','手动细调']
    ].map(([value,label])=>`<button type="button" data-prod-mode="${value}" class="${policy.mode===value?'active':''}">${label}</button>`).join('')}</div><small>三个入口共用同一个 GPT 总控与本地生产引擎。全自动模式只会使用已经接入并可验证的内容来源。</small></div><div class="kz-prod-quality"><h5>质量优先级</h5><select id="kz-prod-quality"><option value="fast" ${policy.quality==='fast'?'selected':''}>快速测试</option><option value="standard" ${policy.quality==='standard'?'selected':''}>标准质量</option><option value="high" ${policy.quality==='high'?'selected':''}>高质量</option><option value="premium" ${policy.quality==='premium'?'selected':''}>精品模式</option></select><small>当前：${esc(l.quality)}。质量越高，关键镜头可分配更多候选和重试。</small></div></section>`;
  }

  function renderCandidates(shot, outputs) {
    const list = outputs.filter(x => x.shot_id === shot.id);
    const count = Math.max(1, Math.min(Number(shot.candidate_count || 1), 3));
    const cards = [];
    for (let i=0;i<Math.max(count,list.length);i++) {
      const item = list[i];
      if (!item) {
        cards.push(`<div class="kz-candidate"><strong>候选 ${String.fromCharCode(65+i)}</strong><small>等待真实候选文件</small></div>`);
        continue;
      }
      const url = outputUrl(item);
      const chosen = item.selected === true || /已采用|已确认/.test(String(item.status||''));
      const recommended = item.recommended === true || item.ai_recommended === true;
      cards.push(`<div class="kz-candidate ready ${chosen?'chosen':''}">${url?`<video controls preload="metadata" src="${esc(url)}"></video>`:''}<strong>候选 ${String.fromCharCode(65+i)}${recommended?' · AI推荐':''}</strong><small>${esc(item.status||'候选已生成')}</small><div class="kz-candidate-actions"><button type="button" class="primary" data-pick-candidate="${esc(item.id)}" data-shot="${esc(shot.id)}">${chosen?'已采用':'采用这个'}</button><button type="button" data-revise-shot="${esc(shot.id)}">告诉AI怎么改</button></div></div>`);
    }
    return cards.join('');
  }

  function render(monitor) {
    if (!ensureRoot()) return;
    last = monitor;
    const root = byId('kz-production-monitor');
    const textAI = monitor.text_ai || {};
    const gpu = monitor.gpu || {};
    const production = monitor.production || {};
    const policy = monitor.policy || {};
    const project = production.project;
    const shots = production.shots || [];
    const outputs = production.outputs || [];
    const totalShots = Number(production.total_shots || 0);
    const confirmed = Number(production.confirmed_shots || 0);
    const plannedCandidates = Number(production.planned_candidates || 0);
    const stage = stageState(monitor);
    const work = currentWork(production);
    const loaded = Array.isArray(textAI.loaded_models) && textAI.loaded_models.length ? textAI.loaded_models.join(', ') : '未驻留';
    const liveClass = textAI.status === 'running' ? '' : textAI.status === 'error' ? 'bad' : 'idle';
    const liveText = textAI.status === 'running' ? '后台正在工作' : textAI.status === 'error' ? '本轮出现异常' : '等待 / 已完成';
    const gpuText = gpu.available ? `${Math.round(gpu.utilization_percent||0)}%` : '未读取';
    const vram = gpu.available ? `${(Number(gpu.memory_used_mb||0)/1024).toFixed(1)} / ${(Number(gpu.memory_total_mb||0)/1024).toFixed(1)}GB` : '未读取';

    root.innerHTML = `<div class="kz-prod-monitor-head"><div><h4>生产任务实时监控</h4><p>动态镜头、动态候选；不再固定5个镜头，也不显示假的精确剩余时间。</p></div><span class="kz-prod-live ${liveClass}"><i></i>${liveText}</span></div>
      ${renderPolicy(policy)}
      <div class="kz-prod-summary"><div class="kz-prod-metric"><small>当前工作</small><b>${esc(work.text)}</b><span>${esc(work.shot || textAI.message || '')}</span></div><div class="kz-prod-metric"><small>GPU</small><b>${esc(gpuText)}</b><span>${gpu.available?`${Math.round(gpu.temperature_c||0)}°C`:'等待 nvidia-smi'}</span></div><div class="kz-prod-metric"><small>显存</small><b>${esc(vram)}</b><span>RTX3060 按任务串行</span></div><div class="kz-prod-metric"><small>当前模型</small><b>${esc(loaded)}</b><span>${textAI.status==='running'?'正在推理':'按需加载/释放'}</span></div><div class="kz-prod-metric"><small>已运行</small><b>${esc(formatElapsed(textAI.elapsed_seconds||0))}</b><span>质量优先，不承诺固定ETA</span></div></div>
      <section class="kz-prod-progress"><div class="kz-prod-progress-top"><span>${project?esc(project.name):'还没有进入正式生产项目'}</span><b>${totalShots?`已确认 ${confirmed}/${totalShots} 镜头 · 计划 ${plannedCandidates} 候选`:'等待 GPT 动态导演'}</b></div><div class="kz-prod-track"><i style="width:${stage.percent}%"></i></div><div class="kz-prod-stages">${stage.stages.map(x=>`<span class="kz-prod-stage ${x.done?'done':x.active?'active':''}">${esc(x.label)}${x.done?' ✓':''}</span>`).join('')}</div></section>
      ${textAI.last_error?`<div class="kz-prod-error">最近异常：${esc(textAI.last_error)}</div>`:''}
      ${totalShots?`<section class="kz-shot-review"><div class="kz-shot-review-title"><div><h4>动态分镜选择区</h4><span>GPT根据内容自动规划 ${totalShots} 个镜头；每镜头按重要度分配 1～3 个候选。</span></div><button type="button" class="kz-queue-all" id="kz-queue-all">生成 / 补齐镜头候选</button></div>${shots.map(shot=>{const selected=outputs.some(x=>x.shot_id===shot.id&&(x.selected===true||/已采用|已确认/.test(String(x.status||''))));return `<article class="kz-review-shot ${selected?'selected':''}"><div class="kz-review-shot-head"><b>镜头 ${shot.order} · ${esc(shot.purpose||'')}</b><span>${esc(shot.importance||'B')}级 · ${esc(shot.duration_seconds)}秒 · 候选 ${esc(shot.candidate_count||1)}${selected?' · 已确认':''}</span></div><p>${esc(shot.narration||shot.action||'')}</p><div class="kz-candidate-grid">${renderCandidates(shot,outputs)}</div><div class="kz-shot-actions"><button type="button" data-revise-shot="${esc(shot.id)}">这个镜头重做 / 修改</button></div></article>`;}).join('')}</section><div class="kz-final-row"><span>${confirmed>=totalShots?`全部 ${totalShots} 个镜头已确认，可以进入配音、字幕、剪辑与整片质检。`:`还需确认 ${Math.max(0,totalShots-confirmed)} 个镜头。`}</span><button type="button" class="kz-final-btn" id="kz-final-render" ${confirmed>=totalShots?'':'disabled'}>确认全部镜头并生成完整视频</button></div>`:''}`;
    bindActions();
  }

  async function savePolicy(patch) {
    const current = last?.policy || {};
    await post('/api/production-policy', {mode:patch.mode || current.mode || 'assisted', quality:patch.quality || current.quality || 'high'});
    await refresh();
  }

  async function queueMissingCandidates() {
    const production = last?.production || {};
    const shots = production.shots || [];
    const tasks = production.tasks || [];
    const button = byId('kz-queue-all');
    if (button) { button.disabled=true; button.textContent='正在建立候选任务…'; }
    try {
      let queued = 0;
      for (const shot of shots) {
        const exists = tasks.some(task => task.shot_id===shot.id && /镜头候选生成|修改\/重做/.test(String(task.kind||'')) && !/失败|取消/.test(String(task.status||'')));
        if (exists) continue;
        await post('/api/ai-content-center/candidates/queue', {shot_id:shot.id, asset_ids:[]});
        queued += 1;
      }
      await refresh();
      if (!queued && button) button.textContent='候选任务已建立';
    } catch (error) {
      if (button) { button.disabled=false; button.textContent='生成 / 补齐镜头候选'; }
      alert(`建立候选任务失败：${error.message}`);
    }
  }

  function bindActions() {
    document.querySelectorAll('[data-prod-mode]').forEach(button => button.addEventListener('click', () => savePolicy({mode:button.dataset.prodMode}).catch(error=>alert(error.message)), {once:true}));
    byId('kz-prod-quality')?.addEventListener('change', event => savePolicy({quality:event.target.value}).catch(error=>alert(error.message)), {once:true});
    byId('kz-queue-all')?.addEventListener('click', queueMissingCandidates, {once:true});
    document.querySelectorAll('[data-pick-candidate]').forEach(button => button.addEventListener('click', async () => {
      try { await post('/api/ai-content-center/candidates/select', {shot_id:button.dataset.shot, candidate_id:button.dataset.pickCandidate}); await refresh(); }
      catch (error) { alert(`采用候选失败：${error.message}`); }
    }, {once:true}));
    document.querySelectorAll('[data-revise-shot]').forEach(button => button.addEventListener('click', async () => {
      const instruction = window.prompt('告诉 GPT 这个镜头怎么改。未提到的人物、服装、场景和风格会按连续性锁尽量保持：');
      if (instruction === null) return;
      try { await post('/api/ai-content-center/candidates/revise', {shot_id:button.dataset.reviseShot, instruction:instruction.trim() || '重新生成一个不同候选'}); await refresh(); }
      catch (error) { alert(`提交修改失败：${error.message}`); }
    }, {once:true}));
    byId('kz-final-render')?.addEventListener('click', async () => {
      const projectId = last?.production?.project?.id;
      if (!projectId) return;
      const button = byId('kz-final-render');
      if (button) { button.disabled=true; button.textContent='正在建立成片任务…'; }
      try { await post('/api/ai-content-center/final/queue', {project_id:projectId}); await refresh(); }
      catch (error) { alert(`进入成片失败：${error.message}`); if(button){button.disabled=false;button.textContent='确认全部镜头并生成完整视频';} }
    }, {once:true});
  }

  async function refresh() {
    try { render(await json('/api/production-monitor')); }
    catch (error) {
      if (!ensureRoot()) return;
      const root = byId('kz-production-monitor');
      root.innerHTML = `<div class="kz-prod-monitor-head"><div><h4>生产任务实时监控</h4><p>后台状态暂时不可读取。</p></div><span class="kz-prod-live bad"><i></i>连接异常</span></div><div class="kz-prod-error">${esc(error.message)}</div>`;
    }
  }

  function install() {
    installStyle();
    if (!ensureRoot()) {
      installAttempts += 1;
      if (installAttempts < 80) setTimeout(install, 250);
      return;
    }
    refresh();
    clearInterval(timer);
    timer = setInterval(refresh, 4000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true});
  else install();
})();
